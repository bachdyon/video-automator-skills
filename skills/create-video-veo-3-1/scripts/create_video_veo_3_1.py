#!/usr/bin/env python3
"""Create videos with KIE.AI Google Veo 3.1."""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import ssl
import sys
import time
import uuid
from pathlib import Path
from urllib import error, parse, request


API_BASE = "https://api.kie.ai"
UPLOAD_BASE = "https://kieai.redpandaai.co"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
FINAL_FLAGS = {1, 2, 3}

try:
    import certifi

    SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    SSL_CONTEXT = ssl.create_default_context()


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
        raise SystemExit("Missing KIE_API_KEY or KIEAI_API_KEY in environment or .env")
    return key


def request_json(method: str, url: str, key: str, payload: dict | None = None) -> dict:
    headers = {"Authorization": f"Bearer {key}", "Accept": "application/json"}
    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = request.Request(url, data=data, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=90, context=SSL_CONTEXT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"HTTP {exc.code} from {url}: {detail}") from exc


def multipart_upload(path: Path, key: str, upload_path: str) -> str:
    if not path.exists():
        raise SystemExit(f"File not found: {path}")
    boundary = f"----veo31-{uuid.uuid4().hex}"
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
        with request.urlopen(req, timeout=180, context=SSL_CONTEXT) as resp:
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


def compact(body: dict) -> dict:
    return {key: value for key, value in body.items() if value is not None and value != []}


def infer_generation_type(args: argparse.Namespace, image_urls: list[str]) -> str:
    if args.generation_type:
        return args.generation_type
    if args.first_frame or args.last_frame:
        return "FIRST_AND_LAST_FRAMES_2_VIDEO"
    if image_urls:
        return "REFERENCE_2_VIDEO"
    return "TEXT_2_VIDEO"


def submit_generate(args: argparse.Namespace, key: str) -> dict:
    image_urls: list[str] = []
    first = resolve_media(args.first_frame, key, args.upload_path)
    last = resolve_media(args.last_frame, key, args.upload_path)
    refs = resolve_media_list(args.reference_images, key, args.upload_path)
    if (first or last) and refs:
        raise SystemExit("Invalid mode: do not mix --first-frame/--last-frame with --reference-images")
    if last and not first:
        raise SystemExit("Invalid mode: --last-frame requires --first-frame")
    if first:
        image_urls.append(first)
    if last:
        image_urls.append(last)
    image_urls.extend(refs)
    generation_type = infer_generation_type(args, image_urls)
    duration = args.duration
    if duration is None:
        if generation_type == "FIRST_AND_LAST_FRAMES_2_VIDEO":
            duration = 4
        elif generation_type == "REFERENCE_2_VIDEO":
            duration = 8

    payload = compact(
        {
            "prompt": args.prompt,
            "imageUrls": image_urls,
            "model": args.model,
            "waterMark": args.watermark,
            "callBackUrl": args.callback_url,
            "aspectRatio": args.aspect_ratio,
            "enableFallback": args.enable_fallback,
            "enableTranslation": args.enable_translation,
            "generationType": generation_type,
            "duration": duration,
            "resolution": args.resolution,
        }
    )
    response = request_json("POST", f"{API_BASE}/api/v1/veo/generate", key, payload)
    task_id = ((response.get("data") or {}).get("taskId") or "").strip()
    if not task_id:
        raise SystemExit(f"Generate response missing data.taskId: {json.dumps(response, ensure_ascii=False)}")
    return {"taskId": task_id, "createResponse": response, "request": payload}


def record_info(task_id: str, key: str) -> dict:
    query = parse.urlencode({"taskId": task_id})
    return request_json("GET", f"{API_BASE}/api/v1/veo/record-info?{query}", key)


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


def collect_result_urls(record: dict) -> list[str]:
    data = record.get("data") or {}
    response_data = data.get("response") or {}
    urls: list[str] = []
    for key in ("resultUrls", "originUrls", "fullResultUrls", "resultUrl"):
        urls.extend(collect_urls(response_data.get(key)))
        urls.extend(collect_urls(data.get(key)))
    return list(dict.fromkeys(urls))


def filename_from_url(url: str, fallback: str) -> str:
    path = parse.urlparse(url).path
    suffix = Path(path).suffix
    suffix = suffix if re.fullmatch(r"\.[A-Za-z0-9]{1,8}", suffix or "") else ".mp4"
    return fallback + suffix


def download_urls(urls: list[str], output_dir: Path, base_name: str) -> list[str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    for index, url in enumerate(dict.fromkeys(urls), start=1):
        out = output_dir / filename_from_url(url, f"{base_name}_{index}")
        req = request.Request(url, headers={"User-Agent": "video-agent-veo-3-1/1.0"})
        with request.urlopen(req, timeout=300, context=SSL_CONTEXT) as resp:
            out.write_bytes(resp.read())
        paths.append(str(out))
    return paths


def write_report(output_dir: Path, task_id: str, report: dict, suffix: str = "task") -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"veo_3_1_{suffix}_{task_id}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def success_flag(record: dict) -> int | None:
    value = (record.get("data") or {}).get("successFlag")
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def poll_until_done(args: argparse.Namespace, key: str) -> dict:
    deadline = time.time() + args.timeout
    last: dict = {}
    while time.time() < deadline:
        last = record_info(args.task_id, key)
        data = last.get("data") or {}
        flag = success_flag(last)
        print(
            json.dumps(
                {
                    "taskId": args.task_id,
                    "successFlag": flag,
                    "completeTime": data.get("completeTime"),
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
        if flag in FINAL_FLAGS:
            break
        time.sleep(args.interval)
    if success_flag(last) == 1 and args.download:
        paths = download_urls(collect_result_urls(last), Path(args.output_dir), f"veo_3_1_result_{args.task_id}")
        last["downloadedFiles"] = paths
        print(json.dumps({"downloadedFiles": paths}, ensure_ascii=False))
    return last


def command_generate(args: argparse.Namespace) -> None:
    key = api_key(args.env_file)
    created = submit_generate(args, key)
    task_id = created["taskId"]
    print(json.dumps({"taskId": task_id}, ensure_ascii=False))
    args.task_id = task_id
    final = poll_until_done(args, key)
    report = dict(created)
    report["finalStatus"] = final
    report_path = write_report(Path(args.output_dir), task_id, report)
    print(json.dumps({"report": str(report_path), "successFlag": success_flag(final)}, ensure_ascii=False))


def command_status(args: argparse.Namespace) -> None:
    key = api_key(args.env_file)
    final = poll_until_done(args, key)
    report_path = write_report(Path(args.output_dir), args.task_id, {"finalStatus": final})
    print(json.dumps({"report": str(report_path), "successFlag": success_flag(final)}, ensure_ascii=False))


def submit_extend(args: argparse.Namespace, key: str) -> dict:
    payload = compact(
        {
            "taskId": args.task_id,
            "prompt": args.prompt,
            "seeds": args.seeds,
            "watermark": args.watermark,
            "callBackUrl": args.callback_url,
            "model": args.model,
        }
    )
    response = request_json("POST", f"{API_BASE}/api/v1/veo/extend", key, payload)
    task_id = ((response.get("data") or {}).get("taskId") or args.task_id).strip()
    return {"taskId": task_id, "extendResponse": response, "request": payload}


def command_extend(args: argparse.Namespace) -> None:
    key = api_key(args.env_file)
    created = submit_extend(args, key)
    task_id = created["taskId"]
    print(json.dumps({"taskId": task_id}, ensure_ascii=False))
    args.task_id = task_id
    final = poll_until_done(args, key)
    report = dict(created)
    report["finalStatus"] = final
    report_path = write_report(Path(args.output_dir), task_id, report, suffix="extend")
    print(json.dumps({"report": str(report_path), "successFlag": success_flag(final)}, ensure_ascii=False))


def command_get_1080p(args: argparse.Namespace) -> None:
    key = api_key(args.env_file)
    query = parse.urlencode({"taskId": args.task_id, "index": args.index})
    deadline = time.time() + args.timeout
    response: dict = {}
    url = ""
    while time.time() < deadline:
        response = request_json("GET", f"{API_BASE}/api/v1/veo/get-1080p-video?{query}", key)
        url = (((response.get("data") or {}).get("resultUrl")) or "").strip()
        print(json.dumps({"taskId": args.task_id, "hasResultUrl": bool(url)}, ensure_ascii=False), flush=True)
        if url:
            break
        time.sleep(args.interval)
    paths = download_urls([url], Path(args.output_dir), f"veo_3_1_1080p_{args.task_id}_{args.index}") if url else []
    report = {"request": {"taskId": args.task_id, "index": args.index}, "response": response, "downloadedFiles": paths}
    report_path = write_report(Path(args.output_dir), args.task_id, report, suffix="1080p")
    print(json.dumps({"report": str(report_path), "downloadedFiles": paths}, ensure_ascii=False))


def submit_4k(args: argparse.Namespace, key: str) -> dict:
    payload = compact({"taskId": args.task_id, "index": args.index, "callBackUrl": args.callback_url})
    return {"request": payload, "response": request_json("POST", f"{API_BASE}/api/v1/veo/get-4k-video", key, payload)}


def command_get_4k(args: argparse.Namespace) -> None:
    key = api_key(args.env_file)
    submitted = submit_4k(args, key)
    data = submitted["response"].get("data") or {}
    upgrade_task_id = (data.get("taskId") or args.task_id).strip()
    urls = collect_urls(data.get("resultUrls")) or collect_urls(data.get("resultUrl"))
    final: dict = submitted["response"]
    paths: list[str] = []
    if not urls and upgrade_task_id:
        args.task_id = upgrade_task_id
        final = poll_until_done(args, key)
        urls = collect_result_urls(final)
    if urls and args.download:
        paths = download_urls(urls, Path(args.output_dir), f"veo_3_1_4k_{args.task_id}_{args.index}")
    report = {"request": submitted["request"], "initialResponse": submitted["response"], "finalStatus": final, "downloadedFiles": paths}
    report_path = write_report(Path(args.output_dir), args.task_id, report, suffix="4k")
    print(json.dumps({"report": str(report_path), "downloadedFiles": paths}, ensure_ascii=False))


def add_poll_args(parser: argparse.ArgumentParser, download_default: bool = True) -> None:
    parser.add_argument("--output-dir", default=".")
    parser.add_argument("--download", action=argparse.BooleanOptionalAction, default=download_default)
    parser.add_argument("--interval", type=float, default=10)
    parser.add_argument("--timeout", type=float, default=1200)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="submit a Veo 3.1 generation task")
    gen.add_argument("--env-file", default=".env")
    gen.add_argument("--prompt", required=True)
    gen.add_argument("--first-frame")
    gen.add_argument("--last-frame")
    gen.add_argument("--reference-images", help="comma-separated URLs or local image paths")
    gen.add_argument("--model", default="veo3_fast")
    gen.add_argument("--watermark", default="")
    gen.add_argument("--callback-url", default="playground")
    gen.add_argument("--aspect-ratio", default="9:16")
    gen.add_argument("--generation-type", choices=["TEXT_2_VIDEO", "FIRST_AND_LAST_FRAMES_2_VIDEO", "REFERENCE_2_VIDEO"])
    gen.add_argument("--duration", type=int, choices=[4, 6, 8])
    gen.add_argument("--resolution", default="720p", choices=["720p", "1080p", "4k", "720P", "1080P", "4K"])
    gen.add_argument("--enable-fallback", action=argparse.BooleanOptionalAction, default=None)
    gen.add_argument("--enable-translation", action=argparse.BooleanOptionalAction, default=None)
    gen.add_argument("--upload-path", default="veo_3_1")
    add_poll_args(gen, download_default=True)
    gen.set_defaults(func=command_generate)

    stat = sub.add_parser("status", help="query a Veo 3.1 task")
    stat.add_argument("--env-file", default=".env")
    stat.add_argument("--task-id", required=True)
    add_poll_args(stat, download_default=False)
    stat.set_defaults(func=command_status)

    ext = sub.add_parser("extend", help="extend a successful Veo 3.1 task")
    ext.add_argument("--env-file", default=".env")
    ext.add_argument("--task-id", required=True)
    ext.add_argument("--prompt", required=True)
    ext.add_argument("--model", default="fast")
    ext.add_argument("--seeds")
    ext.add_argument("--watermark")
    ext.add_argument("--callback-url")
    add_poll_args(ext, download_default=True)
    ext.set_defaults(func=command_extend)

    up1080 = sub.add_parser("get-1080p", help="request/download a 1080p result")
    up1080.add_argument("--env-file", default=".env")
    up1080.add_argument("--task-id", required=True)
    up1080.add_argument("--index", type=int, default=0)
    up1080.add_argument("--output-dir", default=".")
    up1080.add_argument("--interval", type=float, default=20)
    up1080.add_argument("--timeout", type=float, default=600)
    up1080.set_defaults(func=command_get_1080p)

    up4k = sub.add_parser("get-4k", help="request/download a 4K result")
    up4k.add_argument("--env-file", default=".env")
    up4k.add_argument("--task-id", required=True)
    up4k.add_argument("--index", type=int, default=0)
    up4k.add_argument("--callback-url")
    add_poll_args(up4k, download_default=True)
    up4k.set_defaults(func=command_get_4k)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
