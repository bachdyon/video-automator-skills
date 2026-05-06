#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import tomllib
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
TEMPLATE_DIR = REPO_ROOT / "templates" / "podcast-dong-phuong"


def die(message: str) -> None:
    raise SystemExit(f"error: {message}")


def rel_to_repo(path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else REPO_ROOT / p


def copytree_template(job: Path) -> None:
    target = job / "remotion"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(
        TEMPLATE_DIR / "remotion",
        target,
        ignore=shutil.ignore_patterns("node_modules", "dist", "build", ".git"),
    )


def copy_asset(src: Path, dest_dir: Path, name: str) -> str:
    if not src.exists():
        die(f"missing asset: {src}")
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{name}{src.suffix.lower()}"
    shutil.copy2(src, dest)
    return f"assets/{dest.name}"


def normalized_word(text: str) -> str:
    return re.sub(r"^[^\wÀ-ỹ]+|[^\wÀ-ỹ]+$", "", text, flags=re.UNICODE).casefold()


def restore_punctuation(words: list[dict], transcript_text: str) -> list[dict]:
    spoken_tokens = transcript_text.split()
    aligned: list[dict] = []
    token_index = 0

    for item in words:
        raw = str(item.get("word") or item.get("text") or "")
        display = raw
        while token_index < len(spoken_tokens):
            candidate = spoken_tokens[token_index]
            token_index += 1
            if normalized_word(candidate) == normalized_word(raw):
                display = candidate
                break
        aligned.append(
            {
                "id": item["id"],
                "text": display,
                "start": float(item["start"]),
                "end": float(item["end"]),
                "sentenceId": item.get("sentence_id") or item.get("sentenceId"),
            }
        )
    return aligned


def build_props(job: Path, brand: str, subtitle_top_pct: float, highlight_color: str) -> dict:
    render_plan_path = job / "source" / "render_plan.toml"
    transcript_path = job / "source" / "transcript_word_level.toml"
    if not render_plan_path.exists():
        die(f"render plan not found: {render_plan_path}")
    if not transcript_path.exists():
        die(f"transcript not found: {transcript_path}")

    render_plan = tomllib.loads(render_plan_path.read_text())
    transcript = tomllib.loads(transcript_path.read_text())
    public_assets = job / "remotion" / "public" / "assets"

    copied: dict[str, str] = {}
    clips = []
    for clip in render_plan.get("clips", []):
        src = rel_to_repo(clip["file_path"])
        key = str(src)
        if key not in copied:
            copied[key] = copy_asset(src, public_assets, f"clip_{len(copied) + 1:02d}")
        clips.append(
            {
                "id": clip["id"],
                "src": copied[key],
                "timelineStart": float(clip["timeline_start"]),
                "timelineEnd": float(clip["timeline_end"]),
                "sourceStart": float(clip["source_start"]),
                "sourceEnd": float(clip["source_end"]),
            }
        )

    voice_src = ""
    voice = (render_plan.get("audio") or {}).get("voice") or {}
    if voice.get("file_path"):
        voice_src = copy_asset(rel_to_repo(voice["file_path"]), public_assets, "voice")

    render = render_plan.get("render") or {}
    words = restore_punctuation(
        list(transcript.get("words", [])),
        str((transcript.get("metadata") or {}).get("text") or ""),
    )

    return {
        "fps": int(render.get("fps") or 30),
        "width": int(render.get("width") or 1080),
        "height": int(render.get("height") or 1920),
        "durationSeconds": float(render.get("duration_seconds") or (transcript.get("metadata") or {}).get("duration_seconds") or 0),
        "voiceSrc": voice_src,
        "brand": brand,
        "subtitleTopPct": subtitle_top_pct,
        "highlightColor": highlight_color,
        "frame": {
            "left": 0,
            "top": 302,
            "width": 1080,
            "height": 1180,
            "radius": 0,
        },
        "clips": clips,
        "words": words,
    }


def write_template_params(job: Path, props: dict) -> None:
    text = f"""[template]
id = "podcast-dong-phuong"
name = "Podcast Đông Phương"

[pipeline_boundary]
semantic_mapping_stage = "upstream_job_specific"
template_stage = "render_only"
does_not_run_semantic_mapper = true
does_not_choose_assets = true

[style]
brand = {json.dumps(props["brand"], ensure_ascii=False)}
subtitle_top_pct = {props["subtitleTopPct"]}
highlight_color = {json.dumps(props["highlightColor"])}
font_family = "Asimovian"
subtitle_max_words_per_page = 6

[inputs]
clips = {len(props["clips"])}
words = {len(props["words"])}
voice_src = {json.dumps(props["voiceSrc"], ensure_ascii=False)}
"""
    (job / "source").mkdir(parents=True, exist_ok=True)
    (job / "source" / "template_params.toml").write_text(text)


def main() -> None:
    parser = argparse.ArgumentParser(description="Instantiate podcast-dong-phuong template for an existing job.")
    parser.add_argument("--job", required=True, type=Path, help="Job directory with source/render_plan.toml and source/transcript_word_level.toml")
    parser.add_argument("--brand", default="")
    parser.add_argument("--subtitle-top-pct", type=float, default=45.0)
    parser.add_argument("--highlight-color", default="#f3dd3d")
    args = parser.parse_args()

    job = args.job if args.job.is_absolute() else REPO_ROOT / args.job
    if not job.exists():
        die(f"job not found: {job}")
    copytree_template(job)
    props = build_props(job, args.brand, args.subtitle_top_pct, args.highlight_color)
    props_path = job / "remotion" / "public" / "template-props.json"
    props_path.write_text(json.dumps(props, ensure_ascii=False, indent=2) + "\n")
    write_template_params(job, props)
    print(f"wrote {props_path}")
    print(f"wrote {job / 'source' / 'template_params.toml'}")


if __name__ == "__main__":
    main()
