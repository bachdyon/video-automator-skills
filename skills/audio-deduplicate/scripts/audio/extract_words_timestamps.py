#!/usr/bin/env python3
"""Extract word-level timestamps from audio and save to JSON."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Word:
    text: str
    start: float
    end: float


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)


def require_binary(name: str) -> None:
    if shutil.which(name) is None:
        raise SystemExit(f"Missing required binary: {name}")


def audio_duration(path: Path) -> float:
    result = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ]
    )
    return float(result.stdout.strip())


def transcribe(input_path: Path, model_name: str, language: str | None, device: str, compute_type: str) -> list[Word]:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise SystemExit(
            "Missing Python package: faster-whisper. Install it in the active environment before using this skill."
        ) from exc

    model = WhisperModel(model_name, device=device, compute_type=compute_type)
    segments, _ = model.transcribe(
        str(input_path),
        language=language,
        word_timestamps=True,
        vad_filter=True,
    )

    words: list[Word] = []
    for segment in segments:
        for item in segment.words or []:
            raw = (item.word or "").strip()
            if not raw:
                continue
            words.append(Word(text=raw, start=float(item.start), end=float(item.end)))
    return words


def save_words(path: Path, words: list[Word]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([word.__dict__ for word in words], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def write_plan(path: Path, input_path: Path, words_path: Path, duration: float, words: list[Word]) -> None:
    payload = {
        "input_audio": str(input_path),
        "output_words_json": str(words_path),
        "duration_seconds": duration,
        "word_count": len(words),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Input .wav or .mp3 file")
    parser.add_argument("--output-words-json", type=Path, required=True, help="Output word timestamps JSON")
    parser.add_argument("--model", default="small", help="faster-whisper model name or path")
    parser.add_argument("--language", help="Optional language code, for example vi or en")
    parser.add_argument("--device", default="auto", help="Whisper device: auto, cpu, cuda")
    parser.add_argument("--compute-type", default="default", help="faster-whisper compute_type")
    parser.add_argument("--plan-json", type=Path, help="Optional extraction plan JSON")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = args.input.expanduser().resolve()
    output_words_path = args.output_words_json.expanduser().resolve()

    if not input_path.exists():
        raise SystemExit(f"Input file does not exist: {input_path}")
    if input_path.suffix.lower() not in {".wav", ".mp3"}:
        raise SystemExit("Input path must end with .wav or .mp3")

    require_binary("ffprobe")
    duration = audio_duration(input_path)
    words = transcribe(
        input_path=input_path,
        model_name=args.model,
        language=args.language,
        device=args.device,
        compute_type=args.compute_type,
    )
    save_words(output_words_path, words)
    print(f"Wrote words: {output_words_path}")
    print(f"Audio duration: {duration:.2f}s")
    print(f"Word count: {len(words)}")

    if args.plan_json:
        plan_path = args.plan_json.expanduser().resolve()
        write_plan(plan_path, input_path, output_words_path, duration, words)
        print(f"Wrote plan: {plan_path}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        print(exc.stderr or exc.stdout)
        raise SystemExit(exc.returncode)
