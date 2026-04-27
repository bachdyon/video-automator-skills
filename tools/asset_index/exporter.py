"""Export assets from the SQLite vector index to ``asset_semantics.toml``.

Replaces the heavy probe + Gemini Vision pass with a fast DB read whenever
files have already been indexed by the watcher. Files that are not yet in
the DB can be auto-indexed in place via ``tools.asset_index.router`` so each
file goes through Gemini at most once across its lifetime.

Usage:

    # Export every asset under one folder
    python -m tools.asset_index.exporter raw_assets/ \
        --output source/asset_semantics.toml

    # Job-scoped export (auto-indexes any new file before exporting)
    python -m tools.asset_index.exporter jobs/<id>/input/raw_assets/ \
        --output jobs/<id>/source/asset_semantics.toml

    # Selective export driven by a creative plan (vector-search per scene intent)
    python -m tools.asset_index.exporter \
        --from-creative-plan jobs/<id>/source/creative_plan.toml \
        --output jobs/<id>/source/asset_semantics.toml \
        --top-per-intent 5

The output schema matches what ``probe_assets.py`` + ``analyze_with_gemini.py``
produce together, so ``semantic-asset-mapper`` and ``shot-coverage-planner``
can consume it without modification.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable

from skills._shared.pipeline_utils import (  # type: ignore
    MEDIA_IMAGE_EXTENSIONS,
    MEDIA_VIDEO_EXTENSIONS,
    read_toml,
    write_toml_document,
)
from tools.asset_index import store
from tools.asset_index.embed import embed_text

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = WORKSPACE_ROOT / ".asset_index" / "index.db"
DEFAULT_ENV = WORKSPACE_ROOT / ".env"


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


def _discover_media_files(paths: Iterable[Path]) -> list[Path]:
    """Walk inputs and return every supported image/video file (sorted, unique)."""
    files: list[Path] = []
    seen: set[Path] = set()
    valid_suffixes = MEDIA_IMAGE_EXTENSIONS | MEDIA_VIDEO_EXTENSIONS
    for raw in paths:
        path = Path(raw).resolve()
        if path.is_file():
            if path.suffix.lower() in valid_suffixes and path not in seen:
                seen.add(path)
                files.append(path)
        elif path.is_dir():
            for item in sorted(path.rglob("*")):
                if item.is_file() and item.suffix.lower() in valid_suffixes and item not in seen:
                    seen.add(item)
                    files.append(item)
    return files


# ---------------------------------------------------------------------------
# DB row -> TOML record conversion
# ---------------------------------------------------------------------------


def _maybe_json(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, str):
        if not value.strip():
            return default
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return default
    return value


def _string_list(value: Any) -> list[str]:
    parsed = _maybe_json(value, [])
    if isinstance(parsed, list):
        return [str(item) for item in parsed if item is not None]
    return []


def _build_video_record(row: dict[str, Any], asset_id: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Convert a DB video row into one ``[[assets]]`` entry + N ``[[asset_scenes]]`` entries."""
    raw = _maybe_json(row.get("raw_json"), {})
    raw_asset = (raw.get("asset") if isinstance(raw, dict) else {}) or {}
    db_scenes = _maybe_json(row.get("scenes_json"), [])
    if not isinstance(db_scenes, list):
        db_scenes = []

    duration = float(row.get("duration_seconds") or raw_asset.get("duration_seconds") or 0.0)

    asset_record = {
        "id": asset_id,
        "file_path": row.get("file_path") or "",
        "type": "video",
        "duration_seconds": duration,
        "width": int(row.get("width") or raw_asset.get("width") or 0),
        "height": int(row.get("height") or raw_asset.get("height") or 0),
        "fps": float(row.get("fps") or raw_asset.get("fps") or 0.0),
        "has_audio": bool(row.get("has_audio") or raw_asset.get("has_audio")),
        "summary": (row.get("summary") or raw_asset.get("summary") or "").strip(),
        "visual_style": (row.get("style") or raw_asset.get("visual_style") or "").strip(),
        "mood": _string_list(row.get("mood_json")) or list(raw_asset.get("mood") or []),
        "tags": _string_list(row.get("tags_json")) or list(raw_asset.get("tags") or []),
        "privacy_notes": list(raw_asset.get("privacy_notes") or []),
        "quality_notes": list(raw_asset.get("quality_notes") or []),
    }

    scenes: list[dict[str, Any]] = []
    for index, scene in enumerate(db_scenes, start=1):
        if not isinstance(scene, dict):
            continue
        scenes.append(
            {
                "id": f"{asset_id}_SC_{index:02d}",
                "start": round(float(scene.get("start") or 0.0), 3),
                "end": round(float(scene.get("end") or duration), 3),
                "description": (scene.get("description") or "").strip(),
                "subjects": list(scene.get("subjects") or []),
                "actions": list(scene.get("actions") or []),
                "environment": (scene.get("environment") or "").strip(),
                "shot_type": (scene.get("shot_type") or "").strip(),
                "camera_motion": (scene.get("camera_motion") or "").strip(),
                "composition": (scene.get("composition") or "").strip(),
                "colors": list(scene.get("colors") or []),
                "mood": list(scene.get("mood") or []),
                "semantic_tags": list(scene.get("semantic_tags") or []),
                "recommended_uses": list(scene.get("recommended_uses") or []),
                "avoid_uses": list(scene.get("avoid_uses") or []),
                "sample_frames": list(scene.get("sample_frames") or []),
            }
        )

    if not scenes:
        scenes.append(
            {
                "id": f"{asset_id}_SC_01",
                "start": 0.0,
                "end": duration,
                "description": asset_record["summary"],
                "subjects": [],
                "actions": [],
                "environment": "",
                "shot_type": "",
                "camera_motion": "",
                "composition": "",
                "colors": [],
                "mood": asset_record["mood"],
                "semantic_tags": asset_record["tags"],
                "recommended_uses": [],
                "avoid_uses": [],
                "sample_frames": [],
            }
        )
    return asset_record, scenes


def _build_image_record(row: dict[str, Any], asset_id: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Convert a DB image row into one ``[[assets]]`` entry + 1 ``[[asset_scenes]]`` entry."""
    raw = _maybe_json(row.get("raw_json"), {})
    gemini = (raw.get("gemini") if isinstance(raw, dict) else {}) or {}

    asset_record = {
        "id": asset_id,
        "file_path": row.get("file_path") or "",
        "type": "image",
        "duration_seconds": 0.0,
        "width": int(row.get("width") or 0),
        "height": int(row.get("height") or 0),
        "fps": 0.0,
        "has_audio": False,
        "summary": (row.get("summary") or gemini.get("summary") or "").strip(),
        "visual_style": (row.get("style") or gemini.get("visual_style") or "").strip(),
        "mood": _string_list(row.get("mood_json")) or list(gemini.get("mood") or []),
        "tags": _string_list(row.get("tags_json")) or list(gemini.get("tags") or []),
        "privacy_notes": list(gemini.get("privacy_notes") or []),
        "quality_notes": list(gemini.get("quality_notes") or []),
    }

    scene = {
        "id": f"{asset_id}_SC_01",
        "start": 0.0,
        "end": 0.0,
        "description": (gemini.get("summary") or asset_record["summary"]).strip(),
        "subjects": list(gemini.get("subjects") or []),
        "actions": list(gemini.get("actions") or []),
        "environment": (gemini.get("environment") or "").strip(),
        "shot_type": (gemini.get("shot_type") or "").strip(),
        "camera_motion": "",
        "composition": (gemini.get("composition") or "").strip(),
        "colors": list(gemini.get("colors") or []),
        "mood": list(gemini.get("mood") or asset_record["mood"]),
        "semantic_tags": list(gemini.get("tags") or asset_record["tags"]),
        "recommended_uses": list(gemini.get("recommended_uses") or []),
        "avoid_uses": list(gemini.get("avoid_uses") or []),
        "sample_frames": [],
    }
    return asset_record, [scene]


def _row_to_toml(row: dict[str, Any], asset_id: str) -> tuple[dict[str, Any], list[dict[str, Any]]] | None:
    media_type = (row.get("media_type") or "").lower()
    if media_type == "video":
        return _build_video_record(row, asset_id)
    if media_type == "image":
        return _build_image_record(row, asset_id)
    return None


# ---------------------------------------------------------------------------
# Auto-index on demand
# ---------------------------------------------------------------------------


def _ensure_indexed(
    files: list[Path],
    *,
    conn: Any,
    env_file: Path,
    auto_index: bool,
) -> tuple[list[dict[str, Any]], list[str], int]:
    """For each file, return its DB row (looking up by path).

    When a file is missing and ``auto_index`` is True we run the router so
    Gemini analyzes it once and we can pull the row right after. Returns
    ``(rows_in_input_order, warnings, indexed_now_count)``.
    """
    from tools.asset_index.router import process_file  # local import avoids circular

    rows: list[dict[str, Any]] = []
    warnings: list[str] = []
    indexed_now = 0
    for src in files:
        existing = store.get_by_path(conn, src)
        if existing is None and auto_index:
            print(f"[exporter] indexing on demand: {src}", file=sys.stderr)
            result = process_file(src, conn=conn, env_file=env_file)
            status = result.get("status")
            if status == "ok":
                indexed_now += 1
                existing = store.get_by_path(conn, src)
            else:
                warnings.append(
                    f"INDEX_FAILED: {src} ({status}: {result.get('reason') or 'unknown'})"
                )
                continue
        if existing is None:
            warnings.append(f"NOT_INDEXED: {src} (skipped; pass --auto-index or run watcher)")
            continue
        rows.append(existing)
    return rows, warnings, indexed_now


# ---------------------------------------------------------------------------
# Folder mode
# ---------------------------------------------------------------------------


def export_paths(
    inputs: Iterable[str | Path],
    *,
    output: str | Path,
    db_path: str | Path = DEFAULT_DB,
    env_file: str | Path = DEFAULT_ENV,
    auto_index: bool = True,
) -> dict[str, Any]:
    """Export every supported file under ``inputs`` to a TOML at ``output``."""
    db_path = Path(db_path)
    if not db_path.exists() and not auto_index:
        raise FileNotFoundError(
            f"asset-index DB not found at {db_path}. Start the watcher or pass --auto-index."
        )
    files = _discover_media_files([Path(p) for p in inputs])
    if not files:
        raise FileNotFoundError("no image/video files discovered under the given paths")

    conn = store.open_db(db_path)
    try:
        rows, warnings, indexed_now = _ensure_indexed(
            files,
            conn=conn,
            env_file=Path(env_file),
            auto_index=auto_index,
        )
    finally:
        conn.close()

    return _write_toml_from_rows(rows, output=Path(output), warnings=warnings, indexed_now=indexed_now)


# ---------------------------------------------------------------------------
# Creative-plan / scene-intent mode (vector search)
# ---------------------------------------------------------------------------


def _intent_query(scene: dict[str, Any]) -> str:
    parts = [
        scene.get("narrative_role"),
        scene.get("visual_intent"),
        scene.get("spoken_text"),
        scene.get("mood"),
    ]
    asset_reqs = scene.get("asset_requirements") or []
    if isinstance(asset_reqs, list):
        parts.extend(str(item) for item in asset_reqs)
    flat: list[str] = []
    for item in parts:
        if item is None:
            continue
        if isinstance(item, list):
            flat.extend(str(x) for x in item if x is not None)
        else:
            flat.append(str(item))
    return " ".join(s.strip() for s in flat if s and s.strip())


def export_for_creative_plan(
    creative_plan_toml: str | Path,
    *,
    output: str | Path,
    db_path: str | Path = DEFAULT_DB,
    env_file: str | Path = DEFAULT_ENV,
    top_per_intent: int = 5,
    job_id: str | None = None,
    source_root: str | None = None,
    media_filter: str | None = None,
) -> dict[str, Any]:
    """Pick assets from the DB by vector-searching each scene intent.

    Useful when the raw_assets pool is large and you only want the TOML to
    hold the assets relevant to the new video. Each intent contributes the
    top ``top_per_intent`` matches (deduped across intents).
    """
    db_path = Path(db_path)
    if not db_path.exists():
        raise FileNotFoundError(
            f"asset-index DB not found at {db_path}. Start the watcher first."
        )
    creative = read_toml(Path(creative_plan_toml))
    intents = creative.get("scene_intents") or []
    if not intents:
        raise ValueError(f"no [[scene_intents]] in {creative_plan_toml}")

    queries = [_intent_query(scene) for scene in intents]
    queries = [q for q in queries if q]
    if not queries:
        raise ValueError("scene intents had no usable text for vector queries")

    conn = store.open_db(db_path)
    try:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        warnings: list[str] = []
        for query in queries:
            try:
                vec = embed_text(query, env_file=Path(env_file))
            except Exception as exc:  # noqa: BLE001
                warnings.append(f"EMBED_FAILED: {query[:60]!r}: {exc}")
                continue
            hits = store.search(
                conn,
                vec,
                k=top_per_intent,
                media_type=media_filter,
                job_id=job_id,
                source_root=source_root,
            )
            for hit in hits:
                asset_id = hit.get("id")
                if asset_id in seen:
                    continue
                seen.add(asset_id)
                rows.append(hit)
    finally:
        conn.close()

    if not rows:
        raise RuntimeError(
            "vector search returned no results; check that raw_assets are indexed and DB is populated"
        )
    return _write_toml_from_rows(rows, output=Path(output), warnings=warnings, indexed_now=0)


# ---------------------------------------------------------------------------
# Shared writer
# ---------------------------------------------------------------------------


def _write_toml_from_rows(
    rows: list[dict[str, Any]],
    *,
    output: Path,
    warnings: list[str],
    indexed_now: int,
) -> dict[str, Any]:
    rows_sorted = sorted(rows, key=lambda r: r.get("file_path") or "")
    asset_records: list[dict[str, Any]] = []
    scene_records: list[dict[str, Any]] = []
    for index, row in enumerate(rows_sorted, start=1):
        asset_id = f"AST_{index:03d}"
        built = _row_to_toml(row, asset_id)
        if built is None:
            warnings.append(
                f"UNSUPPORTED_MEDIA: {row.get('file_path')} type={row.get('media_type')}"
            )
            continue
        asset_record, scenes = built
        asset_records.append(asset_record)
        scene_records.extend(scenes)

    sections: list[tuple[str | None, dict[str, Any] | list[dict[str, Any]]]] = [
        ("assets", asset_records),
        ("asset_scenes", scene_records),
    ]
    if warnings:
        warning_rows: list[dict[str, str]] = []
        for warning in warnings:
            if ":" in warning:
                code, msg = warning.split(":", 1)
            else:
                code, msg = "INFO", warning
            warning_rows.append({"code": code.strip(), "message": msg.strip()})
        sections.append(("warnings", warning_rows))
    write_toml_document(output, sections)
    summary = {
        "output": str(output),
        "assets": len(asset_records),
        "scenes": len(scene_records),
        "indexed_now": indexed_now,
        "warnings": warnings,
    }
    return summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("inputs", nargs="*", type=Path, help="folders or files to export")
    parser.add_argument("--output", type=Path, required=True, help="destination TOML path")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV)
    parser.add_argument(
        "--no-auto-index",
        action="store_true",
        help="skip files that are not yet in the DB instead of indexing on demand",
    )
    parser.add_argument(
        "--from-creative-plan",
        type=Path,
        help="instead of scanning a folder, vector-search assets per scene_intent in this creative plan",
    )
    parser.add_argument("--top-per-intent", type=int, default=5)
    parser.add_argument("--job-id", help="restrict creative-plan search to one job_id")
    parser.add_argument("--source-root", help="restrict creative-plan search to a specific source_root or 'raw_assets' / 'jobs'")
    parser.add_argument("--media", choices=("image", "video"), help="restrict creative-plan search by media type")
    return parser


def _main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.from_creative_plan:
            summary = export_for_creative_plan(
                args.from_creative_plan,
                output=args.output,
                db_path=args.db,
                env_file=args.env_file,
                top_per_intent=args.top_per_intent,
                job_id=args.job_id,
                source_root=args.source_root,
                media_filter=args.media,
            )
        else:
            if not args.inputs:
                print(
                    "error: provide folders/files OR --from-creative-plan",
                    file=sys.stderr,
                )
                return 2
            summary = export_paths(
                args.inputs,
                output=args.output,
                db_path=args.db,
                env_file=args.env_file,
                auto_index=not args.no_auto_index,
            )
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(
        f"wrote {summary['output']} with {summary['assets']} assets, "
        f"{summary['scenes']} scenes, indexed_now={summary['indexed_now']}, "
        f"warnings={len(summary['warnings'])}"
    )
    if summary["warnings"]:
        for warning in summary["warnings"]:
            print(f"  warn: {warning}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(_main())
