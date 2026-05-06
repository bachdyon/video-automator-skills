#!/usr/bin/env python3
"""Create HeyGen image-to-video talking-head videos from image plus audio."""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import sys
import time
import uuid
from pathlib import Path
from urllib import error, parse, request


API_BASE = "https://api.heygen.com"
MAX_SIZE_BYTES = 32 * 1024 * 1024
SUPPORTED_UPLOAD_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".mp4",
    ".webm",
    ".mp3",
    ".wav",
    ".pdf",
}


def load_env(path: Path) -> dict[str, str]:
    values = dict(os.environ)
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    return values


def api_key(env_file: str) -> str:
    key = load_env(Path(env_file)).get("HEYGEN_API_KEY")
    if not key:
        raise SystemExit("Missing HEYGEN_API_KEY in environment or .env")
    return key


def is_url(value: str | None) -> bool:
    return bool(value and (value.startswith("http://") or value.startswith("https://")))


def validate_upload_file(path: Path) -> None:
    if not path.exists():
        raise SystemExit(f"File not found: {path}")
    if not path.is_file():
        raise SystemExit(f"Not a file: {path}")
    if path.stat().st_size > MAX_SIZE_BYTES:
        raise SystemExit(f"File too large for HeyGen 32 MB limit: {path}")
    if path.suffix.lower() not in SUPPORTED_UPLOAD_EXTENSIONS:
        raise SystemExit(f"Unsupported file extension for HeyGen upload: {path.suffix}")


def request_json(method: str, url: str, key: str, payload: dict | None = None) -> dict:
    headers = {"X-Api-Key": key, "Accept": "application/json"}
    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = request.Request(url, data=data, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=180) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"HTTP {exc.code} from {url}: {detail}") from exc


def upload_asset(path: Path, key: str) -> dict:
    validate_upload_file(path)
    boundary = f"----heygen-{uuid.uuid4().hex}"
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    body = b"".join(
        [
            f"--{boundary}\r\n".encode("utf-8"),
            (
                f'Content-Disposition: form-data; name="file"; filename="{path.name}"\r\n'
                f"Content-Type: {mime}\r\n\r\n"
            ).encode("utf-8"),
            path.read_bytes(),
            b"\r\n",
            f"--{boundary}--\r\n".encode("utf-8"),
        ]
    )
    req = request.Request(
        f"{API_BASE}/v3/assets",
        data=body,
        headers={
            "X-Api-Key": key,
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Accept": "application/json",
            "User-Agent": "video-agent-heygen/1.0",
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=180) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"HeyGen upload failed for {path}: HTTP {exc.code}: {detail}") from exc
    data = payload.get("data") or {}
    asset_id = data.get("asset_id")
    if not asset_id:
        raise SystemExit(f"HeyGen response missing data.asset_id: {json.dumps(payload, ensure_ascii=False)}")
    return {
        "path": str(path),
        "asset_id": asset_id,
        "url": data.get("url"),
        "mime_type": data.get("mime_type"),
        "size_bytes": data.get("size_bytes"),
        "response": payload,
    }


def exactly_one(*values: str | None) -> bool:
    return sum(1 for value in values if value) == 1


def build_image(args: argparse.Namespace, key: str, uploads: list[dict]) -> dict:
    if not exactly_one(args.image, args.image_url, args.image_asset_id):
        raise SystemExit("Provide exactly one of --image, --image-url, or --image-asset-id")
    if args.image:
        uploaded = upload_asset(Path(args.image), key)
        uploads.append(uploaded)
        return {"type": "asset_id", "asset_id": uploaded["asset_id"]}
    if args.image_url:
        if not is_url(args.image_url):
            raise SystemExit("--image-url must be http(s)")
        return {"type": "url", "url": args.image_url}
    return {"type": "asset_id", "asset_id": args.image_asset_id}


def build_audio(args: argparse.Namespace, key: str, uploads: list[dict]) -> dict:
    if not exactly_one(args.audio, args.audio_url, args.audio_asset_id):
        raise SystemExit("Provide exactly one of --audio, --audio-url, or --audio-asset-id")
    if args.audio:
        uploaded = upload_asset(Path(args.audio), key)
        uploads.append(uploaded)
        return {"audio_asset_id": uploaded["asset_id"]}
    if args.audio_url:
        if not is_url(args.audio_url):
            raise SystemExit("--audio-url must be http(s)")
        return {"audio_url": args.audio_url}
    return {"audio_asset_id": args.audio_asset_id}


def build_background(args: argparse.Namespace) -> dict | None:
    if args.background_color:
        return {"type": "color", "value": args.background_color}
    if args.background_image_url:
        return {"type": "image", "image": {"type": "url", "url": args.background_image_url}}
    return None


def submit(args: argparse.Namespace, key: str) -> dict:
    uploads: list[dict] = []
    payload: dict = {
        "type": "image",
        "image": build_image(args, key, uploads),
        "title": args.title,
        "resolution": args.resolution,
        "aspect_ratio": args.aspect_ratio,
    }
    payload.update(build_audio(args, key, uploads))
    if args.remove_background:
        payload["remove_background"] = True
    background = build_background(args)
    if background:
        payload["background"] = background
    if args.callback_url:
        payload["callback_url"] = args.callback_url
    if args.callback_id:
        payload["callback_id"] = args.callback_id

    response = request_json("POST", f"{API_BASE}/v3/videos", key, payload)
    data = response.get("data") or {}
    video_id = data.get("video_id")
    if not video_id:
        raise SystemExit(f"HeyGen create response missing data.video_id: {json.dumps(response, ensure_ascii=False)}")
    return {"video_id": video_id, "request": payload, "uploads": uploads, "createResponse": response}


def get_status(video_id: str, key: str) -> dict:
    return request_json("GET", f"{API_BASE}/v3/videos/{parse.quote(video_id)}", key)


def collect_video_url(payload: dict) -> str | None:
    data = payload.get("data") if isinstance(payload, dict) else None
    if isinstance(data, dict):
        for key in ("video_url", "url", "download_url"):
            value = data.get(key)
            if is_url(value):
                return value
    for key in ("video_url", "url", "download_url"):
        value = payload.get(key) if isinstance(payload, dict) else None
        if is_url(value):
            return value
    return None


def filename_from_url(url: str, fallback: str) -> str:
    suffix = Path(parse.urlparse(url).path).suffix
    suffix = suffix if re.fullmatch(r"\.[A-Za-z0-9]{1,8}", suffix or "") else ".mp4"
    return fallback + suffix


def download_video(url: str, output_dir: Path, video_id: str) -> str:
    output_dir.mkdir(parents=True, exist_ok=True)
    out = output_dir / filename_from_url(url, f"heygen_video_{video_id}")
    req = request.Request(url, headers={"User-Agent": "video-agent-heygen/1.0"})
    with request.urlopen(req, timeout=600) as resp:
        out.write_bytes(resp.read())
    return str(out)


def write_report(output_dir: Path, video_id: str, report: dict) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"heygen_video_{video_id}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def poll_until_done(args: argparse.Namespace, key: str) -> dict:
    deadline = time.time() + args.timeout
    last: dict = {}
    while time.time() < deadline:
        last = get_status(args.video_id, key)
        data = last.get("data") or {}
        status = data.get("status")
        print(json.dumps({"video_id": args.video_id, "status": status}, ensure_ascii=False), flush=True)
        if status in {"completed", "failed"}:
            break
        time.sleep(args.interval)
    data = last.get("data") or {}
    if data.get("status") == "completed" and args.download:
        url = collect_video_url(last)
        if url:
            last["downloaded_file"] = download_video(url, Path(args.output_dir), args.video_id)
            print(json.dumps({"downloaded_file": last["downloaded_file"]}, ensure_ascii=False))
    return last


def command_generate(args: argparse.Namespace) -> None:
    key = api_key(args.env_file)
    created = submit(args, key)
    args.video_id = created["video_id"]
    print(json.dumps({"video_id": args.video_id}, ensure_ascii=False))
    final = poll_until_done(args, key)
    report = dict(created)
    report["finalStatus"] = final
    report_path = write_report(Path(args.output_dir), args.video_id, report)
    print(json.dumps({"report": str(report_path)}, ensure_ascii=False))


def command_status(args: argparse.Namespace) -> None:
    key = api_key(args.env_file)
    final = poll_until_done(args, key)
    report_path = write_report(Path(args.output_dir), args.video_id, {"finalStatus": final})
    print(json.dumps({"report": str(report_path), "status": (final.get("data") or {}).get("status")}, ensure_ascii=False))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="create a HeyGen talking-head image video")
    gen.add_argument("--env-file", default=".env")
    gen.add_argument("--image", help="local image path")
    gen.add_argument("--image-url", help="public image URL")
    gen.add_argument("--image-asset-id", help="existing HeyGen image asset ID")
    gen.add_argument("--audio", help="local audio path")
    gen.add_argument("--audio-url", help="public audio URL")
    gen.add_argument("--audio-asset-id", help="existing HeyGen audio asset ID")
    gen.add_argument("--title", default="HeyGen photo avatar video")
    gen.add_argument("--resolution", default="1080p", choices=["4k", "1080p", "720p"])
    gen.add_argument("--aspect-ratio", default="9:16", choices=["16:9", "9:16"])
    gen.add_argument("--remove-background", action="store_true")
    gen.add_argument("--background-color")
    gen.add_argument("--background-image-url")
    gen.add_argument("--callback-url")
    gen.add_argument("--callback-id")
    gen.add_argument("--output-dir", default=".")
    gen.add_argument("--download", action=argparse.BooleanOptionalAction, default=True)
    gen.add_argument("--interval", type=float, default=10)
    gen.add_argument("--timeout", type=float, default=1800)
    gen.set_defaults(func=command_generate)

    stat = sub.add_parser("status", help="poll an existing HeyGen video")
    stat.add_argument("--env-file", default=".env")
    stat.add_argument("--video-id", required=True)
    stat.add_argument("--output-dir", default=".")
    stat.add_argument("--download", action="store_true")
    stat.add_argument("--interval", type=float, default=10)
    stat.add_argument("--timeout", type=float, default=1800)
    stat.set_defaults(func=command_status)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
