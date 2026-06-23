"""Shared Remotion dependency helpers."""

from __future__ import annotations

import os
from pathlib import Path


def link_shared_node_modules(remotion_dir: Path, repo_root: Path) -> None:
    """Point a job Remotion project at the repo-level node_modules directory."""
    link = remotion_dir / "node_modules"
    shared = repo_root / "node_modules"
    target = Path(os.path.relpath(shared, link.parent))

    if link.is_symlink():
        if os.readlink(link) != str(target):
            link.unlink()
            link.symlink_to(target)
        return

    if link.exists():
        return

    link.symlink_to(target)
