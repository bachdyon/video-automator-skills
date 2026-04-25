#!/usr/bin/env python3
"""List, select, and generate AusyncLab voices for the video pipeline."""

from __future__ import annotations

import argparse
import hashlib
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from pipeline_utils import die, download_file, env_value, http_json, load_env_file, tokenize, upsert_env_file, write_toml_document


VOICE_BASE = "https://api.ausynclab.io/api/v1/voices"
SPEECH_BASE = "https://api.ausynclab.io/api/v1/speech"


def api_key(env_path: Path) -> str:
    key = env_value(env_path, "AUSYNCLAB_API_KEY")
    if not key:
        die("AUSYNCLAB_API_KEY is required in source/.env")
    return key


def headers(key: str) -> dict[str, str]:
    return {"accept": "application/json", "X-API-Key": key}


def list_voices(args: argparse.Namespace) -> list[dict[str, Any]]:
    data = http_json(f"{VOICE_BASE}/list", headers=headers(api_key(args.env_file)))
    voices = data.get("result") or []
    if args.output:
        rows = []
        for voice in voices:
            rows.append(
                {
                    "id": int(voice.get("id") or 0),
                    "name": voice.get("name") or "",
                    "language": voice.get("language") or "",
                    "gender": voice.get("gender") or "",
                    "age": voice.get("age") or "",
                    "use_case": voice.get("use_case") or "",
                    "audio_url": voice.get("audio_url") or "",
                }
            )
        write_toml_document(args.output, [("voices", rows)])
    else:
        for voice in voices:
            print(
                f"{voice.get('id')}\t{voice.get('language','')}\t"
                f"{voice.get('gender','')}\t{voice.get('age','')}\t"
                f"{voice.get('use_case','')}\t{voice.get('name','')}"
            )
    return voices


def score_voice(voice: dict[str, Any], args: argparse.Namespace) -> tuple[int, list[str]]:
    score = 0
    reasons: list[str] = []
    if args.language and voice.get("language") == args.language:
        score += 8
        reasons.append("language")
    if args.gender and voice.get("gender") == args.gender:
        score += 3
        reasons.append("gender")
    if args.age and voice.get("age") == args.age:
        score += 2
        reasons.append("age")
    if args.use_case and voice.get("use_case") == args.use_case:
        score += 4
        reasons.append("use_case")
    text_tokens = tokenize(" ".join([args.tone or "", args.delivery or "", args.brief or ""]))
    voice_tokens = tokenize(" ".join(str(voice.get(k) or "") for k in ["name", "language", "gender", "age", "use_case"]))
    overlap = text_tokens & voice_tokens
    if overlap:
        score += min(len(overlap), 3)
        reasons.append("metadata_overlap")
    return score, reasons


def recommend(args: argparse.Namespace) -> dict[str, Any]:
    voices = list_voices(args)
    if not voices:
        die("no voices returned from AusyncLab")
    ranked = sorted(voices, key=lambda voice: score_voice(voice, args)[0], reverse=True)
    selected = ranked[0]
    score, labels = score_voice(selected, args)
    reason = f"Selected by {', '.join(labels) or 'available voice'} fit; score={score}."
    write_voice_selection(args.output, selected, args, reason, audio={})
    if args.save_preference:
        upsert_env_file(
            args.env_file,
            {
                "AUSYNCLAB_VOICE_ID": str(selected.get("id") or ""),
            },
        )
    print(f"recommended voice_id={selected.get('id')} name={selected.get('name')}")
    return selected


def read_text(args: argparse.Namespace) -> str:
    if args.text:
        return args.text
    if args.text_file:
        return Path(args.text_file).read_text(encoding="utf-8")
    if args.creative_plan:
        import tomllib

        with Path(args.creative_plan).open("rb") as f:
            data = tomllib.load(f)
        script = ((data.get("voiceover") or {}).get("script") or "").strip()
        if script:
            return script
    die("provide --text, --text-file, or --creative-plan with [voiceover].script")


def speech_detail(key: str, audio_id: int) -> dict[str, Any]:
    return http_json(f"{SPEECH_BASE}/{audio_id}", headers=headers(key)).get("result") or {}


def poll_audio(key: str, audio_id: int, timeout_seconds: int, interval_seconds: int) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        detail = speech_detail(key, audio_id)
        state = str(detail.get("state") or detail.get("status") or "").upper()
        if state in {"SUCCEED", "SUCCEEDED", "FAILED", "ERROR"}:
            return detail
        time.sleep(interval_seconds)
    die(f"timed out waiting for audio_id={audio_id}")


def synthesize(args: argparse.Namespace) -> None:
    key = api_key(args.env_file)
    env = load_env_file(args.env_file)
    voice_id = args.voice_id or env.get("AUSYNCLAB_VOICE_ID")
    if not voice_id:
        die("voice_id is required via --voice-id or AUSYNCLAB_VOICE_ID in source/.env")
    text = read_text(args)
    payload = {
        "audio_name": args.audio_name,
        "text": text,
        "voice_id": int(voice_id),
        "speed": args.speed,
        "model_name": args.model_name,
        "language": args.language,
    }
    response = http_json(f"{SPEECH_BASE}/text-to-speech", method="POST", headers=headers(key), body=payload, timeout=120)
    result = response.get("result") or response
    audio_id = int(result.get("id") or result.get("audio_id") or 0)
    if not audio_id:
        die(f"could not find audio id in response: {response}")
    detail = poll_audio(key, audio_id, args.timeout_seconds, args.poll_interval)
    audio_url = detail.get("audio_url") or result.get("audio_url")
    if not audio_url:
        die(f"audio_id={audio_id} completed without audio_url")
    output_audio = download_file(audio_url, args.output_audio)
    voice = {
        "id": int(voice_id),
        "name": "",
        "language": args.language,
        "gender": "",
        "age": "",
        "use_case": "",
    }
    audio = {
        "audio_id": audio_id,
        "file_path": str(output_audio),
        "audio_url": audio_url,
        "format": output_audio.suffix.lstrip("."),
        "sample_rate": int(detail.get("sample_rate") or 0),
        "duration_seconds": 0.0,
        "state": str(detail.get("state") or detail.get("status") or ""),
    }
    reason = "Generated narration audio using the selected AusyncLab voice."
    args.text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    write_voice_selection(args.output, voice, args, reason, audio=audio)
    print(f"wrote {output_audio} and {args.output}")


def write_voice_selection(path: Path, voice: dict[str, Any], args: argparse.Namespace, reason: str, audio: dict[str, Any]) -> None:
    write_toml_document(
        path,
        [
            (
                "voice",
                {
                    "provider": "ausynclab",
                    "voice_id": int(voice.get("id") or 0),
                    "voice_name": voice.get("name") or "",
                    "language": voice.get("language") or args.language or "",
                    "gender": voice.get("gender") or "",
                    "age": voice.get("age") or "",
                    "use_case": voice.get("use_case") or "",
                    "model_name": args.model_name,
                    "speed": args.speed,
                    "reason": reason,
                },
            ),
            (
                "audio",
                {
                    "audio_id": int(audio.get("audio_id") or 0),
                    "file_path": audio.get("file_path") or "",
                    "audio_url": audio.get("audio_url") or "",
                    "format": audio.get("format") or "",
                    "sample_rate": int(audio.get("sample_rate") or 0),
                    "duration_seconds": float(audio.get("duration_seconds") or 0.0),
                    "state": audio.get("state") or "",
                },
            ),
            (
                "source",
                {
                    "script_path": str(getattr(args, "creative_plan", "") or getattr(args, "text_file", "") or ""),
                    "text_hash": getattr(args, "text_hash", ""),
                },
            ),
        ],
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=Path("source/.env"))
    sub = parser.add_subparsers(dest="command", required=True)

    list_parser = sub.add_parser("list")
    list_parser.add_argument("--output", type=Path)
    list_parser.set_defaults(func=list_voices)

    recommend_parser = sub.add_parser("recommend")
    recommend_parser.add_argument("--language", default="vi")
    recommend_parser.add_argument("--gender")
    recommend_parser.add_argument("--age")
    recommend_parser.add_argument("--use-case", default="NARRATION")
    recommend_parser.add_argument("--tone")
    recommend_parser.add_argument("--delivery")
    recommend_parser.add_argument("--brief")
    recommend_parser.add_argument("--model-name", default="myna-2")
    recommend_parser.add_argument("--speed", type=float, default=1.0)
    recommend_parser.add_argument("--output", type=Path, default=Path("source/voice_selection.toml"))
    recommend_parser.add_argument("--save-preference", action="store_true")
    recommend_parser.set_defaults(func=recommend)

    synth_parser = sub.add_parser("synthesize")
    synth_parser.add_argument("--voice-id")
    synth_parser.add_argument("--audio-name", default="video-agent narration")
    synth_parser.add_argument("--text")
    synth_parser.add_argument("--text-file")
    synth_parser.add_argument("--creative-plan", type=Path, default=Path("source/creative_plan.toml"))
    synth_parser.add_argument("--language", default="vi")
    synth_parser.add_argument("--model-name", default="myna-2")
    synth_parser.add_argument("--speed", type=float, default=1.0)
    synth_parser.add_argument("--poll-interval", type=int, default=5)
    synth_parser.add_argument("--timeout-seconds", type=int, default=600)
    synth_parser.add_argument("--output-audio", type=Path, default=Path("source/voice.wav"))
    synth_parser.add_argument("--output", type=Path, default=Path("source/voice_selection.toml"))
    synth_parser.set_defaults(func=synthesize)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
