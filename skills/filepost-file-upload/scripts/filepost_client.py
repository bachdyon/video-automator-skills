#!/usr/bin/env python3
"""FilePost API client for list, get, upload, and delete.

Uses Python requests only, matching FilePost's documented examples.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
from pathlib import Path
from typing import Any

import requests


BASE_URL = "https://filepost.dev"


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


def parse_response(response: requests.Response) -> Any:
    if not response.text:
        return {}
    try:
        return response.json()
    except ValueError:
        return {"raw": response.text}


def raise_for_api_error(response: requests.Response) -> None:
    if response.ok:
        return
    detail = parse_response(response)
    raise RuntimeError(f"FilePost HTTP {response.status_code}: {detail}")


def session(api_key: str) -> requests.Session:
    client = requests.Session()
    client.headers.update(
        {
            "X-API-Key": api_key,
            "Accept": "application/json",
        }
    )
    return client


def upload(api_key: str, file_path: Path) -> Any:
    if not file_path.exists() or not file_path.is_file():
        raise RuntimeError(f"File not found: {file_path}")

    content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    with file_path.open("rb") as file_handle:
        response = session(api_key).post(
            f"{BASE_URL}/v1/upload",
            files={"file": (file_path.name, file_handle, content_type)},
            timeout=300,
        )
    raise_for_api_error(response)
    return parse_response(response)


def list_files(api_key: str, page: int, per_page: int) -> Any:
    response = session(api_key).get(
        f"{BASE_URL}/v1/files",
        params={"page": page, "per_page": per_page},
        timeout=60,
    )
    raise_for_api_error(response)
    return parse_response(response)


def get_file(api_key: str, file_id: str) -> Any:
    response = session(api_key).get(f"{BASE_URL}/v1/files/{file_id}", timeout=60)
    raise_for_api_error(response)
    return parse_response(response)


def delete_file(api_key: str, file_id: str) -> Any:
    response = session(api_key).delete(f"{BASE_URL}/v1/files/{file_id}", timeout=60)
    raise_for_api_error(response)
    return parse_response(response)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="FilePost list/get/upload/delete client.")
    parser.add_argument("--env-file", help="Optional .env file to load before reading FILEPOST_API_KEY")
    parser.add_argument("--output", help="Optional path to write JSON response")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    subparsers = parser.add_subparsers(dest="command", required=True)

    upload_parser = subparsers.add_parser("upload", help="Upload a local file")
    upload_parser.add_argument("file", help="Local file path")

    list_parser = subparsers.add_parser("list", help="List uploaded files")
    list_parser.add_argument("--page", type=int, default=1)
    list_parser.add_argument("--per-page", type=int, default=50)

    get_parser = subparsers.add_parser("get", help="Get file details")
    get_parser.add_argument("file_id")

    delete_parser = subparsers.add_parser("delete", help="Delete a file")
    delete_parser.add_argument("file_id")

    args = parser.parse_args(argv)
    if args.env_file:
        load_env_file(Path(args.env_file))

    api_key = os.environ.get("FILEPOST_API_KEY")
    if not api_key:
        print("Missing FILEPOST_API_KEY. Export it or pass --env-file .env.", file=sys.stderr)
        return 2

    try:
        if args.command == "upload":
            data = upload(api_key, Path(args.file))
        elif args.command == "list":
            data = list_files(api_key, args.page, args.per_page)
        elif args.command == "get":
            data = get_file(api_key, args.file_id)
        elif args.command == "delete":
            data = delete_file(api_key, args.file_id)
        else:
            raise RuntimeError(f"Unsupported command: {args.command}")
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1

    output_text = json.dumps(data, ensure_ascii=False, indent=2 if args.pretty else None)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output_text + "\n", encoding="utf-8")
    print(output_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
