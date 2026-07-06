#!/usr/bin/env python3
"""Prepare stock effect videos for use as compositing overlays."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from fractions import Fraction
from pathlib import Path


def run(cmd: list[str], *, capture: bool = False, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        check=check,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )


def require_binary(name: str) -> None:
    if not shutil.which(name):
        raise SystemExit(f"Missing required binary: {name}")


def probe(path: Path) -> dict:
    result = run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration,size,bit_rate",
            "-show_entries",
            "stream=index,codec_type,codec_name,width,height,r_frame_rate,avg_frame_rate,pix_fmt,nb_frames",
            "-of",
            "json",
            str(path),
        ],
        capture=True,
    )
    return json.loads(result.stdout)


def first_video_stream(metadata: dict) -> dict:
    for stream in metadata.get("streams", []):
        if stream.get("codec_type") == "video":
            return stream
    raise SystemExit("No video stream found")


def parse_rate(rate: str | None) -> float | None:
    if not rate or rate == "0/0":
        return None
    try:
        return float(Fraction(rate))
    except (ValueError, ZeroDivisionError):
        return None


def valid_rate(rate: str | None) -> bool:
    return parse_rate(rate) is not None


def source_fps(stream: dict) -> str:
    for key in ("avg_frame_rate", "r_frame_rate"):
        rate = stream.get(key)
        if valid_rate(rate):
            return rate
    raise SystemExit("Could not determine source fps with ffprobe; pass --fps explicitly.")


def fps_label(fps: str) -> str:
    value = parse_rate(fps)
    if value is not None:
        if abs(round(value) - value) < 0.001:
            return str(int(round(value)))
        return f"{value:.3f}".rstrip("0").rstrip(".").replace(".", "p")
    return fps.replace("/", "p").replace(".", "p")


def pix_fmt_suggests_alpha(pix_fmt: str | None) -> bool:
    if not pix_fmt:
        return False
    alpha_formats = ("yuva", "rgba", "argb", "bgra", "abgr", "gbrap")
    return pix_fmt.startswith(alpha_formats) or pix_fmt.endswith("a")


def alphaextract_succeeds(path: Path) -> bool:
    result = run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(path),
            "-vf",
            "alphaextract",
            "-frames:v",
            "1",
            "-f",
            "null",
            "-",
        ],
        capture=True,
        check=False,
    )
    return result.returncode == 0


def fit_filter(width: int, height: int, fit: str) -> str:
    if fit == "cover":
        return (
            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height}"
        )
    if fit == "contain":
        return (
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black"
        )
    if fit == "stretch":
        return f"scale={width}:{height}"
    raise ValueError(f"Unsupported fit: {fit}")


def default_output_path(input_path: Path, output_dir: Path, width: int, height: int, fps: str, mode: str) -> Path:
    label = fps_label(fps)
    if mode == "preserve-alpha":
        return output_dir / f"{input_path.stem}_{width}x{height}_{label}fps_alpha.webm"
    return output_dir / f"{input_path.stem}_{width}x{height}_{label}fps_overlay.mp4"


def build_screen_filter(args: argparse.Namespace, fps: str) -> str:
    filters = [
        fit_filter(args.width, args.height, args.fit),
        "setsar=1",
        f"fps={fps}",
        f"eq=saturation={args.saturation}:contrast={args.contrast}:brightness={args.brightness}",
        "format=yuv420p",
    ]
    return ",".join(filters)


def build_alpha_filter(args: argparse.Namespace, fps: str) -> str:
    return ",".join([fit_filter(args.width, args.height, args.fit), "setsar=1", f"fps={fps}", "format=yuva420p"])


def convert_screen(input_path: Path, output_path: Path, args: argparse.Namespace, fps: str) -> None:
    run(
        [
            "ffmpeg",
            "-y" if args.overwrite else "-n",
            "-i",
            str(input_path),
            "-map",
            "0:v:0",
            "-an",
            "-dn",
            "-map_metadata",
            "-1",
            "-vf",
            build_screen_filter(args, fps),
            "-c:v",
            "libx264",
            "-preset",
            args.preset,
            "-crf",
            str(args.crf),
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            "-write_tmcd",
            "0",
            str(output_path),
        ]
    )


def convert_preserve_alpha(input_path: Path, output_path: Path, args: argparse.Namespace, fps: str) -> None:
    run(
        [
            "ffmpeg",
            "-y" if args.overwrite else "-n",
            "-i",
            str(input_path),
            "-map",
            "0:v:0",
            "-an",
            "-dn",
            "-map_metadata",
            "-1",
            "-vf",
            build_alpha_filter(args, fps),
            "-c:v",
            "libvpx-vp9",
            "-pix_fmt",
            "yuva420p",
            "-auto-alt-ref",
            "0",
            "-b:v",
            "0",
            "-crf",
            str(args.vp9_crf),
            str(output_path),
        ]
    )


def write_preview(output_path: Path, preview_path: Path, at_seconds: float) -> None:
    run(
        [
            "ffmpeg",
            "-y",
            "-ss",
            f"{at_seconds:.3f}",
            "-i",
            str(output_path),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            "-update",
            "1",
            str(preview_path),
        ]
    )


def remotion_snippet(filename: str, mode: str, opacity: float, playback_rate: float) -> str:
    blend_line = "" if mode == "preserve-alpha" else "    mixBlendMode: 'screen',\n"
    return (
        "<OffthreadVideo\n"
        f"  src={{staticFile('{filename}')}}\n"
        "  muted\n"
        "  loop\n"
        f"  playbackRate={{{playback_rate}}}\n"
        "  style={{\n"
        "    position: 'absolute',\n"
        "    inset: 0,\n"
        "    width: '100%',\n"
        "    height: '100%',\n"
        "    objectFit: 'cover',\n"
        f"{blend_line}"
        f"    opacity: {opacity},\n"
        "    pointerEvents: 'none',\n"
        "  }}\n"
        "/>"
    )


def process_one(input_path: Path, args: argparse.Namespace) -> dict:
    if not input_path.exists() or not input_path.is_file():
        raise SystemExit(f"Input video not found: {input_path}")

    input_metadata = probe(input_path)
    stream = first_video_stream(input_metadata)
    target_fps = args.fps if args.fps else source_fps(stream)
    target_fps_source = "override" if args.fps else "source"
    pix_fmt = stream.get("pix_fmt")
    alpha_by_pix_fmt = pix_fmt_suggests_alpha(pix_fmt)
    alpha_by_extract = alphaextract_succeeds(input_path)
    has_real_alpha = alpha_by_pix_fmt and alpha_by_extract

    mode = args.mode
    if mode == "auto":
        mode = "preserve-alpha" if has_real_alpha else "screen"
    if mode == "preserve-alpha" and not has_real_alpha:
        raise SystemExit(
            f"{input_path} does not expose a real alpha channel. "
            "Use --mode screen for black-background stock overlays."
        )

    output_dir = Path(args.output_dir) if args.output_dir else input_path.parent / "overlay_prepared"
    output_dir.mkdir(parents=True, exist_ok=True)
    if args.output and len(args.inputs) == 1:
        output_path = Path(args.output)
    else:
        output_path = default_output_path(input_path, output_dir, args.width, args.height, target_fps, mode)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if mode == "preserve-alpha":
        convert_preserve_alpha(input_path, output_path, args, target_fps)
    else:
        convert_screen(input_path, output_path, args, target_fps)

    output_metadata = probe(output_path)
    preview_path = None
    if not args.no_preview:
        preview_path = output_path.with_suffix(".preview.jpg")
        write_preview(output_path, preview_path, args.preview_at)

    report = {
        "input": str(input_path),
        "output": str(output_path),
        "preview": str(preview_path) if preview_path else None,
        "mode": mode,
        "has_real_alpha": has_real_alpha,
        "alpha_by_pix_fmt": alpha_by_pix_fmt,
        "alpha_by_extract": alpha_by_extract,
        "target": {
            "width": args.width,
            "height": args.height,
            "fps": target_fps,
            "fps_value": parse_rate(target_fps),
            "fps_source": target_fps_source,
            "fit": args.fit,
        },
        "screen_mode_settings": {
            "saturation": args.saturation,
            "contrast": args.contrast,
            "brightness": args.brightness,
            "crf": args.crf,
            "preset": args.preset,
        },
        "input_video": {
            "codec": stream.get("codec_name"),
            "pix_fmt": pix_fmt,
            "width": stream.get("width"),
            "height": stream.get("height"),
            "fps": parse_rate(stream.get("avg_frame_rate") or stream.get("r_frame_rate")),
            "duration": float(input_metadata.get("format", {}).get("duration", 0) or 0),
            "size": int(input_metadata.get("format", {}).get("size", 0) or 0),
        },
        "output_metadata": output_metadata,
        "recommended_remotion": {
            "component": "OffthreadVideo",
            "blend": None if mode == "preserve-alpha" else "screen",
            "loop": True,
            "snippet": remotion_snippet(output_path.name, mode, args.recommended_opacity, args.recommended_playback_rate),
        },
    }
    report_path = output_path.with_suffix(output_path.suffix + ".json")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report["report"] = str(report_path)
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Prepare stock effect videos for overlay compositing.")
    parser.add_argument("inputs", nargs="+", help="Input overlay/effect videos")
    parser.add_argument("--output-dir", help="Directory for prepared outputs")
    parser.add_argument("--output", help="Output file path; only valid with one input")
    parser.add_argument("--width", type=int, default=1024)
    parser.add_argument("--height", type=int, default=1536)
    parser.add_argument("--fps", help="Override output fps. Defaults to each input video's source fps.")
    parser.add_argument("--fit", choices=["cover", "contain", "stretch"], default="cover")
    parser.add_argument("--mode", choices=["auto", "screen", "preserve-alpha"], default="screen")
    parser.add_argument("--saturation", type=float, default=1.8)
    parser.add_argument("--contrast", type=float, default=1.08)
    parser.add_argument("--brightness", type=float, default=0.01)
    parser.add_argument("--crf", type=int, default=18)
    parser.add_argument("--preset", default="medium")
    parser.add_argument("--vp9-crf", type=int, default=28)
    parser.add_argument("--recommended-opacity", type=float, default=0.6)
    parser.add_argument("--recommended-playback-rate", type=float, default=0.55)
    parser.add_argument("--preview-at", type=float, default=5.0)
    parser.add_argument("--no-preview", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)

    if args.output and len(args.inputs) != 1:
        raise SystemExit("--output can only be used with one input")

    require_binary("ffmpeg")
    require_binary("ffprobe")

    reports = [process_one(Path(input_path), args) for input_path in args.inputs]
    print(json.dumps(reports, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
