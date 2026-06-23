#!/usr/bin/env python3
"""Convert a local PNG file to SVG through the Convertio API."""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import requests


BASE_URL = "https://api.convertio.co"


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


def raise_for_convertio_error(response: requests.Response, context: str) -> Any:
    data = parse_response(response)
    if response.ok and data.get("status") != "error":
        return data
    detail = data.get("error") if isinstance(data, dict) else data
    raise RuntimeError(f"{context} failed: HTTP {response.status_code}: {detail}")


def get_api_key() -> str | None:
    return os.environ.get("CONVERTIO_API_KEY") or os.environ.get("convertio_api_key")


def start_conversion(client: requests.Session, api_key: str) -> dict[str, Any]:
    response = client.post(
        f"{BASE_URL}/convert",
        json={"apikey": api_key, "input": "upload", "outputformat": "svg"},
        timeout=60,
    )
    data = raise_for_convertio_error(response, "Start conversion")
    conversion_id = data.get("data", {}).get("id")
    if not conversion_id:
        raise RuntimeError(f"Convertio response did not include conversion id: {data}")
    return data


def upload_file(client: requests.Session, conversion_id: str, file_path: Path) -> dict[str, Any]:
    with file_path.open("rb") as file_handle:
        response = client.put(
            f"{BASE_URL}/convert/{conversion_id}/{file_path.name}",
            data=file_handle,
            timeout=300,
        )
    return raise_for_convertio_error(response, "Upload file")


def poll_status(
    client: requests.Session,
    conversion_id: str,
    timeout_seconds: int,
    poll_interval: float,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_data: dict[str, Any] | None = None
    while time.monotonic() < deadline:
        response = client.get(f"{BASE_URL}/convert/{conversion_id}/status", timeout=60)
        data = raise_for_convertio_error(response, "Check conversion status")
        last_data = data
        payload = data.get("data", {})
        step = payload.get("step")
        if step == "finish":
            return data
        if step in {"failed", "error"}:
            raise RuntimeError(f"Convertio conversion failed: {payload}")
        time.sleep(poll_interval)
    raise TimeoutError(f"Timed out waiting for Convertio conversion: {last_data}")


def download_svg(client: requests.Session, conversion_id: str) -> bytes:
    response = client.get(f"{BASE_URL}/convert/{conversion_id}/dl/base64", timeout=120)
    data = raise_for_convertio_error(response, "Download result")
    content = data.get("data", {}).get("content")
    if not content:
        raise RuntimeError(f"Convertio download response did not include content: {data}")
    return base64.b64decode(content)


def delete_conversion(client: requests.Session, conversion_id: str) -> dict[str, Any] | None:
    response = client.delete(f"{BASE_URL}/convert/{conversion_id}", timeout=60)
    if response.status_code == 404:
        return None
    return raise_for_convertio_error(response, "Delete conversion")


def convert_png_to_svg(
    file_path: Path,
    output_path: Path,
    api_key: str,
    timeout_seconds: int,
    poll_interval: float,
    keep_remote: bool,
) -> dict[str, Any]:
    client = requests.Session()
    start = start_conversion(client, api_key)
    conversion_id = start["data"]["id"]
    upload = upload_file(client, conversion_id, file_path)
    status = poll_status(client, conversion_id, timeout_seconds, poll_interval)
    svg_bytes = download_svg(client, conversion_id)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(svg_bytes)

    cleanup = None
    if not keep_remote:
        cleanup = delete_conversion(client, conversion_id)

    return {
        "conversion_id": conversion_id,
        "input": str(file_path),
        "output": str(output_path),
        "output_size": output_path.stat().st_size,
        "minutes": status.get("data", {}).get("minutes"),
        "upload": upload.get("data", {}),
        "status": status.get("data", {}),
        "cleanup": cleanup,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Convert a PNG file to SVG via Convertio.")
    parser.add_argument("input", help="Local PNG file path")
    parser.add_argument("--env-file", help="Optional .env file to load before reading CONVERTIO_API_KEY")
    parser.add_argument("--output", help="Output SVG path. Defaults to input path with .svg suffix")
    parser.add_argument("--metadata-output", help="Optional path to write conversion metadata JSON")
    parser.add_argument("--timeout-seconds", type=int, default=300)
    parser.add_argument("--poll-interval", type=float, default=2.0)
    parser.add_argument("--keep-remote", action="store_true", help="Do not delete the remote conversion after download")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    args = parser.parse_args(argv)

    if args.env_file:
        load_env_file(Path(args.env_file))

    api_key = get_api_key()
    if not api_key:
        print("Missing CONVERTIO_API_KEY. Export it or pass --env-file .env.", file=sys.stderr)
        return 2

    input_path = Path(args.input)
    if not input_path.exists() or not input_path.is_file():
        print(f"File not found: {input_path}", file=sys.stderr)
        return 2
    if input_path.suffix.lower() != ".png":
        print(f"Expected a .png input file: {input_path}", file=sys.stderr)
        return 2

    output_path = Path(args.output) if args.output else input_path.with_suffix(".svg")

    try:
        data = convert_png_to_svg(
            input_path,
            output_path,
            api_key,
            args.timeout_seconds,
            args.poll_interval,
            args.keep_remote,
        )
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1

    output_text = json.dumps(data, ensure_ascii=False, indent=2 if args.pretty else None)
    if args.metadata_output:
        metadata_path = Path(args.metadata_output)
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        metadata_path.write_text(output_text + "\n", encoding="utf-8")
    print(output_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
