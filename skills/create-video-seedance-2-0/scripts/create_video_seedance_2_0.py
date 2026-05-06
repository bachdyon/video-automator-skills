#!/usr/bin/env python3
"""Create videos with KIE.AI Bytedance Seedance 2.0 Fast."""

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


API_BASE = "https://api.kie.ai"
UPLOAD_BASE = "https://kieai.redpandaai.co"
MODEL = "bytedance/seedance-2-fast"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


def load_env(path: Path) -> dict[str, str]:
    values = dict(os.environ)
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        values.setdefault(key, value)
    return values


def api_key(env_file: str) -> str:
    env = load_env(Path(env_file))
    key = env.get("KIE_API_KEY") or env.get("KIEAI_API_KEY")
    if not key:
        raise SystemExit("Missing KIE_API_KEY in environment or .env")
    return key


def request_json(method: str, url: str, key: str, payload: dict | None = None) -> dict:
    headers = {"Authorization": f"Bearer {key}"}
    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = request.Request(url, data=data, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"HTTP {exc.code} from {url}: {detail}") from exc


def multipart_upload(path: Path, key: str, upload_path: str) -> str:
    if not path.exists():
        raise SystemExit(f"File not found: {path}")
    boundary = f"----seedance-{uuid.uuid4().hex}"
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    parts: list[bytes] = []

    def field(name: str, value: str) -> None:
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        parts.append(value.encode("utf-8"))
        parts.append(b"\r\n")

    field("uploadPath", upload_path)
    field("fileName", path.name)
    parts.append(f"--{boundary}\r\n".encode())
    parts.append(
        (
            f'Content-Disposition: form-data; name="file"; filename="{path.name}"\r\n'
            f"Content-Type: {mime}\r\n\r\n"
        ).encode()
    )
    parts.append(path.read_bytes())
    parts.append(b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    body = b"".join(parts)

    req = request.Request(
        f"{UPLOAD_BASE}/api/file-stream-upload",
        data=body,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"Upload failed for {path}: HTTP {exc.code}: {detail}") from exc

    file_data = data.get("data") or {}
    file_url = file_data.get("fileUrl") or file_data.get("downloadUrl")
    if not file_url:
        raise SystemExit(f"Upload response missing data.fileUrl: {json.dumps(data, ensure_ascii=False)}")
    return file_url


def is_url(value: str) -> bool:
    return value.startswith("http://") or value.startswith("https://")


def split_values(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def resolve_media(value: str | None, key: str, upload_path: str) -> str | None:
    if not value:
        return None
    return value if is_url(value) else multipart_upload(Path(value), key, upload_path)


def resolve_media_list(raw: str | None, key: str, upload_path: str) -> list[str]:
    return [item if is_url(item) else multipart_upload(Path(item), key, upload_path) for item in split_values(raw)]


def validate_modes(input_body: dict) -> None:
    has_first = bool(input_body.get("first_frame_url"))
    has_last = bool(input_body.get("last_frame_url"))
    has_refs = any(input_body.get(name) for name in ("reference_image_urls", "reference_video_urls", "reference_audio_urls"))
    if has_refs and (has_first or has_last):
        raise SystemExit("Invalid mode: do not mix first/last frame fields with reference_*_urls")
    if has_last and not has_first:
        raise SystemExit("Invalid mode: last_frame_url requires first_frame_url")


def submit(args: argparse.Namespace, key: str) -> dict:
    input_body: dict = {
        "prompt": args.prompt,
        "return_last_frame": args.return_last_frame,
        "generate_audio": args.generate_audio,
        "resolution": args.resolution,
        "aspect_ratio": args.aspect_ratio,
        "duration": args.duration,
        "web_search": args.web_search,
    }
    upload_path = args.upload_path
    optional = {
        "first_frame_url": resolve_media(args.first_frame, key, upload_path),
        "last_frame_url": resolve_media(args.last_frame, key, upload_path),
        "reference_image_urls": resolve_media_list(args.reference_images, key, upload_path),
        "reference_video_urls": resolve_media_list(args.reference_videos, key, upload_path),
        "reference_audio_urls": resolve_media_list(args.reference_audios, key, upload_path),
    }
    for name, value in optional.items():
        if value:
            input_body[name] = value
    validate_modes(input_body)

    payload = {"model": MODEL, "input": input_body}
    response = request_json("POST", f"{API_BASE}/api/v1/jobs/createTask", key, payload)
    task_id = ((response.get("data") or {}).get("taskId") or "").strip()
    if not task_id:
        raise SystemExit(f"Create response missing data.taskId: {json.dumps(response, ensure_ascii=False)}")
    return {"taskId": task_id, "createResponse": response, "request": payload}


def status(task_id: str, key: str) -> dict:
    query = parse.urlencode({"taskId": task_id})
    return request_json("GET", f"{API_BASE}/api/v1/jobs/recordInfo?{query}", key)


def parse_result_json(record: dict) -> dict:
    data = record.get("data") or {}
    raw = data.get("resultJson")
    if isinstance(raw, str) and raw:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"raw": raw}
    return raw if isinstance(raw, dict) else {}


def collect_urls(value) -> list[str]:
    urls: list[str] = []
    if isinstance(value, str) and is_url(value):
        urls.append(value)
    elif isinstance(value, list):
        for item in value:
            urls.extend(collect_urls(item))
    elif isinstance(value, dict):
        for item in value.values():
            urls.extend(collect_urls(item))
    return urls


def filename_from_url(url: str, fallback: str) -> str:
    path = parse.urlparse(url).path
    suffix = Path(path).suffix
    suffix = suffix if re.fullmatch(r"\.[A-Za-z0-9]{1,8}", suffix or "") else ".mp4"
    return fallback + suffix


def download_urls(urls: list[str], output_dir: Path, task_id: str) -> list[str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    for index, url in enumerate(dict.fromkeys(urls), start=1):
        out = output_dir / filename_from_url(url, f"seedance_result_{task_id}_{index}")
        req = request.Request(url, headers={"User-Agent": "video-agent-seedance/1.0"})
        with request.urlopen(req, timeout=300) as resp:
            out.write_bytes(resp.read())
        paths.append(str(out))
    return paths


def write_report(output_dir: Path, task_id: str, report: dict) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"seedance_task_{task_id}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def command_generate(args: argparse.Namespace) -> None:
    key = api_key(args.env_file)
    created = submit(args, key)
    task_id = created["taskId"]
    report = dict(created)
    print(json.dumps({"taskId": task_id}, ensure_ascii=False))
    args.task_id = task_id
    final = poll_until_done(args, key)
    report["finalStatus"] = final
    report_path = write_report(Path(args.output_dir), task_id, report)
    print(json.dumps({"report": str(report_path)}, ensure_ascii=False))


def poll_until_done(args: argparse.Namespace, key: str) -> dict:
    deadline = time.time() + args.timeout
    last = {}
    while time.time() < deadline:
        last = status(args.task_id, key)
        data = last.get("data") or {}
        state = data.get("state")
        print(json.dumps({"taskId": args.task_id, "state": state}, ensure_ascii=False), flush=True)
        if state in {"success", "fail"}:
            break
        time.sleep(args.interval)
    data = last.get("data") or {}
    if data.get("state") == "success" and args.download:
        result = parse_result_json(last)
        urls = collect_urls(result)
        paths = download_urls(urls, Path(args.output_dir), args.task_id)
        last["downloadedFiles"] = paths
        print(json.dumps({"downloadedFiles": paths}, ensure_ascii=False))
    return last


def command_status(args: argparse.Namespace) -> None:
    key = api_key(args.env_file)
    result = poll_until_done(args, key)
    report_path = write_report(Path(args.output_dir), args.task_id, {"finalStatus": result})
    print(json.dumps({"report": str(report_path), "state": (result.get("data") or {}).get("state")}, ensure_ascii=False))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="submit a Seedance generation task")
    gen.add_argument("--env-file", default=".env")
    gen.add_argument("--prompt", required=True)
    gen.add_argument("--first-frame")
    gen.add_argument("--last-frame")
    gen.add_argument("--reference-images", help="comma-separated URLs or local image paths")
    gen.add_argument("--reference-videos", help="comma-separated URLs or local video paths")
    gen.add_argument("--reference-audios", help="comma-separated URLs or local audio paths")
    gen.add_argument("--return-last-frame", action="store_true")
    gen.add_argument("--generate-audio", action="store_true")
    gen.add_argument("--web-search", action="store_true")
    gen.add_argument("--resolution", default="720p")
    gen.add_argument("--aspect-ratio", default="9:16")
    gen.add_argument("--duration", type=int, default=15)
    gen.add_argument("--upload-path", default="seedance")
    gen.add_argument("--output-dir", default=".")
    gen.add_argument("--download", action=argparse.BooleanOptionalAction, default=True)
    gen.add_argument("--interval", type=float, default=5)
    gen.add_argument("--timeout", type=float, default=900)
    gen.set_defaults(func=command_generate)

    stat = sub.add_parser("status", help="query a Seedance task")
    stat.add_argument("--env-file", default=".env")
    stat.add_argument("--task-id", required=True)
    stat.add_argument("--output-dir", default=".")
    stat.add_argument("--download", action="store_true")
    stat.add_argument("--interval", type=float, default=5)
    stat.add_argument("--timeout", type=float, default=900)
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
