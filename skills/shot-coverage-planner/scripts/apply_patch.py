#!/usr/bin/env python3
"""Apply agent-authored coverage decisions JSON onto a baseline semantic_mapping.toml.

The agent owns every creative choice (which strategy, which asset, which slice
of source). This script only:

1. Reads the baseline TOML.
2. Reads decisions JSON (one entry per scene_id).
3. Validates each decision (asset_scene exists, source range fits, sub-clip
   timeline is continuous and matches baseline scene span, min sub-clip
   duration, playback_rate sane).
4. Replaces all baseline rows for affected scene_ids with the agent's
   sub-clips, renumbering MAP ids globally.
5. Writes the new TOML.

Refuses to overwrite output if validation fails.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from pipeline_utils import die, read_toml, write_toml_document


VALID_STRATEGIES = {"cutaway_subdivision", "slowdown", "hold_and_kenburns", "keep"}
MIN_SUBCLIP_DURATION = 0.6
TIMELINE_TOL = 0.05
PLAYBACK_RATE_RANGE = (0.5, 1.5)


def asset_scene_index(asset_data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    asset_by_id = {str(a.get("id")): a for a in asset_data.get("assets") or []}
    out: dict[str, dict[str, Any]] = {}

    for scene in asset_data.get("asset_scenes") or []:
        sid = str(scene.get("id") or "")
        if not sid:
            continue
        parent_asset_id = sid.split("_SC_", 1)[0]
        asset = asset_by_id.get(parent_asset_id, {})
        out[sid] = {
            **scene,
            "asset_id": parent_asset_id,
            "file_path": asset.get("file_path") or scene.get("file_path") or "",
            "_asset_duration": float(asset.get("duration_seconds") or 0.0),
        }

    for asset in asset_data.get("assets") or []:
        for scene in asset.get("scenes") or []:
            sid = str(scene.get("id") or "")
            if not sid or sid in out:
                continue
            out[sid] = {
                **scene,
                "asset_id": str(asset.get("id")),
                "file_path": asset.get("file_path") or "",
                "_asset_duration": float(asset.get("duration_seconds") or 0.0),
            }
    return out


def baseline_scene_spans(mappings: list[dict[str, Any]]) -> dict[str, tuple[float, float]]:
    spans: dict[str, tuple[float, float]] = {}
    for m in mappings:
        sid = str(m.get("scene_id") or "")
        if not sid:
            continue
        s = float(m.get("start") or 0.0)
        e = float(m.get("end") or 0.0)
        existing = spans.get(sid)
        if existing is None:
            spans[sid] = (s, e)
        else:
            spans[sid] = (min(existing[0], s), max(existing[1], e))
    return spans


def validate_decisions(
    decisions: list[dict[str, Any]],
    baseline_spans: dict[str, tuple[float, float]],
    asset_scenes: dict[str, dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    seen_scene_ids: set[str] = set()

    for d_index, decision in enumerate(decisions, start=1):
        scene_id = str(decision.get("scene_id") or "")
        if not scene_id:
            errors.append(f"decision[{d_index}] missing scene_id")
            continue
        if scene_id in seen_scene_ids:
            errors.append(f"decision for {scene_id} duplicated")
            continue
        seen_scene_ids.add(scene_id)

        if scene_id not in baseline_spans:
            errors.append(f"decision references unknown scene_id {scene_id}")
            continue

        strategy = str(decision.get("strategy") or "")
        if strategy not in VALID_STRATEGIES:
            errors.append(f"{scene_id} has invalid strategy '{strategy}'")
            continue

        if not str(decision.get("rationale") or "").strip():
            errors.append(f"{scene_id} missing rationale")

        sub_clips = decision.get("sub_clips") or []
        if not isinstance(sub_clips, list) or not sub_clips:
            errors.append(f"{scene_id} has no sub_clips")
            continue

        baseline_start, baseline_end = baseline_spans[scene_id]
        prev_end: float | None = None
        primary_count = 0

        for c_index, clip in enumerate(sub_clips, start=1):
            tag = f"{scene_id}.sub[{c_index}]"
            asset_scene_id = str(clip.get("asset_scene_id") or "")
            if not asset_scene_id:
                errors.append(f"{tag} missing asset_scene_id")
                continue
            asset_scene = asset_scenes.get(asset_scene_id)
            if not asset_scene:
                errors.append(f"{tag} unknown asset_scene_id '{asset_scene_id}'")
                continue

            role = str(clip.get("role") or "")
            if role == "primary":
                primary_count += 1
            elif strategy == "cutaway_subdivision" and not role.startswith("cutaway_"):
                errors.append(f"{tag} cutaway_subdivision requires role primary or cutaway_N (got '{role}')")

            ts = float(clip.get("timeline_start") or 0.0)
            te = float(clip.get("timeline_end") or 0.0)
            ss = float(clip.get("source_start") or 0.0)
            se = float(clip.get("source_end") or 0.0)

            if te - ts < MIN_SUBCLIP_DURATION:
                errors.append(
                    f"{tag} timeline duration {te - ts:.3f}s below min {MIN_SUBCLIP_DURATION}s"
                )

            if c_index == 1 and abs(ts - baseline_start) > TIMELINE_TOL:
                errors.append(
                    f"{tag} timeline_start {ts:.3f} != baseline scene start {baseline_start:.3f}"
                )
            if c_index == len(sub_clips) and abs(te - baseline_end) > TIMELINE_TOL:
                errors.append(
                    f"{tag} timeline_end {te:.3f} != baseline scene end {baseline_end:.3f}"
                )
            if prev_end is not None and abs(ts - prev_end) > TIMELINE_TOL:
                errors.append(
                    f"{tag} discontinuous timeline (prev end {prev_end:.3f}, this start {ts:.3f})"
                )
            prev_end = te

            scene_start = float(asset_scene.get("start") or 0.0)
            scene_end = float(asset_scene.get("end") or 0.0)
            asset_dur = float(asset_scene.get("_asset_duration") or 0.0)
            physical_end = max(scene_end, asset_dur) if asset_dur else scene_end

            if strategy == "hold_and_kenburns":
                pass  # source range may be 0-length placeholder for stills
            else:
                if ss < scene_start - TIMELINE_TOL:
                    errors.append(
                        f"{tag} source_start {ss:.3f} before asset_scene start {scene_start:.3f}"
                    )
                if se > physical_end + TIMELINE_TOL:
                    errors.append(
                        f"{tag} source_end {se:.3f} after physical end {physical_end:.3f}"
                    )
                if se <= ss:
                    errors.append(f"{tag} source_end <= source_start")

            playback_rate = float(clip.get("playback_rate") or 1.0)
            if not (PLAYBACK_RATE_RANGE[0] <= playback_rate <= PLAYBACK_RATE_RANGE[1]):
                errors.append(
                    f"{tag} playback_rate {playback_rate} outside {PLAYBACK_RATE_RANGE}"
                )

            if strategy == "slowdown" and playback_rate >= 1.0:
                errors.append(f"{tag} slowdown strategy requires playback_rate < 1.0")

            file_path = asset_scene.get("file_path") or ""
            if file_path and not Path(file_path).exists():
                errors.append(f"{tag} file does not exist: {file_path}")

        if strategy == "cutaway_subdivision" and primary_count != 1:
            errors.append(f"{scene_id} cutaway_subdivision must have exactly 1 primary sub-clip")
        if strategy in {"slowdown", "hold_and_kenburns", "keep"} and len(sub_clips) != 1:
            errors.append(f"{scene_id} {strategy} must have exactly 1 sub-clip")

    return errors


def build_new_mappings(
    baseline_mappings: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    asset_scenes: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    decisions_by_scene = {str(d.get("scene_id")): d for d in decisions}

    seen_scenes: set[str] = set()
    out: list[dict[str, Any]] = []

    baseline_sorted = sorted(baseline_mappings, key=lambda m: float(m.get("start") or 0.0))

    for m in baseline_sorted:
        sid = str(m.get("scene_id") or "")
        if not sid:
            out.append(m)
            continue
        if sid in seen_scenes:
            continue
        seen_scenes.add(sid)

        decision = decisions_by_scene.get(sid)
        if decision is None:
            out.append(m)
            continue

        strategy = str(decision.get("strategy"))
        sub_clips = decision.get("sub_clips") or []
        rationale = decision.get("rationale") or ""
        total = len(sub_clips)

        for sub_index, clip in enumerate(sub_clips, start=1):
            asset_scene_id = str(clip.get("asset_scene_id"))
            asset_scene = asset_scenes[asset_scene_id]
            asset_id = str(asset_scene.get("asset_id") or "")
            file_path = asset_scene.get("file_path") or ""
            ts = round(float(clip.get("timeline_start") or 0.0), 3)
            te = round(float(clip.get("timeline_end") or 0.0), 3)
            ss = round(float(clip.get("source_start") or 0.0), 3)
            se = round(float(clip.get("source_end") or 0.0), 3)
            playback_rate = round(float(clip.get("playback_rate") or 1.0), 4)
            role = str(clip.get("role") or ("primary" if total == 1 else f"cutaway_{sub_index - 1}"))
            reason = str(clip.get("reason") or rationale)

            timeline_dur = max(0.0, te - ts)
            source_dur = max(0.0, se - ss)
            gap_seconds = round(max(0.0, timeline_dur - source_dur * playback_rate), 3)

            out.append(
                {
                    "scene_id": sid,
                    "subdivision_role": role,
                    "subdivision_index": sub_index,
                    "subdivision_total": total,
                    "asset_id": asset_id,
                    "asset_scene_id": asset_scene_id,
                    "start": ts,
                    "end": te,
                    "file_path": file_path,
                    "source_start": ss,
                    "source_end": se,
                    "fit_score": 0.0,
                    "fit_labels": ["agent_decision"],
                    "reason": reason,
                    "fallback": False,
                    "warnings": [],
                    "coverage_strategy": strategy,
                    "playback_rate": playback_rate,
                    "gap_seconds": gap_seconds,
                    "coverage_warnings": [],
                    "coverage_rationale": rationale,
                }
            )

    out.sort(key=lambda r: float(r.get("start") or 0.0))
    for index, row in enumerate(out, start=1):
        row["id"] = f"MAP_{index:03d}"
    final = [
        {**{"id": r["id"]}, **{k: v for k, v in r.items() if k != "id"}}
        for r in out
    ]
    return final


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--asset-semantics", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    baseline_doc = read_toml(args.mapping)
    asset_doc = read_toml(args.asset_semantics)
    decisions_payload = json.loads(args.decisions.read_text(encoding="utf-8"))

    baseline_mappings = baseline_doc.get("mappings") or []
    decisions = decisions_payload.get("decisions") or []
    if not decisions:
        die("decisions JSON has no 'decisions' array")

    asset_scenes = asset_scene_index(asset_doc)
    spans = baseline_scene_spans(baseline_mappings)

    errors = validate_decisions(decisions, spans, asset_scenes)
    if errors:
        for err in errors:
            print(f"ERROR: {err}", file=sys.stderr)
        die(f"refusing to write {args.output}: {len(errors)} validation error(s)")

    new_mappings = build_new_mappings(baseline_mappings, decisions, asset_scenes)

    sorted_rows = sorted(new_mappings, key=lambda r: float(r.get("start") or 0.0))
    last_end = 0.0
    timeline_warnings: list[dict[str, str]] = []
    for row in sorted_rows:
        s = float(row.get("start") or 0.0)
        e = float(row.get("end") or 0.0)
        if s < last_end - TIMELINE_TOL:
            timeline_warnings.append(
                {"code": "TIMELINE_OVERLAP", "message": f"{row.get('id')} overlaps previous"}
            )
        if s > last_end + TIMELINE_TOL:
            timeline_warnings.append(
                {"code": "TIMELINE_GAP", "message": f"gap before {row.get('id')} ({last_end:.3f} -> {s:.3f})"}
            )
        last_end = max(last_end, e)

    write_toml_document(
        args.output,
        [("mappings", new_mappings), ("warnings", timeline_warnings)],
    )
    affected = sorted({d["scene_id"] for d in decisions})
    print(
        f"wrote {args.output}: {len(new_mappings)} mappings, "
        f"{len(affected)} scenes patched, "
        f"{len(timeline_warnings)} timeline warning(s)"
    )


if __name__ == "__main__":
    main()
