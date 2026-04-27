#!/usr/bin/env python3
"""Enrich an asset_semantics.toml scaffold with Gemini Vision per-scene analysis.

Reads the TOML produced by `probe_assets.py`, sends each asset's sample frames
plus its scene list to Gemini, and writes a new TOML where every asset and
scene has unique semantic content. Designed for the `asset-semantic-extractor`
skill's required vision pass.

The script never falls back to per-asset bulk text and never asciifies output.
If Gemini fails for an asset, the script aborts with a non-zero exit code so
downstream stages cannot consume a placeholder index.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from pipeline_utils import die, env_value, read_toml, write_toml_document

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
)

DEFAULT_MODEL = "gemini-3-flash-preview"
DEFAULT_FALLBACKS = ["gemini-2.5-pro", "gemini-2.5-flash"]

PROMPT_TEMPLATE = """Bạn là chuyên gia phân tích footage cho video vlog short-form (TikTok/Reels) tiếng Việt.

Bạn được cho {n_frames} sample frame trích từ một clip nguồn. Các frame được lấy lần lượt ở các mốc thời gian: {frame_timestamps}.

Thông tin clip:
- file_path: {file_path}
- type: {asset_type}
- duration_seconds: {duration_seconds}
- resolution: {width}x{height}
- fps: {fps}
- has_audio: {has_audio}

Danh sách scene (đã được chia sẵn theo cửa sổ thời gian, không thay đổi id, start, end):
{scenes_json}

Yêu cầu output (CHỈ trả về 1 JSON object hợp lệ, không markdown, không text khác):

{{
  "asset_summary": "1 câu tóm tắt nội dung chính cả clip, tiếng Việt CÓ DẤU.",
  "asset_visual_style": "VD: handheld, ánh sáng tự nhiên, tông ấm, cinematic vlog...",
  "asset_mood": ["1-3 mood lowercase, vd: vat-va, chan-thuc, mo-hoi"],
  "asset_tags": ["3-7 tag lowercase, dạng kebab-case, vd: cong-truong, lao-dong, gia-dinh"],
  "privacy_notes": ["nêu rõ nếu có khuôn mặt rõ, biển số, tên riêng nhìn thấy được; rỗng nếu không"],
  "quality_notes": ["nêu vấn đề kỹ thuật rõ ràng: rung, mờ, thiếu sáng, gió ồn audio, ...; rỗng nếu OK"],
  "scenes": [
    {{
      "id": "<giữ nguyên scene id từ input>",
      "description": "Mô tả thị giác CỤ THỂ cho scene này, tiếng Việt CÓ DẤU. Phải khác mọi scene khác trong cùng clip. Bắt đầu bằng quan sát thực tế, sau đó mới diễn giải.",
      "subjects": ["danh từ ngắn quan sát được trong scene"],
      "actions": ["động từ/cụm động từ ngắn cho hành động trong scene"],
      "environment": "địa điểm/khung cảnh ngắn",
      "shot_type": "VD: wide shot, medium shot, close-up, OTS, low angle...",
      "camera_motion": "VD: handheld static, slow pan, push-in, drift, locked...",
      "composition": "VD: subject centered, rule-of-thirds, leading lines...",
      "colors": ["2-4 màu chủ đạo, tiếng Việt hoặc tiếng Anh ngắn"],
      "mood": ["1-3 mood lowercase kebab-case"],
      "semantic_tags": ["3-6 tag lowercase kebab-case mô tả vai trò ngữ nghĩa, vd: hook, lao-dong, ket-thuc, b-roll-cong-truong"],
      "recommended_uses": ["1-3 vai trò narrative phù hợp, vd: hook, hardship-beat, payoff, CTA"],
      "avoid_uses": ["1-3 vai trò KHÔNG phù hợp, vd: high-energy-cut, intro-tinh-cam"]
    }}
  ]
}}

Quy tắc bắt buộc:
- Trả về JSON HỢP LỆ duy nhất. Không kèm ```json hay text giải thích.
- Mọi scene phải có description KHÁC NHAU. Cấm copy-paste cùng một câu cho nhiều scene.
- Tiếng Việt phải có dấu. Cấm asciify (vd KHÔNG được viết "cong truong" thay cho "công trường" trong description).
- Tags lowercase, kebab-case, không khoảng trắng.
- Nếu không chắc một field, để string rỗng "" hoặc list rỗng [], KHÔNG bịa.
- Số scene trong output phải khớp số scene trong input và đúng id.
"""


def encode_image_b64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


def http_post_json(url: str, body: dict[str, Any], timeout: int) -> dict[str, Any]:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else {}


def call_gemini(model: str, api_key: str, parts: list[dict[str, Any]], timeout: int) -> dict[str, Any]:
    body = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.4,
            "topP": 0.9,
            "maxOutputTokens": 8192,
        },
    }
    url = GEMINI_URL.format(model=model, key=api_key)
    return http_post_json(url, body, timeout=timeout)


def extract_text(response: dict[str, Any]) -> str:
    for candidate in response.get("candidates") or []:
        content = candidate.get("content") or {}
        for part in content.get("parts") or []:
            text = part.get("text")
            if text:
                return text
    return ""


def parse_json_strict(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def call_with_model_fallback(
    models: list[str],
    api_key: str,
    parts: list[dict[str, Any]],
    timeout: int,
) -> tuple[dict[str, Any], str]:
    errors: list[str] = []
    for model in models:
        try:
            print(f"[gemini] model={model} parts={len(parts)} ...", flush=True)
            response = call_gemini(model, api_key, parts, timeout=timeout)
            text = extract_text(response)
            if not text:
                errors.append(f"{model}: empty response")
                continue
            data = parse_json_strict(text)
            print(f"[gemini] model={model} ok", flush=True)
            return data, model
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            errors.append(f"{model}: HTTP {exc.code} {detail[:240]}")
        except urllib.error.URLError as exc:
            errors.append(f"{model}: URL {exc}")
        except json.JSONDecodeError as exc:
            errors.append(f"{model}: invalid JSON ({exc})")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{model}: {exc}")
        print(f"[warn] {errors[-1]}", file=sys.stderr, flush=True)
    die("all gemini models failed: " + " | ".join(errors))


def collect_sample_frames(asset: dict[str, Any], scenes: list[dict[str, Any]], sample_dir: Path) -> list[Path]:
    seen: list[Path] = []
    for scene in scenes:
        for raw in scene.get("sample_frames") or []:
            if not raw:
                continue
            path = Path(raw)
            if path.exists() and path not in seen:
                seen.append(path)
    if not seen and sample_dir.exists():
        stem = Path(asset.get("file_path") or "").stem
        if stem:
            for path in sorted(sample_dir.glob(f"{stem}_sample_*.jpg")):
                if path not in seen:
                    seen.append(path)
    return seen


def estimate_frame_timestamps(duration: float, count: int) -> list[float]:
    if count <= 0 or duration <= 0:
        return []
    return [round(min(duration - 0.1, duration * (i + 1) / (count + 1)), 2) for i in range(count)]


def build_prompt(
    asset: dict[str, Any],
    scenes: list[dict[str, Any]],
    frame_timestamps: list[float],
) -> str:
    duration = float(asset.get("duration_seconds") or 0.0)
    scene_summary = [
        {
            "id": scene.get("id"),
            "start": float(scene.get("start") or 0.0),
            "end": float(scene.get("end") or duration),
        }
        for scene in scenes
    ]
    return PROMPT_TEMPLATE.format(
        n_frames=len(frame_timestamps),
        frame_timestamps=", ".join(f"{t:.2f}s" for t in frame_timestamps) or "n/a",
        file_path=asset.get("file_path") or "",
        asset_type=asset.get("type") or "video",
        duration_seconds=duration,
        width=int(asset.get("width") or 0),
        height=int(asset.get("height") or 0),
        fps=float(asset.get("fps") or 0.0),
        has_audio=bool(asset.get("has_audio")),
        scenes_json=json.dumps(scene_summary, ensure_ascii=False, indent=2),
    )


def merge_asset(asset: dict[str, Any], gemini: dict[str, Any]) -> dict[str, Any]:
    asset["summary"] = (gemini.get("asset_summary") or asset.get("summary") or "").strip()
    asset["visual_style"] = (gemini.get("asset_visual_style") or asset.get("visual_style") or "").strip()
    asset["mood"] = list(gemini.get("asset_mood") or asset.get("mood") or [])
    asset["tags"] = list(gemini.get("asset_tags") or asset.get("tags") or [])
    asset["privacy_notes"] = list(gemini.get("privacy_notes") or asset.get("privacy_notes") or [])
    asset["quality_notes"] = list(gemini.get("quality_notes") or asset.get("quality_notes") or [])
    return asset


def merge_scenes(scenes: list[dict[str, Any]], gemini_scenes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {scene.get("id"): scene for scene in gemini_scenes}
    merged: list[dict[str, Any]] = []
    for scene in scenes:
        update = by_id.get(scene.get("id")) or {}
        merged_scene = dict(scene)
        merged_scene["description"] = (update.get("description") or "").strip()
        merged_scene["subjects"] = list(update.get("subjects") or [])
        merged_scene["actions"] = list(update.get("actions") or [])
        merged_scene["environment"] = (update.get("environment") or "").strip()
        merged_scene["shot_type"] = (update.get("shot_type") or "").strip()
        merged_scene["camera_motion"] = (update.get("camera_motion") or "").strip()
        merged_scene["composition"] = (update.get("composition") or "").strip()
        merged_scene["colors"] = list(update.get("colors") or [])
        merged_scene["mood"] = list(update.get("mood") or [])
        merged_scene["semantic_tags"] = list(update.get("semantic_tags") or [])
        merged_scene["recommended_uses"] = list(update.get("recommended_uses") or [])
        merged_scene["avoid_uses"] = list(update.get("avoid_uses") or [])
        merged.append(merged_scene)
    return merged


def quality_gate(asset: dict[str, Any], scenes: list[dict[str, Any]]) -> list[str]:
    issues: list[str] = []
    descriptions: list[str] = []
    for scene in scenes:
        desc = (scene.get("description") or "").strip()
        if not desc:
            issues.append(f"{scene.get('id')}: description rỗng")
            continue
        if "TODO:" in desc:
            issues.append(f"{scene.get('id')}: description còn chứa 'TODO:'")
        descriptions.append(desc)
    if len(descriptions) != len(set(descriptions)):
        issues.append(f"asset {asset.get('id')}: có scene description trùng nhau")
    for tag_field in ("tags", "mood"):
        for value in asset.get(tag_field) or []:
            if value != value.lower() or " " in value:
                issues.append(f"asset {asset.get('id')}.{tag_field} '{value}' phải lowercase, không khoảng trắng")
    for scene in scenes:
        for tag in scene.get("semantic_tags") or []:
            if tag != tag.lower() or " " in tag:
                issues.append(f"{scene.get('id')}.semantic_tags '{tag}' phải lowercase, không khoảng trắng")
    return issues


def run(args: argparse.Namespace) -> None:
    api_key = env_value(args.env_file, "GEMINI_API_KEY")
    if not api_key:
        die("GEMINI_API_KEY missing in .env. Add it then re-run.")

    data = read_toml(args.input)
    assets = list(data.get("assets") or [])
    flat_scenes = list(data.get("asset_scenes") or [])
    if not assets:
        die(f"no [[assets]] in {args.input}")
    if not flat_scenes:
        die(f"no [[asset_scenes]] in {args.input}")

    grouped: dict[str, list[dict[str, Any]]] = {}
    for scene in flat_scenes:
        scene_id = str(scene.get("id") or "")
        asset_id = scene_id.split("_SC_", 1)[0] if scene_id else ""
        grouped.setdefault(asset_id, []).append(scene)

    sample_dir = args.sample_dir
    models = [args.model] + [m for m in (args.fallback_models or "").split(",") if m.strip() and m.strip() != args.model]

    enriched_assets: list[dict[str, Any]] = []
    enriched_scenes: list[dict[str, Any]] = []
    aggregate_issues: list[str] = []

    for asset in assets:
        asset_id = asset.get("id") or ""
        scenes = grouped.get(asset_id, [])
        if not scenes:
            print(f"[warn] asset {asset_id} has no scenes, skipping", file=sys.stderr)
            enriched_assets.append(asset)
            continue
        frame_paths = collect_sample_frames(asset, scenes, sample_dir)
        if not frame_paths:
            die(f"no sample frames found for {asset_id}; run probe_assets.py with --sample-frames first")
        timestamps = estimate_frame_timestamps(float(asset.get("duration_seconds") or 0.0), len(frame_paths))
        prompt_text = build_prompt(asset, scenes, timestamps)
        parts: list[dict[str, Any]] = [{"text": prompt_text}]
        for path in frame_paths:
            parts.append(
                {
                    "inline_data": {
                        "mime_type": "image/jpeg",
                        "data": encode_image_b64(path),
                    }
                }
            )
        gemini_data, _ = call_with_model_fallback(models, api_key, parts, timeout=args.timeout_seconds)
        merged_asset = merge_asset(dict(asset), gemini_data)
        merged_scenes = merge_scenes(scenes, gemini_data.get("scenes") or [])
        issues = quality_gate(merged_asset, merged_scenes)
        if issues:
            print(f"[retry] quality issues on {asset_id}; rerunning with stricter prompt", file=sys.stderr)
            retry_parts: list[dict[str, Any]] = [
                {
                    "text": prompt_text
                    + "\n\nLẦN TRƯỚC bạn đã sinh description trùng giữa các scene hoặc còn 'TODO:' / tag không hợp lệ. Lần này BẮT BUỘC mỗi scene description phải khác hẳn nhau, mô tả rõ chi tiết thị giác riêng của scene đó."
                }
            ]
            for path in frame_paths:
                retry_parts.append(
                    {
                        "inline_data": {
                            "mime_type": "image/jpeg",
                            "data": encode_image_b64(path),
                        }
                    }
                )
            gemini_data, _ = call_with_model_fallback(models, api_key, retry_parts, timeout=args.timeout_seconds)
            merged_asset = merge_asset(dict(asset), gemini_data)
            merged_scenes = merge_scenes(scenes, gemini_data.get("scenes") or [])
            issues = quality_gate(merged_asset, merged_scenes)
        if issues and args.strict:
            die("quality gate failed after retry:\n  " + "\n  ".join(issues))
        if issues:
            print("[warn] quality issues:\n  " + "\n  ".join(issues), file=sys.stderr)
            aggregate_issues.extend(issues)
        enriched_assets.append(merged_asset)
        enriched_scenes.extend(merged_scenes)

    sections: list[tuple[str | None, dict[str, Any] | list[dict[str, Any]]]] = [
        ("assets", enriched_assets),
        ("asset_scenes", enriched_scenes),
    ]
    if aggregate_issues:
        sections.append(
            (
                "warnings",
                [{"code": "QUALITY", "message": msg} for msg in aggregate_issues],
            )
        )
    write_toml_document(args.output, sections)
    print(
        f"wrote {args.output} with {len(enriched_assets)} assets, {len(enriched_scenes)} scenes, {len(aggregate_issues)} warnings",
        flush=True,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("source/asset_semantics.toml"))
    parser.add_argument("--output", type=Path, default=Path("source/asset_semantics.toml"))
    parser.add_argument("--sample-dir", type=Path, default=Path("source/asset_samples"))
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--fallback-models", default=",".join(DEFAULT_FALLBACKS))
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--strict", action="store_true", help="fail if quality gate finds issues")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    run(args)


if __name__ == "__main__":
    main()
