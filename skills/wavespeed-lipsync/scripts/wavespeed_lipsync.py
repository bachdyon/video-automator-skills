#!/usr/bin/env python3
"""Create low-cost lipsync videos with WaveSpeedAI InfiniteTalk."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib import error, parse, request


API_BASE = "https://api.wavespeed.ai/api/v3"
MODEL_ENDPOINT = f"{API_BASE}/wavespeed-ai/infinitetalk"
USER_AGENT = "video-agent-wavespeed-lipsync/1.0"


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
    key = load_env(Path(env_file)).get("WAVESPEED_API_KEY")
    if not key:
        raise SystemExit("Missing WAVESPEED_API_KEY in environment or .env")
    return key


def is_url(value: str) -> bool:
    return value.startswith("https://")


def require_https_url(value: str, name: str) -> None:
    if not is_url(value):
        raise SystemExit(f"{name} must be an HTTPS URL. Upload local files first, then pass the URL.")


def request_json(method: str, url: str, key: str, payload: dict | None = None) -> dict:
    headers = {
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    }
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


def submit(args: argparse.Namespace, key: str) -> dict:
    require_https_url(args.image_url, "--image-url")
    require_https_url(args.audio_url, "--audio-url")
    payload: dict = {
        "image": args.image_url,
        "audio": args.audio_url,
        "resolution": args.resolution,
        "seed": args.seed,
    }
    if args.mask_image_url:
        require_https_url(args.mask_image_url, "--mask-image-url")
        payload["mask_image"] = args.mask_image_url
    if args.prompt:
        payload["prompt"] = args.prompt

    response = request_json("POST", MODEL_ENDPOINT, key, payload)
    data = response.get("data") or {}
    task_id = (data.get("id") or "").strip()
    if not task_id:
        raise SystemExit(f"Create response missing data.id: {json.dumps(response, ensure_ascii=False)}")
    return {"taskId": task_id, "createResponse": response, "request": payload}


def status(task_id: str, key: str) -> dict:
    return request_json("GET", f"{API_BASE}/predictions/{parse.quote(task_id)}/result", key)


def filename_from_url(url: str, fallback: str) -> str:
    suffix = Path(parse.urlparse(url).path).suffix
    suffix = suffix if re.fullmatch(r"\.[A-Za-z0-9]{1,8}", suffix or "") else ".mp4"
    return fallback + suffix


def download_outputs(urls: list[str], output_dir: Path, task_id: str) -> list[str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    for index, url in enumerate(dict.fromkeys(urls), start=1):
        out = output_dir / filename_from_url(url, f"wavespeed_lipsync_result_{task_id}_{index}")
        req = request.Request(url, headers={"User-Agent": USER_AGENT})
        with request.urlopen(req, timeout=600) as resp:
            out.write_bytes(resp.read())
        paths.append(str(out))
    return paths


def write_report(output_dir: Path, task_id: str, report: dict) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"wavespeed_lipsync_task_{task_id}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def poll_until_done(args: argparse.Namespace, key: str) -> dict:
    deadline = time.time() + args.timeout
    last: dict = {}
    while time.time() < deadline:
        last = status(args.task_id, key)
        data = last.get("data") or {}
        state = data.get("status")
        print(json.dumps({"taskId": args.task_id, "status": state}, ensure_ascii=False), flush=True)
        if state in {"completed", "failed"}:
            break
        time.sleep(args.interval)

    data = last.get("data") or {}
    if data.get("status") == "completed" and args.download:
        outputs = data.get("outputs") or []
        if not isinstance(outputs, list):
            outputs = [outputs]
        urls = [item for item in outputs if isinstance(item, str) and item.startswith("http")]
        paths = download_outputs(urls, Path(args.output_dir), args.task_id)
        last["downloadedFiles"] = paths
        print(json.dumps({"downloadedFiles": paths}, ensure_ascii=False), flush=True)
    return last


def command_generate(args: argparse.Namespace) -> None:
    key = api_key(args.env_file)
    created = submit(args, key)
    task_id = created["taskId"]
    print(json.dumps({"taskId": task_id}, ensure_ascii=False), flush=True)
    args.task_id = task_id
    final = poll_until_done(args, key)
    report = {**created, "finalStatus": final}
    report_path = write_report(Path(args.output_dir), task_id, report)
    print(json.dumps({"report": str(report_path)}, ensure_ascii=False))


def command_status(args: argparse.Namespace) -> None:
    key = api_key(args.env_file)
    final = poll_until_done(args, key)
    report_path = write_report(Path(args.output_dir), args.task_id, {"finalStatus": final})
    state = (final.get("data") or {}).get("status")
    print(json.dumps({"report": str(report_path), "status": state}, ensure_ascii=False))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="submit an InfiniteTalk lipsync task")
    gen.add_argument("--env-file", default=".env")
    gen.add_argument("--image-url", required=True)
    gen.add_argument("--audio-url", required=True)
    gen.add_argument("--mask-image-url")
    gen.add_argument("--prompt")
    gen.add_argument("--resolution", choices=["480p", "720p"], default="480p")
    gen.add_argument("--seed", type=int, default=-1)
    gen.add_argument("--output-dir", default=".")
    gen.add_argument("--download", action=argparse.BooleanOptionalAction, default=True)
    gen.add_argument("--interval", type=float, default=10)
    gen.add_argument("--timeout", type=float, default=3600)
    gen.set_defaults(func=command_generate)

    stat = sub.add_parser("status", help="query an InfiniteTalk task")
    stat.add_argument("--env-file", default=".env")
    stat.add_argument("--task-id", required=True)
    stat.add_argument("--output-dir", default=".")
    stat.add_argument("--download", action="store_true")
    stat.add_argument("--interval", type=float, default=10)
    stat.add_argument("--timeout", type=float, default=60)
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
