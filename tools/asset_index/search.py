"""Semantic search over the asset index.

Usage:
    python -m tools.asset_index.search "vlog du lịch ngoài trời"
    python -m tools.asset_index.search --media video --top 5 "intro xanh"
    python -m tools.asset_index.search --json --source raw_assets "voice over tiếng Anh"

Programmatic:
    from tools.asset_index.search import search_assets
    rows = search_assets("phong cảnh núi", k=5)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from tools.asset_index import store
from tools.asset_index.embed import EmbeddingError, embed_text

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = WORKSPACE_ROOT / ".asset_index" / "index.db"
DEFAULT_ENV = WORKSPACE_ROOT / ".env"

_DEFAULT_FIELDS = (
    "rank",
    "score",
    "media_type",
    "audio_role",
    "file_path",
    "summary",
    "tags_json",
)


def _force_utf8_console() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None:
            continue
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8")
        except (LookupError, ValueError, OSError):
            pass


def _shorten(text: str, limit: int = 140) -> str:
    text = (text or "").strip().replace("\n", " ")
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def search_assets(
    query: str,
    *,
    k: int = 5,
    media_type: str | None = None,
    job_id: str | None = None,
    source_root: str | None = None,
    db_path: str | Path = DEFAULT_DB,
    env_file: str | Path = DEFAULT_ENV,
) -> list[dict[str, Any]]:
    """Search the index for ``query`` and return the top ``k`` rows.

    The score is ``1 - distance`` so 1.0 means identical and 0.0 means
    orthogonal (cosine-flavoured semantics from sqlite-vec).
    """
    if not query or not query.strip():
        return []
    embedding = embed_text(query.strip(), env_file=Path(env_file))
    conn = store.open_db(Path(db_path))
    try:
        rows = store.search(
            conn,
            embedding,
            k=k,
            media_type=media_type,
            job_id=job_id,
            source_root=source_root,
        )
    finally:
        conn.close()
    enriched: list[dict[str, Any]] = []
    for idx, row in enumerate(rows, start=1):
        distance = float(row.get("distance") or 0.0)
        enriched.append(
            {
                "rank": idx,
                "score": round(1.0 - distance, 4),
                "distance": round(distance, 4),
                **row,
            }
        )
    return enriched


def _format_human(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "(no results)"
    lines: list[str] = []
    for r in rows:
        score = r.get("score", 0)
        media = r.get("media_type") or "?"
        role = f" / {r['audio_role']}" if r.get("audio_role") else ""
        path = r.get("file_path") or ""
        summary = _shorten(r.get("summary") or "")
        tags = r.get("tags_json") or ""
        if isinstance(tags, str):
            try:
                tags_list = json.loads(tags)
            except json.JSONDecodeError:
                tags_list = []
        else:
            tags_list = tags
        tag_text = ", ".join(tags_list[:5]) if isinstance(tags_list, list) else ""
        header = f"#{r['rank']}  score={score:.3f}  [{media}{role}]"
        lines.append(header)
        lines.append(f"   {path}")
        if summary:
            lines.append(f"   {summary}")
        if tag_text:
            lines.append(f"   tags: {tag_text}")
        lines.append("")
    return "\n".join(lines).rstrip()


def main(argv: list[str] | None = None) -> int:
    _force_utf8_console()
    parser = argparse.ArgumentParser(description="Semantic search over the asset index")
    parser.add_argument("query", help="natural-language query (Vietnamese ok)")
    parser.add_argument("--top", "-k", type=int, default=5)
    parser.add_argument("--media", choices=("image", "video", "audio"))
    parser.add_argument("--job", help="restrict to a single job_id")
    parser.add_argument(
        "--source",
        help="restrict to 'raw_assets', 'jobs', or an exact source_root prefix",
    )
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV)
    parser.add_argument("--json", action="store_true", help="emit JSON instead of human text")
    args = parser.parse_args(argv)

    if not args.db.exists():
        print(
            f"error: database not found at {args.db}.\n"
            "Run the watcher (or process some files) first.",
            file=sys.stderr,
        )
        return 2

    try:
        rows = search_assets(
            args.query,
            k=args.top,
            media_type=args.media,
            job_id=args.job,
            source_root=args.source,
            db_path=args.db,
            env_file=args.env_file,
        )
    except EmbeddingError as exc:
        print(f"error: failed to embed query: {exc}", file=sys.stderr)
        return 1

    if args.json:
        printable = []
        for r in rows:
            entry = {k: r.get(k) for k in _DEFAULT_FIELDS}
            entry["distance"] = r.get("distance")
            entry["id"] = r.get("id")
            printable.append(entry)
        print(json.dumps(printable, ensure_ascii=False, indent=2, default=str))
    else:
        print(_format_human(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
