#!/usr/bin/env python3
"""Upload local assets to HeyGen and return reusable asset IDs."""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
import uuid
from pathlib import Path
from urllib import error, request


API_BASE = "https://api.heygen.com"
MAX_SIZE_BYTES = 32 * 1024 * 1024
SUPPORTED_EXTENSIONS = {
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


def split_values(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def validate_file(path: Path) -> None:
    if not path.exists():
        raise SystemExit(f"File not found: {path}")
    if not path.is_file():
        raise SystemExit(f"Not a file: {path}")
    if path.stat().st_size > MAX_SIZE_BYTES:
        raise SystemExit(f"File too large for HeyGen 32 MB limit: {path}")
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise SystemExit(f"Unsupported file extension for HeyGen upload: {path.suffix}")


def upload_file(path: Path, key: str) -> dict:
    validate_file(path)
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


def command_upload(args: argparse.Namespace) -> None:
    key = api_key(args.env_file)
    assets = [upload_file(Path(item), key) for item in split_values(args.files)]
    result = {"assets": assets}
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    upload = sub.add_parser("upload", help="upload local files to HeyGen assets")
    upload.add_argument("--env-file", default=".env")
    upload.add_argument("--files", required=True, help="comma-separated local file paths")
    upload.add_argument("--output", help="optional JSON report path")
    upload.set_defaults(func=command_upload)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
