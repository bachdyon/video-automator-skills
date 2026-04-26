#!/usr/bin/env python3
"""Ensure faster-whisper and model cache are available."""

from __future__ import annotations

import argparse
import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)


def require_binary(name: str) -> None:
    if shutil.which(name) is None:
        raise SystemExit(f"Missing required binary: {name}")


def module_exists(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def install_faster_whisper() -> None:
    cmd = [sys.executable, "-m", "pip", "install", "faster-whisper"]
    print("Installing faster-whisper...")
    subprocess.run(cmd, check=True)


def detect_model_cache_path(model: object) -> Path | None:
    # Compatible across different faster-whisper / ctranslate2 versions.
    candidates = [
        ("model", "model_path"),
        ("model", "_model_path"),
        ("model", "path"),
    ]
    for parent_attr, child_attr in candidates:
        parent = getattr(model, parent_attr, None)
        if parent is None:
            continue
        value = getattr(parent, child_attr, None)
        if isinstance(value, (str, Path)) and str(value):
            return Path(value).expanduser().resolve()
    return None


def warmup_model(model_name: str, device: str, compute_type: str) -> Path | None:
    from faster_whisper import WhisperModel  # type: ignore

    print(f"Preparing model cache for: {model_name}")
    model = WhisperModel(model_name, device=device, compute_type=compute_type)
    return detect_model_cache_path(model)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model",
        default="small",
        help="faster-whisper model name or local path (default: small)",
    )
    parser.add_argument(
        "--device",
        default="cpu",
        help="Device for warmup download (default: cpu)",
    )
    parser.add_argument(
        "--compute-type",
        default="int8",
        help="Compute type for warmup download (default: int8)",
    )
    parser.add_argument(
        "--skip-install",
        action="store_true",
        help="Do not run pip install even if faster-whisper is missing",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    require_binary("ffmpeg")
    require_binary("ffprobe")

    if not module_exists("faster_whisper"):
        if args.skip_install:
            raise SystemExit("faster-whisper is missing and --skip-install was used.")
        install_faster_whisper()

    if not module_exists("faster_whisper"):
        raise SystemExit("Failed to import faster-whisper after installation.")

    model_path = warmup_model(args.model, args.device, args.compute_type)
    print("Prerequisites are ready.")
    if model_path is not None:
        print(f"Model cache path: {model_path}")
    else:
        print("Model cache path: unavailable (warmup succeeded, version does not expose path attribute).")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as exc:
        print(exc.stderr or exc.stdout)
        raise SystemExit(exc.returncode)
