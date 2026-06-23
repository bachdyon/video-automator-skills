#!/usr/bin/env python3
"""Probe raw image/video assets and create a TOML semantic scaffold."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from pipeline_utils import MEDIA_IMAGE_EXTENSIONS, MEDIA_VIDEO_EXTENSIONS, die, media_metadata, write_toml_document


def discover(paths: list[Path]) -> list[Path]:
    assets: list[Path] = []
    for path in paths:
        if path.is_file() and path.suffix.lower() in MEDIA_IMAGE_EXTENSIONS | MEDIA_VIDEO_EXTENSIONS:
            assets.append(path)
        elif path.is_dir():
            for item in sorted(path.rglob("*")):
                if item.is_file() and item.suffix.lower() in MEDIA_IMAGE_EXTENSIONS | MEDIA_VIDEO_EXTENSIONS:
                    assets.append(item)
        else:
            die(f"asset path not found or unsupported: {path}")
    return sorted(dict.fromkeys(assets))


def extract_sample_frames(asset_path: Path, output_dir: Path, count: int) -> list[str]:
    if count <= 0 or shutil.which("ffmpeg") is None:
        return []
    metadata = media_metadata(asset_path)
    duration = float(metadata.get("duration_seconds") or 0.0)
    if duration <= 0:
        return []
    output_dir.mkdir(parents=True, exist_ok=True)
    samples: list[str] = []
    for index in range(count):
        timestamp = min(duration - 0.1, duration * (index + 1) / (count + 1))
        frame_path = output_dir / f"{asset_path.stem}_sample_{index + 1:02d}.jpg"
        cmd = [
            "ffmpeg",
            "-y",
            "-ss",
            f"{timestamp:.3f}",
            "-i",
            str(asset_path),
            "-frames:v",
            "1",
            "-q:v",
            "3",
            str(frame_path),
        ]
        result = subprocess.run(cmd, text=True, capture_output=True)
        if result.returncode == 0 and frame_path.exists():
            samples.append(str(frame_path))
    return samples


def make_scene(asset_id: str, asset_type: str, duration: float, scene_index: int, start: float, end: float, sample_frames: list[str]) -> dict[str, Any]:
    return {
        "id": f"{asset_id}_SC_{scene_index:02d}",
        "start": round(start, 3),
        "end": round(end, 3),
        "description": "TODO: describe visible content with multimodal analysis.",
        "subjects": [],
        "actions": [],
        "environment": "",
        "shot_type": "",
        "camera_motion": "",
        "composition": "",
        "colors": [],
        "mood": [],
        "semantic_tags": [],
        "recommended_uses": [],
        "avoid_uses": [],
        "sample_frames": sample_frames if asset_type == "video" else [],
    }


def build_assets(args: argparse.Namespace) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    paths = discover(args.inputs)
    rows: list[dict[str, Any]] = []
    scenes: list[dict[str, Any]] = []
    for index, path in enumerate(paths, start=1):
        suffix = path.suffix.lower()
        asset_type = "image" if suffix in MEDIA_IMAGE_EXTENSIONS else "video"
        metadata = media_metadata(path)
        duration = float(metadata.get("duration_seconds") or 0.0)
        asset_id = f"AST_{index:03d}"
        samples = extract_sample_frames(path, args.sample_dir, args.sample_frames) if asset_type == "video" else []
        rows.append(
            {
                "id": asset_id,
                "file_path": str(path),
                "type": asset_type,
                "duration_seconds": duration,
                "width": int(metadata.get("width") or 0),
                "height": int(metadata.get("height") or 0),
                "fps": float(metadata.get("fps") or 0.0),
                "has_audio": bool(metadata.get("has_audio")),
                "summary": "TODO: add semantic summary.",
                "visual_style": "",
                "mood": [],
                "tags": [],
                "privacy_notes": [],
                "quality_notes": [],
            }
        )
        if asset_type == "image":
            scenes.append(make_scene(asset_id, asset_type, 0.0, 1, 0.0, 0.0, []))
        elif args.scene_window_seconds > 0 and duration > args.scene_window_seconds:
            start = 0.0
            scene_index = 1
            while start < duration:
                end = min(duration, start + args.scene_window_seconds)
                scenes.append(make_scene(asset_id, asset_type, duration, scene_index, start, end, samples))
                start = end
                scene_index += 1
        else:
            scenes.append(make_scene(asset_id, asset_type, duration, 1, 0.0, duration, samples))
    return rows, scenes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, default=Path("source/asset_semantics.toml"))
    parser.add_argument("--sample-dir", type=Path, default=Path("source/asset_samples"))
    parser.add_argument("--sample-frames", type=int, default=0)
    parser.add_argument("--scene-window-seconds", type=float, default=0.0)
    args = parser.parse_args()
    assets, scenes = build_assets(args)
    write_toml_document(args.output, [("assets", assets), ("asset_scenes", scenes)])
    print(f"wrote {args.output} with {len(assets)} assets and {len(scenes)} scenes")


if __name__ == "__main__":
    main()
