#!/usr/bin/env python3
"""Create sentence and word timestamp TOML from OpenAI Whisper transcription."""

from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from pipeline_utils import die, env_value, guess_mime, media_metadata, write_toml_document


OPENAI_TRANSCRIPTIONS_URL = "https://api.openai.com/v1/audio/transcriptions"


def multipart_form(fields: dict[str, str], files: dict[str, Path]) -> tuple[bytes, str]:
    boundary = f"----video-agent-{uuid.uuid4().hex}"
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.append(f"--{boundary}\r\n".encode())
        chunks.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        chunks.append(str(value).encode("utf-8"))
        chunks.append(b"\r\n")
    for name, path in files.items():
        filename = path.name
        chunks.append(f"--{boundary}\r\n".encode())
        chunks.append(f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode())
        chunks.append(f"Content-Type: {guess_mime(path)}\r\n\r\n".encode())
        chunks.append(path.read_bytes())
        chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), boundary


def openai_key(env_file: Path) -> str:
    key = env_value(env_file, "OPENAI_API_KEY")
    if not key:
        die("OPENAI_API_KEY is required in the environment or .env")
    return key


def transcribe(args: argparse.Namespace) -> dict[str, Any]:
    audio_path = Path(args.audio)
    if not audio_path.exists():
        die(f"audio file not found: {audio_path}")
    if args.model != "whisper-1":
        die("word-level timestamp_granularities are only supported by whisper-1")
    fields = {
        "model": args.model,
        "response_format": "verbose_json",
        "timestamp_granularities[]": "word",
    }
    if args.language:
        fields["language"] = args.language
    if args.prompt:
        fields["prompt"] = args.prompt
    body, boundary = multipart_form(fields, {"file": audio_path})
    request = urllib.request.Request(
        OPENAI_TRANSCRIPTIONS_URL,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {openai_key(args.env_file)}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=args.timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        die(f"OpenAI transcription failed with HTTP {exc.code}: {detail}")
    except urllib.error.URLError as exc:
        die(f"OpenAI transcription failed: {exc}")


def normalize_words(data: dict[str, Any]) -> list[dict[str, Any]]:
    raw_words = data.get("words") or []
    words: list[dict[str, Any]] = []
    for index, item in enumerate(raw_words, start=1):
        word = str(item.get("word") or item.get("text") or "").strip()
        if not word:
            continue
        words.append(
            {
                "id": f"W_{index:04d}",
                "word": word,
                "start": round(float(item.get("start") or 0.0), 3),
                "end": round(float(item.get("end") or item.get("start") or 0.0), 3),
                "sentence_id": "",
                "confidence": float(item.get("confidence") or 0.0),
            }
        )
    return words


def group_sentences(words: list[dict[str, Any]], max_gap: float, max_words: int) -> list[dict[str, Any]]:
    sentences: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []

    def flush() -> None:
        if not current:
            return
        sentence_id = f"S_{len(sentences) + 1:03d}"
        text = " ".join(item["word"] for item in current)
        text = re.sub(r"\s+([,.!?;:])", r"\1", text).strip()
        for item in current:
            item["sentence_id"] = sentence_id
        sentences.append(
            {
                "id": sentence_id,
                "start": current[0]["start"],
                "end": current[-1]["end"],
                "sentence": text,
                "word_ids": [item["id"] for item in current],
            }
        )
        current.clear()

    for word in words:
        gap = word["start"] - current[-1]["end"] if current else 0.0
        if current and (gap > max_gap or len(current) >= max_words):
            flush()
        current.append(word)
        if re.search(r"[.!?…]$", word["word"]):
            flush()
    flush()
    return sentences


def validate(words: list[dict[str, Any]]) -> list[dict[str, str]]:
    warnings: list[dict[str, str]] = []
    last_end = -1.0
    for word in words:
        if word["start"] < last_end:
            warnings.append({"code": "WORD_OVERLAP", "message": f"{word['id']} starts before previous word ended"})
        if word["end"] < word["start"]:
            warnings.append({"code": "NEGATIVE_WORD_DURATION", "message": f"{word['id']} has end before start"})
        last_end = max(last_end, word["end"])
    return warnings


def write_output(args: argparse.Namespace, data: dict[str, Any]) -> None:
    words = normalize_words(data)
    sentences = group_sentences(words, args.max_gap, args.max_words_per_sentence)
    warnings = validate(words)
    metadata = media_metadata(args.audio)
    duration = metadata.get("duration_seconds") or data.get("duration") or 0.0
    write_toml_document(
        args.output,
        [
            (
                "metadata",
                {
                    "audio_path": str(args.audio),
                    "language": args.language or data.get("language") or "",
                    "duration_seconds": float(duration or 0.0),
                    "model": args.model,
                    "text": data.get("text") or "",
                },
            ),
            ("sentences", sentences),
            ("words", words),
            ("warnings", warnings),
        ],
    )
    print(f"wrote {args.output}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audio", type=Path, default=Path("source/voice.wav"))
    parser.add_argument("--output", type=Path, default=Path("source/transcript_word_level.toml"))
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--model", default="whisper-1")
    parser.add_argument("--language", default="vi")
    parser.add_argument("--prompt", default="")
    parser.add_argument("--timeout-seconds", type=int, default=300)
    parser.add_argument("--max-gap", type=float, default=0.8)
    parser.add_argument("--max-words-per-sentence", type=int, default=18)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    data = transcribe(args)
    write_output(args, data)


if __name__ == "__main__":
    main()
