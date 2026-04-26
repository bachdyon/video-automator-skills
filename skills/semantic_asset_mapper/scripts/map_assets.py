#!/usr/bin/env python3
"""Create and validate semantic asset mappings from pipeline TOML artifacts."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from pipeline_utils import die, read_toml, tokenize, write_toml_document


def listify(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def asset_scene_rows(asset_data: dict[str, Any]) -> list[dict[str, Any]]:
    assets = asset_data.get("assets") or []
    flat = asset_data.get("asset_scenes") or []
    rows: list[dict[str, Any]] = []
    by_id = {asset.get("id"): asset for asset in assets}
    for scene in flat:
        asset_id = str(scene.get("id", "")).split("_SC_", 1)[0]
        asset = by_id.get(asset_id, {})
        rows.append({**scene, "asset_id": asset_id, "file_path": asset.get("file_path") or "", "asset": asset})
    for asset in assets:
        for scene in asset.get("scenes") or []:
            rows.append({**scene, "asset_id": asset.get("id"), "file_path": asset.get("file_path") or "", "asset": asset})
    if not rows:
        for asset in assets:
            rows.append(
                {
                    "id": f"{asset.get('id')}_SC_01",
                    "asset_id": asset.get("id"),
                    "file_path": asset.get("file_path") or "",
                    "start": 0.0,
                    "end": float(asset.get("duration_seconds") or 0.0),
                    "description": asset.get("summary") or "",
                    "asset": asset,
                }
            )
    return rows


def scene_intents(creative_data: dict[str, Any], transcript_data: dict[str, Any]) -> list[dict[str, Any]]:
    scenes = creative_data.get("scene_intents") or []
    if scenes:
        return scenes
    generated = []
    for index, sentence in enumerate(transcript_data.get("sentences") or [], start=1):
        generated.append(
            {
                "id": f"SC_{index:02d}",
                "start_hint": sentence.get("start"),
                "end_hint": sentence.get("end"),
                "narrative_role": "transcript_sentence",
                "spoken_text": sentence.get("sentence") or "",
                "visual_intent": sentence.get("sentence") or "",
                "mood": "",
                "preferred_shot_types": [],
                "asset_requirements": [],
            }
        )
    return generated


def scene_bounds(scene: dict[str, Any], transcript_sentences: list[dict[str, Any]], index: int, total: int, total_duration: float) -> tuple[float, float]:
    start = scene.get("start_hint")
    end = scene.get("end_hint")
    if start is not None and end is not None:
        return float(start), float(end)
    if index < len(transcript_sentences):
        sentence = transcript_sentences[index]
        return float(sentence.get("start") or 0.0), float(sentence.get("end") or 0.0)
    if total_duration > 0 and total > 0:
        span = total_duration / total
        return round(index * span, 3), round((index + 1) * span, 3)
    return float(index * 5), float((index + 1) * 5)


def score(scene: dict[str, Any], asset_scene: dict[str, Any]) -> tuple[float, list[str]]:
    scene_tokens = tokenize(
        [
            scene.get("narrative_role"),
            scene.get("spoken_text"),
            scene.get("visual_intent"),
            scene.get("mood"),
            scene.get("preferred_shot_types"),
            scene.get("asset_requirements"),
        ]
    )
    asset = asset_scene.get("asset") or {}
    asset_tokens = tokenize(
        [
            asset_scene.get("description"),
            asset_scene.get("subjects"),
            asset_scene.get("actions"),
            asset_scene.get("environment"),
            asset_scene.get("shot_type"),
            asset_scene.get("camera_motion"),
            asset_scene.get("composition"),
            asset_scene.get("colors"),
            asset_scene.get("mood"),
            asset_scene.get("semantic_tags"),
            asset_scene.get("recommended_uses"),
            asset.get("summary"),
            asset.get("visual_style"),
            asset.get("tags"),
        ]
    )
    overlap = scene_tokens & asset_tokens
    labels: list[str] = []
    base = 0.0
    if overlap:
        base += min(len(overlap) / max(len(scene_tokens), 1), 1.0) * 0.7
        labels.append("semantic")
    scene_mood = tokenize(scene.get("mood"))
    asset_mood = tokenize([asset_scene.get("mood"), asset.get("mood")])
    if scene_mood and scene_mood & asset_mood:
        base += 0.2
        labels.append("mood")
    shot_tokens = tokenize(scene.get("preferred_shot_types"))
    asset_shot = tokenize(asset_scene.get("shot_type"))
    if shot_tokens and shot_tokens & asset_shot:
        base += 0.1
        labels.append("shot_type")
    return round(min(base, 1.0), 3), labels


def validate_mapping(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    warnings: list[dict[str, str]] = []
    last_end = 0.0
    for row in sorted(rows, key=lambda item: float(item.get("start") or 0.0)):
        start = float(row.get("start") or 0.0)
        end = float(row.get("end") or 0.0)
        file_path = row.get("file_path") or ""
        if end <= start:
            warnings.append({"code": "INVALID_RANGE", "message": f"{row.get('id')} has end <= start"})
        if start > last_end + 0.05:
            warnings.append({"code": "TIMELINE_GAP", "message": f"gap before {row.get('id')} from {last_end:.3f} to {start:.3f}"})
        if start < last_end - 0.05:
            warnings.append({"code": "TIMELINE_OVERLAP", "message": f"{row.get('id')} overlaps previous mapping"})
        if file_path and not Path(file_path).exists():
            warnings.append({"code": "MISSING_FILE", "message": f"{row.get('id')} references missing file {file_path}"})
        last_end = max(last_end, end)
    return warnings


def asset_scene_duration(asset_scene: dict[str, Any]) -> float:
    start = float(asset_scene.get("start") or 0.0)
    end = float(asset_scene.get("end") or 0.0)
    duration = end - start
    if duration > 0:
        return duration
    asset = asset_scene.get("asset") or {}
    return float(asset.get("duration_seconds") or 0.0)


def asset_max_end(asset_scene: dict[str, Any]) -> float:
    """Return the maximum playable source position (asset duration cap)."""
    asset = asset_scene.get("asset") or {}
    asset_duration = float(asset.get("duration_seconds") or 0.0)
    scene_end = float(asset_scene.get("end") or 0.0)
    if asset_duration > 0:
        return max(scene_end, asset_duration)
    return scene_end


def select_cutaway_sequence(
    ranked: list[tuple[float, float, list[str], dict[str, Any]]],
    needed_duration: float,
    parent_asset_id: str,
    min_subscene_duration: float,
    min_score: float,
) -> list[dict[str, Any]]:
    """Greedy pick a sequence of asset_scenes to fill `needed_duration`.

    Diversity heuristic:
    - never reuse the same asset_scene_id within one parent scene_intent
    - de-prioritize repeating the same asset_id back-to-back
    - skip candidates with score below `min_score` (avoid totally unrelated cutaways)
    """

    selected: list[dict[str, Any]] = []
    remaining = needed_duration
    used_scene_ids: set[str] = set()
    consumed_by_asset: dict[str, float] = {}

    pool = [
        {
            "ranked_score": r[0],
            "raw_score": r[1],
            "labels": r[2],
            "asset_scene": r[3],
            "duration": asset_scene_duration(r[3]),
            "max_end": asset_max_end(r[3]),
        }
        for r in ranked
        if r[1] >= min_score and asset_scene_duration(r[3]) >= min_subscene_duration
    ]

    while remaining > min_subscene_duration and pool:
        last_asset_id = selected[-1]["asset_scene"].get("asset_id") if selected else parent_asset_id

        def diversity_key(item: dict[str, Any]) -> tuple[float, float]:
            asset_id = item["asset_scene"].get("asset_id") or ""
            penalty = 0.0
            if asset_id == last_asset_id:
                penalty += 0.25
            penalty += 0.05 * consumed_by_asset.get(asset_id, 0.0)
            return (item["ranked_score"] - penalty, item["raw_score"])

        pool.sort(key=diversity_key, reverse=True)

        pick = None
        for cand in pool:
            if cand["asset_scene"].get("id") in used_scene_ids:
                continue
            pick = cand
            break

        if pick is None:
            break

        used_scene_ids.add(pick["asset_scene"].get("id"))
        asset_id = pick["asset_scene"].get("asset_id") or ""
        consumed_by_asset[asset_id] = consumed_by_asset.get(asset_id, 0.0) + min(pick["duration"], remaining)
        selected.append(pick)
        remaining -= pick["duration"]

    return selected


def build(args: argparse.Namespace) -> None:
    creative = read_toml(args.creative_plan)
    transcript = read_toml(args.transcript) if args.transcript.exists() else {}
    assets = read_toml(args.asset_semantics)
    scenes = scene_intents(creative, transcript)
    asset_scenes = asset_scene_rows(assets)
    if not scenes:
        die("no scene intents or transcript sentences found")
    if not asset_scenes:
        die("no assets found in asset semantics")
    transcript_sentences = transcript.get("sentences") or []
    total_duration = float((transcript.get("metadata") or {}).get("duration_seconds") or 0.0)
    mappings: list[dict[str, Any]] = []
    used: dict[str, int] = {}

    cutaway_threshold = float(getattr(args, "cutaway_threshold", 0.5) or 0.5)
    min_subscene_duration = float(getattr(args, "min_subscene_duration", 0.8) or 0.8)
    min_cutaway_score = float(getattr(args, "min_cutaway_score", 0.05) or 0.05)
    enable_cutaway = bool(getattr(args, "legacy_cutaway", False))

    map_counter = 0

    for index, scene in enumerate(scenes):
        start, end = scene_bounds(scene, transcript_sentences, index, len(scenes), total_duration)
        scene_id = scene.get("id") or f"SC_{index + 1:02d}"
        scene_duration = max(0.0, end - start)

        ranked: list[tuple[float, float, list[str], dict[str, Any]]] = []
        for asset_scene in asset_scenes:
            asset_score, labels = score(scene, asset_scene)
            reuse_penalty = used.get(asset_scene.get("id"), 0) * 0.05
            ranked.append((asset_score - reuse_penalty, asset_score, labels, asset_scene))
        ranked.sort(key=lambda item: item[0], reverse=True)

        _, best_fit_score, best_labels, best_selected = ranked[0]
        best_max_end = asset_max_end(best_selected)
        best_source_start = float(best_selected.get("start") or 0.0)
        best_available_dur = max(0.0, best_max_end - best_source_start)

        cutaway_chunks: list[dict[str, Any]] = []

        if (
            enable_cutaway
            and scene_duration > best_available_dur + cutaway_threshold
            and scene_duration > min_subscene_duration * 2
        ):
            needed_after_primary = scene_duration - best_available_dur
            extra = select_cutaway_sequence(
                [r for r in ranked if r[3].get("id") != best_selected.get("id")],
                needed_after_primary + cutaway_threshold,
                best_selected.get("asset_id") or "",
                min_subscene_duration=min_subscene_duration,
                min_score=min_cutaway_score,
            )
            if extra:
                primary_chunk = {
                    "ranked_score": ranked[0][0],
                    "raw_score": best_fit_score,
                    "labels": best_labels,
                    "asset_scene": best_selected,
                    "duration": best_available_dur,
                    "max_end": best_max_end,
                }
                cutaway_chunks = [primary_chunk] + extra

        if cutaway_chunks:
            total_chunks = len(cutaway_chunks)
            cursor = start
            remaining = scene_duration
            for sub_index, chunk in enumerate(cutaway_chunks):
                is_last = sub_index == total_chunks - 1
                chunk_dur = chunk["duration"]
                take_dur = min(chunk_dur, remaining) if not is_last else remaining
                if take_dur < min_subscene_duration and not is_last:
                    take_dur = min(remaining, min_subscene_duration)
                if is_last and take_dur > chunk_dur + cutaway_threshold:
                    take_dur = chunk_dur

                sub_start = cursor
                sub_end = min(end, cursor + take_dur)
                src_start = float(chunk["asset_scene"].get("start") or 0.0)
                src_end = src_start + (sub_end - sub_start)
                if src_end > chunk["max_end"]:
                    src_end = chunk["max_end"]

                map_counter += 1
                used[chunk["asset_scene"].get("id")] = used.get(chunk["asset_scene"].get("id"), 0) + 1
                role = "primary" if sub_index == 0 else f"cutaway_{sub_index}"
                reason = (
                    f"Cutaway chunk {sub_index + 1}/{total_chunks} for {scene_id}"
                    f" — fills {scene_duration:.2f}s by stitching {total_chunks} different shots"
                )
                if scene.get("visual_intent"):
                    reason += f" (intent: {scene.get('visual_intent')})"
                warnings_row: list[str] = []
                if (sub_end - sub_start) > (src_end - src_start) + 0.05:
                    warnings_row.append("SUBCLIP_SHORT_SOURCE")

                mappings.append(
                    {
                        "id": f"MAP_{map_counter:03d}",
                        "scene_id": scene_id,
                        "subdivision_role": role,
                        "subdivision_index": sub_index + 1,
                        "subdivision_total": total_chunks,
                        "asset_id": chunk["asset_scene"].get("asset_id") or "",
                        "asset_scene_id": chunk["asset_scene"].get("id") or "",
                        "start": round(sub_start, 3),
                        "end": round(sub_end, 3),
                        "file_path": chunk["asset_scene"].get("file_path") or "",
                        "source_start": round(src_start, 3),
                        "source_end": round(src_end, 3),
                        "fit_score": chunk["raw_score"],
                        "fit_labels": chunk["labels"],
                        "reason": reason,
                        "fallback": chunk["raw_score"] == 0.0,
                        "warnings": warnings_row,
                    }
                )
                cursor = sub_end
                remaining = max(0.0, end - cursor)
                if remaining <= 0.001:
                    break
        else:
            map_counter += 1
            used[best_selected.get("id")] = used.get(best_selected.get("id"), 0) + 1
            src_start = float(best_selected.get("start") or 0.0)
            src_end_default = float(best_selected.get("end") or 0.0)
            extended_src_end = max(src_end_default, src_start + scene_duration)
            if extended_src_end > best_max_end:
                extended_src_end = best_max_end
            reason = "Best available semantic match"
            if best_labels:
                reason += f" by {', '.join(best_labels)}"
            if scene.get("visual_intent"):
                reason += f" for: {scene.get('visual_intent')}"
            warnings_row = []
            if scene_duration > (extended_src_end - src_start) + cutaway_threshold:
                warnings_row.append("SOURCE_SHORTER_THAN_TIMELINE")
            mappings.append(
                {
                    "id": f"MAP_{map_counter:03d}",
                    "scene_id": scene_id,
                    "subdivision_role": "primary",
                    "subdivision_index": 1,
                    "subdivision_total": 1,
                    "asset_id": best_selected.get("asset_id") or "",
                    "asset_scene_id": best_selected.get("id") or "",
                    "start": round(start, 3),
                    "end": round(end, 3),
                    "file_path": best_selected.get("file_path") or "",
                    "source_start": round(src_start, 3),
                    "source_end": round(extended_src_end, 3),
                    "fit_score": best_fit_score,
                    "fit_labels": best_labels,
                    "reason": reason,
                    "fallback": best_fit_score == 0.0,
                    "warnings": warnings_row,
                }
            )

    warnings = validate_mapping(mappings)
    write_toml_document(args.output, [("mappings", mappings), ("warnings", warnings)])
    print(f"wrote {args.output} with {len(mappings)} mappings and {len(warnings)} warnings")


def validate(args: argparse.Namespace) -> None:
    data = read_toml(args.mapping)
    warnings = validate_mapping(data.get("mappings") or [])
    if warnings:
        for warning in warnings:
            print(f"{warning['code']}: {warning['message']}")
        raise SystemExit(1)
    print("semantic mapping validation passed")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build_parser = sub.add_parser("build")
    build_parser.add_argument("--creative-plan", type=Path, default=Path("source/creative_plan.toml"))
    build_parser.add_argument("--transcript", type=Path, default=Path("source/transcript_word_level.toml"))
    build_parser.add_argument("--asset-semantics", type=Path, default=Path("source/asset_semantics.toml"))
    build_parser.add_argument("--output", type=Path, default=Path("source/semantic_mapping.toml"))
    build_parser.add_argument(
        "--cutaway-threshold",
        type=float,
        default=0.5,
        help="Trigger subdivide when (timeline_dur - best_source_dur) > this many seconds.",
    )
    build_parser.add_argument(
        "--min-subscene-duration",
        type=float,
        default=0.8,
        help="Minimum duration per cutaway sub-clip in seconds.",
    )
    build_parser.add_argument(
        "--min-cutaway-score",
        type=float,
        default=0.05,
        help="Minimum semantic fit score required for a cutaway candidate.",
    )
    build_parser.add_argument(
        "--no-cutaway",
        action="store_true",
        help="(Default behaviour now) Disable cutaway subdivide. Kept for back-compat with old scripts.",
    )
    build_parser.add_argument(
        "--legacy-cutaway",
        action="store_true",
        help="Re-enable the deprecated heuristic cutaway algorithm. Production should use shot-coverage-planner instead.",
    )
    build_parser.set_defaults(func=build)
    validate_parser = sub.add_parser("validate")
    validate_parser.add_argument("--mapping", type=Path, default=Path("source/semantic_mapping.toml"))
    validate_parser.set_defaults(func=validate)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
