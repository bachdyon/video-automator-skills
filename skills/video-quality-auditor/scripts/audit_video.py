#!/usr/bin/env python3
from __future__ import annotations

import argparse
import math
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import tomllib
except Exception as exc:  # pragma: no cover
    raise SystemExit(f"tomllib unavailable: {exc}")

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from pipeline_utils import write_toml_document  # noqa: E402


SAFE_LEFT = 100
SAFE_TOP = 100
SAFE_RIGHT = 980
SAFE_BOTTOM = 1720


def load_toml(path: Path) -> dict[str, Any]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def ffprobe_duration(video_path: Path) -> float:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(video_path),
    ]
    out = subprocess.check_output(cmd, text=True).strip()
    return float(out)


def estimate_overlay_box(render_plan: dict[str, Any], frame_width: int, frame_height: int) -> dict[str, float]:
    overlay = render_plan.get("text_overlay", {})
    lines = overlay.get("lines", [])
    font_size = float(overlay.get("font_size", 48))
    pad_h = float(overlay.get("padding_horizontal", 10))
    pad_v = float(overlay.get("padding_vertical", 4))
    line_gap = float(overlay.get("line_gap", 0))
    top_percent = float(overlay.get("top_percent", 70))
    right_offset_percent = float(overlay.get("right_offset_percent", 0))

    char_w = font_size * 0.58
    line_ws = [len(str(line)) * char_w + (pad_h * 2) for line in lines]
    width = max(line_ws) if line_ws else 0

    line_h = font_size * 1.12 + (pad_v * 2)
    height = (len(lines) * line_h) + max(0, len(lines) - 1) * line_gap

    center_x = frame_width * 0.5 + (frame_width * right_offset_percent / 100.0)
    x = center_x - width / 2
    y = frame_height * top_percent / 100.0

    return {"x": x, "y": y, "w": width, "h": height}


def build_findings(render_plan: dict[str, Any], box: dict[str, float]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    overlay = render_plan.get("text_overlay", {})
    font_size = float(overlay.get("font_size", 48))
    tilt_deg = float(overlay.get("tilt_deg", 0))
    text_color = str(overlay.get("text_color", "")).upper()
    bg_color = str(overlay.get("background_color", "")).upper()

    if box["x"] < SAFE_LEFT or box["y"] < SAFE_TOP or (box["x"] + box["w"]) > SAFE_RIGHT or (box["y"] + box["h"]) > SAFE_BOTTOM:
        findings.append(
            {
                "id": "SAFE_AREA_VIOLATION",
                "severity": "error",
                "message": "Khối overlay đang vượt ra ngoài vùng safe-area cứng 9:16.",
                "detail": {
                    "overlay_box_px": box,
                    "safe_area_px": {"left": SAFE_LEFT, "top": SAFE_TOP, "right": SAFE_RIGHT, "bottom": SAFE_BOTTOM},
                },
            }
        )

    if font_size < 28:
        findings.append(
            {
                "id": "FONT_TOO_SMALL",
                "severity": "error",
                "message": "Cỡ chữ nhỏ hơn ngưỡng dễ đọc trên mobile.",
                "detail": {"current_font_size": font_size, "recommended_min": 28},
            }
        )
    elif font_size > 72:
        findings.append(
            {
                "id": "FONT_TOO_LARGE",
                "severity": "error",
                "message": "Cỡ chữ lớn quá mức khuyến nghị, dễ gây che khung hình.",
                "detail": {"current_font_size": font_size, "recommended_max": 72},
            }
        )

    if abs(tilt_deg) > 15:
        findings.append(
            {
                "id": "TILT_TOO_HIGH",
                "severity": "warning",
                "message": "Độ nghiêng đang cao, có thể giảm readability.",
                "detail": {"current_tilt_deg": tilt_deg, "recommended_abs_max": 15},
            }
        )

    if not ((text_color == "#FFFFFF" and bg_color == "#000000") or (text_color == "#000000" and bg_color == "#FFFFFF")):
        findings.append(
            {
                "id": "LOW_CONTRAST_RISK",
                "severity": "warning",
                "message": "Màu chữ và nền pill có nguy cơ tương phản thấp.",
                "detail": {"text_color": text_color, "background_color": bg_color},
            }
        )

    if not findings:
        findings.append(
            {
                "id": "NO_ERROR_FOUND",
                "severity": "info",
                "message": "Không phát hiện lỗi mức error trong pass này.",
                "detail": {},
            }
        )
    return findings


def build_batch_fix(render_plan: dict[str, Any], box: dict[str, float], findings: list[dict[str, Any]]) -> dict[str, Any]:
    overlay = render_plan.get("text_overlay", {})
    fixes: dict[str, Any] = {}
    has_error = any(item.get("severity") == "error" for item in findings)
    if not has_error:
        return {"apply": False, "reason": "Không có lỗi mức error.", "changes": fixes}

    font_size = float(overlay.get("font_size", 48))
    top_percent = float(overlay.get("top_percent", 70))
    right_offset_percent = float(overlay.get("right_offset_percent", 0))

    if box["x"] < SAFE_LEFT:
        delta = SAFE_LEFT - box["x"]
        right_offset_percent += (delta / 1080.0) * 100.0
    if (box["x"] + box["w"]) > SAFE_RIGHT:
        delta = (box["x"] + box["w"]) - SAFE_RIGHT
        right_offset_percent -= (delta / 1080.0) * 100.0
    if box["y"] < SAFE_TOP:
        delta = SAFE_TOP - box["y"]
        top_percent += (delta / 1920.0) * 100.0
    if (box["y"] + box["h"]) > SAFE_BOTTOM:
        delta = (box["y"] + box["h"]) - SAFE_BOTTOM
        top_percent -= (delta / 1920.0) * 100.0

    available_w = SAFE_RIGHT - SAFE_LEFT
    if box["w"] > available_w:
        scale = max(0.5, available_w / box["w"])
        font_size = max(28.0, math.floor(font_size * scale))

    if font_size < 28:
        font_size = 28
    if font_size > 72:
        font_size = 72

    fixes["text_overlay.font_size"] = round(font_size, 2)
    fixes["text_overlay.top_percent"] = round(top_percent, 2)
    fixes["text_overlay.right_offset_percent"] = round(right_offset_percent, 2)
    fixes["remotion_props.textTopPercent"] = round(top_percent, 2)
    fixes["remotion_props.textRightOffsetPercent"] = round(right_offset_percent, 2)

    return {"apply": True, "reason": "Áp dụng batch fix để đưa overlay vào safe-area và tối ưu readability.", "changes": fixes}


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit overlay quality for rendered video.")
    parser.add_argument("--job", required=True, help="Path to job directory.")
    parser.add_argument("--pass-index", required=True, type=int, help="Audit pass number (1..3).")
    args = parser.parse_args()

    job_dir = Path(args.job)
    render_plan_path = job_dir / "source" / "render_plan.toml"
    audit_config_path = job_dir / "source" / "audit_config.toml"
    composition_path = job_dir / "remotion" / "src" / "composition.tsx"
    root_path = job_dir / "remotion" / "src" / "Root.tsx"
    output_video = job_dir / "output" / "final_video.mp4"
    if not render_plan_path.exists():
        raise SystemExit(f"missing render plan: {render_plan_path}")
    if not composition_path.exists() or not root_path.exists():
        raise SystemExit("missing remotion source files for code-first audit")

    render_plan = load_toml(render_plan_path)
    audit_config: dict[str, Any] = {}
    if audit_config_path.exists():
        audit_config = load_toml(audit_config_path)

    max_passes = int(audit_config.get("audit", {}).get("max_audit_passes", 3))
    if args.pass_index > max_passes:
        raise SystemExit(f"pass-index vượt quá max_audit_passes ({max_passes})")

    if output_video.exists():
        video_duration = ffprobe_duration(output_video)
    else:
        video_duration = float(render_plan.get("render", {}).get("duration_seconds", 0.0))
    frame_width = int(render_plan.get("render", {}).get("width", 1080))
    frame_height = int(render_plan.get("render", {}).get("height", 1920))
    box = estimate_overlay_box(render_plan, frame_width, frame_height)
    findings = build_findings(render_plan, box)
    batch_fix = build_batch_fix(render_plan, box, findings)

    has_error = any(item.get("severity") == "error" for item in findings)
    pass_status = "needs_fix" if has_error else "pass"

    out_path = job_dir / "logs" / f"audit_pass_{args.pass_index:02d}.toml"
    write_toml_document(
        out_path,
        [
            (
                "metadata",
                {
                    "job_id": job_dir.name,
                    "pass_index": args.pass_index,
                    "max_passes": max_passes,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                    "video_duration_seconds": video_duration,
                    "pass_status": pass_status,
                    "fix_mode": "batch_all_findings",
                    "audit_mode": "code_first",
                },
            ),
            ("findings", findings),
            ("batch_fix", batch_fix),
        ],
    )
    print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
