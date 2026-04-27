"""Video analyzer for the asset index.

Wraps the existing ``probe_assets.py`` + ``analyze_with_gemini.py`` scripts via
``subprocess`` so we get the exact same per-scene Gemini analysis the rest of
the pipeline already trusts. We do not touch those scripts; we only feed them
inputs and parse the TOML they produce.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

try:
    import certifi
except Exception:  # pragma: no cover
    certifi = None  # type: ignore

from skills._shared.pipeline_utils import (  # type: ignore
    media_metadata,
    read_toml,
)
from tools.asset_index.embed import build_embed_source

WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_ENV = WORKSPACE_ROOT / ".env"
PROBE_SCRIPT = WORKSPACE_ROOT / "skills" / "asset_semantic_extractor" / "scripts" / "probe_assets.py"
ANALYZE_SCRIPT = WORKSPACE_ROOT / "skills" / "asset_semantic_extractor" / "scripts" / "analyze_with_gemini.py"


class VideoAnalysisError(RuntimeError):
    pass


def _subprocess_env() -> dict[str, str]:
    """Inherit os.environ but inject certifi's CA bundle.

    Required so the wrapped ``analyze_with_gemini.py`` (which uses plain
    ``urllib.request.urlopen``) succeeds in fresh virtualenvs.
    """
    env = os.environ.copy()
    if certifi is not None and "SSL_CERT_FILE" not in env:
        env["SSL_CERT_FILE"] = certifi.where()
    return env


def _run(cmd: list[str], cwd: Path) -> None:
    completed = subprocess.run(
        cmd,
        cwd=str(cwd),
        env=_subprocess_env(),
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise VideoAnalysisError(
            f"command failed (rc={completed.returncode}): {' '.join(cmd)}\n"
            f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}"
        )


def analyze(
    path: str | Path,
    *,
    env_file: str | Path = DEFAULT_ENV,
    sample_root: Path | None = None,
    sample_frames: int = 3,
    scene_window_seconds: float = 8.0,
    timeout_seconds: int = 240,
) -> dict[str, Any]:
    """Analyze a single video clip and return a record dict.

    Steps:

    1. Run ``probe_assets.py`` against the file -> tmp TOML with metadata + scenes
       (each scene has sample frames extracted with ffmpeg).
    2. Run ``analyze_with_gemini.py`` with ``--strict`` against that TOML ->
       enriched TOML with summary, visual_style, mood, tags, scenes.
    3. Parse and flatten into a record dict.
    """
    src = Path(path).resolve()
    if not src.exists():
        raise FileNotFoundError(f"video not found: {src}")
    if shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None:
        raise VideoAnalysisError(
            "ffmpeg/ffprobe not found in PATH; install via 'brew install ffmpeg' (macOS) "
            "or 'winget install Gyan.FFmpeg' (Windows)."
        )
    if not PROBE_SCRIPT.exists() or not ANALYZE_SCRIPT.exists():
        raise VideoAnalysisError(
            f"required scripts missing: {PROBE_SCRIPT} / {ANALYZE_SCRIPT}"
        )

    sample_root = sample_root or (WORKSPACE_ROOT / ".asset_index" / "samples")
    sample_root.mkdir(parents=True, exist_ok=True)

    tmpdir = Path(tempfile.mkdtemp(prefix="asset_video_", dir=str(WORKSPACE_ROOT / ".asset_index")))
    toml_path = tmpdir / "asset_semantics.toml"

    try:
        sample_dir = sample_root / src.stem
        sample_dir.mkdir(parents=True, exist_ok=True)

        probe_cmd = [
            sys.executable,
            str(PROBE_SCRIPT),
            str(src),
            "--output",
            str(toml_path),
            "--sample-dir",
            str(sample_dir),
            "--sample-frames",
            str(sample_frames),
            "--scene-window-seconds",
            str(scene_window_seconds),
        ]
        _run(probe_cmd, cwd=WORKSPACE_ROOT)

        analyze_cmd = [
            sys.executable,
            str(ANALYZE_SCRIPT),
            "--input",
            str(toml_path),
            "--output",
            str(toml_path),
            "--sample-dir",
            str(sample_dir),
            "--env-file",
            str(env_file),
            "--strict",
        ]
        _run(analyze_cmd, cwd=WORKSPACE_ROOT)

        data = read_toml(toml_path)
        assets = list(data.get("assets") or [])
        if not assets:
            raise VideoAnalysisError(f"empty assets table in {toml_path}")
        asset = assets[0]
        asset_id = str(asset.get("id") or "")
        scenes = [
            scene
            for scene in (data.get("asset_scenes") or [])
            if str(scene.get("id") or "").startswith(asset_id + "_SC_")
        ]
    finally:
        try:
            shutil.rmtree(tmpdir, ignore_errors=True)
        except Exception:
            pass

    metadata = media_metadata(src)
    stat = src.stat()
    summary = (asset.get("summary") or "").strip()
    style = (asset.get("visual_style") or "").strip()
    tags = list(asset.get("tags") or [])
    mood = list(asset.get("mood") or [])
    scene_descriptions = [
        (scene.get("description") or "").strip()
        for scene in scenes
        if (scene.get("description") or "").strip()
    ]
    embed_source = build_embed_source([summary, style, *tags, *mood, *scene_descriptions])

    record: dict[str, Any] = {
        "file_name": src.name,
        "media_type": "video",
        "size_bytes": stat.st_size,
        "mtime": stat.st_mtime,
        "width": metadata.get("width") or asset.get("width"),
        "height": metadata.get("height") or asset.get("height"),
        "duration_seconds": metadata.get("duration_seconds") or asset.get("duration_seconds"),
        "fps": metadata.get("fps") or asset.get("fps"),
        "has_audio": int(bool(metadata.get("has_audio"))),
        "style": style,
        "summary": summary,
        "transcript": None,
        "audio_role": None,
        "tags_json": tags,
        "mood_json": mood,
        "scenes_json": scenes,
        "raw_json": json.dumps({"asset": asset, "scenes": scenes}, ensure_ascii=False),
        "embed_source": embed_source,
        "embed_model": "text-embedding-3-small",
    }
    return record


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Analyze a single video clip via the existing skill scripts")
    parser.add_argument("video", type=Path)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV)
    parser.add_argument("--sample-root", type=Path, default=None)
    parser.add_argument("--sample-frames", type=int, default=3)
    parser.add_argument("--scene-window-seconds", type=float, default=8.0)
    args = parser.parse_args(argv)
    try:
        record = analyze(
            args.video,
            env_file=args.env_file,
            sample_root=args.sample_root,
            sample_frames=args.sample_frames,
            scene_window_seconds=args.scene_window_seconds,
        )
    except (FileNotFoundError, VideoAnalysisError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    printable = {k: v for k, v in record.items() if k != "raw_json"}
    printable["raw_json_chars"] = len(record["raw_json"] or "")
    print(json.dumps(printable, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(_main())
