#!/usr/bin/env python3
"""Fast YouTube/Shorts downloader with MP3 export by default."""

from __future__ import annotations

import argparse
import glob
import os
import shutil
import subprocess
import sys
from pathlib import Path


DEFAULT_VIDEO_DIR = Path("raw_assets/videos/downloaded")
DEFAULT_AUDIO_DIR = Path("raw_assets/audio/downloaded")
DEFAULT_FORMAT = "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/best"


def run(cmd: list[str]) -> None:
    print("+ " + " ".join(cmd))
    subprocess.run(cmd, check=True)


def newest_match(pattern: str) -> Path | None:
    matches = [Path(p) for p in glob.glob(pattern)]
    if not matches:
        return None
    return max(matches, key=lambda p: p.stat().st_mtime)


def find_video_for_id(output_dir: Path, video_id: str) -> Path:
    found = newest_match(str(output_dir / f"{video_id}_*.mp4"))
    if found:
        return found
    found = newest_match(str(output_dir / "*.mp4"))
    if found:
        return found
    raise FileNotFoundError(f"No MP4 output found in {output_dir}")


def download_video(url: str, output_dir: Path, fragments: int) -> Path:
    try:
        import yt_dlp  # type: ignore
    except ImportError as exc:
        raise SystemExit(
            "yt_dlp is missing. Install it in the project venv, then retry."
        ) from exc

    output_dir.mkdir(parents=True, exist_ok=True)
    outtmpl = str(output_dir / "%(id)s_%(title).80B.%(ext)s")

    opts = {
        "format": DEFAULT_FORMAT,
        "merge_output_format": "mp4",
        "outtmpl": outtmpl,
        "restrictfilenames": True,
        "noprogress": False,
        "no_mtime": True,
        "concurrent_fragment_downloads": fragments,
    }

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)

    video_id = info.get("id") if isinstance(info, dict) else None
    if not video_id:
        raise RuntimeError("yt-dlp did not return a video id")
    return find_video_for_id(output_dir, video_id)


def mp3_output_path(video_path: Path, audio_dir: Path) -> Path:
    audio_dir.mkdir(parents=True, exist_ok=True)
    return audio_dir / f"{video_path.stem}.mp3"


def export_mp3(video_path: Path, audio_dir: Path, bitrate: str) -> Path:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise SystemExit("ffmpeg is required to export MP3")
    out = mp3_output_path(video_path, audio_dir)
    run([
        ffmpeg,
        "-y",
        "-i",
        str(video_path),
        "-vn",
        "-codec:a",
        "libmp3lame",
        "-b:a",
        bitrate,
        str(out),
    ])
    return out


def probe(path: Path) -> str:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return ""
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration,size,bit_rate:stream=codec_type,codec_name,width,height,sample_rate,channels,avg_frame_rate",
            "-of",
            "default=noprint_wrappers=1",
            str(path),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    return result.stdout.strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", nargs="?", help="Public YouTube video or Shorts URL")
    parser.add_argument("--from-video", type=Path, help="Export MP3 from an existing local video")
    parser.add_argument("--video-dir", type=Path, default=DEFAULT_VIDEO_DIR)
    parser.add_argument("--audio-dir", type=Path, default=DEFAULT_AUDIO_DIR)
    parser.add_argument(
        "--mp3",
        action="store_true",
        default=True,
        help="Export an MP3 audio file (default; kept for compatibility)",
    )
    parser.add_argument("--mp3-bitrate", default="192k")
    parser.add_argument("-N", "--fragments", type=int, default=16)
    parser.add_argument("--probe", action="store_true", help="Print ffprobe metadata")
    args = parser.parse_args()
    if not args.url and not args.from_video:
        parser.error("provide a URL or --from-video")
    return args


def main() -> int:
    args = parse_args()
    video_path = args.from_video if args.from_video else download_video(args.url, args.video_dir, args.fragments)

    if not video_path.exists():
        raise FileNotFoundError(video_path)

    print(f"VIDEO={video_path}")
    if args.probe:
        print(probe(video_path))

    if args.mp3:
        audio_path = export_mp3(video_path, args.audio_dir, args.mp3_bitrate)
        print(f"MP3={audio_path}")
        if args.probe:
            print(probe(audio_path))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
