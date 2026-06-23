#!/usr/bin/env python3
"""Telegram Bot API sender using environment-backed credentials."""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
from pathlib import Path
from typing import Any

import requests


BASE_URL = "https://api.telegram.org"
MAX_MULTIPART_BYTES = 50 * 1024 * 1024
DEFAULT_ENV_FILE = None


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


def request_url(token: str, method: str) -> str:
    return f"{BASE_URL}/bot{token}/{method}"


def parse_response(response: requests.Response) -> dict[str, Any]:
    try:
        data = response.json()
    except ValueError:
        data = {"ok": False, "description": response.text}
    if not response.ok or not data.get("ok", False):
        description = data.get("description") or response.text
        error_code = data.get("error_code") or response.status_code
        raise RuntimeError(f"Telegram HTTP {error_code}: {description}")
    return data


def api_post_json(token: str, method: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = requests.post(request_url(token, method), json=payload, timeout=60)
    return parse_response(response)


def api_get(token: str, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    response = requests.get(request_url(token, method), params=params or {}, timeout=60)
    return parse_response(response)


def api_post_file(
    token: str,
    method: str,
    payload: dict[str, Any],
    file_field: str,
    file_path: Path,
) -> dict[str, Any]:
    if not file_path.exists() or not file_path.is_file():
        raise RuntimeError(f"File not found: {file_path}")
    size = file_path.stat().st_size
    if size > MAX_MULTIPART_BYTES:
        raise RuntimeError(f"Telegram upload limit exceeded: {size} bytes > {MAX_MULTIPART_BYTES} bytes")
    content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    with file_path.open("rb") as file_handle:
        response = requests.post(
            request_url(token, method),
            data=payload,
            files={file_field: (file_path.name, file_handle, content_type)},
            timeout=600,
        )
    return parse_response(response)


def read_text_arg(text: str | None, text_file: str | None, label: str) -> str | None:
    if text and text_file:
        raise RuntimeError(f"Use either --{label} or --{label}-file, not both")
    if text_file:
        return Path(text_file).read_text(encoding="utf-8").strip()
    return text


def env_value(name: str, args: argparse.Namespace) -> str | None:
    value = os.environ.get(name)
    if value:
        return value
    prefix = getattr(args, "env_prefix", None)
    if prefix:
        return os.environ.get(f"{prefix}_{name}")
    return None


def chat_id(args: argparse.Namespace) -> str:
    value = args.chat_id or env_value("TELEGRAM_CHAT_ID", args)
    if not value:
        raise RuntimeError("Missing chat id. Pass --chat-id or set TELEGRAM_CHAT_ID.")
    return value


def add_common_message_fields(payload: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    if args.parse_mode:
        payload["parse_mode"] = args.parse_mode
    if args.disable_notification:
        payload["disable_notification"] = True
    if args.protect_content:
        payload["protect_content"] = True
    return payload


def extract_file_id(message: dict[str, Any]) -> str | None:
    for key in ("video", "document", "photo"):
        value = message.get(key)
        if isinstance(value, dict):
            return value.get("file_id")
        if isinstance(value, list) and value:
            last = value[-1]
            if isinstance(last, dict):
                return last.get("file_id")
    return None


def compact_result(data: dict[str, Any]) -> dict[str, Any]:
    result = data.get("result")
    if not isinstance(result, dict):
        return data
    chat = result.get("chat") if isinstance(result.get("chat"), dict) else {}
    compact = {
        "ok": True,
        "message_id": result.get("message_id"),
        "chat_id": chat.get("id"),
        "chat_type": chat.get("type"),
    }
    file_id = extract_file_id(result)
    if file_id:
        compact["file_id"] = file_id
    return compact


def command_get_me(token: str, _args: argparse.Namespace) -> dict[str, Any]:
    return api_get(token, "getMe")


def command_updates(token: str, args: argparse.Namespace) -> dict[str, Any]:
    params: dict[str, Any] = {"limit": args.limit}
    if args.offset is not None:
        params["offset"] = args.offset
    return api_get(token, "getUpdates", params)


def command_send_message(token: str, args: argparse.Namespace) -> dict[str, Any]:
    text = read_text_arg(args.text, args.text_file, "text")
    if not text:
        raise RuntimeError("Missing message text. Use --text or --text-file.")
    payload = add_common_message_fields({"chat_id": chat_id(args), "text": text}, args)
    return compact_result(api_post_json(token, "sendMessage", payload))


def command_send_video(token: str, args: argparse.Namespace) -> dict[str, Any]:
    caption = read_text_arg(args.caption, args.caption_file, "caption")
    payload = add_common_message_fields({"chat_id": chat_id(args)}, args)
    if caption:
        payload["caption"] = caption[:1024]
    video = Path(args.video)
    if video.exists():
        return compact_result(api_post_file(token, "sendVideo", payload, "video", video))
    payload["video"] = args.video
    return compact_result(api_post_json(token, "sendVideo", payload))


def command_send_document(token: str, args: argparse.Namespace) -> dict[str, Any]:
    caption = read_text_arg(args.caption, args.caption_file, "caption")
    payload = add_common_message_fields({"chat_id": chat_id(args)}, args)
    if caption:
        payload["caption"] = caption[:1024]
    document = Path(args.document)
    if document.exists():
        return compact_result(api_post_file(token, "sendDocument", payload, "document", document))
    payload["document"] = args.document
    return compact_result(api_post_json(token, "sendDocument", payload))


def command_send_photo(token: str, args: argparse.Namespace) -> dict[str, Any]:
    caption = read_text_arg(args.caption, args.caption_file, "caption")
    payload = add_common_message_fields({"chat_id": chat_id(args)}, args)
    if caption:
        payload["caption"] = caption[:1024]
    photo = Path(args.photo)
    if photo.exists():
        return compact_result(api_post_file(token, "sendPhoto", payload, "photo", photo))
    payload["photo"] = args.photo
    return compact_result(api_post_json(token, "sendPhoto", payload))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--env-file",
        default=DEFAULT_ENV_FILE,
        help="Channel-specific env file to load before reading Telegram env vars, for example .env.<channel>.",
    )
    parser.add_argument(
        "--env-prefix",
        help=(
            "Optional channel env prefix. For example --env-prefix <PREFIX> reads "
            "<PREFIX>_TELEGRAM_BOT_TOKEN and <PREFIX>_TELEGRAM_CHAT_ID."
        ),
    )
    parser.add_argument("--output", help="Optional path to write JSON response")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    parser.add_argument("--chat-id", help="Target chat id or @channel username. Defaults to TELEGRAM_CHAT_ID.")
    parser.add_argument("--parse-mode", choices=["MarkdownV2", "HTML", "Markdown"], help="Telegram parse mode")
    parser.add_argument("--disable-notification", action="store_true")
    parser.add_argument("--protect-content", action="store_true")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("get-me", help="Check bot identity")

    updates = subparsers.add_parser("updates", help="Read recent bot updates to discover chat IDs")
    updates.add_argument("--limit", type=int, default=10)
    updates.add_argument("--offset", type=int)

    message = subparsers.add_parser("send-message", help="Send a text message")
    message.add_argument("--text")
    message.add_argument("--text-file")

    video = subparsers.add_parser("send-video", help="Send a video file, file_id, or URL")
    video.add_argument("video")
    video.add_argument("--caption")
    video.add_argument("--caption-file")

    document = subparsers.add_parser("send-document", help="Send a document file, file_id, or URL")
    document.add_argument("document")
    document.add_argument("--caption")
    document.add_argument("--caption-file")

    photo = subparsers.add_parser("send-photo", help="Send a photo file, file_id, or URL")
    photo.add_argument("photo")
    photo.add_argument("--caption")
    photo.add_argument("--caption-file")

    args = parser.parse_args(argv)
    if args.env_file:
        load_env_file(Path(args.env_file))
    token = env_value("TELEGRAM_BOT_TOKEN", args)
    if not token:
        print(
            "Missing TELEGRAM_BOT_TOKEN. Export it or pass --env-file .env.<channel>.",
            file=sys.stderr,
        )
        return 2

    try:
        if args.command == "get-me":
            data = command_get_me(token, args)
        elif args.command == "updates":
            data = command_updates(token, args)
        elif args.command == "send-message":
            data = command_send_message(token, args)
        elif args.command == "send-video":
            data = command_send_video(token, args)
        elif args.command == "send-document":
            data = command_send_document(token, args)
        elif args.command == "send-photo":
            data = command_send_photo(token, args)
        else:
            raise RuntimeError(f"Unsupported command: {args.command}")
    except Exception as exc:
        print(str(exc).replace(token, "[redacted]"), file=sys.stderr)
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
