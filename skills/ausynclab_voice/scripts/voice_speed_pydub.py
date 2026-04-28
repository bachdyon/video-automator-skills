#!/usr/bin/env python3
"""Tăng/giảm tốc file WAV narration sau TTS bằng pydub.effects.speedup.

Dùng khi user muốn nhịp nhanh/chậm hơn so với tham số speed của API AusyncLab,
hoặc muốn thử nhiều hệ số mà không gọi lại TTS.

Python 3.13+: cần `pip install audioop-lts` (xem requirements-voice-speed.txt).
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

_SHARED = Path(__file__).resolve().parents[2] / "_shared"
sys.path.insert(0, str(_SHARED))
from pipeline_utils import die, media_metadata, read_toml, write_toml_document  # noqa: E402


def ensure_audioop_shim() -> None:
    try:
        import audioop  # noqa: F401
    except ModuleNotFoundError as first:
        if sys.version_info >= (3, 13):
            try:
                import audioop_lts as audioop  # type: ignore[import-not-found]

                sys.modules["audioop"] = audioop
            except ImportError:
                die(
                    "Python 3.13+ cần cài: pip install -r skills/ausynclab_voice/scripts/requirements-voice-speed.txt "
                    "(hoặc: pip install audioop-lts pydub). Có thể chạy bằng Python 3.12 nếu máy có sẵn."
                )
        else:
            die(f"Không import được audioop (Python {sys.version_info.major}.{sys.version_info.minor}): {first}")


def apply_speed_wav(
    input_wav: Path,
    output_wav: Path,
    *,
    playback_speed: float,
    chunk_size: int,
    crossfade: int,
) -> None:
    ensure_audioop_shim()
    from pydub import AudioSegment
    from pydub.effects import speedup

    if playback_speed <= 0:
        die("--playback-speed phải > 0")
    if not input_wav.is_file():
        die(f"Không thấy file đầu vào: {input_wav}")
    output_wav.parent.mkdir(parents=True, exist_ok=True)

    audio = AudioSegment.from_wav(str(input_wav))
    sped = speedup(
        audio,
        playback_speed=playback_speed,
        chunk_size=max(20, chunk_size),
        crossfade=max(0, min(crossfade, chunk_size // 2)),
    )
    tmp: Path | None = None
    try:
        if output_wav.resolve() == input_wav.resolve():
            fd, tmp_name = tempfile.mkstemp(suffix=".wav", dir=str(output_wav.parent))
            import os

            os.close(fd)
            tmp = Path(tmp_name)
            sped.export(str(tmp), format="wav")
            shutil.move(str(tmp), str(output_wav))
            tmp = None
        else:
            sped.export(str(output_wav), format="wav")
    finally:
        if tmp is not None and tmp.is_file():
            tmp.unlink(missing_ok=True)


def _append_reason(reason: str, note: str) -> str:
    r = (reason or "").strip()
    if note.strip() in r:
        return r or note.strip()
    if r:
        return f"{r} {note.strip()}"
    return note.strip()


def update_voice_selection_toml(
    selection_path: Path,
    *,
    new_duration_seconds: float,
    playback_speed: float,
    relative_audio_path: str | None,
) -> None:
    data = read_toml(selection_path)
    voice = dict(data.get("voice") or {})
    audio = dict(data.get("audio") or {})
    source = dict(data.get("source") or {})
    audio["duration_seconds"] = round(float(new_duration_seconds), 6)
    if relative_audio_path:
        audio["file_path"] = relative_audio_path
    note = f"Hậu xử lý pydub speedup {playback_speed}x; duration_seconds cập nhật theo file WAV."
    voice["reason"] = _append_reason(str(voice.get("reason") or ""), note)
    write_toml_document(
        selection_path,
        [
            ("voice", voice),
            ("audio", audio),
            ("source", source),
        ],
    )


def run(args: argparse.Namespace) -> None:
    input_wav: Path = args.input.expanduser().resolve()
    if args.in_place:
        output_wav = input_wav
    else:
        if not args.output:
            die("Cần --output hoặc --in-place")
        output_wav = args.output.expanduser().resolve()

    apply_speed_wav(
        input_wav,
        output_wav,
        playback_speed=float(args.playback_speed),
        chunk_size=int(args.chunk_size),
        crossfade=int(args.crossfade),
    )

    meta = media_metadata(output_wav)
    dur = float(meta.get("duration_seconds") or 0.0)
    print(f"Đã xử lý: {output_wav}")
    print(f"Độ dài (ffprobe): {dur:.6f}s, playback_speed={args.playback_speed}")

    if args.update_voice_selection:
        sel = Path(args.update_voice_selection).expanduser().resolve()
        if not sel.is_file():
            die(f"Không thấy voice_selection: {sel}")
        job_root = sel.parent.parent
        try:
            rel = str(output_wav.resolve().relative_to(job_root.resolve()))
        except ValueError:
            rel = None
        update_voice_selection_toml(
            sel,
            new_duration_seconds=dur,
            playback_speed=float(args.playback_speed),
            relative_audio_path=rel,
        )
        print(f"Đã cập nhật: {sel}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, required=True, help="File WAV đầu vào (thường source/voice.wav)")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--output", type=Path, help="File WAV đầu ra")
    g.add_argument("--in-place", action="store_true", help="Ghi đè chính file --input")
    p.add_argument(
        "--playback-speed",
        type=float,
        default=1.12,
        help="Hệ số tốc độ phát (>1 nhanh hơn). Mặc định 1.12",
    )
    p.add_argument("--chunk-size", type=int, default=120, help="Tham số pydub speedup (chunk ms)")
    p.add_argument("--crossfade", type=int, default=12, help="Crossfade ms giữa các chunk")
    p.add_argument(
        "--update-voice-selection",
        type=Path,
        metavar="PATH",
        help="Cập nhật duration_seconds (+ ghi chú reason) trong voice_selection.toml; nên dùng kèm --in-place hoặc khi --output là voice.wav chuẩn",
    )
    p.set_defaults(func=run)
    return p


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
