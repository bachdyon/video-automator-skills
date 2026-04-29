#!/usr/bin/env python3
"""Audit a copied video job that has been converted into a reusable template."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def warn(message: str) -> None:
    print(f"WARN: {message}")


def ok(message: str) -> None:
    print(f"OK: {message}")


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def iter_source_files(root: Path) -> list[Path]:
    suffixes = {".ts", ".tsx", ".js", ".jsx", ".json", ".toml", ".md", ".css"}
    ignored_parts = {"node_modules", ".git", "dist", "build"}
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in ignored_parts for part in path.parts):
            continue
        if path.suffix in suffixes:
            files.append(path)
    return files


def check_no_forbidden_dirs(template_dir: Path) -> None:
    forbidden = ["node_modules", "output", "logs", ".git"]
    found = [name for name in forbidden if (template_dir / name).exists()]
    if found:
        fail(f"template contains forbidden generated directories: {', '.join(found)}")
    ok("template excludes generated directories")


def check_contract(template_dir: Path) -> dict:
    contract = template_dir / "template.toml"
    if not contract.exists():
        fail(f"missing contract: {contract}")
    text = read_text(contract)
    required = ["[template]", "[remotion]", "[defaults]", "[style]", "[rules]"]
    missing = [section for section in required if section not in text]
    if missing:
        fail(f"template.toml missing sections: {', '.join(missing)}")
    ok("template.toml has required sections")
    return {"text": text}


def check_props(template_dir: Path) -> None:
    props_path = template_dir / "remotion" / "public" / "template-props.json"
    if not props_path.exists():
        fail(f"missing props file: {props_path}")
    try:
        props = json.loads(read_text(props_path))
    except json.JSONDecodeError as exc:
        fail(f"invalid template-props.json: {exc}")
    if not isinstance(props, dict):
        fail("template-props.json must contain an object")
    serialized = json.dumps(props, ensure_ascii=False)
    forbidden = [str(REPO_ROOT), "/Users/", "jobs/", "Downloads/"]
    hits = [item for item in forbidden if item in serialized]
    if hits:
        fail(f"template-props.json contains non-portable references: {', '.join(hits)}")
    ok("template-props.json is portable JSON")


def check_remotion_project(template_dir: Path) -> None:
    remotion_dir = template_dir / "remotion"
    required = [remotion_dir / "package.json", remotion_dir / "src" / "index.ts", remotion_dir / "src" / "Root.tsx"]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        fail(f"missing Remotion files: {', '.join(missing)}")
    root_text = read_text(remotion_dir / "src" / "Root.tsx")
    if "template-props.json" not in root_text:
        warn("Root.tsx does not appear to import template-props.json")
    ok("Remotion project files are present")


def check_source_portability(template_dir: Path) -> None:
    forbidden = [str(REPO_ROOT), "/Users/", "jobs/", "Downloads/"]
    offenders: list[str] = []
    for path in iter_source_files(template_dir):
        text = read_text(path)
        for item in forbidden:
            if item in text:
                offenders.append(f"{path.relative_to(REPO_ROOT)} contains {item}")
    if offenders:
        fail("non-portable source references:\n" + "\n".join(offenders))
    ok("source files contain no obvious local/job path hardcodes")


def check_template_skill(skill_dir: Path) -> None:
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        fail(f"missing template skill: {skill_md}")
    text = read_text(skill_md)
    for phrase in ["instantiate", "npm run render"]:
        if phrase not in text:
            warn(f"{skill_md.relative_to(REPO_ROOT)} does not mention {phrase!r}")
    scripts = skill_dir / "scripts"
    if scripts.exists():
        py_scripts = list(scripts.glob("*.py"))
        if not py_scripts:
            warn("template skill scripts directory exists but contains no Python scripts")
    ok("template skill exists")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template-id", required=True)
    parser.add_argument("--template-skill", help="Defaults to <template-id>-template")
    args = parser.parse_args()

    template_dir = REPO_ROOT / "templates" / args.template_id
    skill_name = args.template_skill or f"{args.template_id}-template"
    skill_dir = REPO_ROOT / "skills" / skill_name

    if not template_dir.exists():
        fail(f"missing template directory: {template_dir}")

    check_no_forbidden_dirs(template_dir)
    check_contract(template_dir)
    check_props(template_dir)
    check_remotion_project(template_dir)
    check_source_portability(template_dir)
    check_template_skill(skill_dir)
    ok("template audit passed")


if __name__ == "__main__":
    main()
