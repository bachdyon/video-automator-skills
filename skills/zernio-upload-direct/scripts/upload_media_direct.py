#!/usr/bin/env python3
"""Upload a local file to Zernio /v1/media/upload-direct."""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import secrets
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path


API_URL = "https://zernio.com/api/v1/media/upload-direct"
MAX_BYTES = 25 * 1024 * 1024


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def build_multipart(file_path: Path, content_type: str | None) -> tuple[bytes, str]:
    boundary = f"----zernio-upload-{secrets.token_hex(16)}"
    detected = content_type or mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    chunks: list[bytes] = []

    def add(value: str | bytes) -> None:
        chunks.append(value if isinstance(value, bytes) else value.encode("utf-8"))

    add(f"--{boundary}\r\n")
    add(
        'Content-Disposition: form-data; name="file"; '
        f'filename="{file_path.name}"\r\n'
    )
    add(f"Content-Type: {detected}\r\n\r\n")
    add(file_path.read_bytes())
    add("\r\n")

    if content_type:
        add(f"--{boundary}\r\n")
        add('Content-Disposition: form-data; name="contentType"\r\n\r\n')
        add(content_type)
        add("\r\n")

    add(f"--{boundary}--\r\n")
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def ssl_context() -> ssl.SSLContext | None:
    try:
        import certifi  # type: ignore
    except ImportError:
        return None
    return ssl.create_default_context(cafile=certifi.where())


def upload(file_path: Path, api_key: str, content_type: str | None) -> dict:
    size = file_path.stat().st_size
    if size > MAX_BYTES:
        raise ValueError(f"File is {size} bytes; Zernio upload-direct limit is {MAX_BYTES} bytes.")

    body, request_content_type = build_multipart(file_path, content_type)
    request = urllib.request.Request(
        API_URL,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": request_content_type,
            "Accept": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=120, context=ssl_context()) as response:
            response_body = response.read().decode("utf-8")
            data = json.loads(response_body) if response_body else {}
    except urllib.error.HTTPError as exc:
        response_body = exc.read().decode("utf-8", errors="replace")
        try:
            detail = json.loads(response_body)
        except json.JSONDecodeError:
            detail = response_body
        raise RuntimeError(f"Zernio upload failed with HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Zernio upload failed: {exc.reason}") from exc

    return {
        "path": str(file_path),
        "url": data.get("url"),
        "filename": data.get("filename"),
        "contentType": data.get("contentType"),
        "size": data.get("size"),
        "response": data,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Upload a local file to Zernio upload-direct.")
    parser.add_argument("file", help="Local file path to upload")
    parser.add_argument("--env-file", help="Optional .env file to load before reading ZERNIO_API_KEY")
    parser.add_argument("--content-type", help="Optional MIME override, e.g. image/jpeg")
    parser.add_argument("--output", help="Optional path to write JSON output")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    args = parser.parse_args(argv)

    if args.env_file:
        load_env_file(Path(args.env_file))

    api_key = os.environ.get("ZERNIO_API_KEY")
    if not api_key:
        print("Missing ZERNIO_API_KEY. Export it or pass --env-file .env.", file=sys.stderr)
        return 2

    file_path = Path(args.file)
    if not file_path.exists() or not file_path.is_file():
        print(f"File not found: {file_path}", file=sys.stderr)
        return 2

    try:
        result = upload(file_path, api_key, args.content_type)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1

    indent = 2 if args.pretty else None
    output_text = json.dumps(result, ensure_ascii=False, indent=indent)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output_text + "\n", encoding="utf-8")
    print(output_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
