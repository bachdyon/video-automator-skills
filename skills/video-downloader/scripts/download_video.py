#!/usr/bin/env python3
"""Download TikTok media through the TikWM form API for the video pipeline."""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from pipeline_utils import _ssl_context, die, download_file, media_metadata, write_toml_document  # noqa: E402


TIKWM_API = "https://www.tikwm.com/api/"
DEFAULT_HEADERS = {
    "accept": "application/json, text/javascript, */*; q=0.01",
    "accept-language": "en-US,en;q=0.9,vi;q=0.8",
    "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
    "origin": "https://app.bachdyon.com",
    "referer": "https://app.bachdyon.com/",
    "sec-ch-ua": '"Google Chrome";v="147", "Not.A/Brand";v="8", "Chromium";v="147"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "cross-site",
    "user-agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
    ),
}
VIDEO_EXTENSIONS = (".mp4", ".mov", ".m4v", ".webm")
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")
AUDIO_EXTENSIONS = (".mp3", ".m4a", ".aac", ".wav")


def post_form_json(url: str, fields: dict[str, Any], timeout: int = 90) -> dict[str, Any]:
    import json

    data = urllib.parse.urlencode(fields).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST", headers=DEFAULT_HEADERS)
    try:
        context = _ssl_context()
        kwargs: dict[str, Any] = {"timeout": timeout}
        if context is not None:
            kwargs["context"] = context
        with urllib.request.urlopen(req, **kwargs) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        die(f"TikWM API failed with HTTP {exc.code}: {detail}")
    except urllib.error.URLError as exc:
        die(f"TikWM API request failed: {exc}")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        die(f"TikWM API returned non-JSON response: {raw[:500]}")


def resolve_tikwm_url(value: str) -> str:
    if value.startswith("//"):
        return "https:" + value
    if value.startswith("/"):
        return "https://www.tikwm.com" + value
    return value


def fetch_media(url: str, *, count: int, cursor: int, hd: bool) -> dict[str, Any]:
    response = post_form_json(
        TIKWM_API,
        {
            "url": url,
            "count": count,
            "cursor": cursor,
            "web": 1,
            "hd": 1 if hd else 0,
        },
    )
    code = response.get("code")
    if code not in (0, "0", None):
        die(f"TikWM API returned code={code}: {response.get('msg') or response}")
    data = response.get("data") or {}
    if not isinstance(data, dict):
        die(f"TikWM API response has no media object: {response}")
    return data


def slugify(value: str, fallback: str = "download") -> str:
    text = re.sub(r"[^\w\s.-]+", "", value.lower(), flags=re.UNICODE)
    text = re.sub(r"[\s_]+", "-", text).strip(".-")
    return (text or fallback)[:70]


def short_hash(value: str, length: int = 8) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:length]


def extension_from_url(url: str, fallback: str) -> str:
    path = urllib.parse.urlparse(url).path.lower()
    suffix = Path(path).suffix
    if suffix in VIDEO_EXTENSIONS + IMAGE_EXTENSIONS + AUDIO_EXTENSIONS:
        return suffix
    return fallback


def media_id(data: dict[str, Any], source_url: str) -> str:
    value = data.get("id") or data.get("aweme_id") or data.get("video_id")
    if value:
        return str(value)
    match = re.search(r"/video/(\d+)", source_url)
    if match:
        return match.group(1)
    return short_hash(source_url, 12)


def author_name(data: dict[str, Any]) -> str:
    author = data.get("author") or {}
    if isinstance(author, dict):
        return str(author.get("unique_id") or author.get("nickname") or "")
    return ""


def choose_video_url(data: dict[str, Any], *, hd: bool) -> str:
    keys = ["hdplay", "play", "wmplay"] if hd else ["play", "hdplay", "wmplay"]
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value:
            return resolve_tikwm_url(value)
    return ""


def choose_audio_url(data: dict[str, Any]) -> str:
    values = [data.get("music")]
    music_info = data.get("music_info") or {}
    if isinstance(music_info, dict):
        values.extend([music_info.get("play"), music_info.get("url")])
    for value in values:
        if isinstance(value, str) and value:
            return resolve_tikwm_url(value)
    return ""


def output_defaults(args: argparse.Namespace) -> tuple[Path, Path]:
    if args.output_dir:
        output_dir = Path(args.output_dir)
    elif args.job:
        output_dir = Path(args.job) / "input" / "raw_assets" / "videos" / "downloaded"
    else:
        output_dir = Path("raw_assets") / "videos" / "downloaded"
    if args.report_toml:
        report = Path(args.report_toml)
    elif args.job:
        report = Path(args.job) / "source" / "download_report.toml"
    else:
        report = output_dir / "download_report.toml"
    return output_dir, report


def output_for_kind(base_output_dir: Path, kind: str) -> Path:
    if kind == "video":
        return base_output_dir
    parent = base_output_dir
    parts = list(parent.parts)
    if "videos" in parts:
        parts[parts.index("videos")] = "images" if kind == "image" else "audio"
        return Path(*parts)
    return parent.parent / ("images" if kind == "image" else "audio") / parent.name


def read_urls(args: argparse.Namespace) -> list[str]:
    urls: list[str] = []
    if args.url:
        urls.append(args.url)
    if args.urls_file:
        for line in Path(args.urls_file).read_text(encoding="utf-8").splitlines():
            item = line.strip()
            if item and not item.startswith("#"):
                urls.append(item)
    if not urls:
        die("provide --url or --urls-file")
    return urls


def download_asset(url: str, path: Path, *, overwrite: bool) -> tuple[Path, bool]:
    if path.exists() and not overwrite:
        return path, False
    headers = {"user-agent": DEFAULT_HEADERS["user-agent"], "referer": "https://www.tiktok.com/"}
    return download_file(url, path, headers=headers, timeout=240), True


def append_asset_row(
    rows: list[dict[str, Any]],
    *,
    source_url: str,
    data: dict[str, Any],
    kind: str,
    direct_url: str,
    output_path: Path,
    downloaded: bool,
) -> None:
    metadata = media_metadata(output_path) if output_path.exists() else {}
    rows.append(
        {
            "provider": "tikwm",
            "media_type": kind,
            "source_url": source_url,
            "asset_id": media_id(data, source_url),
            "title": str(data.get("title") or ""),
            "author": author_name(data),
            "output_path": str(output_path),
            "downloaded": downloaded,
            "size_bytes": int(output_path.stat().st_size) if output_path.exists() else 0,
            "duration_seconds": float(metadata.get("duration_seconds") or 0.0),
            "width": int(metadata.get("width") or 0),
            "height": int(metadata.get("height") or 0),
            "direct_url_hash": short_hash(direct_url, 12),
        }
    )


def process_one(source_url: str, args: argparse.Namespace, base_output_dir: Path, rows: list[dict[str, Any]]) -> None:
    data = fetch_media(source_url, count=args.count, cursor=args.cursor, hd=args.hd)
    item_id = media_id(data, source_url)
    slug = slugify(str(data.get("title") or author_name(data) or item_id), fallback=item_id)

    if args.mode in {"video", "all"}:
        video_url = choose_video_url(data, hd=args.hd)
        if not video_url:
            if args.mode == "video":
                die(f"no video URL found for {source_url}; try --mode images or --mode all")
        else:
            ext = extension_from_url(video_url, ".mp4")
            output_path = output_for_kind(base_output_dir, "video") / f"{item_id}_{slug}{ext}"
            path, downloaded = download_asset(video_url, output_path, overwrite=args.overwrite)
            append_asset_row(rows, source_url=source_url, data=data, kind="video", direct_url=video_url, output_path=path, downloaded=downloaded)

    if args.mode in {"images", "all"}:
        images = data.get("images") or []
        if isinstance(images, list):
            for idx, image_url_value in enumerate(images, start=1):
                if not isinstance(image_url_value, str) or not image_url_value:
                    continue
                image_url = resolve_tikwm_url(image_url_value)
                ext = extension_from_url(image_url, ".jpg")
                output_path = output_for_kind(base_output_dir, "image") / f"{item_id}_image_{idx:03d}{ext}"
                path, downloaded = download_asset(image_url, output_path, overwrite=args.overwrite)
                append_asset_row(rows, source_url=source_url, data=data, kind="image", direct_url=image_url, output_path=path, downloaded=downloaded)

    if args.mode in {"audio", "all"}:
        audio_url = choose_audio_url(data)
        if audio_url:
            ext = extension_from_url(audio_url, ".mp3")
            output_path = output_for_kind(base_output_dir, "audio") / f"{item_id}_{slug}{ext}"
            path, downloaded = download_asset(audio_url, output_path, overwrite=args.overwrite)
            append_asset_row(rows, source_url=source_url, data=data, kind="audio", direct_url=audio_url, output_path=path, downloaded=downloaded)


def write_report(path: Path, rows: list[dict[str, Any]], args: argparse.Namespace) -> None:
    write_toml_document(
        path,
        [
            (
                "metadata",
                {
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "provider": "tikwm",
                    "mode": args.mode,
                    "hd": bool(args.hd),
                    "total_assets": len(rows),
                },
            ),
            ("assets", rows),
        ],
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Download TikTok media through TikWM.")
    parser.add_argument("--url", help="TikTok URL to download.")
    parser.add_argument("--urls-file", help="Text file with one TikTok URL per line.")
    parser.add_argument("--job", help="Job directory; defaults output/report into the job layout.")
    parser.add_argument("--output-dir", help="Output directory for video assets.")
    parser.add_argument("--report-toml", help="Path to write download report TOML.")
    parser.add_argument("--mode", choices=["video", "images", "audio", "all"], default="video")
    parser.add_argument("--hd", action="store_true", help="Prefer hdplay when available.")
    parser.add_argument("--count", type=int, default=12)
    parser.add_argument("--cursor", type=int, default=0)
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing files.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    base_output_dir, report_path = output_defaults(args)
    rows: list[dict[str, Any]] = []
    for url in read_urls(args):
        process_one(url, args, base_output_dir, rows)
    if not rows:
        die("no assets were downloaded")
    write_report(report_path, rows, args)
    downloaded_count = sum(1 for row in rows if row.get("downloaded"))
    print(f"assets={len(rows)} downloaded={downloaded_count} report={report_path}")
    for row in rows:
        print(f"{row['media_type']}\t{row['output_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
