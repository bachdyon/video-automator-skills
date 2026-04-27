"""SQLite + sqlite-vec storage layer for the asset index.

Uses ``apsw`` (Another Python SQLite Wrapper) rather than the stdlib ``sqlite3``
because:

1. ``sqlite-vec`` is loaded as a SQLite extension and requires
   ``Connection.enable_load_extension``. The python.org macOS installer
   compiles its bundled SQLite without that capability, so the stdlib module
   fails on a typical user machine.
2. ``apsw`` ships its own up-to-date SQLite and exposes the full extension
   API across macOS, Windows, and Linux via prebuilt wheels.

All other modules must go through this module instead of touching SQL
directly so that path normalisation, vector encoding, and schema migration
stay in one place.
"""

from __future__ import annotations

import json
import struct
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

import apsw
import sqlite_vec

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"
EMBED_DIM = 1536
WORKSPACE_ROOT = Path(__file__).resolve().parents[2]

_lock = threading.Lock()


def workspace_relative(path: str | Path) -> str:
    """Return a workspace-relative POSIX path string.

    Uses forward slashes on every OS so DB rows stay portable. Falls back to
    the absolute POSIX form when the path lives outside the workspace.
    """
    abspath = Path(path).resolve()
    try:
        rel = abspath.relative_to(WORKSPACE_ROOT)
    except ValueError:
        return abspath.as_posix()
    return rel.as_posix()


def parse_source_root(rel_path: str) -> tuple[str, str | None]:
    """Infer ``(source_root, job_id)`` from a workspace-relative path.

    - ``raw_assets/...``                   -> ("raw_assets", None)
    - ``jobs/<id>/input/raw_assets/...``   -> ("jobs/<id>/input/raw_assets", "<id>")
    - anything else                        -> ("external", None)
    """
    parts = rel_path.split("/")
    if parts and parts[0] == "raw_assets":
        return "raw_assets", None
    if len(parts) >= 4 and parts[0] == "jobs" and parts[2] == "input" and parts[3] == "raw_assets":
        job_id = parts[1]
        return f"jobs/{job_id}/input/raw_assets", job_id
    return "external", None


def encode_vector(vec: Iterable[float]) -> bytes:
    """Pack a float32 vector for sqlite-vec's vec0 BLOB column."""
    floats = list(vec)
    if len(floats) != EMBED_DIM:
        raise ValueError(f"expected {EMBED_DIM}-dim vector, got {len(floats)}")
    return struct.pack(f"{EMBED_DIM}f", *floats)


def open_db(db_path: str | Path) -> apsw.Connection:
    """Open the asset-index DB, load sqlite-vec, and ensure the schema exists."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = apsw.Connection(str(path))
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        conn.execute(f.read())
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


ASSET_COLUMNS = (
    "id",
    "file_name",
    "file_path",
    "source_root",
    "job_id",
    "media_type",
    "size_bytes",
    "mtime",
    "width",
    "height",
    "duration_seconds",
    "fps",
    "has_audio",
    "style",
    "summary",
    "transcript",
    "audio_role",
    "tags_json",
    "mood_json",
    "scenes_json",
    "raw_json",
    "embed_source",
    "embed_model",
    "indexed_at",
)


def _record_to_row(record: Mapping[str, Any]) -> dict[str, Any]:
    row: dict[str, Any] = {}
    for col in ASSET_COLUMNS:
        row[col] = record.get(col)
    if not row.get("indexed_at"):
        row["indexed_at"] = _now_iso()
    if isinstance(row.get("has_audio"), bool):
        row["has_audio"] = int(row["has_audio"])
    for json_col in ("tags_json", "mood_json", "scenes_json", "raw_json"):
        value = row.get(json_col)
        if isinstance(value, (list, dict)):
            row[json_col] = json.dumps(value, ensure_ascii=False)
    return row


def _rows_as_dicts(cursor: apsw.Cursor) -> list[dict[str, Any]]:
    """Materialise an apsw cursor into a list of dict rows.

    apsw raises ``ExecutionCompleteError`` when ``getdescription`` is called
    on a fully-consumed cursor that yielded zero rows, so we read the
    description proactively and fall back to an empty list when the query
    matched nothing.
    """
    try:
        description = cursor.getdescription()
    except apsw.ExecutionCompleteError:
        return []
    columns = [d[0] for d in description]
    return [dict(zip(columns, row)) for row in cursor]


def upsert_asset(
    conn: apsw.Connection,
    record: Mapping[str, Any],
    embedding: Iterable[float] | None,
) -> None:
    """Insert or replace an asset row and its vector counterpart atomically."""
    row = _record_to_row(record)
    if not row.get("id") or not row.get("file_path") or not row.get("media_type"):
        raise ValueError("upsert_asset requires id, file_path, media_type")
    placeholders = ",".join(":" + c for c in ASSET_COLUMNS)
    columns = ",".join(ASSET_COLUMNS)
    with _lock:
        conn.execute("BEGIN IMMEDIATE")
        try:
            conn.execute(
                f"INSERT OR REPLACE INTO assets ({columns}) VALUES ({placeholders})",
                row,
            )
            if embedding is not None:
                conn.execute("DELETE FROM assets_vec WHERE id = ?", (row["id"],))
                conn.execute(
                    "INSERT INTO assets_vec(id, embedding) VALUES (?, ?)",
                    (row["id"], encode_vector(embedding)),
                )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise


def delete_by_path(conn: apsw.Connection, file_path: str) -> None:
    rel = workspace_relative(file_path)
    with _lock:
        conn.execute("BEGIN IMMEDIATE")
        try:
            ids = [r[0] for r in conn.execute("SELECT id FROM assets WHERE file_path = ?", (rel,))]
            for asset_id in ids:
                conn.execute("DELETE FROM assets_vec WHERE id = ?", (asset_id,))
            conn.execute("DELETE FROM assets WHERE file_path = ?", (rel,))
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise


def get_by_hash(conn: apsw.Connection, content_hash: str) -> dict[str, Any] | None:
    cursor = conn.execute("SELECT * FROM assets WHERE id = ?", (content_hash,))
    rows = _rows_as_dicts(cursor)
    return rows[0] if rows else None


def get_by_path(conn: apsw.Connection, file_path: str) -> dict[str, Any] | None:
    rel = workspace_relative(file_path)
    cursor = conn.execute("SELECT * FROM assets WHERE file_path = ?", (rel,))
    rows = _rows_as_dicts(cursor)
    return rows[0] if rows else None


def search(
    conn: apsw.Connection,
    query_vec: Iterable[float],
    *,
    k: int = 10,
    media_type: str | None = None,
    job_id: str | None = None,
    source_root: str | None = None,
) -> list[dict[str, Any]]:
    """Vector search via vec0 KNN with optional metadata filters."""
    knn_k = max(k * 4, k + 5) if (media_type or job_id or source_root) else k
    sql = (
        "SELECT v.id AS vec_id, v.distance AS distance, a.* FROM assets_vec v "
        "JOIN assets a ON a.id = v.id "
        "WHERE v.embedding MATCH ? AND k = ?"
    )
    params: list[Any] = [encode_vector(query_vec), knn_k]
    if media_type:
        sql += " AND a.media_type = ?"
        params.append(media_type)
    if job_id:
        sql += " AND a.job_id = ?"
        params.append(job_id)
    if source_root:
        if source_root == "raw_assets":
            sql += " AND a.source_root = 'raw_assets'"
        elif source_root == "jobs":
            sql += " AND a.source_root LIKE 'jobs/%'"
        else:
            sql += " AND a.source_root = ?"
            params.append(source_root)
    sql += " ORDER BY v.distance LIMIT ?"
    params.append(k)
    cursor = conn.execute(sql, params)
    return _rows_as_dicts(cursor)


def log_process(
    conn: apsw.Connection,
    *,
    file_path: str,
    content_hash: str | None,
    status: str,
    error: str | None = None,
) -> None:
    rel = workspace_relative(file_path)
    with _lock:
        conn.execute(
            "INSERT INTO process_log(file_path, content_hash, status, error, ran_at) VALUES (?,?,?,?,?)",
            (rel, content_hash, status, error, _now_iso()),
        )


def db_summary(conn: apsw.Connection) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for media_type, n in conn.execute(
        "SELECT media_type, COUNT(*) FROM assets GROUP BY media_type"
    ):
        counts[media_type] = n
    total = next(conn.execute("SELECT COUNT(*) FROM assets"))[0]
    last_error_rows = _rows_as_dicts(
        conn.execute(
            "SELECT file_path, error, ran_at FROM process_log WHERE status='failed' ORDER BY id DESC LIMIT 1"
        )
    )
    return {
        "total_assets": total,
        "by_media_type": counts,
        "last_error": last_error_rows[0] if last_error_rows else None,
    }


__all__ = [
    "EMBED_DIM",
    "WORKSPACE_ROOT",
    "open_db",
    "upsert_asset",
    "delete_by_path",
    "get_by_hash",
    "get_by_path",
    "search",
    "log_process",
    "db_summary",
    "workspace_relative",
    "parse_source_root",
    "encode_vector",
]
