"""Content-addressed hashing utilities for the asset index."""

from __future__ import annotations

import hashlib
from pathlib import Path

CHUNK = 1 << 20  # 1 MiB


def sha256_file(path: str | Path) -> str:
    """Return hex-encoded SHA-256 of the file's bytes."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(CHUNK)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def short_id(content_hash: str, length: int = 12) -> str:
    """Short prefix of a content hash, useful for sample-frame folder names."""
    return content_hash[:length]
