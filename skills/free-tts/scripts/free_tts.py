#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import wave
from pathlib import Path
from typing import Any

VOICE_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def read_shared(path: Path) -> dict[str, Path]:
    values: dict[str, Path] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        voice_name = key.strip().strip('"').strip("'")
        sample_path = value.strip().strip('"').strip("'")
        if voice_name and sample_path:
            if not VOICE_NAME_RE.fullmatch(voice_name):
                raise SystemExit(
                    f"Tên giọng `{voice_name}` trong {path} không hợp lệ. "
                    "Chỉ dùng ASCII không dấu: A-Z, a-z, 0-9, dấu gạch dưới; bắt đầu bằng chữ."
                )
            path_value = Path(sample_path).expanduser()
            values[voice_name] = path_value if path_value.is_absolute() else (path.parent / path_value)
    return values


def validate_voice_name(voice_name: str) -> None:
    if not VOICE_NAME_RE.fullmatch(voice_name):
        raise SystemExit(
            f"Tên giọng `{voice_name}` không hợp lệ. "
            "Dùng tên không dấu dạng ASCII, ví dụ `GIONG_NU_NEWS` hoặc `GIONG_NAM_DOC`."
        )


def save_shared_voice(path: Path, voice_name: str, sample_path: Path) -> None:
    voice_name = voice_name.strip()
    validate_voice_name(voice_name)
    sample_path = sample_path.expanduser()
    if not voice_name:
        raise SystemExit("Tên giọng rỗng, không thể lưu vào .shared.")
    if not sample_path.exists():
        raise SystemExit(f"Không tìm thấy sample audio để lưu giọng: {sample_path}")

    rows: list[tuple[str, str]] = []
    seen = False
    if path.exists():
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            if not raw_line.strip() or raw_line.lstrip().startswith("#") or "=" not in raw_line:
                rows.append((raw_line, ""))
                continue
            key, value = raw_line.split("=", 1)
            if key.strip().strip('"').strip("'") == voice_name:
                rows.append((voice_name, str(sample_path)))
                seen = True
            else:
                rows.append((key.strip(), value.strip()))
    if not seen:
        rows.append((voice_name, str(sample_path)))

    lines = []
    for key, value in rows:
        lines.append(key if value == "" else f"{key}={value}")
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def has_ausynclab_key(env_file: Path) -> bool:
    value = read_env(env_file).get("AUSYNCLAB_API_KEY") or os.environ.get("AUSYNCLAB_API_KEY", "")
    return bool(value.strip())


def load_text_file(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def collect_strings(value: Any, keys: set[str], found: list[str]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            key_l = str(key).lower()
            if isinstance(child, str) and key_l in keys:
                found.append(child.strip())
            else:
                collect_strings(child, keys, found)
    elif isinstance(value, list):
        for child in value:
            collect_strings(child, keys, found)


def load_creative_plan(path: Path) -> str:
    try:
        import tomllib
    except ModuleNotFoundError:
        try:
            import tomli as tomllib  # type: ignore
        except ModuleNotFoundError as exc:
            raise SystemExit(
                "Thiếu TOML parser cho Python này. Dùng Python 3.11+ hoặc cài `tomli`."
            ) from exc

    data = tomllib.loads(path.read_text(encoding="utf-8"))
    preferred_keys = {
        "voice_text",
        "narration",
        "narration_text",
        "script",
        "script_text",
        "text",
        "spoken_text",
        "line",
        "sentence",
    }
    found: list[str] = []
    collect_strings(data, preferred_keys, found)
    text = "\n".join(part for part in found if part)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        raise SystemExit(f"Không tìm thấy narration/script text trong creative plan: {path}")
    return text


def duration_seconds(path: Path) -> float:
    try:
        with wave.open(str(path), "rb") as wav:
            frames = wav.getnframes()
            rate = wav.getframerate()
            return round(frames / float(rate), 3) if rate else 0.0
    except wave.Error:
        return 0.0


def toml_quote(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def write_selection(
    path: Path,
    *,
    audio_path: Path,
    mode: str,
    voice_id: str,
    voice_name: str,
    ref_audio: Path | None,
    text: str,
    source_path: str,
    sample_rate: int,
    reason: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    audio_duration = duration_seconds(audio_path)
    text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    content = f"""[voice]
provider = "vieneu-tts"
mode = {toml_quote(mode)}
voice_id = {toml_quote(voice_id)}
voice_name = {toml_quote(voice_name)}
language = "vi"
reference_audio = {toml_quote(str(ref_audio)) if ref_audio else '""'}
reason = {toml_quote(reason)}

[audio]
file_path = {toml_quote(str(audio_path))}
format = "wav"
sample_rate = {sample_rate}
duration_seconds = {audio_duration}
state = "SUCCEED"

[source]
script_path = {toml_quote(source_path)}
text_hash = {toml_quote(text_hash)}
"""
    path.write_text(content, encoding="utf-8")


def install_vieneu(extra_index_url: str | None) -> None:
    cmd = [sys.executable, "-m", "pip", "install", "vieneu"]
    if extra_index_url:
        cmd.extend(["--extra-index-url", extra_index_url])
    print("Không tìm thấy package `vieneu`; đang tự động cài đặt theo quickstart...", flush=True)
    subprocess.check_call(cmd)


def import_vieneu(*, auto_install: bool, extra_index_url: str | None):
    try:
        from vieneu import Vieneu
    except ModuleNotFoundError as exc:
        if not auto_install:
            raise SystemExit(
                "Thiếu package `vieneu`. Chạy lại không kèm `--no-auto-install` để script tự cài, "
                "hoặc cài thủ công: `python -m pip install vieneu`."
            ) from exc
        install_vieneu(extra_index_url)
        try:
            from vieneu import Vieneu
        except ModuleNotFoundError as retry_exc:
            raise SystemExit(
                "Đã thử cài `vieneu` nhưng vẫn không import được. Kiểm tra pip/Python environment."
            ) from retry_exc
    return Vieneu


def create_tts(Vieneu, mode: str):
    return Vieneu() if mode == "standard" else Vieneu(mode=mode)


def split_paragraph_chunks(text: str) -> list[str]:
    chunks = [part.strip() for part in re.split(r"\n\s*\n+", text) if part.strip()]
    return chunks or [text.strip()]


def concatenate_audio(chunks: list[Any]) -> Any:
    if len(chunks) == 1:
        return chunks[0]
    try:
        import numpy as np
    except ModuleNotFoundError as exc:
        raise SystemExit("Cần package `numpy` để nối audio chunks từ VieNeu-TTS.") from exc
    return np.concatenate(chunks)


def infer_audio(tts: Any, text: str, voice: Any | None, *, chunk_by_paragraph: bool) -> Any:
    if not chunk_by_paragraph:
        return tts.infer(text=text, voice=voice) if voice is not None else tts.infer(text=text)

    audio_chunks = []
    chunks = split_paragraph_chunks(text)
    for index, chunk in enumerate(chunks, start=1):
        print(f"Đang tạo voice chunk {index}/{len(chunks)}...", flush=True)
        audio_chunks.append(tts.infer(text=chunk, voice=voice) if voice is not None else tts.infer(text=chunk))
    return concatenate_audio(audio_chunks)


def synthesize(args: argparse.Namespace) -> None:
    if args.require_missing_ausynclab_key and has_ausynclab_key(args.env_file):
        raise SystemExit(
            "Phát hiện AUSYNCLAB_API_KEY trong env. Bỏ `--require-missing-ausynclab-key` "
            "nếu vẫn muốn ép dùng VieNeu-TTS."
        )

    if args.text:
        text = args.text.strip()
        source_path = "direct-input"
    elif args.text_file:
        text = load_text_file(args.text_file)
        source_path = str(args.text_file)
    elif args.creative_plan:
        text = load_creative_plan(args.creative_plan)
        source_path = str(args.creative_plan)
    else:
        raise SystemExit("Cần truyền một trong: --text, --text-file, --creative-plan.")

    if not text:
        raise SystemExit("Text rỗng, không thể tạo giọng đọc.")

    Vieneu = import_vieneu(auto_install=args.auto_install, extra_index_url=args.pip_extra_index_url)
    tts = create_tts(Vieneu, args.mode)

    voice = None
    voice_id = args.voice_id or "default"
    voice_name = "VieNeu-TTS default preset"
    ref_audio = args.ref_audio

    if args.voice_name:
        validate_voice_name(args.voice_name)
        named_voices = read_shared(args.shared_file)
        if args.voice_name not in named_voices:
            available = ", ".join(sorted(named_voices)) or "chưa có giọng nào"
            raise SystemExit(
                f"Không tìm thấy giọng `{args.voice_name}` trong {args.shared_file}. "
                f"Các giọng hiện có: {available}"
            )
        ref_audio = named_voices[args.voice_name]
        if not ref_audio.exists():
            raise SystemExit(f"Sample audio cho giọng `{args.voice_name}` không tồn tại: {ref_audio}")
        voice_id = args.voice_name
        voice_name = args.voice_name

    if ref_audio:
        if args.mode == "turbo":
            voice = tts.encode_reference(str(ref_audio))
        else:
            infer_kwargs = {"ref_audio": str(ref_audio)}
            if args.ref_text:
                infer_kwargs["ref_text"] = args.ref_text
            audio = tts.infer(text=text, **infer_kwargs)
            args.output_audio.parent.mkdir(parents=True, exist_ok=True)
            tts.save(audio, str(args.output_audio))
            write_selection(
                args.output,
                audio_path=args.output_audio,
                mode=args.mode,
                voice_id=voice_id if args.voice_name else "reference-audio",
                voice_name=voice_name if args.voice_name else f"Reference audio: {ref_audio}",
                ref_audio=ref_audio,
                text=text,
                source_path=source_path,
                sample_rate=args.sample_rate,
                reason="Dùng VieNeu-TTS local/free với audio tham chiếu vì workflow không dùng AusyncLab.",
            )
            return
        if not args.voice_name:
            voice_id = "reference-audio"
            voice_name = f"Reference audio: {ref_audio}"
    elif args.voice_id:
        voice = tts.get_preset_voice(args.voice_id)
        voice_name = f"VieNeu-TTS preset {args.voice_id}"

    audio = infer_audio(tts, text, voice, chunk_by_paragraph=args.chunk_by_paragraph)
    args.output_audio.parent.mkdir(parents=True, exist_ok=True)
    tts.save(audio, str(args.output_audio))

    write_selection(
        args.output,
        audio_path=args.output_audio,
        mode=args.mode,
        voice_id=voice_id,
        voice_name=voice_name,
        ref_audio=ref_audio,
        text=text,
        source_path=source_path,
        sample_rate=args.sample_rate,
        reason="Dùng VieNeu-TTS local/free vì không có AUSYNCLAB_API_KEY hoặc user yêu cầu free TTS.",
    )


def list_voices(args: argparse.Namespace) -> None:
    Vieneu = import_vieneu(auto_install=args.auto_install, extra_index_url=args.pip_extra_index_url)
    tts = create_tts(Vieneu, args.mode)
    for desc, voice_id in tts.list_preset_voices():
        print(f"{voice_id}\t{desc}")


def list_named_voices(args: argparse.Namespace) -> None:
    named_voices = read_shared(args.shared_file)
    for voice_name, sample_path in sorted(named_voices.items()):
        print(f"{voice_name}\t{sample_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate free/local Vietnamese TTS with VieNeu-TTS.")
    parser.add_argument("--text")
    parser.add_argument("--text-file", type=Path)
    parser.add_argument("--creative-plan", type=Path)
    parser.add_argument("--output-audio", type=Path, default=Path("source/voice.wav"))
    parser.add_argument("--output", type=Path, default=Path("source/voice_selection.toml"))
    parser.add_argument("--mode", choices=["standard", "turbo"], default="standard")
    parser.add_argument("--voice-id")
    parser.add_argument("--voice-name")
    parser.add_argument("--ref-audio", type=Path)
    parser.add_argument("--ref-text")
    parser.add_argument("--shared-file", type=Path, default=Path(".shared"))
    parser.add_argument("--save-voice-name")
    parser.add_argument("--save-voice-audio", type=Path)
    parser.add_argument("--list-named-voices", action="store_true")
    parser.add_argument("--sample-rate", type=int, default=24000)
    parser.add_argument("--chunk-by-paragraph", action="store_true")
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--require-missing-ausynclab-key", action="store_true")
    parser.add_argument("--list-voices", action="store_true")
    parser.add_argument("--no-auto-install", dest="auto_install", action="store_false")
    parser.add_argument("--pip-extra-index-url")
    parser.set_defaults(auto_install=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.save_voice_name or args.save_voice_audio:
        if not args.save_voice_name or not args.save_voice_audio:
            raise SystemExit("Cần truyền cả --save-voice-name và --save-voice-audio.")
        save_shared_voice(args.shared_file, args.save_voice_name, args.save_voice_audio)
    elif args.list_named_voices:
        list_named_voices(args)
    elif args.list_voices:
        list_voices(args)
    else:
        synthesize(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
