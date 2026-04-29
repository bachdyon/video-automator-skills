#!/usr/bin/env python3
"""Instantiate the templates/theanh28 Remotion shell into a job directory."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from pipeline_utils import die, media_metadata, read_toml, write_toml_document


REPO_ROOT = Path(__file__).resolve().parents[3]
TEMPLATE_DIR = REPO_ROOT / "templates" / "theanh28"
REMOTION_TEMPLATE_DIR = TEMPLATE_DIR / "remotion"
TEMPLATE_CONFIG = TEMPLATE_DIR / "template.toml"


def copytree_clean(src: Path, dst: Path, *, force: bool) -> None:
    if not src.exists():
        die(f"missing template remotion directory: {src}")
    if dst.exists() and force:
        shutil.rmtree(dst)

    def ignore(_dir: str, names: list[str]) -> set[str]:
        ignored = {"node_modules", ".DS_Store"}
        if Path(_dir).name == "public":
            ignored.add("assets")
        return ignored.intersection(names)

    shutil.copytree(src, dst, ignore=ignore, dirs_exist_ok=True)


def rel(path: Path, base: Path) -> str:
    try:
        return str(path.resolve().relative_to(base.resolve()))
    except ValueError:
        return str(path)


def frames(seconds: float, fps: int) -> int:
    return max(1, int(round(seconds * fps)))


def default_date_stamp() -> str:
    return datetime.now().strftime("%d/%m/%Y")


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def copy_if_different(src: Path, dst: Path) -> None:
    try:
        if src.resolve() == dst.resolve():
            return
    except FileNotFoundError:
        pass
    shutil.copy2(src, dst)


def instantiate(args: argparse.Namespace) -> None:
    config = read_toml(TEMPLATE_CONFIG)
    remotion_cfg = config["remotion"]
    defaults = config["defaults"]
    style = config["style"]

    job_dir = args.job_dir
    source_clip = args.source_clip
    intro_voice = args.intro_voice
    if not source_clip.exists():
        die(f"source clip not found: {source_clip}")
    if not intro_voice.exists():
        die(f"intro voice not found: {intro_voice}")

    for subdir in [
        "input/raw_assets/videos/template",
        "source",
        "output",
        "logs",
    ]:
        (job_dir / subdir).mkdir(parents=True, exist_ok=True)

    copytree_clean(REMOTION_TEMPLATE_DIR, job_dir / "remotion", force=args.force_remotion)
    (job_dir / "remotion" / "public" / "assets").mkdir(parents=True, exist_ok=True)

    source_ext = source_clip.suffix or ".mp4"
    voice_ext = intro_voice.suffix or ".wav"
    canonical_source = job_dir / "input" / "raw_assets" / "videos" / "template" / f"source{source_ext}"
    canonical_voice = job_dir / "source" / f"voice{voice_ext}"
    source_asset = job_dir / "remotion" / "public" / "assets" / f"source{source_ext}"
    voice_asset = job_dir / "remotion" / "public" / "assets" / f"voice{voice_ext}"
    copy_if_different(source_clip, canonical_source)
    copy_if_different(intro_voice, canonical_voice)
    copy_if_different(canonical_source, source_asset)
    copy_if_different(canonical_voice, voice_asset)
    music_path = ""
    music_for_plan = ""
    music_intro_volume = args.background_music_intro_volume or float(defaults["background_music_intro_volume"])
    music_source_volume = (
        args.background_music_source_volume
        or args.background_music_volume
        or float(defaults["background_music_source_volume"])
    )
    if args.background_music:
        if not args.background_music.exists():
            die(f"background music not found: {args.background_music}")
        music_ext = args.background_music.suffix or ".mp3"
        canonical_music = job_dir / "input" / "audio" / f"background_music{music_ext}"
        music_asset = job_dir / "remotion" / "public" / "assets" / f"background_music{music_ext}"
        canonical_music.parent.mkdir(parents=True, exist_ok=True)
        copy_if_different(args.background_music, canonical_music)
        copy_if_different(canonical_music, music_asset)
        music_path = f"assets/background_music{music_ext}"
        music_for_plan = rel(canonical_music, job_dir)

    source_meta = media_metadata(canonical_source)
    voice_meta = media_metadata(canonical_voice)
    fps = int(remotion_cfg.get("fps", 30))
    voice_duration = float(voice_meta.get("duration_seconds") or 0)
    source_duration = float(source_meta.get("duration_seconds") or 0)
    intro_seconds = args.intro_duration_seconds or voice_duration or float(defaults["intro_duration_seconds"])
    source_start = args.source_start
    requested_source_end = args.source_end
    if requested_source_end is None:
        if args.target_duration_seconds:
            requested_source_end = source_start + max(0.1, args.target_duration_seconds - intro_seconds)
        elif source_duration:
            requested_source_end = source_duration
        else:
            requested_source_end = source_start + float(defaults["source_duration_seconds"])
    source_end = max(source_start + 0.1, requested_source_end)
    source_seconds = source_end - source_start
    duration_seconds = intro_seconds + source_seconds

    date_stamp = args.date_stamp or str(defaults.get("date_stamp") or "") or default_date_stamp()
    video_credit = args.video_credit or str(defaults["video_credit"])
    brand_number = args.brand_number or str(defaults["brand_number"])
    brand_label = args.brand_label or str(defaults["brand_label"])
    logo_path = ""
    if args.logo_path:
        if not args.logo_path.exists():
            die(f"logo path not found: {args.logo_path}")
        logo_ext = args.logo_path.suffix or ".png"
        logo_asset = job_dir / "remotion" / "public" / "assets" / f"logo{logo_ext}"
        shutil.copy2(args.logo_path, logo_asset)
        logo_path = f"assets/logo{logo_ext}"
    overlay_color = args.overlay_color or str(style["overlay_color"])
    text_color = args.text_color or str(style["text_color"])
    headline_font_scale = args.headline_font_scale or float(defaults["headline_font_scale"])
    intro_object_position = args.intro_object_position or str(style["intro_object_position"])
    intro_transform = args.intro_transform or str(style["intro_transform"])
    source_object_position = args.source_object_position or str(style["source_object_position"])

    props = {
        "introDurationFrames": frames(intro_seconds, fps),
        "sourceDurationFrames": frames(source_seconds, fps),
        "sourceVideo": f"assets/source{source_ext}",
        "introVoice": f"assets/voice{voice_ext}",
        "backgroundMusic": music_path,
        "backgroundMusicIntroVolume": music_intro_volume,
        "backgroundMusicSourceVolume": music_source_volume,
        "mainHeadline": args.main_headline,
        "videoCredit": video_credit,
        "dateStamp": date_stamp,
        "brandNumber": brand_number,
        "brandLabel": brand_label,
        "logoPath": logo_path,
        "overlayColor": overlay_color,
        "textColor": text_color,
        "headlineFontScale": headline_font_scale,
        "introObjectPosition": intro_object_position,
        "introTransform": intro_transform,
        "sourceObjectPosition": source_object_position,
    }
    write_json(job_dir / "remotion" / "public" / "template-props.json", props)

    source_clip_for_plan = rel(canonical_source, job_dir)
    voice_for_plan = rel(canonical_voice, job_dir)
    creative_plan = {
        "metadata": {
            "title": args.title,
            "language": args.language,
            "platform": args.platform,
            "target_duration_seconds": round(duration_seconds, 3),
            "aspect_ratio": "9:16",
            "vds_template": config["template"]["name"],
        },
        "creative": {
            "audience": "Khán giả TikTok/Reels/Shorts thích nội dung tình huống đời thường.",
            "goal": "Đặt ngữ cảnh bằng intro tin tức ngắn rồi phát clip gốc.",
            "tone": "tin tức giải trí, nhanh, rõ, hơi meme",
            "cta": args.cta,
        },
        "voiceover": {
            "script": args.intro_script,
            "delivery": args.voice_delivery,
        },
    }
    render_plan_sections: list[tuple[str | None, dict[str, Any] | list[dict[str, Any]]]] = [
        (
            "render",
            {
                "fps": fps,
                "width": int(remotion_cfg["width"]),
                "height": int(remotion_cfg["height"]),
                "duration_seconds": round(duration_seconds, 6),
                "background": remotion_cfg["background"],
                "creative_plan_path": "source/creative_plan.toml",
                "template_id": config["template"]["id"],
            },
        ),
        ("intro_chrome", {"video_credit": video_credit, "brand_number": brand_number, "brand_label": brand_label, "logo_path": logo_path, "date_stamp": date_stamp}),
        (
            "style",
            {
                "template_contract_path": "templates/theanh28/template.toml",
                "vds_path": "templates/theanh28/reference/vds.md",
                "subtitle_style": style["subtitle_style"],
                "title_style": style["title_style"],
                "color_treatment": "news_overlay_then_source",
                "main_headline_font": style["main_headline_font"],
                "main_headline_no_text_background": bool(style["main_headline_no_text_background"]),
                "transition_to_source": style["transition_to_source"],
            },
        ),
        ("audio.voice", {"file_path": voice_for_plan, "start": 0.0, "gain_db": 0.0, "duck_source_under_intro": True}),
        (
            "audio.music",
            {
                "file_path": music_for_plan,
                "start": 0.0,
                "gain_db": -18.0 if music_for_plan else -99.0,
                "duck_under_voice": True if music_for_plan else False,
                "loop": True if music_for_plan else False,
            },
        ),
        (
            "clips",
            [
                {
                    "id": "CLIP_001",
                    "scene_id": "SC_01",
                    "mapping_id": "TEMPLATE_INTRO",
                    "narrative_role": "news_intro_card",
                    "file_path": source_clip_for_plan,
                    "type": "video",
                    "timeline_start": 0.0,
                    "timeline_end": round(intro_seconds, 6),
                    "source_start": source_start,
                    "source_end": round(source_start + intro_seconds, 6),
                    "fit": "cover",
                    "crop_anchor": "center",
                    "speed": 1.0,
                    "motion": "news_overlay",
                    "transition_in": "cut",
                    "transition_out": "cut",
                    "color": "overlay_on_source_light_dim",
                },
                {
                    "id": "CLIP_002",
                    "scene_id": "SC_03",
                    "mapping_id": "TEMPLATE_SOURCE",
                    "narrative_role": "source_clip_playback",
                    "file_path": source_clip_for_plan,
                    "type": "video",
                    "timeline_start": round(intro_seconds, 6),
                    "timeline_end": round(duration_seconds, 6),
                    "source_start": source_start,
                    "source_end": round(source_end, 6),
                    "fit": "cover",
                    "crop_anchor": "center",
                    "speed": 1.0,
                    "motion": "none",
                    "transition_in": "cut",
                    "transition_out": "cut",
                    "color": "source_original",
                },
            ],
        ),
        (
            "overlays",
            [
                {
                    "id": "TXT_01",
                    "creative_overlay_id": "TXT_01",
                    "scene_id": "SC_01",
                    "start": 0.0,
                    "end": round(intro_seconds, 6),
                    "text": args.main_headline,
                    "style": "MAIN_TITLE",
                    "style_ref": "MAIN_TITLE",
                    "position": "lower_third",
                    "animation_in": "fade_slide",
                    "animation_out": "fade",
                }
            ],
        ),
    ]

    write_toml_document(
        job_dir / "source" / "creative_plan.toml",
        [
            ("metadata", creative_plan["metadata"]),
            ("creative", creative_plan["creative"]),
            ("voiceover", creative_plan["voiceover"]),
            (
                "scene_intents",
                [
                    {
                        "id": "SC_01",
                        "start_hint": 0.0,
                        "end_hint": round(intro_seconds, 6),
                        "narrative_role": "news_intro_card",
                        "spoken_text": args.intro_script,
                        "visual_intent": "Theanh28 news overlay on source footage.",
                        "mood": "khẩn trương, dễ hiểu",
                        "preferred_shot_types": ["overlay intro", "lower-third panel"],
                        "asset_requirements": ["SOURCE_CLIP", "AI_INTRO_VOICE", "MAIN_HEADLINE"],
                    },
                    {
                        "id": "SC_03",
                        "start_hint": round(intro_seconds, 6),
                        "end_hint": round(duration_seconds, 6),
                        "narrative_role": "source_clip_playback",
                        "spoken_text": "No AI voice; original source audio leads.",
                        "visual_intent": "Full-bleed source clip playback.",
                        "mood": "tự nhiên",
                        "preferred_shot_types": ["original source clip"],
                        "asset_requirements": ["SOURCE_CLIP", "SOURCE_AUDIO"],
                    },
                ],
            ),
            (
                "text_overlays",
                [
                    {
                        "id": "TXT_01",
                        "scene_id": "SC_01",
                        "text": args.main_headline,
                        "role": "main_headline",
                        "timing": "full_intro_hold",
                        "start": 0.0,
                        "end": round(intro_seconds, 6),
                        "style_ref": "MAIN_TITLE",
                        "position": "lower_third",
                        "animation_in": "fade_slide",
                        "animation_out": "fade",
                    }
                ],
            ),
        ],
    )
    write_toml_document(job_dir / "source" / "render_plan.toml", render_plan_sections)
    write_toml_document(
        job_dir / "source" / "template_params.toml",
        [
            ("template", {"id": config["template"]["id"], "version": config["template"]["version"], "contract_path": "templates/theanh28/template.toml"}),
            (
                "inputs",
                {
                    "source_clip": source_clip_for_plan,
                    "intro_voice": voice_for_plan,
                    "background_music": music_for_plan,
                    "main_headline": args.main_headline,
                    "intro_script": args.intro_script,
                },
            ),
            ("props", props),
        ],
    )
    print(f"instantiated {config['template']['id']} into {job_dir}")
    print(f"duration_seconds={duration_seconds:.3f} intro={intro_seconds:.3f} source={source_seconds:.3f}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job-dir", type=Path, required=True)
    parser.add_argument("--source-clip", type=Path, required=True)
    parser.add_argument("--intro-voice", type=Path, required=True)
    parser.add_argument("--main-headline", required=True)
    parser.add_argument("--intro-script", default="")
    parser.add_argument("--video-credit", default="")
    parser.add_argument("--background-music", type=Path)
    parser.add_argument("--background-music-volume", type=float, default=0.0, help="Backward-compatible alias for --background-music-source-volume.")
    parser.add_argument("--background-music-intro-volume", type=float, default=0.0)
    parser.add_argument("--background-music-source-volume", type=float, default=0.0)
    parser.add_argument("--title", default="Theanh28 template video")
    parser.add_argument("--language", default="vi")
    parser.add_argument("--platform", default="tiktok")
    parser.add_argument("--cta", default="Mời bình luận bên nào hợp lý hơn.")
    parser.add_argument("--voice-delivery", default="Giọng AI rõ lời, nhịp nhanh vừa phải, phong cách tin tức giải trí.")
    parser.add_argument("--date-stamp", default="")
    parser.add_argument("--brand-number", default="")
    parser.add_argument("--brand-label", default="")
    parser.add_argument("--logo-path", type=Path)
    parser.add_argument("--overlay-color", default="")
    parser.add_argument("--text-color", default="")
    parser.add_argument("--headline-font-scale", type=float, default=0.0)
    parser.add_argument("--intro-object-position", default="")
    parser.add_argument("--intro-transform", default="")
    parser.add_argument("--source-object-position", default="")
    parser.add_argument("--source-start", type=float, default=0.0)
    parser.add_argument("--source-end", type=float)
    parser.add_argument("--intro-duration-seconds", type=float)
    parser.add_argument("--target-duration-seconds", type=float)
    parser.add_argument("--force-remotion", action="store_true")
    return parser


def main() -> None:
    instantiate(build_parser().parse_args())


if __name__ == "__main__":
    main()
