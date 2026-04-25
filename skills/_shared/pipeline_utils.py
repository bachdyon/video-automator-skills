#!/usr/bin/env python3
"""Shared helpers for the video-agent skills scripts."""

from __future__ import annotations

import json
import mimetypes
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    tomllib = None


MEDIA_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff"}
MEDIA_VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi"}
MEDIA_AUDIO_EXTENSIONS = {".mp3", ".mp4", ".mpeg", ".mpga", ".m4a", ".wav", ".webm"}


def die(message: str, code: int = 1) -> None:
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(code)


def read_toml(path: str | Path) -> dict[str, Any]:
    if tomllib is None:
        die("Python 3.11+ is required for TOML input via tomllib.")
    with Path(path).open("rb") as f:
        return tomllib.load(f)


def toml_escape(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if value is None:
        return '""'
    if isinstance(value, str):
        if "\n" in value:
            return '"""\n' + value.replace('"""', '\\"\\"\\"') + '\n"""'
        return toml_escape(value)
    if isinstance(value, list):
        if all(not isinstance(item, (dict, list)) for item in value):
            return "[" + ", ".join(toml_value(item) for item in value) + "]"
        return "[" + ", ".join(toml_inline_table(item) for item in value) + "]"
    if isinstance(value, dict):
        return toml_inline_table(value)
    return toml_escape(str(value))


def toml_inline_table(value: dict[str, Any]) -> str:
    parts = [f"{key} = {toml_value(item)}" for key, item in value.items()]
    return "{ " + ", ".join(parts) + " }"


def write_toml_document(path: str | Path, sections: list[tuple[str | None, dict[str, Any] | list[dict[str, Any]]]]) -> None:
    lines: list[str] = []
    for name, value in sections:
        if isinstance(value, list):
            if name is None:
                die("array sections require a name")
            for item in value:
                lines.append(f"[[{name}]]")
                for key, field in item.items():
                    lines.append(f"{key} = {toml_value(field)}")
                lines.append("")
        else:
            if name:
                lines.append(f"[{name}]")
            for key, field in value.items():
                lines.append(f"{key} = {toml_value(field)}")
            lines.append("")
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def load_env_file(path: str | Path) -> dict[str, str]:
    env: dict[str, str] = {}
    env_path = Path(path)
    if not env_path.exists():
        return env
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


def env_value(path: str | Path, *keys: str) -> str:
    env = load_env_file(path)
    for key in keys:
        value = env.get(key)
        if value:
            return value
    return ""


def upsert_env_file(path: str | Path, updates: dict[str, str]) -> None:
    env_path = Path(path)
    existing_lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    seen: set[str] = set()
    output: list[str] = []
    for line in existing_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            output.append(line)
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in updates:
            output.append(f"{key}={updates[key]}")
            seen.add(key)
        else:
            output.append(line)
    for key, value in updates.items():
        if key not in seen:
            output.append(f"{key}={value}")
    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")


def http_json(url: str, *, method: str = "GET", headers: dict[str, str] | None = None, body: Any = None, timeout: int = 60) -> dict[str, Any]:
    data = None
    request_headers = dict(headers or {})
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=data, method=method, headers=request_headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        die(f"{method} {url} failed with HTTP {exc.code}: {detail}")
    except urllib.error.URLError as exc:
        die(f"{method} {url} failed: {exc}")


def download_file(url: str, output_path: str | Path, *, headers: dict[str, str] | None = None, timeout: int = 120) -> Path:
    req = urllib.request.Request(url, headers=headers or {})
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            path.write_bytes(resp.read())
    except urllib.error.URLError as exc:
        die(f"download failed for {url}: {exc}")
    return path


def guess_mime(path: str | Path) -> str:
    return mimetypes.guess_type(str(path))[0] or "application/octet-stream"


def ffprobe(path: str | Path) -> dict[str, Any]:
    if shutil.which("ffprobe") is None:
        return {}
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_format",
        "-show_streams",
        "-of",
        "json",
        str(path),
    ]
    try:
        result = subprocess.run(cmd, check=True, text=True, capture_output=True)
        return json.loads(result.stdout)
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return {}


def media_metadata(path: str | Path) -> dict[str, Any]:
    data = ffprobe(path)
    format_info = data.get("format") or {}
    streams = data.get("streams") or []
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), {})
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), {})
    duration = format_info.get("duration") or video_stream.get("duration") or audio_stream.get("duration") or 0
    try:
        duration_seconds = float(duration)
    except (TypeError, ValueError):
        duration_seconds = 0.0
    fps = 0.0
    rate = video_stream.get("avg_frame_rate") or video_stream.get("r_frame_rate")
    if rate and rate != "0/0" and "/" in rate:
        numerator, denominator = rate.split("/", 1)
        try:
            fps = float(numerator) / float(denominator)
        except (ValueError, ZeroDivisionError):
            fps = 0.0
    return {
        "duration_seconds": round(duration_seconds, 3),
        "width": int(video_stream.get("width") or 0),
        "height": int(video_stream.get("height") or 0),
        "fps": round(fps, 3),
        "video_codec": video_stream.get("codec_name") or "",
        "audio_codec": audio_stream.get("codec_name") or "",
        "has_audio": bool(audio_stream),
        "size_bytes": int(format_info.get("size") or Path(path).stat().st_size if Path(path).exists() else 0),
    }


def tokenize(value: Any) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, list):
        return set().union(*(tokenize(item) for item in value))
    text = str(value).lower()
    return {item for item in re.findall(r"[\wÀ-ỹ]+", text, flags=re.UNICODE) if len(item) > 1}


def now_epoch() -> int:
    return int(time.time())
