#!/usr/bin/env python3
"""Compress a video to fit under a target size using ffmpeg."""

from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path


MIB = 1024 * 1024


def run(cmd: list[str], *, capture: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        check=True,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )


def require_binary(name: str) -> None:
    if not shutil.which(name):
        raise SystemExit(f"Missing required binary: {name}")


def probe(path: Path) -> dict:
    result = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration,size,bit_rate",
            "-show_entries",
            "stream=index,codec_type,codec_name,width,height,r_frame_rate,bit_rate",
            "-of",
            "json",
            str(path),
        ],
        capture=True,
    )
    return json.loads(result.stdout)


def parse_duration(metadata: dict) -> float:
    try:
        return float(metadata["format"]["duration"])
    except (KeyError, TypeError, ValueError) as exc:
        raise SystemExit("Could not determine video duration with ffprobe") from exc


def default_output_path(input_path: Path, codec: str) -> Path:
    suffix = "h265" if codec == "h265" else "h264"
    return input_path.with_name(f"{input_path.stem}_under25mb_{suffix}.mp4")


def compute_video_bitrate_kbps(
    duration_seconds: float,
    target_mib: float,
    audio_bitrate_kbps: int,
    mux_overhead_fraction: float,
    min_video_bitrate_kbps: int,
) -> int:
    target_bits = target_mib * MIB * 8
    available_kbps = (target_bits / duration_seconds / 1000) * (1 - mux_overhead_fraction)
    video_kbps = math.floor(available_kbps - audio_bitrate_kbps)
    if video_kbps < min_video_bitrate_kbps:
        raise SystemExit(
            f"Target size is too small for duration: computed video bitrate {video_kbps} kbps "
            f"is below minimum {min_video_bitrate_kbps} kbps."
        )
    return video_kbps


def ffmpeg_h264_2pass(
    input_path: Path,
    output_path: Path,
    video_bitrate_kbps: int,
    audio_bitrate_kbps: int,
    preset: str,
    passlog: Path,
) -> None:
    first = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-c:v",
        "libx264",
        "-b:v",
        f"{video_bitrate_kbps}k",
        "-preset",
        preset,
        "-pass",
        "1",
        "-passlogfile",
        str(passlog),
        "-an",
        "-f",
        "mp4",
        "/dev/null",
    ]
    second = [
        "ffmpeg",
        "-y",
        "-i",
        str(input_path),
        "-c:v",
        "libx264",
        "-b:v",
        f"{video_bitrate_kbps}k",
        "-preset",
        preset,
        "-pass",
        "2",
        "-passlogfile",
        str(passlog),
        "-c:a",
        "aac",
        "-b:a",
        f"{audio_bitrate_kbps}k",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    run(first)
    run(second)


def ffmpeg_h265(
    input_path: Path,
    output_path: Path,
    video_bitrate_kbps: int,
    audio_bitrate_kbps: int,
    preset: str,
) -> None:
    run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(input_path),
            "-c:v",
            "libx265",
            "-b:v",
            f"{video_bitrate_kbps}k",
            "-preset",
            preset,
            "-tag:v",
            "hvc1",
            "-c:a",
            "aac",
            "-b:a",
            f"{audio_bitrate_kbps}k",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
    )


def write_preview(output_path: Path, preview_path: Path, at_seconds: float) -> None:
    run(
        [
            "ffmpeg",
            "-y",
            "-ss",
            f"{at_seconds:.3f}",
            "-i",
            str(output_path),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            "-update",
            "1",
            str(preview_path),
        ]
    )


def cleanup_passlog(passlog: Path) -> None:
    for candidate in passlog.parent.glob(passlog.name + "*"):
        try:
            candidate.unlink()
        except FileNotFoundError:
            pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compress a video below a target MiB size.")
    parser.add_argument("input", help="Input video path")
    parser.add_argument("--output", help="Output MP4 path")
    parser.add_argument("--max-mib", type=float, default=25.0, help="Hard max size in MiB")
    parser.add_argument("--target-mib", type=float, default=24.0, help="Target output size in MiB")
    parser.add_argument("--audio-bitrate-kbps", type=int, default=96)
    parser.add_argument("--codec", choices=["h264", "h265"], default="h264")
    parser.add_argument("--preset", default="medium", help="ffmpeg encoder preset")
    parser.add_argument("--min-video-bitrate-kbps", type=int, default=700)
    parser.add_argument("--mux-overhead-fraction", type=float, default=0.02)
    parser.add_argument("--metadata-output", help="JSON summary output path")
    parser.add_argument("--preview-output", help="JPEG preview output path")
    parser.add_argument("--preview-at", type=float, default=10.0, help="Preview timestamp in seconds")
    parser.add_argument("--no-preview", action="store_true")
    args = parser.parse_args(argv)

    require_binary("ffmpeg")
    require_binary("ffprobe")

    input_path = Path(args.input)
    if not input_path.exists() or not input_path.is_file():
        raise SystemExit(f"Input video not found: {input_path}")
    if args.target_mib >= args.max_mib:
        raise SystemExit("--target-mib must be smaller than --max-mib")

    output_path = Path(args.output) if args.output else default_output_path(input_path, args.codec)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    input_metadata = probe(input_path)
    duration = parse_duration(input_metadata)
    video_bitrate_kbps = compute_video_bitrate_kbps(
        duration,
        args.target_mib,
        args.audio_bitrate_kbps,
        args.mux_overhead_fraction,
        args.min_video_bitrate_kbps,
    )

    passlog = Path("/private/tmp") / f"video_compress_{output_path.stem}"
    try:
        if args.codec == "h264":
            ffmpeg_h264_2pass(
                input_path,
                output_path,
                video_bitrate_kbps,
                args.audio_bitrate_kbps,
                args.preset,
                passlog,
            )
        else:
            ffmpeg_h265(input_path, output_path, video_bitrate_kbps, args.audio_bitrate_kbps, args.preset)
    finally:
        cleanup_passlog(passlog)

    output_metadata = probe(output_path)
    output_size = output_path.stat().st_size
    max_bytes = int(args.max_mib * MIB)

    preview_path = None
    if not args.no_preview:
        preview_path = Path(args.preview_output) if args.preview_output else output_path.with_suffix(".preview.jpg")
        write_preview(output_path, preview_path, min(args.preview_at, max(duration - 0.1, 0)))

    summary = {
        "input": {
            "path": str(input_path),
            "size_bytes": input_path.stat().st_size,
            "metadata": input_metadata,
        },
        "output": {
            "path": str(output_path),
            "size_bytes": output_size,
            "size_mib": round(output_size / MIB, 3),
            "under_max_size": output_size <= max_bytes,
            "metadata": output_metadata,
            "preview_path": str(preview_path) if preview_path else None,
        },
        "settings": {
            "codec": args.codec,
            "target_mib": args.target_mib,
            "max_mib": args.max_mib,
            "computed_video_bitrate_kbps": video_bitrate_kbps,
            "audio_bitrate_kbps": args.audio_bitrate_kbps,
            "preset": args.preset,
        },
    }

    metadata_path = Path(args.metadata_output) if args.metadata_output else output_path.with_suffix(".json")
    metadata_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if summary["output"]["under_max_size"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
