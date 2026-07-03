#!/usr/bin/env python3
"""Search Klipy for meme/reaction assets and optionally download media."""

from __future__ import annotations

import argparse
import json
import os
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


TENOR_ENDPOINT = "https://api.klipy.com/v2/search"
PRODUCT_ENDPOINT = "https://api.klipy.com/api/v1/{key}/{product}/search"

GIF_FORMATS = ["mp4", "tinymp4", "nanomp4", "webm", "tinywebm", "preview", "gif", "tinygif"]
STICKER_FORMATS = [
    "webp_transparent",
    "tinywebp_transparent",
    "gif_transparent",
    "tinygif_transparent",
    "png",
    "preview",
]


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values


def get_api_key(args: argparse.Namespace) -> str:
    if args.api_key:
        return args.api_key
    if os.environ.get("KLIPY_API_KEY"):
        return os.environ["KLIPY_API_KEY"]
    env_values = load_env_file(Path(args.env_file))
    if env_values.get("KLIPY_API_KEY"):
        return env_values["KLIPY_API_KEY"]
    raise SystemExit("Missing KLIPY_API_KEY. Set it in the environment or repo .env.")


def slugify(value: str, fallback: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9._-]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-._")
    return value[:80] or fallback


def redact_secret(text: str, secret: str) -> str:
    if secret:
        text = text.replace(secret, "[redacted]")
    return text


def ssl_context(insecure: bool) -> ssl.SSLContext | None:
    if not insecure:
        return None
    return ssl._create_unverified_context()


def request_json(url: str, timeout: int, api_key: str, insecure: bool) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "video-agent-klipy-meme-search/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=ssl_context(insecure)) as response:
            payload = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"Klipy HTTP {exc.code}: {redact_secret(body, api_key)[:500]}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"Klipy request failed: {exc}") from exc
    try:
        return json.loads(payload)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Klipy returned non-JSON response: {redact_secret(payload, api_key)[:500]}") from exc


def build_url(args: argparse.Namespace, api_key: str) -> str:
    params: dict[str, str] = {
        "q": args.query,
        "limit": str(args.limit),
        "locale": args.locale,
        "contentfilter": args.contentfilter,
    }
    if args.pos:
        params["pos"] = args.pos
    if args.random:
        params["random"] = "true"

    media_filter = args.media_filter
    if not media_filter:
        media_filter = ",".join(STICKER_FORMATS if args.kind == "sticker" else GIF_FORMATS)
    params["media_filter"] = media_filter

    if args.api_style == "product":
        product = {"gif": "gifs", "sticker": "stickers", "clip": "clips", "meme": "memes"}[args.kind]
        base = PRODUCT_ENDPOINT.format(key=urllib.parse.quote(api_key), product=product)
    else:
        base = args.endpoint or TENOR_ENDPOINT
        params["key"] = api_key
        if args.kind == "sticker":
            params["searchfilter"] = "sticker"
        elif args.kind in {"clip", "meme"}:
            params["searchfilter"] = args.kind

    return base + "?" + urllib.parse.urlencode(params)


def extract_results(payload: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("results", "data", "items"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
    if isinstance(payload.get("result"), list):
        return payload["result"]
    return []


def select_media(result: dict[str, Any], preferred: list[str]) -> tuple[str, dict[str, Any]] | tuple[None, None]:
    formats = result.get("media_formats") or result.get("media") or {}
    if isinstance(formats, list):
        normalized = {}
        for item in formats:
            if isinstance(item, dict) and item.get("format") and item.get("url"):
                normalized[item["format"]] = item
        formats = normalized
    if not isinstance(formats, dict):
        return None, None
    for fmt in preferred:
        media = formats.get(fmt)
        if isinstance(media, dict) and media.get("url"):
            return fmt, media
    for fmt, media in formats.items():
        if isinstance(media, dict) and media.get("url"):
            return fmt, media
    return None, None


def extension_from_url(url: str, fmt: str) -> str:
    path = urllib.parse.urlparse(url).path
    suffix = Path(path).suffix.lower()
    if suffix and len(suffix) <= 6:
        return suffix
    if "mp4" in fmt:
        return ".mp4"
    if "webm" in fmt:
        return ".webm"
    if "webp" in fmt:
        return ".webp"
    if "png" in fmt:
        return ".png"
    if "jpg" in fmt or fmt == "preview":
        return ".jpg"
    return ".gif"


def download_file(url: str, path: Path, timeout: int, overwrite: bool, insecure: bool) -> int:
    if path.exists() and not overwrite:
        return path.stat().st_size
    path.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "video-agent-klipy-meme-search/1.0"})
    with urllib.request.urlopen(request, timeout=timeout, context=ssl_context(insecure)) as response:
        data = response.read()
    path.write_bytes(data)
    return len(data)


def summarize_result(
    result: dict[str, Any],
    index: int,
    args: argparse.Namespace,
    preferred: list[str],
) -> dict[str, Any]:
    fmt, media = select_media(result, preferred)
    item_id = str(result.get("id") or result.get("slug") or f"result-{index + 1}")
    title = str(result.get("title") or result.get("content_description") or item_id)
    summary: dict[str, Any] = {
        "rank": index + 1,
        "id": item_id,
        "title": title,
        "content_description": result.get("content_description"),
        "tags": result.get("tags") or [],
        "itemurl": result.get("itemurl"),
        "url": result.get("url"),
        "selected_format": fmt,
        "selected_media": media,
    }
    if args.download and fmt and media:
        ext = extension_from_url(media["url"], fmt)
        filename = f"{index + 1:02d}_{slugify(title, item_id)}_{fmt}{ext}"
        local_path = Path(args.output_dir) / args.kind / filename
        size = download_file(media["url"], local_path, args.timeout, args.overwrite, args.insecure)
        summary["local_path"] = str(local_path)
        summary["downloaded_bytes"] = size
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", required=True, help="Search query, e.g. 'confused office worker reaction'.")
    parser.add_argument("--kind", choices=["gif", "sticker", "clip", "meme"], default="gif")
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--pos", default="")
    parser.add_argument("--locale", default="vi_VN")
    parser.add_argument("--contentfilter", default="high")
    parser.add_argument("--media-filter", default="")
    parser.add_argument("--random", action="store_true")
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--output-dir", default="raw_assets/memes/klipy")
    parser.add_argument("--report", default="")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--api-key", default="", help="Prefer KLIPY_API_KEY or .env; this is for ad hoc use only.")
    parser.add_argument("--api-style", choices=["tenor", "product"], default="tenor")
    parser.add_argument("--endpoint", default="", help="Override Tenor-compatible search endpoint.")
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--insecure", action="store_true", help="Disable TLS verification when local CA setup is broken.")
    args = parser.parse_args()

    api_key = get_api_key(args)
    url = build_url(args, api_key)
    payload = request_json(url, args.timeout, api_key, args.insecure)
    results = extract_results(payload)
    preferred = STICKER_FORMATS if args.kind == "sticker" else GIF_FORMATS
    summaries = [summarize_result(result, i, args, preferred) for i, result in enumerate(results)]

    report = {
        "metadata": {
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "provider": "klipy",
            "query": args.query,
            "kind": args.kind,
            "api_style": args.api_style,
            "locale": args.locale,
            "contentfilter": args.contentfilter,
            "limit": args.limit,
            "next": payload.get("next") or payload.get("pos") or "",
        },
        "results": summaries,
    }

    report_path = Path(args.report) if args.report else Path(args.output_dir) / f"klipy_{slugify(args.query, 'query')}_{args.kind}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"results={len(summaries)} downloaded={sum(1 for item in summaries if item.get('local_path'))} report={report_path}")
    for item in summaries:
        local = item.get("local_path", "")
        title = str(item.get("title") or item.get("id"))[:90]
        print(f"{item['rank']:02d}\t{item.get('selected_format') or '-'}\t{local}\t{title}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
