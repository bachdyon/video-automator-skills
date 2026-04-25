#!/usr/bin/env python3
"""Create and manage isolated video production jobs."""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from pipeline_utils import die, read_toml, write_toml_document


STAGES = [
    "request",
    "reference_style",
    "creative_plan",
    "voice",
    "transcript",
    "asset_semantics",
    "semantic_mapping",
    "render_plan",
    "render",
]

STAGE_OUTPUTS = {
    "request": "job.toml",
    "reference_style": "source/vds.md",
    "creative_plan": "source/creative_plan.toml",
    "voice": "source/voice.wav",
    "transcript": "source/transcript_word_level.toml",
    "asset_semantics": "source/asset_semantics.toml",
    "semantic_mapping": "source/semantic_mapping.toml",
    "render_plan": "source/render_plan.toml",
    "render": "output/final_video.mp4",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def slugify(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    return text[:48].strip("-") or "video-job"


def jobs_root(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def next_job_id(root: Path, title: str, timestamp: datetime | None = None) -> str:
    stamp = (timestamp or datetime.now()).strftime("%Y-%m-%d")
    prefix = f"{stamp}_"
    existing = sorted(item.name for item in root.iterdir() if item.is_dir() and item.name.startswith(prefix))
    next_number = 1
    if existing:
        numbers = []
        for name in existing:
            match = re.match(rf"{re.escape(stamp)}_(\d+)_", name)
            if match:
                numbers.append(int(match.group(1)))
        if numbers:
            next_number = max(numbers) + 1
    return f"{stamp}_{next_number:03d}_{slugify(title)}"


def job_dir(value: str | Path) -> Path:
    path = Path(value)
    if path.name == "job.toml":
        path = path.parent
    if not (path / "job.toml").exists():
        die(f"job.toml not found under {path}")
    return path


def load_job(path: Path) -> dict[str, Any]:
    return read_toml(path / "job.toml")


def relative_to_job(path: Path, base: Path) -> str:
    try:
        return str(path.resolve().relative_to(base.resolve()))
    except ValueError:
        return str(path)


def initial_stages(created_at: str) -> list[dict[str, Any]]:
    return [
        {
            "name": stage,
            "status": "done" if stage == "request" else "pending",
            "output": STAGE_OUTPUTS[stage],
            "updated_at": created_at if stage == "request" else "",
            "reason": "",
        }
        for stage in STAGES
    ]


def write_job(path: Path, data: dict[str, Any]) -> None:
    sections: list[tuple[str | None, dict[str, Any] | list[dict[str, Any]]]] = [
        ("job", data["job"]),
        ("request", data["request"]),
        ("paths", data["paths"]),
        ("inputs", data.get("inputs", [])),
        ("stages", data.get("stages", [])),
    ]
    write_toml_document(path / "job.toml", sections)
    write_toml_document(path / "logs" / "pipeline_status.toml", [("stages", data.get("stages", []))])


def create(args: argparse.Namespace) -> None:
    root = jobs_root(args.jobs_root)
    job_id = args.job_id or next_job_id(root, args.title)
    path = root / job_id
    if path.exists():
        die(f"job already exists: {path}")
    for subdir in [
        "input/reference",
        "input/raw_assets",
        "input/audio",
        "input/brand",
        "source",
        "output/previews",
        "logs",
    ]:
        (path / subdir).mkdir(parents=True, exist_ok=True)
    created_at = now_iso()
    data = {
        "job": {
            "id": job_id,
            "title": args.title,
            "status": "created",
            "created_at": created_at,
            "updated_at": created_at,
        },
        "request": {
            "brief": args.brief,
            "platform": args.platform,
            "language": args.language,
            "target_duration_seconds": float(args.target_duration),
        },
        "paths": {
            "job_dir": str(path),
            "input_dir": "input",
            "reference_dir": "input/reference",
            "raw_assets_dir": "input/raw_assets",
            "audio_dir": "input/audio",
            "brand_dir": "input/brand",
            "source_dir": "source",
            "output_dir": "output",
            "logs_dir": "logs",
        },
        "inputs": [],
        "stages": initial_stages(created_at),
    }
    write_job(path, data)
    print(str(path))


def destination_for(kind: str, source: Path, base: Path) -> Path:
    folders = {
        "reference": "input/reference",
        "raw_assets": "input/raw_assets",
        "audio": "input/audio",
        "brand": "input/brand",
    }
    if kind not in folders:
        die(f"unsupported input kind {kind}; expected one of {', '.join(folders)}")
    dest_dir = base / folders[kind]
    dest_dir.mkdir(parents=True, exist_ok=True)
    candidate = dest_dir / source.name
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    suffix = candidate.suffix
    index = 2
    while True:
        candidate = dest_dir / f"{stem}_{index}{suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def register_input(args: argparse.Namespace) -> None:
    path = job_dir(args.job)
    data = load_job(path)
    source = Path(args.path)
    if not source.exists():
        die(f"input path not found: {source}")
    if args.copy:
        dest = destination_for(args.kind, source, path)
        if source.is_dir():
            shutil.copytree(source, dest)
        else:
            shutil.copy2(source, dest)
        stored_path = dest
    else:
        stored_path = source
    data.setdefault("inputs", []).append(
        {
            "kind": args.kind,
            "path": relative_to_job(stored_path, path),
            "original_path": str(source),
            "registered_at": now_iso(),
            "note": args.note or "",
        }
    )
    data["job"]["updated_at"] = now_iso()
    if args.kind in {"reference", "raw_assets", "audio", "brand"}:
        stale_stage = {
            "reference": "reference_style",
            "raw_assets": "asset_semantics",
            "audio": "transcript",
            "brand": "creative_plan",
        }[args.kind]
        mark_stale(data, stale_stage, f"{args.kind} input registered")
    write_job(path, data)
    print(relative_to_job(stored_path, path))


def stage_index(stage: str) -> int:
    if stage not in STAGES:
        die(f"unknown stage {stage}; expected one of {', '.join(STAGES)}")
    return STAGES.index(stage)


def find_stage(data: dict[str, Any], stage: str) -> dict[str, Any]:
    for row in data.get("stages", []):
        if row.get("name") == stage:
            return row
    row = {"name": stage, "status": "pending", "output": STAGE_OUTPUTS.get(stage, ""), "updated_at": "", "reason": ""}
    data.setdefault("stages", []).append(row)
    return row


def mark_stale(data: dict[str, Any], stage: str, reason: str) -> None:
    start = stage_index(stage)
    timestamp = now_iso()
    for row in data.get("stages", []):
        name = row.get("name")
        if name in STAGES and STAGES.index(name) >= start and row.get("status") == "done":
            row["status"] = "stale"
            row["updated_at"] = timestamp
            row["reason"] = reason


def mark_stage(args: argparse.Namespace) -> None:
    path = job_dir(args.job)
    data = load_job(path)
    row = find_stage(data, args.stage)
    row["status"] = args.status
    row["output"] = args.output or row.get("output") or STAGE_OUTPUTS.get(args.stage, "")
    row["updated_at"] = now_iso()
    row["reason"] = args.reason or ""
    if args.status in {"done", "running"}:
        data["job"]["status"] = args.status if args.stage == "render" else "in_progress"
    if args.status == "failed":
        data["job"]["status"] = "failed"
    if args.stage == "render" and args.status == "done":
        data["job"]["status"] = "done"
    data["job"]["updated_at"] = now_iso()
    write_job(path, data)
    print(f"{args.stage}={args.status}")


def stale_from(args: argparse.Namespace) -> None:
    path = job_dir(args.job)
    data = load_job(path)
    mark_stale(data, args.stage, args.reason or f"stale from {args.stage}")
    data["job"]["updated_at"] = now_iso()
    write_job(path, data)
    print(f"marked stale from {args.stage}")


def status(args: argparse.Namespace) -> None:
    path = job_dir(args.job)
    data = load_job(path)
    job = data.get("job", {})
    request = data.get("request", {})
    print(f"job: {job.get('id')} ({job.get('status')})")
    print(f"title: {job.get('title')}")
    print(f"platform/language/duration: {request.get('platform')}/{request.get('language')}/{request.get('target_duration_seconds')}s")
    for row in data.get("stages", []):
        output = row.get("output") or ""
        exists = "exists" if output and (path / output).exists() else "missing"
        print(f"{row.get('name')}: {row.get('status')} [{exists}] {output}")


def paths(args: argparse.Namespace) -> None:
    path = job_dir(args.job)
    data = load_job(path)
    key = args.key
    if key == "job_dir":
        print(path)
        return
    if key in STAGE_OUTPUTS:
        print(path / STAGE_OUTPUTS[key])
        return
    paths_data = data.get("paths", {})
    if key in paths_data:
        print(path / paths_data[key])
        return
    die(f"unknown path key {key}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    create_parser = sub.add_parser("create")
    create_parser.add_argument("--jobs-root", type=Path, default=Path("jobs"))
    create_parser.add_argument("--job-id")
    create_parser.add_argument("--title", required=True)
    create_parser.add_argument("--brief", required=True)
    create_parser.add_argument("--platform", default="tiktok")
    create_parser.add_argument("--language", default="vi")
    create_parser.add_argument("--target-duration", type=float, default=45.0)
    create_parser.set_defaults(func=create)

    input_parser = sub.add_parser("register-input")
    input_parser.add_argument("--job", required=True)
    input_parser.add_argument("--kind", required=True, choices=["reference", "raw_assets", "audio", "brand"])
    input_parser.add_argument("--path", required=True)
    input_parser.add_argument("--copy", action="store_true")
    input_parser.add_argument("--note")
    input_parser.set_defaults(func=register_input)

    mark_parser = sub.add_parser("mark-stage")
    mark_parser.add_argument("--job", required=True)
    mark_parser.add_argument("--stage", required=True, choices=STAGES)
    mark_parser.add_argument("--status", required=True, choices=["pending", "running", "done", "failed", "stale"])
    mark_parser.add_argument("--output")
    mark_parser.add_argument("--reason")
    mark_parser.set_defaults(func=mark_stage)

    stale_parser = sub.add_parser("stale-from")
    stale_parser.add_argument("--job", required=True)
    stale_parser.add_argument("--stage", required=True, choices=STAGES)
    stale_parser.add_argument("--reason")
    stale_parser.set_defaults(func=stale_from)

    status_parser = sub.add_parser("status")
    status_parser.add_argument("--job", required=True)
    status_parser.set_defaults(func=status)

    paths_parser = sub.add_parser("paths")
    paths_parser.add_argument("--job", required=True)
    paths_parser.add_argument("--key", required=True)
    paths_parser.set_defaults(func=paths)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
