#!/usr/bin/env python3
"""Render audio by keeping only words marked keep=true in words_timestamp TOML."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Word:
    text: str
    start: float
    end: float
    keep: bool


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


def load_words_toml(path: Path) -> list[Word]:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    raw_words = data.get("words", [])
    if not isinstance(raw_words, list):
        raise SystemExit("Input TOML must contain repeated [[words]] tables.")

    metadata = data.get("metadata", {}) or {}
    rewrite_section = data.get("reconstructed_article_rewrite", {}) or {}
    rewrite_text = str(rewrite_section.get("text") or "").strip()
    rewrite_status = str(metadata.get("rewrite_status") or "").strip().lower()

    if not rewrite_text:
        raise SystemExit(
            "reconstructed_article_rewrite.text is empty. "
            "Phase 1 (semantic rewrite) must be filled before rendering."
        )
    if rewrite_status != "filled":
        raise SystemExit(
            f"metadata.rewrite_status is '{rewrite_status or 'pending'}'. "
            "Set it to 'filled' after Phase 1 completes and Phase 2 keep flags are aligned."
        )

    words: list[Word] = []
    for index, item in enumerate(raw_words, start=1):
        if not isinstance(item, dict):
            raise SystemExit(f"Word #{index} must be a TOML table.")
        text = str(item.get("word") or item.get("text") or "").strip()
        if not text:
            continue
        start = float(item.get("start", 0.0))
        end = float(item.get("end", start))
        if end <= start:
            end = round(start + 0.001, 3)
        words.append(
            Word(
                text=text,
                start=start,
                end=end,
                keep=bool(item.get("keep", True)),
            )
        )

    if words and all(word.keep for word in words):
        print(
            "warning: every word still has keep=true. "
            "Verify that Phase 2 alignment matched reconstructed_article_rewrite intentionally.",
            file=sys.stderr,
        )

    return words


def build_keep_intervals(
    words: list[Word],
    duration: float,
    pad_before: float,
    pad_after: float,
    merge_gap: float,
    min_interval: float,
) -> list[tuple[float, float]]:
    intervals: list[tuple[float, float]] = []
    for word in words:
        if not word.keep:
            continue
        start = max(0.0, word.start - pad_before)
        end = min(duration, word.end + pad_after)
        if end - start >= min_interval:
            intervals.append((start, end))

    if not intervals:
        return []

    intervals.sort(key=lambda pair: (pair[0], pair[1]))
    merged: list[tuple[float, float]] = [intervals[0]]
    for start, end in intervals[1:]:
        prev_start, prev_end = merged[-1]
        if start <= prev_end + merge_gap:
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))
    return merged


def build_filter_complex(intervals: list[tuple[float, float]]) -> str:
    if not intervals:
        raise SystemExit("No keep intervals available to build ffmpeg graph.")
    chains: list[str] = []
    labels: list[str] = []
    for idx, (start, end) in enumerate(intervals):
        label = f"s{idx}"
        labels.append(f"[{label}]")
        chains.append(f"[0:a]atrim=start={start:.3f}:end={end:.3f},asetpts=PTS-STARTPTS[{label}]")
    concat = "".join(labels) + f"concat=n={len(intervals)}:v=0:a=1[out]"
    return ";".join(chains + [concat])


def render_audio(input_path: Path, output_path: Path, intervals: list[tuple[float, float]]) -> None:
    if not intervals:
        raise SystemExit("No keep=true intervals were found. Refusing to render empty audio.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    suffix = output_path.suffix.lower()
    if suffix not in {".wav", ".mp3"}:
        raise SystemExit("Output path must end with .wav or .mp3")
    filter_complex = build_filter_complex(intervals)
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(input_path),
        "-filter_complex",
        filter_complex,
        "-map",
        "[out]",
    ]
    if suffix == ".wav":
        cmd += ["-acodec", "pcm_s16le", "-ar", "48000", "-ac", "2", str(output_path)]
    else:
        cmd += ["-codec:a", "libmp3lame", "-q:a", "2", str(output_path)]
    run(cmd)


def write_plan(
    path: Path,
    input_path: Path,
    words_toml_path: Path,
    output_path: Path,
    duration: float,
    words: list[Word],
    intervals: list[tuple[float, float]],
    pad_before: float,
    pad_after: float,
    merge_gap: float,
) -> None:
    kept_words = [word for word in words if word.keep]
    kept_seconds = sum(end - start for start, end in intervals)
    payload = {
        "input_audio": str(input_path),
        "input_words_toml": str(words_toml_path),
        "output_audio": str(output_path),
        "input_duration_seconds": duration,
        "output_duration_seconds": round(kept_seconds, 3),
        "removed_seconds": round(duration - kept_seconds, 3),
        "original_word_count": len(words),
        "kept_word_count": len(kept_words),
        "keep_interval_count": len(intervals),
        "padding_before_seconds": pad_before,
        "padding_after_seconds": pad_after,
        "merge_gap_seconds": merge_gap,
        "keep_intervals": [{"start": round(start, 3), "end": round(end, 3)} for start, end in intervals],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Input .wav or .mp3 file")
    parser.add_argument("--words-toml", type=Path, required=True, help="words_timestamp.toml with keep flags")
    parser.add_argument("--output", type=Path, required=True, help="Output .wav or .mp3")
    parser.add_argument("--pad-before", type=float, default=0.03, help="Seconds added before each kept word")
    parser.add_argument("--pad-after", type=float, default=0.05, help="Seconds added after each kept word")
    parser.add_argument("--merge-gap", type=float, default=0.08, help="Merge intervals if gap is <= this value")
    parser.add_argument("--min-interval", type=float, default=0.01, help="Drop intervals shorter than this value")
    parser.add_argument("--plan-json", type=Path, help="Write keep-render plan JSON")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = args.input.expanduser().resolve()
    words_toml_path = args.words_toml.expanduser().resolve()
    output_path = args.output.expanduser().resolve()

    if not input_path.exists():
        raise SystemExit(f"Input file does not exist: {input_path}")
    if input_path.suffix.lower() not in {".wav", ".mp3"}:
        raise SystemExit("Input path must end with .wav or .mp3")
    if not words_toml_path.exists():
        raise SystemExit(f"Words TOML does not exist: {words_toml_path}")
    if args.pad_before < 0 or args.pad_after < 0 or args.merge_gap < 0 or args.min_interval < 0:
        raise SystemExit("pad-before, pad-after, merge-gap and min-interval must be >= 0.")

    require_binary("ffmpeg")
    require_binary("ffprobe")

    duration = audio_duration(input_path)
    words = load_words_toml(words_toml_path)
    intervals = build_keep_intervals(
        words=words,
        duration=duration,
        pad_before=args.pad_before,
        pad_after=args.pad_after,
        merge_gap=args.merge_gap,
        min_interval=args.min_interval,
    )

    kept_seconds = sum(end - start for start, end in intervals)
    print(f"Keep intervals: {len(intervals)}")
    print(f"Input duration: {duration:.2f}s")
    print(f"Planned output duration: {kept_seconds:.2f}s ({(kept_seconds / duration * 100 if duration else 0):.2f}%)")

    render_audio(input_path, output_path, intervals)
    print(f"Wrote: {output_path}")

    if args.plan_json:
        write_plan(
            path=args.plan_json.expanduser().resolve(),
            input_path=input_path,
            words_toml_path=words_toml_path,
            output_path=output_path,
            duration=duration,
            words=words,
            intervals=intervals,
            pad_before=args.pad_before,
            pad_after=args.pad_after,
            merge_gap=args.merge_gap,
        )
        print(f"Wrote plan: {args.plan_json.expanduser().resolve()}")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        print(exc.stderr or exc.stdout)
        raise SystemExit(exc.returncode)
