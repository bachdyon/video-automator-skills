"""Image analyzer for the asset index.

For a single still image, probe metadata with Pillow then ask Gemini Vision
for a structured JSON description with the same flavour as the video pipeline
(summary, visual_style, tags, mood, etc.) tailored for short-form video reuse.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps

from skills._shared.pipeline_utils import env_value  # type: ignore
from tools.asset_index.embed import build_embed_source
from tools.asset_index.gemini_client import (
    DEFAULT_FALLBACKS,
    DEFAULT_MODEL,
    GeminiError,
    call_gemini_json,
    encode_image_b64,
)

WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_ENV = WORKSPACE_ROOT / ".env"
MAX_PIXELS = 4_000_000  # downscale very large images before sending to Gemini

PROMPT_TEMPLATE = """Bạn là chuyên gia phân tích ảnh tĩnh để tái sử dụng cho video vlog short-form (TikTok/Reels) tiếng Việt.

Bạn được cho 1 ảnh nguồn và metadata sau:
- file_path: {file_path}
- resolution: {width}x{height}
- size_bytes: {size_bytes}
- format: {image_format}

Yêu cầu output (CHỈ trả về 1 JSON object hợp lệ, không markdown, không text khác):

{{
  "summary": "1-2 câu tóm tắt nội dung ảnh, tiếng Việt CÓ DẤU.",
  "visual_style": "VD: tự nhiên, cinematic, flat lay, vintage, đen trắng, chân thực, ấm...",
  "subjects": ["danh từ ngắn quan sát được, vd: cong-nhan, may-xuc, gia-dinh"],
  "actions": ["động từ/cụm động từ ngắn nếu có hành động trong ảnh; rỗng nếu là ảnh tĩnh"],
  "environment": "địa điểm/khung cảnh ngắn",
  "shot_type": "VD: wide, medium, close-up, OTS, low angle, top-down, portrait...",
  "composition": "VD: subject centered, rule-of-thirds, leading lines, symmetric...",
  "colors": ["2-4 màu chủ đạo, tiếng Việt hoặc tiếng Anh ngắn"],
  "mood": ["1-3 mood lowercase kebab-case"],
  "tags": ["3-7 tag lowercase kebab-case mô tả ngữ nghĩa, vd: cong-truong, lao-dong, gia-dinh"],
  "recommended_uses": ["1-3 vai trò narrative phù hợp, vd: hook, b-roll, transition, payoff"],
  "avoid_uses": ["0-3 vai trò KHÔNG phù hợp"],
  "privacy_notes": ["nêu rõ nếu có khuôn mặt rõ, biển số, tên riêng nhìn thấy được; rỗng nếu không"],
  "quality_notes": ["nêu vấn đề kỹ thuật rõ ràng: mờ, thiếu sáng, méo, watermark; rỗng nếu OK"]
}}

Quy tắc bắt buộc:
- Trả về JSON HỢP LỆ duy nhất. Không kèm ```json hay text giải thích.
- Tiếng Việt phải có dấu, không asciify.
- Tags lowercase, kebab-case, không khoảng trắng.
- Nếu không chắc một field, để chuỗi rỗng "" hoặc list rỗng [], KHÔNG bịa.
"""


def probe_image(path: Path) -> dict[str, Any]:
    """Pillow-based metadata probe.

    Reads EXIF orientation so width/height match the displayed image.
    """
    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img)
        width, height = img.size
        image_format = (img.format or path.suffix.lstrip(".")).upper()
        mode = img.mode
    stat = path.stat()
    return {
        "width": width,
        "height": height,
        "image_format": image_format,
        "mode": mode,
        "size_bytes": stat.st_size,
        "mtime": stat.st_mtime,
    }


def _maybe_downscale(path: Path, work_dir: Path) -> tuple[Path, str]:
    """If the image is huge, save a downscaled JPEG copy used for Gemini.

    Returns (path_to_send, mime_type).
    """
    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img)
        if img.width * img.height <= MAX_PIXELS and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
            return path, _mime_for_suffix(path.suffix.lower())
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        scale = (MAX_PIXELS / (img.width * img.height)) ** 0.5 if img.width * img.height > MAX_PIXELS else 1.0
        if scale < 1.0:
            new_size = (max(1, int(img.width * scale)), max(1, int(img.height * scale)))
            img = img.resize(new_size, Image.LANCZOS)
        work_dir.mkdir(parents=True, exist_ok=True)
        out = work_dir / f"{path.stem}_resized.jpg"
        img.save(out, format="JPEG", quality=85, optimize=True)
        return out, "image/jpeg"


def _mime_for_suffix(suffix: str) -> str:
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
        ".bmp": "image/bmp",
        ".tiff": "image/tiff",
    }.get(suffix.lower(), "image/jpeg")


def analyze(
    path: str | Path,
    *,
    env_file: str | Path = DEFAULT_ENV,
    work_dir: Path | None = None,
    model: str = DEFAULT_MODEL,
    fallbacks: tuple[str, ...] = DEFAULT_FALLBACKS,
    timeout: int = 120,
) -> dict[str, Any]:
    """Analyze a single image and return a record dict ready for ``upsert_asset``.

    The record uses the same field names as the ``assets`` table (minus the
    primary keys ``id``/``file_path``/``source_root`` etc, which the router
    fills in). Includes ``embed_source`` for downstream embedding.
    """
    path = Path(path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"image not found: {path}")
    api_key = env_value(Path(env_file), "GEMINI_API_KEY", "GOOGLE_API_KEY")
    if not api_key:
        raise GeminiError("GEMINI_API_KEY missing in .env")

    metadata = probe_image(path)

    work_dir = work_dir or path.parent / ".tmp_resize"
    image_path, mime = _maybe_downscale(path, work_dir)
    try:
        image_b64 = encode_image_b64(image_path)
    finally:
        if image_path != path and image_path.exists():
            try:
                image_path.unlink()
            except OSError:
                pass

    prompt = PROMPT_TEMPLATE.format(
        file_path=str(path),
        width=metadata["width"],
        height=metadata["height"],
        size_bytes=metadata["size_bytes"],
        image_format=metadata["image_format"],
    )
    parts: list[dict[str, Any]] = [
        {"text": prompt},
        {"inline_data": {"mime_type": mime, "data": image_b64}},
    ]

    data, model_used = call_gemini_json(
        api_key,
        parts,
        models=[model, *fallbacks],
        timeout=timeout,
        log_prefix="[image-gemini]",
    )

    summary = (data.get("summary") or "").strip()
    style = (data.get("visual_style") or "").strip()
    tags = list(data.get("tags") or [])
    mood = list(data.get("mood") or [])
    subjects = list(data.get("subjects") or [])
    embed_source = build_embed_source([summary, style, *tags, *mood, *subjects])

    record: dict[str, Any] = {
        "file_name": path.name,
        "media_type": "image",
        "size_bytes": metadata["size_bytes"],
        "mtime": metadata["mtime"],
        "width": metadata["width"],
        "height": metadata["height"],
        "duration_seconds": None,
        "fps": None,
        "has_audio": 0,
        "style": style,
        "summary": summary,
        "transcript": None,
        "audio_role": None,
        "tags_json": tags,
        "mood_json": mood,
        "scenes_json": None,
        "raw_json": data,
        "embed_source": embed_source,
        "embed_model": "text-embedding-3-small",
    }
    record["raw_json"] = json.dumps(
        {"gemini": data, "gemini_model": model_used, "metadata": metadata},
        ensure_ascii=False,
    )
    return record


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Analyze a single image with Gemini Vision")
    parser.add_argument("image", type=Path)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV)
    parser.add_argument("--work-dir", type=Path, default=None)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args(argv)
    try:
        record = analyze(
            args.image,
            env_file=args.env_file,
            work_dir=args.work_dir,
            model=args.model,
            timeout=args.timeout,
        )
    except (FileNotFoundError, GeminiError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    printable = {k: v for k, v in record.items() if k != "raw_json"}
    printable["raw_json_chars"] = len(record["raw_json"] or "")
    print(json.dumps(printable, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(_main())
