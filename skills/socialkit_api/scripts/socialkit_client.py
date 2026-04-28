#!/usr/bin/env python3
"""Python client and CLI for SocialKit API.

This script intentionally uses only the Python standard library so the skill can
run in fresh project environments without installing dependencies.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


BASE_URL = "https://api.socialkit.dev"
ENV_KEY = "SOCIALKIT_ACCESS_KEY"


@dataclass(frozen=True)
class Endpoint:
    path: str
    required: tuple[str, ...] = ()
    optional: tuple[str, ...] = ()
    description: str = ""


SUMMARY_OPTIONAL = ("custom_response", "custom_prompt", "cache", "cache_ttl")
CACHE_OPTIONAL = ("cache", "cache_ttl")

ENDPOINTS: dict[str, Endpoint] = {
    "video.summary": Endpoint("/video/summarize", ("url",), SUMMARY_OPTIONAL, "Summarize a direct video file URL"),
    "video.transcript": Endpoint("/video/transcript", ("url",), CACHE_OPTIONAL, "Transcribe a direct video file URL"),
    "youtube.summary": Endpoint("/youtube/summarize", ("url",), SUMMARY_OPTIONAL, "Summarize a YouTube video"),
    "youtube.transcript": Endpoint("/youtube/transcript", ("url",), CACHE_OPTIONAL, "Transcribe a YouTube video"),
    "youtube.stats": Endpoint("/youtube/stats", ("url",), CACHE_OPTIONAL, "Get YouTube video metrics"),
    "youtube.comments": Endpoint("/youtube/comments", ("url",), ("limit", "sortBy"), "Get YouTube comments"),
    "youtube.channel_stats": Endpoint("/youtube/channel-stats", ("url",), CACHE_OPTIONAL, "Get YouTube channel stats"),
    "youtube.search": Endpoint("/youtube/search", ("query",), ("limit",), "Search YouTube videos"),
    "youtube.videos": Endpoint("/youtube/videos", ("url",), ("limit", "cache", "cache_ttl"), "List channel or playlist videos"),
    "youtube.download": Endpoint("/youtube/download", ("url",), ("format", "quality"), "Create a YouTube download URL"),
    "tiktok.summary": Endpoint("/tiktok/summarize", ("url",), SUMMARY_OPTIONAL, "Summarize a TikTok video"),
    "tiktok.transcript": Endpoint("/tiktok/transcript", ("url",), CACHE_OPTIONAL, "Transcribe a TikTok video"),
    "tiktok.stats": Endpoint("/tiktok/stats", ("url",), CACHE_OPTIONAL, "Get TikTok video metrics"),
    "tiktok.comments": Endpoint("/tiktok/comments", ("url",), ("limit",), "Get TikTok comments"),
    "tiktok.channel_stats": Endpoint("/tiktok/channel-stats", ("url",), CACHE_OPTIONAL, "Get TikTok profile stats"),
    "tiktok.search": Endpoint("/tiktok/search", ("query",), ("limit", "cursor", "sortBy", "datePosted", "cache", "cache_ttl"), "Search TikTok videos"),
    "tiktok.hashtag_search": Endpoint("/tiktok/hashtag-search", ("hashtag",), ("limit", "cursor", "cache", "cache_ttl"), "Search TikTok videos by hashtag"),
    "instagram.summary": Endpoint("/instagram/summarize", ("url",), SUMMARY_OPTIONAL, "Summarize an Instagram reel/video"),
    "instagram.transcript": Endpoint("/instagram/transcript", ("url",), CACHE_OPTIONAL, "Transcribe an Instagram reel/video"),
    "instagram.stats": Endpoint("/instagram/stats", ("url",), CACHE_OPTIONAL, "Get Instagram post/reel metrics"),
    "instagram.channel_stats": Endpoint("/instagram/channel-stats", ("url",), CACHE_OPTIONAL, "Get Instagram profile stats"),
    "facebook.summary": Endpoint("/facebook/summarize", ("url",), SUMMARY_OPTIONAL, "Summarize a Facebook video"),
    "facebook.transcript": Endpoint("/facebook/transcript", ("url",), CACHE_OPTIONAL, "Transcribe a Facebook video"),
    "facebook.stats": Endpoint("/facebook/stats", ("url",), CACHE_OPTIONAL, "Get Facebook video metrics"),
    "facebook.channel_stats": Endpoint("/facebook/channel-stats", ("url",), CACHE_OPTIONAL, "Get Facebook profile/page stats"),
}


ALIASES = {
    "video.summarize": "video.summary",
    "youtube.summarize": "youtube.summary",
    "youtube.channel-stats": "youtube.channel_stats",
    "tiktok.summarize": "tiktok.summary",
    "tiktok.channel-stats": "tiktok.channel_stats",
    "tiktok.hashtag-search": "tiktok.hashtag_search",
    "instagram.summarize": "instagram.summary",
    "instagram.channel-stats": "instagram.channel_stats",
    "facebook.summarize": "facebook.summary",
    "facebook.channel-stats": "facebook.channel_stats",
}


class SocialKitError(RuntimeError):
    def __init__(self, message: str, *, status: int | None = None, payload: Any = None) -> None:
        super().__init__(message)
        self.status = status
        self.payload = payload


def load_env_file(path: str | os.PathLike[str]) -> dict[str, str]:
    env_path = Path(path)
    values: dict[str, str] = {}
    if not env_path.exists():
        return values
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values


def parse_value(value: str) -> Any:
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered == "null":
        return None
    try:
        if value and value[0] != "0":
            return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def parse_key_value(items: list[str] | None) -> dict[str, Any]:
    params: dict[str, Any] = {}
    for item in items or []:
        if "=" not in item:
            raise SystemExit(f"Invalid --param value {item!r}; expected key=value")
        key, value = item.split("=", 1)
        key = key.strip()
        if not key:
            raise SystemExit(f"Invalid --param value {item!r}; key is empty")
        params[key] = parse_value(value)
    return params


def parse_json_key_value(items: list[str] | None) -> dict[str, Any]:
    params: dict[str, Any] = {}
    for item in items or []:
        if "=" not in item:
            raise SystemExit(f"Invalid --json-param value {item!r}; expected key=json")
        key, value = item.split("=", 1)
        try:
            params[key.strip()] = json.loads(value)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Invalid JSON for --json-param {key}: {exc}") from exc
    return params


def normalize_operation(operation: str) -> str:
    normalized = operation.strip()
    return ALIASES.get(normalized, normalized)


class SocialKitClient:
    def __init__(self, access_key: str, *, base_url: str = BASE_URL, timeout: float = 120.0) -> None:
        if not access_key:
            raise ValueError(f"{ENV_KEY} is required")
        self.access_key = access_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    @classmethod
    def from_env_file(cls, env_file: str | os.PathLike[str] = ".env", **kwargs: Any) -> "SocialKitClient":
        values = load_env_file(env_file)
        access_key = os.environ.get(ENV_KEY) or values.get(ENV_KEY)
        if not access_key:
            raise ValueError(f"{ENV_KEY} is missing from environment or {env_file}")
        return cls(access_key, **kwargs)

    def request(self, operation: str, *, method: str = "GET", **params: Any) -> dict[str, Any]:
        operation = normalize_operation(operation)
        if operation not in ENDPOINTS:
            valid = ", ".join(sorted(ENDPOINTS))
            raise ValueError(f"Unknown SocialKit operation {operation!r}. Valid operations: {valid}")

        endpoint = ENDPOINTS[operation]
        missing = [name for name in endpoint.required if params.get(name) in (None, "")]
        if missing:
            raise ValueError(f"Missing required parameter(s) for {operation}: {', '.join(missing)}")

        method = method.upper()
        url = f"{self.base_url}{endpoint.path}"
        headers = {
            "accept": "application/json",
            "x-access-key": self.access_key,
        }
        body: bytes | None = None

        clean_params = {k: v for k, v in params.items() if v is not None}
        if method == "GET":
            query = urllib.parse.urlencode(clean_params, doseq=True)
            if query:
                url = f"{url}?{query}"
        elif method == "POST":
            headers["content-type"] = "application/json"
            body = json.dumps(clean_params).encode("utf-8")
        else:
            raise ValueError("method must be GET or POST")

        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                raw = response.read()
                status = response.status
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            payload = _decode_json(raw)
            message = _extract_error_message(payload) or f"SocialKit HTTP {exc.code}"
            raise SocialKitError(message, status=exc.code, payload=payload) from exc
        except urllib.error.URLError as exc:
            raise SocialKitError(f"SocialKit request failed: {exc.reason}") from exc

        payload = _decode_json(raw)
        if not isinstance(payload, dict):
            raise SocialKitError("SocialKit response was not a JSON object", status=status, payload=payload)
        if payload.get("success") is False:
            raise SocialKitError(_extract_error_message(payload) or "SocialKit returned success=false", status=status, payload=payload)
        return payload


def _decode_json(raw: bytes) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise SocialKitError(f"SocialKit returned invalid JSON: {exc}") from exc


def _extract_error_message(payload: Any) -> str | None:
    if isinstance(payload, dict):
        message = payload.get("message") or payload.get("error")
        if isinstance(message, str):
            return message
    return None


def write_json(path: str | os.PathLike[str], payload: Any) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def download_from_result(payload: dict[str, Any], output_path: str | os.PathLike[str], timeout: float = 300.0) -> None:
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        raise SocialKitError("Cannot download: response does not contain data object")
    download_url = data.get("downloadUrl")
    if not isinstance(download_url, str) or not download_url:
        raise SocialKitError("Cannot download: response data does not contain downloadUrl")
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(download_url, headers={"user-agent": "socialkit-api-skill/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        target.write_bytes(response.read())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Call SocialKit APIs from Python")
    parser.add_argument("--env-file", default=".env", help="Path to env file containing SOCIALKIT_ACCESS_KEY")
    parser.add_argument("--access-key", default=None, help="Access key override; avoid using this in shell history")
    parser.add_argument("--base-url", default=BASE_URL)
    parser.add_argument("--timeout", type=float, default=120.0)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("endpoints", help="List supported operation keys")

    call = subparsers.add_parser("call", help="Call a SocialKit operation")
    call.add_argument("operation", help="Operation key, e.g. youtube.transcript")
    call.add_argument("--method", choices=("GET", "POST"), default="GET")
    call.add_argument("--param", action="append", default=[], help="Parameter as key=value; repeatable")
    call.add_argument("--json-param", action="append", default=[], help="JSON parameter as key=<json>; repeatable")
    call.add_argument("--params-json", default=None, help="Path to JSON object with request params")
    call.add_argument("--output", default=None, help="Write response JSON to this file")
    call.add_argument("--download-to", default=None, help="For youtube.download, download response data.downloadUrl to this file")
    return parser


def command_endpoints() -> int:
    for key in sorted(ENDPOINTS):
        endpoint = ENDPOINTS[key]
        required = ", ".join(endpoint.required) or "-"
        optional = ", ".join(endpoint.optional) or "-"
        print(f"{key}\t{endpoint.path}\trequired: {required}\toptional: {optional}\t{endpoint.description}")
    return 0


def command_call(args: argparse.Namespace) -> int:
    params = parse_key_value(args.param)
    params.update(parse_json_key_value(args.json_param))
    if args.params_json:
        file_params = json.loads(Path(args.params_json).read_text(encoding="utf-8"))
        if not isinstance(file_params, dict):
            raise SystemExit("--params-json must point to a JSON object")
        params.update(file_params)

    access_key = args.access_key
    if not access_key:
        env_values = load_env_file(args.env_file)
        access_key = os.environ.get(ENV_KEY) or env_values.get(ENV_KEY)
    if not access_key:
        raise SystemExit(f"{ENV_KEY} is missing from environment or {args.env_file}")

    client = SocialKitClient(access_key, base_url=args.base_url, timeout=args.timeout)
    payload = client.request(args.operation, method=args.method, **params)

    if args.output:
        write_json(args.output, payload)
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))

    if args.download_to:
        download_from_result(payload, args.download_to)
        print(f"Downloaded file to {args.download_to}", file=sys.stderr)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "endpoints":
            return command_endpoints()
        if args.command == "call":
            return command_call(args)
    except SocialKitError as exc:
        status = f" HTTP {exc.status}" if exc.status else ""
        print(f"SocialKit error{status}: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
