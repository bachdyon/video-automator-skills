#!/usr/bin/env python3
"""Build and validate a deterministic TOML render plan."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from pipeline_utils import die, media_metadata, read_toml, write_toml_document


def rows(data: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = data.get(key) or []
    return value if isinstance(value, list) else []


def infer_duration(mapping_rows: list[dict[str, Any]], transcript: dict[str, Any], voice_path: Path) -> float:
    candidates = [float(row.get("end") or 0.0) for row in mapping_rows]
    metadata_duration = float((transcript.get("metadata") or {}).get("duration_seconds") or 0.0)
    if metadata_duration:
        candidates.append(metadata_duration)
    if voice_path.exists():
        candidates.append(float(media_metadata(voice_path).get("duration_seconds") or 0.0))
    return round(max(candidates or [0.0]), 3)


def build_clips(mapping_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    clips: list[dict[str, Any]] = []
    for index, mapping in enumerate(mapping_rows, start=1):
        file_path = mapping.get("file_path") or ""
        suffix = Path(file_path).suffix.lower()
        clip_type = "image" if suffix in {".jpg", ".jpeg", ".png", ".webp", ".gif"} else "video"
        clips.append(
            {
                "id": f"CLIP_{index:03d}",
                "mapping_id": mapping.get("id") or f"MAP_{index:03d}",
                "file_path": file_path,
                "type": clip_type,
                "timeline_start": float(mapping.get("start") or 0.0),
                "timeline_end": float(mapping.get("end") or 0.0),
                "source_start": float(mapping.get("source_start") or 0.0),
                "source_end": float(mapping.get("source_end") or 0.0),
                "fit": "cover",
                "crop_anchor": "center",
                "speed": 1.0,
                "motion": "slow_push_in" if clip_type == "image" else "match_vds",
                "transition_in": "cut" if index == 1 else "soft_cut",
                "transition_out": "soft_cut",
                "color": "match_vds",
            }
        )
    return clips


def build_subtitles(transcript: dict[str, Any]) -> list[dict[str, Any]]:
    subtitles: list[dict[str, Any]] = []
    for sentence in rows(transcript, "sentences"):
        subtitles.append(
            {
                "start": float(sentence.get("start") or 0.0),
                "end": float(sentence.get("end") or 0.0),
                "text": sentence.get("sentence") or "",
                "words_ref": sentence.get("word_ids") or [],
                "style": "SUBTITLES",
            }
        )
    return subtitles


def build_overlays(creative: dict[str, Any]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for index, overlay in enumerate(rows(creative, "text_overlays"), start=1):
        output.append(
            {
                "id": overlay.get("id") or f"TXT_{index:03d}",
                "start": float(overlay.get("start") or 0.0),
                "end": float(overlay.get("end") or overlay.get("start") or 3.0),
                "text": overlay.get("text") or "",
                "style": overlay.get("style_ref") or overlay.get("style") or "MAIN_TITLE",
                "position": overlay.get("position") or "upper_third",
                "animation_in": overlay.get("animation_in") or "fade_slide",
                "animation_out": overlay.get("animation_out") or "fade",
            }
        )
    return output


def validate_plan(plan: dict[str, list[dict[str, Any]] | dict[str, Any]]) -> list[dict[str, str]]:
    warnings: list[dict[str, str]] = []
    clips = sorted(plan.get("clips", []), key=lambda row: float(row.get("timeline_start") or 0.0))  # type: ignore[arg-type]
    last_end = 0.0
    for clip in clips:
        start = float(clip.get("timeline_start") or 0.0)
        end = float(clip.get("timeline_end") or 0.0)
        if end <= start:
            warnings.append({"code": "INVALID_CLIP_RANGE", "message": f"{clip.get('id')} has end <= start"})
        if start < last_end - 0.05:
            warnings.append({"code": "CLIP_OVERLAP", "message": f"{clip.get('id')} overlaps previous clip"})
        if start > last_end + 0.05:
            warnings.append({"code": "CLIP_GAP", "message": f"gap before {clip.get('id')} from {last_end:.3f} to {start:.3f}"})
        file_path = clip.get("file_path") or ""
        if file_path and not Path(file_path).exists():
            warnings.append({"code": "MISSING_CLIP_FILE", "message": f"{clip.get('id')} references missing file {file_path}"})
        last_end = max(last_end, end)
    for subtitle in plan.get("subtitles", []):  # type: ignore[union-attr]
        start = float(subtitle.get("start") or 0.0)
        end = float(subtitle.get("end") or 0.0)
        text = subtitle.get("text") or ""
        if end <= start:
            warnings.append({"code": "INVALID_SUBTITLE_RANGE", "message": f"subtitle has end <= start: {text[:40]}"})
        if len(text) > 90 and (end - start) < 2.5:
            warnings.append({"code": "SUBTITLE_TOO_DENSE", "message": f"subtitle may be too dense: {text[:40]}"})
    return warnings


def build(args: argparse.Namespace) -> None:
    mapping = read_toml(args.mapping)
    transcript = read_toml(args.transcript) if args.transcript.exists() else {}
    creative = read_toml(args.creative_plan) if args.creative_plan.exists() else {}
    mapping_rows = rows(mapping, "mappings")
    if not mapping_rows:
        die("semantic mapping has no [[mappings]] rows")
    duration = infer_duration(mapping_rows, transcript, args.voice_audio)
    clips = build_clips(mapping_rows)
    subtitles = build_subtitles(transcript)
    overlays = build_overlays(creative)
    plan = {"clips": clips, "subtitles": subtitles, "overlays": overlays}
    warnings = validate_plan(plan)
    write_toml_document(
        args.output,
        [
            ("render", {"fps": args.fps, "width": args.width, "height": args.height, "duration_seconds": duration, "background": "black"}),
            (
                "style",
                {
                    "vds_path": str(args.vds_path),
                    "subtitle_style": "SUBTITLES",
                    "title_style": "MAIN_TITLE",
                    "color_treatment": "match_vds",
                },
            ),
            ("audio.voice", {"file_path": str(args.voice_audio), "start": 0.0, "gain_db": 0.0}),
            ("audio.music", {"file_path": str(args.music_audio or ""), "start": 0.0, "gain_db": -18.0, "duck_under_voice": True}),
            ("clips", clips),
            ("subtitles", subtitles),
            ("overlays", overlays),
            ("warnings", warnings),
        ],
    )
    print(f"wrote {args.output} with {len(clips)} clips, {len(subtitles)} subtitles, {len(warnings)} warnings")


def validate(args: argparse.Namespace) -> None:
    data = read_toml(args.render_plan)
    plan = {"clips": rows(data, "clips"), "subtitles": rows(data, "subtitles"), "overlays": rows(data, "overlays")}
    warnings = validate_plan(plan)
    if warnings:
        for warning in warnings:
            print(f"{warning['code']}: {warning['message']}")
        raise SystemExit(1)
    print("render plan validation passed")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    build_parser = sub.add_parser("build")
    build_parser.add_argument("--mapping", type=Path, default=Path("source/semantic_mapping.toml"))
    build_parser.add_argument("--transcript", type=Path, default=Path("source/transcript_word_level.toml"))
    build_parser.add_argument("--creative-plan", type=Path, default=Path("source/creative_plan.toml"))
    build_parser.add_argument("--voice-audio", type=Path, default=Path("source/voice.wav"))
    build_parser.add_argument("--music-audio", type=Path, default=Path(""))
    build_parser.add_argument("--vds-path", type=Path, default=Path("source/vds.md"))
    build_parser.add_argument("--output", type=Path, default=Path("source/render_plan.toml"))
    build_parser.add_argument("--fps", type=int, default=30)
    build_parser.add_argument("--width", type=int, default=1080)
    build_parser.add_argument("--height", type=int, default=1920)
    build_parser.set_defaults(func=build)
    validate_parser = sub.add_parser("validate")
    validate_parser.add_argument("--render-plan", type=Path, default=Path("source/render_plan.toml"))
    validate_parser.set_defaults(func=validate)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
