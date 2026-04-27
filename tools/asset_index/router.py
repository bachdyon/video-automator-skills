"""Dispatch a single file to the correct analyzer and upsert the result.

Acts as the seam between the watcher (which produces "this path changed"
events) and the per-media analyzers + embedding + storage stack.

Idempotency:
    Each file is content-addressed by its SHA-256. If a file was already
    indexed under the same hash and at the same ``mtime``, ``process_file``
    returns ``"skipped"`` without re-running any analyzer or burning an LLM
    call. Renames keep the same ``id`` because the bytes did not change.
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path
from typing import Any, Callable

from skills._shared.pipeline_utils import (  # type: ignore
    MEDIA_AUDIO_EXTENSIONS,
    MEDIA_IMAGE_EXTENSIONS,
    MEDIA_VIDEO_EXTENSIONS,
)
from tools.asset_index import store
from tools.asset_index.analyzers import audio_gemini, image_gemini, video_gemini
from tools.asset_index.embed import EmbeddingError, embed_text
from tools.asset_index.hashing import sha256_file

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = WORKSPACE_ROOT / ".asset_index" / "index.db"
DEFAULT_ENV = WORKSPACE_ROOT / ".env"

Analyzer = Callable[[Path], dict[str, Any]]


def _classify_extension(path: Path) -> str | None:
    suffix = path.suffix.lower()
    if suffix in MEDIA_IMAGE_EXTENSIONS:
        return "image"
    if suffix in MEDIA_VIDEO_EXTENSIONS:
        return "video"
    if suffix in MEDIA_AUDIO_EXTENSIONS:
        return "audio"
    return None


def _analyze(path: Path, media_type: str, env_file: Path) -> dict[str, Any]:
    if media_type == "image":
        return image_gemini.analyze(path, env_file=env_file)
    if media_type == "video":
        return video_gemini.analyze(path, env_file=env_file)
    if media_type == "audio":
        return audio_gemini.analyze(path, env_file=env_file)
    raise ValueError(f"unsupported media_type: {media_type}")


def process_file(
    path: str | Path,
    *,
    conn: Any,
    env_file: str | Path = DEFAULT_ENV,
    force: bool = False,
) -> dict[str, Any]:
    """Index a single file. Returns ``{"status": ok|skipped|failed, ...}``."""
    abs_path = Path(path).resolve()
    rel = store.workspace_relative(abs_path)
    media_type = _classify_extension(abs_path)
    if media_type is None:
        store.log_process(
            conn,
            file_path=str(abs_path),
            content_hash=None,
            status="skipped",
            error="unsupported extension",
        )
        return {"status": "skipped", "reason": "unsupported extension", "file_path": rel}

    if not abs_path.exists():
        store.log_process(
            conn,
            file_path=str(abs_path),
            content_hash=None,
            status="skipped",
            error="file disappeared before processing",
        )
        return {"status": "skipped", "reason": "missing", "file_path": rel}

    try:
        content_hash = sha256_file(abs_path)
    except OSError as exc:
        store.log_process(
            conn,
            file_path=str(abs_path),
            content_hash=None,
            status="failed",
            error=f"hash error: {exc}",
        )
        return {"status": "failed", "reason": f"hash error: {exc}", "file_path": rel}

    stat = abs_path.stat()
    if not force:
        existing = store.get_by_hash(conn, content_hash)
        if existing is not None:
            same_path = existing.get("file_path") == rel
            mtime_close = abs(float(existing.get("mtime") or 0.0) - stat.st_mtime) < 1.0
            if same_path and mtime_close:
                store.log_process(
                    conn,
                    file_path=str(abs_path),
                    content_hash=content_hash,
                    status="skipped",
                    error=None,
                )
                return {
                    "status": "skipped",
                    "reason": "unchanged",
                    "file_path": rel,
                    "id": content_hash,
                }
            if not same_path:
                store.delete_by_path(conn, existing.get("file_path") or "")

    try:
        record = _analyze(abs_path, media_type, Path(env_file))
    except Exception as exc:  # noqa: BLE001
        tb = traceback.format_exc(limit=4)
        store.log_process(
            conn,
            file_path=str(abs_path),
            content_hash=content_hash,
            status="failed",
            error=f"{exc}\n{tb}",
        )
        return {"status": "failed", "reason": str(exc), "file_path": rel}

    source_root, job_id = store.parse_source_root(rel)
    record["id"] = content_hash
    record["file_path"] = rel
    record["source_root"] = source_root
    record["job_id"] = job_id
    record["size_bytes"] = stat.st_size
    record["mtime"] = stat.st_mtime
    record.setdefault("media_type", media_type)
    record.setdefault("file_name", abs_path.name)

    embed_source = record.get("embed_source") or ""
    embedding: list[float] | None
    if embed_source:
        try:
            embedding = embed_text(embed_source, env_file=Path(env_file))
        except EmbeddingError as exc:
            store.log_process(
                conn,
                file_path=str(abs_path),
                content_hash=content_hash,
                status="failed",
                error=f"embedding failed: {exc}",
            )
            return {"status": "failed", "reason": f"embed: {exc}", "file_path": rel}
    else:
        embedding = None

    if not isinstance(record.get("raw_json"), str):
        record["raw_json"] = json.dumps(record.get("raw_json"), ensure_ascii=False, default=str)

    store.upsert_asset(conn, record, embedding)
    store.log_process(
        conn,
        file_path=str(abs_path),
        content_hash=content_hash,
        status="ok",
        error=None,
    )
    return {
        "status": "ok",
        "file_path": rel,
        "id": content_hash,
        "media_type": media_type,
        "summary": record.get("summary") or "",
    }


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Index one or more files")
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    conn = store.open_db(args.db)
    try:
        results: list[dict[str, Any]] = []
        for path in args.files:
            result = process_file(path, conn=conn, env_file=args.env_file, force=args.force)
            print(json.dumps(result, ensure_ascii=False))
            results.append(result)
        ok = sum(1 for r in results if r["status"] == "ok")
        skipped = sum(1 for r in results if r["status"] == "skipped")
        failed = sum(1 for r in results if r["status"] == "failed")
        print(f"\nsummary: ok={ok} skipped={skipped} failed={failed}", file=sys.stderr)
        return 0 if failed == 0 else 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(_main())
