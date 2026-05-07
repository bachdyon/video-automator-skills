#!/usr/bin/env python3
"""Copy personal-brand-mat-overlay Remotion template into a job folder."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
TEMPLATE_REMOTION = REPO / "templates" / "personal-brand-mat-overlay" / "remotion"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job_id", help="e.g. 2026-05-07_004_my-podcast")
    parser.add_argument(
        "--from-job",
        type=Path,
        help="Optional: copy assets + JSON from an existing job remotion/public",
    )
    args = parser.parse_args()

    if not TEMPLATE_REMOTION.is_dir():
        print("FAIL: missing", TEMPLATE_REMOTION, file=sys.stderr)
        raise SystemExit(1)

    job_root = REPO / "jobs" / args.job_id
    dest = job_root / "remotion"
    job_root.mkdir(parents=True, exist_ok=True)

    if dest.exists():
        print("FAIL: already exists:", dest, file=sys.stderr)
        raise SystemExit(1)

    shutil.copytree(
        TEMPLATE_REMOTION,
        dest,
        ignore=shutil.ignore_patterns(
            "node_modules",
            "output",
            "build",
            "out",
            "dist",
            ".remotion",
        ),
    )

    pub = dest / "public" / "assets"
    pub.mkdir(parents=True, exist_ok=True)

    if args.from_job:
        src = REPO / "jobs" / args.from_job / "remotion"
        if not src.is_dir():
            print("FAIL: --from-job remotion not found:", src, file=sys.stderr)
            raise SystemExit(1)
        for name in ("source.mp4", "voice.wav"):
            path = src / "public" / "assets" / name
            if path.is_file():
                shutil.copy2(path, pub / name)
        for name in ("template-props.json", "overlay-beats.json"):
            path = src / "public" / name
            if path.is_file():
                shutil.copy2(path, dest / "public" / name)
        mm_src = src / "public" / "mat-memes"
        mm_dst = dest / "public" / "mat-memes"
        if mm_src.is_dir():
            if mm_dst.exists():
                shutil.rmtree(mm_dst)
            shutil.copytree(mm_src, mm_dst)

    print("OK: copied template remotion ->", dest)
    if not (pub / "source.mp4").is_file():
        print("WARN: add remotion/public/assets/source.mp4 before render")
    if not (pub / "voice.wav").is_file():
        print("WARN: add remotion/public/assets/voice.wav before render")


if __name__ == "__main__":
    main()
