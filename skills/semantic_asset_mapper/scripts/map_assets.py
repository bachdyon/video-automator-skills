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
    for index, scene in enumerate(scenes):
        start, end = scene_bounds(scene, transcript_sentences, index, len(scenes), total_duration)
        ranked = []
        for asset_scene in asset_scenes:
            asset_score, labels = score(scene, asset_scene)
            reuse_penalty = used.get(asset_scene.get("id"), 0) * 0.05
            ranked.append((asset_score - reuse_penalty, asset_score, labels, asset_scene))
        ranked.sort(key=lambda item: item[0], reverse=True)
        _, fit_score, labels, selected = ranked[0]
        used[selected.get("id")] = used.get(selected.get("id"), 0) + 1
        reason = "Best available semantic match"
        if labels:
            reason += f" by {', '.join(labels)}"
        if scene.get("visual_intent"):
            reason += f" for: {scene.get('visual_intent')}"
        mappings.append(
            {
                "id": f"MAP_{index + 1:03d}",
                "scene_id": scene.get("id") or f"SC_{index + 1:02d}",
                "asset_id": selected.get("asset_id") or "",
                "asset_scene_id": selected.get("id") or "",
                "start": round(start, 3),
                "end": round(end, 3),
                "file_path": selected.get("file_path") or "",
                "source_start": float(selected.get("start") or 0.0),
                "source_end": float(selected.get("end") or 0.0),
                "fit_score": fit_score,
                "fit_labels": labels,
                "reason": reason,
                "fallback": fit_score == 0.0,
                "warnings": [],
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
    build_parser.set_defaults(func=build)
    validate_parser = sub.add_parser("validate")
    validate_parser.add_argument("--mapping", type=Path, default=Path("source/semantic_mapping.toml"))
    validate_parser.set_defaults(func=validate)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
