#!/usr/bin/env python3
"""Mechanical context-pack builder for shot-coverage-planner.

This script does NOT make creative decisions. It scans the baseline
semantic_mapping.toml plus the surrounding artifacts and emits a JSON
context pack so the agent can reason about coverage gaps and asset
repetition in one place.

Output JSON structure:

{
  "summary": {
    "total_scenes": int,
    "scenes_with_shortage": int,
    "scenes_with_overuse": int,
    "shortage_threshold_seconds": float,
    "repetition_threshold": int
  },
  "usage_stats": {
    "asset_id_counts": {"AST_001": 3, ...},
    "asset_scene_id_counts": {"AST_001_SC_01": 2, ...},
    "over_used_asset_ids": ["AST_003"]
  },
  "gaps": [
    {
      "scene_id": "SC_02",
      "trigger": ["shortage", "overuse"],
      "scene_intent": { ... full creative_plan row ... },
      "spoken_excerpt": "...",
      "timeline_duration": 12.0,
      "current_primary": {
        "asset_id": "AST_006",
        "asset_scene_id": "AST_006_SC_01",
        "available_source_duration": 4.0,
        "shortage_seconds": 8.0,
        "fit_score": 0.5
      },
      "candidate_pool": [
        {
          "asset_scene_id": "AST_005_SC_02",
          "asset_id": "AST_005",
          "file_path": "...",
          "asset_scene_start": 8.0,
          "asset_scene_end": 12.0,
          "available_duration": 4.0,
          "description": "...",
          "subjects": [...],
          "actions": [...],
          "shot_type": "...",
          "mood": [...],
          "colors": [...],
          "semantic_tags": [...],
          "recommended_uses": [...],
          "avoid_uses": [...],
          "times_used_in_baseline": 0,
          "asset_id_use_count": 0
        },
        ...
      ]
    }
  ]
}
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from pipeline_utils import die, read_toml


def asset_index(asset_data: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """Return (asset_by_id, asset_scene_by_id). asset_scene rows are flattened from
    both top-level [[asset_scenes]] and nested asset.scenes."""
    asset_by_id: dict[str, dict[str, Any]] = {}
    for asset in asset_data.get("assets") or []:
        asset_by_id[str(asset.get("id"))] = asset

    asset_scene_by_id: dict[str, dict[str, Any]] = {}

    for scene in asset_data.get("asset_scenes") or []:
        scene_id = str(scene.get("id") or "")
        if not scene_id:
            continue
        parent_asset_id = scene_id.split("_SC_", 1)[0]
        asset = asset_by_id.get(parent_asset_id, {})
        enriched = {
            **scene,
            "asset_id": parent_asset_id,
            "file_path": asset.get("file_path") or scene.get("file_path") or "",
            "_asset_duration": float(asset.get("duration_seconds") or 0.0),
        }
        asset_scene_by_id[scene_id] = enriched

    for asset in asset_data.get("assets") or []:
        for scene in asset.get("scenes") or []:
            scene_id = str(scene.get("id") or "")
            if not scene_id or scene_id in asset_scene_by_id:
                continue
            enriched = {
                **scene,
                "asset_id": str(asset.get("id")),
                "file_path": asset.get("file_path") or "",
                "_asset_duration": float(asset.get("duration_seconds") or 0.0),
            }
            asset_scene_by_id[scene_id] = enriched

    return asset_by_id, asset_scene_by_id


def asset_scene_available_duration(scene: dict[str, Any]) -> float:
    """Maximum continuous source range we can play from this asset_scene without
    exceeding the parent asset duration."""
    start = float(scene.get("start") or 0.0)
    end = float(scene.get("end") or 0.0)
    asset_dur = float(scene.get("_asset_duration") or 0.0)
    physical_end = max(end, asset_dur) if asset_dur else end
    return max(0.0, physical_end - start)


def scene_intent_index(creative: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(s.get("id")): s for s in creative.get("scene_intents") or [] if s.get("id")}


def transcript_excerpt(transcript: dict[str, Any], start: float, end: float) -> str:
    sentences = transcript.get("sentences") or []
    chosen: list[str] = []
    for s in sentences:
        s_start = float(s.get("start") or 0.0)
        s_end = float(s.get("end") or 0.0)
        if s_end < start or s_start > end:
            continue
        chosen.append(str(s.get("sentence") or ""))
    return " ".join(t.strip() for t in chosen if t.strip())


def candidate_row(scene: dict[str, Any], baseline_scene_use: int, baseline_asset_use: int) -> dict[str, Any]:
    return {
        "asset_scene_id": scene.get("id"),
        "asset_id": scene.get("asset_id"),
        "file_path": scene.get("file_path"),
        "asset_scene_start": float(scene.get("start") or 0.0),
        "asset_scene_end": float(scene.get("end") or 0.0),
        "available_duration": round(asset_scene_available_duration(scene), 3),
        "description": scene.get("description") or "",
        "subjects": scene.get("subjects") or [],
        "actions": scene.get("actions") or [],
        "environment": scene.get("environment") or "",
        "shot_type": scene.get("shot_type") or "",
        "camera_motion": scene.get("camera_motion") or "",
        "composition": scene.get("composition") or "",
        "mood": scene.get("mood") or [],
        "colors": scene.get("colors") or [],
        "semantic_tags": scene.get("semantic_tags") or [],
        "recommended_uses": scene.get("recommended_uses") or [],
        "avoid_uses": scene.get("avoid_uses") or [],
        "times_used_in_baseline": baseline_scene_use,
        "asset_id_use_count": baseline_asset_use,
    }


def build_context(args: argparse.Namespace) -> dict[str, Any]:
    mapping_doc = read_toml(args.mapping)
    creative_doc = read_toml(args.creative_plan) if args.creative_plan.exists() else {}
    transcript_doc = read_toml(args.transcript) if args.transcript.exists() else {}
    asset_doc = read_toml(args.asset_semantics)

    mappings: list[dict[str, Any]] = mapping_doc.get("mappings") or []
    if not mappings:
        die("baseline semantic_mapping.toml has no [[mappings]] rows")

    asset_by_id, asset_scene_by_id = asset_index(asset_doc)
    intents = scene_intent_index(creative_doc)

    asset_id_counts = Counter(str(m.get("asset_id") or "") for m in mappings if m.get("asset_id"))
    asset_scene_id_counts = Counter(str(m.get("asset_scene_id") or "") for m in mappings if m.get("asset_scene_id"))
    over_used_asset_ids = sorted(
        aid for aid, n in asset_id_counts.items() if n >= args.repetition_threshold
    )

    # Group baseline rows by scene_id so we evaluate one decision per scene_intent
    by_scene: dict[str, list[dict[str, Any]]] = {}
    for m in mappings:
        sid = str(m.get("scene_id") or "")
        if not sid:
            continue
        by_scene.setdefault(sid, []).append(m)

    gaps: list[dict[str, Any]] = []
    scenes_with_shortage = 0
    scenes_with_overuse = 0

    for scene_id in sorted(by_scene.keys()):
        rows = sorted(by_scene[scene_id], key=lambda r: float(r.get("start") or 0.0))
        timeline_start = float(rows[0].get("start") or 0.0)
        timeline_end = float(rows[-1].get("end") or 0.0)
        timeline_duration = max(0.0, timeline_end - timeline_start)

        # The "primary" baseline pick is the first row of the scene (rank 0 from mapper)
        primary = rows[0]
        primary_scene_id = str(primary.get("asset_scene_id") or "")
        primary_asset = asset_scene_by_id.get(primary_scene_id, {})
        primary_available = asset_scene_available_duration(primary_asset)
        shortage = max(0.0, timeline_duration - primary_available)
        over_used = (str(primary.get("asset_id") or "") in over_used_asset_ids)

        triggers: list[str] = []
        if shortage > args.shortage_threshold:
            triggers.append("shortage")
            scenes_with_shortage += 1
        if over_used:
            triggers.append("overuse")
            scenes_with_overuse += 1

        if not triggers:
            continue

        intent = intents.get(scene_id) or {}
        excerpt = transcript_excerpt(transcript_doc, timeline_start, timeline_end)

        candidates: list[dict[str, Any]] = []
        for cand_id, cand in asset_scene_by_id.items():
            if cand_id == primary_scene_id:
                continue
            row = candidate_row(
                cand,
                baseline_scene_use=asset_scene_id_counts.get(cand_id, 0),
                baseline_asset_use=asset_id_counts.get(cand.get("asset_id") or "", 0),
            )
            candidates.append(row)
        candidates.sort(
            key=lambda c: (
                -c["available_duration"],
                c["asset_id_use_count"],
                c["times_used_in_baseline"],
            )
        )

        gaps.append(
            {
                "scene_id": scene_id,
                "trigger": triggers,
                "timeline_start": round(timeline_start, 3),
                "timeline_end": round(timeline_end, 3),
                "timeline_duration": round(timeline_duration, 3),
                "spoken_excerpt": excerpt,
                "scene_intent": {
                    "id": intent.get("id") or scene_id,
                    "narrative_role": intent.get("narrative_role") or "",
                    "visual_intent": intent.get("visual_intent") or "",
                    "mood": intent.get("mood") or "",
                    "preferred_shot_types": intent.get("preferred_shot_types") or [],
                    "asset_requirements": intent.get("asset_requirements") or [],
                    "voiceover_excerpt": intent.get("voiceover_excerpt") or excerpt,
                },
                "current_primary": {
                    "asset_id": primary.get("asset_id"),
                    "asset_scene_id": primary_scene_id,
                    "file_path": primary.get("file_path"),
                    "available_source_duration": round(primary_available, 3),
                    "source_start": float(primary.get("source_start") or 0.0),
                    "source_end": float(primary.get("source_end") or 0.0),
                    "shortage_seconds": round(shortage, 3),
                    "fit_score": float(primary.get("fit_score") or 0.0),
                    "fit_labels": primary.get("fit_labels") or [],
                    "asset_id_use_count": asset_id_counts.get(str(primary.get("asset_id") or ""), 0),
                    "primary_description": primary_asset.get("description") or "",
                    "primary_mood": primary_asset.get("mood") or [],
                    "primary_shot_type": primary_asset.get("shot_type") or "",
                },
                "candidate_pool": candidates,
            }
        )

    return {
        "summary": {
            "total_scenes": len(by_scene),
            "scenes_with_shortage": scenes_with_shortage,
            "scenes_with_overuse": scenes_with_overuse,
            "shortage_threshold_seconds": args.shortage_threshold,
            "repetition_threshold": args.repetition_threshold,
        },
        "usage_stats": {
            "asset_id_counts": dict(asset_id_counts),
            "asset_scene_id_counts": dict(asset_scene_id_counts),
            "over_used_asset_ids": over_used_asset_ids,
        },
        "gaps": gaps,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--asset-semantics", type=Path, required=True)
    parser.add_argument("--creative-plan", type=Path, default=Path("source/creative_plan.toml"))
    parser.add_argument("--transcript", type=Path, default=Path("source/transcript_word_level.toml"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--shortage-threshold",
        type=float,
        default=0.5,
        help="Trigger gap if (timeline_duration - source_duration) > this.",
    )
    parser.add_argument(
        "--repetition-threshold",
        type=int,
        default=3,
        help="Flag asset_id as over-used when its baseline use count >= this.",
    )
    args = parser.parse_args()

    context = build_context(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(context, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = context["summary"]
    print(
        f"wrote {args.output}: "
        f"{summary['scenes_with_shortage']} shortage / "
        f"{summary['scenes_with_overuse']} overuse "
        f"out of {summary['total_scenes']} scenes "
        f"(shortage>{args.shortage_threshold}s, repetition>={args.repetition_threshold})"
    )


if __name__ == "__main__":
    main()
