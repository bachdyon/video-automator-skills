#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

try:
    import tomllib
except Exception as exc:  # pragma: no cover
    raise SystemExit(f"tomllib unavailable: {exc}")


def read_toml(path: Path) -> dict[str, Any]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def flatten_changes(changes: dict[str, Any]) -> dict[str, Any]:
    flat: dict[str, Any] = {}
    for key, value in changes.items():
        if isinstance(value, dict):
            for sub_key, sub_value in value.items():
                flat[f"{key}.{sub_key}"] = sub_value
        else:
            flat[key] = value
    return flat


def replace_or_fail(content: str, pattern: str, replacement: str) -> str:
    updated, count = re.subn(pattern, replacement, content, flags=re.MULTILINE)
    if count == 0:
        raise SystemExit(f"không tìm thấy pattern để cập nhật: {pattern}")
    return updated


def update_render_plan(path: Path, changes: dict[str, Any]) -> None:
    content = path.read_text(encoding="utf-8")
    mapping = {
        "text_overlay.font_size": (r"^font_size = .*$", "font_size"),
        "text_overlay.top_percent": (r"^top_percent = .*$", "top_percent"),
        "text_overlay.right_offset_percent": (r"^right_offset_percent = .*$", "right_offset_percent"),
        "remotion_props.textTopPercent": (r"^textTopPercent = .*$", "textTopPercent"),
        "remotion_props.textRightOffsetPercent": (r"^textRightOffsetPercent = .*$", "textRightOffsetPercent"),
    }
    for key, value in changes.items():
        item = mapping.get(key)
        if not item:
            continue
        pattern, toml_key = item
        content = replace_or_fail(content, pattern, f"{toml_key} = {value}")
    path.write_text(content, encoding="utf-8")


def update_composition(path: Path, changes: dict[str, Any]) -> None:
    content = path.read_text(encoding="utf-8")
    if "text_overlay.font_size" in changes:
        content = replace_or_fail(
            content,
            r"^const FONT_SIZE = [0-9.]+;$",
            f'const FONT_SIZE = {changes["text_overlay.font_size"]};',
        )
    path.write_text(content, encoding="utf-8")


def update_root(path: Path, changes: dict[str, Any]) -> None:
    content = path.read_text(encoding="utf-8")
    if "remotion_props.textTopPercent" in changes:
        content = replace_or_fail(
            content,
            r"^\s*textTopPercent: [0-9.]+,?$",
            f'  textTopPercent: {changes["remotion_props.textTopPercent"]},',
        )
    if "remotion_props.textRightOffsetPercent" in changes:
        content = replace_or_fail(
            content,
            r"^\s*textRightOffsetPercent: [0-9.\-]+,?$",
            f'  textRightOffsetPercent: {changes["remotion_props.textRightOffsetPercent"]},',
        )
    path.write_text(content, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply batch fix from audit pass.")
    parser.add_argument("--job", required=True, help="Path to job directory.")
    parser.add_argument("--pass-index", required=True, type=int, help="Audit pass number.")
    args = parser.parse_args()

    job_dir = Path(args.job)
    audit_path = job_dir / "logs" / f"audit_pass_{args.pass_index:02d}.toml"
    if not audit_path.exists():
        raise SystemExit(f"không thấy file audit: {audit_path}")

    payload = read_toml(audit_path)
    batch_fix = payload.get("batch_fix", {})
    if not batch_fix.get("apply", False):
        print("skip: không có batch fix cần áp dụng")
        return 0

    raw_changes = batch_fix.get("changes", {})
    if not isinstance(raw_changes, dict) or not raw_changes:
        print("skip: batch fix không có changes")
        return 0
    changes = flatten_changes(raw_changes)

    render_plan_path = job_dir / "source" / "render_plan.toml"
    composition_path = job_dir / "remotion" / "src" / "composition.tsx"
    root_path = job_dir / "remotion" / "src" / "Root.tsx"

    update_render_plan(render_plan_path, changes)
    update_composition(composition_path, changes)
    update_root(root_path, changes)

    print("applied batch fix")
    for key, value in changes.items():
        print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
