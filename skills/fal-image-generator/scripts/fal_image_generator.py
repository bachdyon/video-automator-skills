#!/usr/bin/env python3
"""Generate AI images via fal.ai for the video pipeline.

Default model: fal-ai/nano-banana (Gemini 2.5 Flash Image, supports
multi-reference image input for character lock).

This script intentionally avoids the optional `fal_client` SDK and uses the
public REST queue API via urllib so the skill works with the same dependency
surface as the rest of the project.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from pipeline_utils import (  # noqa: E402
    die,
    download_file,
    env_value,
    http_json,
    load_env_file,
    read_toml,
    write_toml_document,
)


FAL_QUEUE_BASE = "https://queue.fal.run"
FAL_STORAGE_INITIATE = "https://rest.alpha.fal.ai/storage/upload/initiate"
DEFAULT_MODEL = "fal-ai/nano-banana"
POLL_INTERVAL_SECONDS = 2.0
POLL_TIMEOUT_SECONDS = 180.0


def api_key(env_path: Path) -> str:
    key = env_value(env_path, "FAL_API_KEY", "FAL_KEY")
    if not key:
        die("FAL_API_KEY is required in .env (sign up at https://fal.ai)")
    return key


def headers(key: str) -> dict[str, str]:
    return {
        "Authorization": f"Key {key}",
        "accept": "application/json",
    }


def short_hash(value: str, length: int = 8) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:length]


def upload_reference(env_path: Path, file_path: Path) -> str:
    """Upload a local file to fal storage and return its public URL.

    fal storage flow:
    1. POST initiate with {file_name, content_type} -> {upload_url, file_url}
    2. PUT raw bytes to upload_url
    3. Use file_url as image input.
    """
    if not file_path.exists():
        die(f"reference image not found: {file_path}")
    content_type = "image/png"
    suffix = file_path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        content_type = "image/jpeg"
    elif suffix == ".webp":
        content_type = "image/webp"
    elif suffix == ".png":
        content_type = "image/png"
    init = http_json(
        FAL_STORAGE_INITIATE,
        method="POST",
        headers={**headers(api_key(env_path)), "Content-Type": "application/json"},
        body={"file_name": file_path.name, "content_type": content_type},
    )
    upload_url = init.get("upload_url")
    file_url = init.get("file_url")
    if not upload_url or not file_url:
        die(f"fal storage initiate did not return upload/file URL: {init}")
    req = urllib.request.Request(
        upload_url,
        data=file_path.read_bytes(),
        method="PUT",
        headers={"Content-Type": content_type},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            resp.read()
    except urllib.error.HTTPError as exc:
        die(f"fal storage PUT failed: HTTP {exc.code} {exc.read().decode('utf-8', 'replace')}")
    except urllib.error.URLError as exc:
        die(f"fal storage PUT failed: {exc}")
    return file_url


def submit_job(env_path: Path, model: str, payload: dict[str, Any]) -> str:
    url = f"{FAL_QUEUE_BASE}/{model}"
    response = http_json(
        url,
        method="POST",
        headers={**headers(api_key(env_path)), "Content-Type": "application/json"},
        body=payload,
    )
    request_id = response.get("request_id")
    if not request_id:
        die(f"fal queue submit returned no request_id: {response}")
    return request_id


def poll_result(env_path: Path, model: str, request_id: str) -> dict[str, Any]:
    status_url = f"{FAL_QUEUE_BASE}/{model}/requests/{request_id}/status"
    result_url = f"{FAL_QUEUE_BASE}/{model}/requests/{request_id}"
    deadline = time.time() + POLL_TIMEOUT_SECONDS
    while time.time() < deadline:
        status = http_json(status_url, headers=headers(api_key(env_path)))
        state = status.get("status")
        if state == "COMPLETED":
            return http_json(result_url, headers=headers(api_key(env_path)))
        if state in {"FAILED", "ERROR"}:
            die(f"fal job {request_id} failed: {status}")
        time.sleep(POLL_INTERVAL_SECONDS)
    die(f"fal job {request_id} timed out after {POLL_TIMEOUT_SECONDS}s")


def build_payload(
    *,
    model: str,
    prompt: str,
    reference_image_urls: list[str],
    num_images: int,
) -> dict[str, Any]:
    if model.startswith("fal-ai/nano-banana"):
        payload: dict[str, Any] = {
            "prompt": prompt,
            "num_images": num_images,
            "output_format": "png",
        }
        if reference_image_urls:
            payload["image_urls"] = reference_image_urls
        return payload
    if model.startswith("fal-ai/flux"):
        payload = {
            "prompt": prompt,
            "image_size": "portrait_16_9",
            "num_inference_steps": 28,
            "num_images": num_images,
            "enable_safety_checker": True,
        }
        return payload
    return {"prompt": prompt, "num_images": num_images}


def resolve_reference_urls(env_path: Path, refs: list[str]) -> tuple[list[str], list[str]]:
    """Return (local_paths, public_urls). HTTP(S) entries are returned as-is."""
    local_paths: list[str] = []
    urls: list[str] = []
    for ref in refs:
        if ref.startswith("http://") or ref.startswith("https://"):
            urls.append(ref)
            local_paths.append(ref)
        else:
            local = Path(ref)
            urls.append(upload_reference(env_path, local))
            local_paths.append(str(local))
    return local_paths, urls


def collect_prompts_from_args(args: argparse.Namespace) -> list[dict[str, Any]]:
    if args.prompt:
        return [{
            "id": "PROMPT_001",
            "scene_id": args.scene_id or "AD_HOC",
            "prompt": args.prompt,
            "num_images": args.num_images,
            "model": args.model,
            "reference_images": args.reference_images.split(",") if args.reference_images else [],
        }]
    if args.prompts_toml:
        data = read_toml(args.prompts_toml)
        meta = data.get("metadata") or {}
        default_model = meta.get("default_model") or args.model
        global_refs = meta.get("reference_images") or []
        rows = []
        for idx, item in enumerate(data.get("prompts") or [], start=1):
            rows.append({
                "id": item.get("id") or f"PROMPT_{idx:03d}",
                "scene_id": item.get("scene_id") or f"AD_HOC_{idx}",
                "prompt": item.get("prompt") or "",
                "num_images": int(item.get("num_images") or args.num_images),
                "model": item.get("model") or default_model,
                "reference_images": item.get("reference_images") or global_refs,
            })
        return rows
    if args.from_creative_plan:
        return collect_prompts_from_creative_plan(args)
    die("provide one of --prompt / --prompts-toml / --from-creative-plan")


AI_FLAGS = ("ai_generated", "ai_image", "ai-generated", "ai-image")


def is_ai_scene(intent: dict[str, Any]) -> bool:
    requirements = intent.get("asset_requirements") or []
    if not isinstance(requirements, list):
        return False
    joined = " ".join(str(r).lower() for r in requirements)
    return any(flag in joined for flag in AI_FLAGS)


def vds_style_hint(vds_path: str | None) -> str:
    if not vds_path:
        return ""
    path = Path(vds_path)
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    for marker in ("Style DNA", "## 4."):
        idx = text.find(marker)
        if idx != -1:
            chunk = text[idx:idx + 800]
            return " ".join(chunk.split())[:600]
    return ""


def build_prompt_from_intent(intent: dict[str, Any], vds_hint: str) -> str:
    visual = (intent.get("visual_intent") or "").strip()
    mood = (intent.get("mood") or "").strip()
    shots = intent.get("preferred_shot_types") or []
    parts = [visual] if visual else []
    if shots:
        parts.append("shot type: " + ", ".join(str(s) for s in shots))
    if mood:
        parts.append(f"mood: {mood}")
    parts.append("vertical composition, portrait orientation, 9:16, cinematic")
    if vds_hint:
        parts.append("style: " + vds_hint)
    return ". ".join(parts)


def collect_prompts_from_creative_plan(args: argparse.Namespace) -> list[dict[str, Any]]:
    plan = read_toml(args.from_creative_plan)
    intents = plan.get("scene_intents") or []
    vds_hint = vds_style_hint(args.vds_path)
    refs = args.reference_images.split(",") if args.reference_images else []
    rows = []
    for idx, intent in enumerate(intents, start=1):
        if args.all_scenes or is_ai_scene(intent):
            rows.append({
                "id": f"PROMPT_{idx:03d}",
                "scene_id": intent.get("id") or f"SC_{idx:02d}",
                "prompt": build_prompt_from_intent(intent, vds_hint),
                "num_images": args.num_images,
                "model": args.model,
                "reference_images": refs,
            })
    if not rows:
        die("no scene_intents flagged for AI generation; add 'ai_generated' to asset_requirements or pass --all-scenes")
    return rows


def generate(args: argparse.Namespace) -> None:
    env_path = Path(args.env_file)
    rows = collect_prompts_from_args(args)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    cached_refs: dict[str, str] = {}

    report_rows: list[dict[str, Any]] = []
    for row in rows:
        refs = row.get("reference_images") or []
        local_refs: list[str] = []
        ref_urls: list[str] = []
        for ref in refs:
            if ref in cached_refs:
                local_refs.append(ref)
                ref_urls.append(cached_refs[ref])
                continue
            local_paths, urls = resolve_reference_urls(env_path, [ref])
            local_refs.extend(local_paths)
            ref_urls.extend(urls)
            for src, url in zip(local_paths, urls):
                cached_refs[src] = url

        model = row.get("model") or args.model
        payload = build_payload(
            model=model,
            prompt=row["prompt"],
            reference_image_urls=ref_urls,
            num_images=int(row.get("num_images") or 1),
        )
        started = time.time()
        request_id = submit_job(env_path, model, payload)
        result = poll_result(env_path, model, request_id)
        duration = round(time.time() - started, 2)
        seed = result.get("seed") or 0
        images = result.get("images") or []
        if not images:
            die(f"fal returned no images for prompt {row['id']}: {result}")
        scene_slug = str(row["scene_id"]).lower().replace("-", "_")
        for img_idx, image in enumerate(images, start=1):
            url = image.get("url") if isinstance(image, dict) else None
            if not url:
                continue
            digest = short_hash(f"{row['prompt']}|{seed}|{img_idx}")
            output_name = f"{scene_slug}_{img_idx}_{digest}.png"
            output_path = output_dir / output_name
            if output_path.exists():
                if not args.overwrite:
                    print(f"skip existing {output_path}")
                    report_rows.append({
                        "id": row["id"] + (f"_{img_idx}" if len(images) > 1 else ""),
                        "scene_id": row["scene_id"],
                        "prompt": row["prompt"],
                        "model": model,
                        "reference_images": local_refs,
                        "reference_image_urls": ref_urls,
                        "seed": int(seed),
                        "output_path": str(output_path),
                        "output_url": url,
                        "duration_seconds": duration,
                        "status": "skipped_existing",
                    })
                    continue
            download_file(url, output_path)
            report_rows.append({
                "id": row["id"] + (f"_{img_idx}" if len(images) > 1 else ""),
                "scene_id": row["scene_id"],
                "prompt": row["prompt"],
                "model": model,
                "reference_images": local_refs,
                "reference_image_urls": ref_urls,
                "seed": int(seed),
                "output_path": str(output_path),
                "output_url": url,
                "duration_seconds": duration,
                "status": "success",
            })
            print(f"wrote {output_path}")

    if args.report_toml:
        meta = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "default_model": args.model,
            "total_images": len(report_rows),
        }
        write_toml_document(
            args.report_toml,
            [("metadata", meta), ("generations", report_rows)],
        )
        print(f"wrote report {args.report_toml}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", default=".env", help="path to .env file (default: ./.env)")
    sub = parser.add_subparsers(dest="command", required=True)

    generate_p = sub.add_parser("generate", help="generate one or more images via fal.ai")
    generate_p.add_argument("--prompt", help="single prompt (text-to-image)")
    generate_p.add_argument("--prompts-toml", help="TOML file with [[prompts]] entries")
    generate_p.add_argument("--from-creative-plan", help="creative_plan.toml; pulls scenes flagged ai_generated")
    generate_p.add_argument("--all-scenes", action="store_true", help="when reading creative plan, generate for every scene_intent (not only ai_generated ones)")
    generate_p.add_argument("--scene-id", help="optional scene_id label for single --prompt")
    generate_p.add_argument("--reference-images", default="", help="comma-separated paths or URLs to lock character/style")
    generate_p.add_argument("--vds-path", default="", help="optional VDS markdown for style hints")
    generate_p.add_argument("--model", default=DEFAULT_MODEL, help=f"fal model id (default: {DEFAULT_MODEL})")
    generate_p.add_argument("--num-images", type=int, default=1, help="images per prompt (default: 1)")
    generate_p.add_argument("--output-dir", required=True, help="directory under jobs/<id>/input/raw_assets/images/ai_generated/")
    generate_p.add_argument("--report-toml", help="path to write generation report TOML")
    generate_p.add_argument("--overwrite", action="store_true", help="overwrite if output filename already exists")
    generate_p.set_defaults(func=generate)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
