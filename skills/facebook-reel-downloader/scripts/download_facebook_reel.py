#!/usr/bin/env python3
"""Download a Facebook Reel/video with yt-dlp and write a small TOML report."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


ALLOWED_HOSTS = {"facebook.com", "www.facebook.com", "m.facebook.com", "fb.watch", "www.fb.watch"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True, help="Facebook Reel/video URL")
    parser.add_argument("--job", type=Path, help="Job directory, e.g. jobs/<job_id>")
    parser.add_argument("--output-dir", type=Path, help="Override download directory")
    parser.add_argument("--cookies-from-browser", help="Browser profile source supported by yt-dlp")
    parser.add_argument("--overwrite", action="store_true", help="Download again instead of skipping")
    parser.add_argument("--report-toml", type=Path, help="Override report path")
    return parser.parse_args()


def validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or (parsed.hostname or "").lower() not in ALLOWED_HOSTS:
        raise SystemExit("Lỗi: --url phải là URL facebook.com hoặc fb.watch hợp lệ.")


def find_ytdlp(repo_root: Path) -> str:
    local = repo_root / ".venv" / "bin" / "yt-dlp"
    if local.is_file():
        return str(local)
    executable = shutil.which("yt-dlp")
    if executable:
        return executable
    raise SystemExit("Lỗi: không tìm thấy yt-dlp. Cài vào .venv trước khi chạy.")


def toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def probe_media(path: Path) -> dict[str, object]:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return {}
    command = [
        ffprobe,
        "-v", "error",
        "-show_entries", "format=duration:stream=codec_type,codec_name,width,height",
        "-of", "json",
        str(path),
    ]
    result = subprocess.run(command, text=True, capture_output=True)
    if result.returncode != 0:
        return {}
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}
    output: dict[str, object] = {}
    duration = data.get("format", {}).get("duration")
    if duration is not None:
        output["duration_seconds"] = round(float(duration), 3)
    for stream in data.get("streams", []):
        if stream.get("codec_type") == "video":
            output["video_codec"] = stream.get("codec_name", "")
            output["width"] = stream.get("width", 0)
            output["height"] = stream.get("height", 0)
        elif stream.get("codec_type") == "audio":
            output["audio_codec"] = stream.get("codec_name", "")
    return output


def write_report(report: Path, url: str, media_path: Path, metadata: dict[str, object]) -> None:
    report.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"source_url = {toml_string(url)}",
        'provider = "facebook"',
        'downloader = "yt-dlp"',
        f"asset_path = {toml_string(str(media_path))}",
        f"byte_size = {media_path.stat().st_size}",
        f"downloaded_at = {toml_string(datetime.now(timezone.utc).isoformat())}",
    ]
    for key in ("duration_seconds", "width", "height", "video_codec", "audio_codec"):
        if key not in metadata:
            continue
        value = metadata[key]
        lines.append(f"{key} = {toml_string(value) if isinstance(value, str) else value}")
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    validate_url(args.url)
    repo_root = Path(__file__).resolve().parents[3]

    if args.output_dir:
        output_dir = args.output_dir
    elif args.job:
        output_dir = args.job / "input" / "raw_assets" / "videos" / "downloaded" / "facebook"
    else:
        output_dir = repo_root / "raw_assets" / "videos" / "downloaded" / "facebook"
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.report_toml:
        report = args.report_toml.resolve()
    elif args.job:
        report = (args.job / "source" / "facebook_reel_download_report.toml").resolve()
    else:
        report = output_dir / "download_report.toml"

    archive = output_dir / ".download_archive.txt"
    command = [
        find_ytdlp(repo_root),
        "--no-playlist",
        "--newline",
        "--format", "bv*[ext=mp4][vcodec^=avc]+ba[ext=m4a]/b[ext=mp4][vcodec^=avc]/bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/bv*+ba/b",
        "--merge-output-format", "mp4",
        "--output", str(output_dir / "%(id)s_%(title).80B.%(ext)s"),
        "--print", "after_move:__DOWNLOADED_FILE__:%(filepath)s",
    ]
    if args.overwrite:
        command.append("--force-overwrites")
    else:
        command += ["--download-archive", str(archive), "--no-overwrites"]
    if args.cookies_from_browser:
        command += ["--cookies-from-browser", args.cookies_from_browser]
    command.append(args.url)

    result = subprocess.run(command, text=True, capture_output=True)
    combined = "\n".join(part for part in (result.stdout, result.stderr) if part)
    if result.returncode != 0:
        print(combined, file=sys.stderr)
        return result.returncode

    marker = "__DOWNLOADED_FILE__:"
    paths = [Path(line.split(marker, 1)[1].strip()) for line in combined.splitlines() if marker in line]
    if not paths:
        print("Không tải file mới (có thể URL đã có trong download archive).", file=sys.stderr)
        return 0

    media_path = paths[-1].resolve()
    if not media_path.is_file():
        print(f"Lỗi: yt-dlp báo thành công nhưng không thấy file: {media_path}", file=sys.stderr)
        return 2

    metadata = probe_media(media_path)
    write_report(report, args.url, media_path, metadata)
    print(f"Đã tải: {media_path}")
    print(f"Report: {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
