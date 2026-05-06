#!/usr/bin/env python3
"""Create or edit images with KIE.AI GPT Image 2."""

from __future__ import annotations

import argparse
import base64
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
TEXT_MODEL = "gpt-image-2-text-to-image"
IMAGE_MODEL = "gpt-image-2-image-to-image"
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
        values.setdefault(key.strip(), value.strip().strip('"').strip("'"))
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
    boundary = f"----gpt-image-2-{uuid.uuid4().hex}"
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

    req = request.Request(
        f"{UPLOAD_BASE}/api/file-stream-upload",
        data=b"".join(parts),
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
        if exc.code == 403:
            return base64_upload(path, key, upload_path)
        raise SystemExit(f"Upload failed for {path}: HTTP {exc.code}: {detail}") from exc
    file_data = data.get("data") or {}
    file_url = file_data.get("fileUrl") or file_data.get("downloadUrl")
    if not file_url:
        raise SystemExit(f"Upload response missing data.fileUrl: {json.dumps(data, ensure_ascii=False)}")
    return file_url


def base64_upload(path: Path, key: str, upload_path: str) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    payload = {
        "base64Data": f"data:{mime};base64,{encoded}",
        "uploadPath": upload_path,
        "fileName": path.name,
    }
    req = request.Request(
        f"{UPLOAD_BASE}/api/file-base64-upload",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
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
        raise SystemExit(f"Base64 upload failed for {path}: HTTP {exc.code}: {detail}") from exc
    file_data = data.get("data") or {}
    file_url = file_data.get("fileUrl") or file_data.get("downloadUrl")
    if not file_url:
        raise SystemExit(f"Base64 upload response missing file URL: {json.dumps(data, ensure_ascii=False)}")
    return file_url


def is_url(value: str) -> bool:
    return value.startswith("http://") or value.startswith("https://")


def split_values(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def resolve_images(raw: str | None, key: str, upload_path: str) -> list[str]:
    urls: list[str] = []
    for item in split_values(raw):
        urls.append(item if is_url(item) else multipart_upload(Path(item), key, upload_path))
    return urls


def submit(args: argparse.Namespace, key: str) -> dict:
    input_urls = resolve_images(args.input_images, key, args.upload_path)
    model = IMAGE_MODEL if input_urls else TEXT_MODEL
    input_body: dict = {
        "prompt": args.prompt,
        "aspect_ratio": args.aspect_ratio,
    }
    if input_urls:
        input_body["input_urls"] = input_urls

    payload = {"model": model, "input": input_body}
    response = request_json("POST", f"{API_BASE}/api/v1/jobs/createTask", key, payload)
    task_id = ((response.get("data") or {}).get("taskId") or "").strip()
    if not task_id:
        raise SystemExit(f"Create response missing data.taskId: {json.dumps(response, ensure_ascii=False)}")
    return {"taskId": task_id, "model": model, "createResponse": response, "request": payload}


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
    suffix = suffix if re.fullmatch(r"\.[A-Za-z0-9]{1,8}", suffix or "") else ".png"
    return fallback + suffix


def download_urls(urls: list[str], output_dir: Path, task_id: str) -> list[str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    for index, url in enumerate(dict.fromkeys(urls), start=1):
        out = output_dir / filename_from_url(url, f"gpt_image_2_result_{task_id}_{index}")
        req = request.Request(url, headers={"User-Agent": "video-agent-gpt-image-2/1.0"})
        with request.urlopen(req, timeout=300) as resp:
            out.write_bytes(resp.read())
        paths.append(str(out))
    return paths


def write_report(output_dir: Path, task_id: str, report: dict) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"gpt_image_2_task_{task_id}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


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
        urls = collect_urls(parse_result_json(last))
        paths = download_urls(urls, Path(args.output_dir), args.task_id)
        last["downloadedFiles"] = paths
        print(json.dumps({"downloadedFiles": paths}, ensure_ascii=False))
    return last


def command_generate(args: argparse.Namespace) -> None:
    key = api_key(args.env_file)
    created = submit(args, key)
    task_id = created["taskId"]
    report = dict(created)
    print(json.dumps({"taskId": task_id, "model": created["model"]}, ensure_ascii=False))
    args.task_id = task_id
    report["finalStatus"] = poll_until_done(args, key)
    report_path = write_report(Path(args.output_dir), task_id, report)
    print(json.dumps({"report": str(report_path)}, ensure_ascii=False))


def command_status(args: argparse.Namespace) -> None:
    key = api_key(args.env_file)
    result = poll_until_done(args, key)
    report_path = write_report(Path(args.output_dir), args.task_id, {"finalStatus": result})
    print(json.dumps({"report": str(report_path), "state": (result.get("data") or {}).get("state")}, ensure_ascii=False))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="submit a GPT Image 2 task")
    gen.add_argument("--env-file", default=".env")
    gen.add_argument("--prompt", required=True)
    gen.add_argument("--input-images", help="comma-separated URLs or local image paths")
    gen.add_argument("--aspect-ratio", default="auto")
    gen.add_argument("--upload-path", default="gpt-image-2")
    gen.add_argument("--output-dir", default=".")
    gen.add_argument("--download", action=argparse.BooleanOptionalAction, default=True)
    gen.add_argument("--interval", type=float, default=5)
    gen.add_argument("--timeout", type=float, default=900)
    gen.set_defaults(func=command_generate)

    stat = sub.add_parser("status", help="query a GPT Image 2 task")
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
