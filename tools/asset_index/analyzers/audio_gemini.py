"""Audio analyzer for the asset index.

Simply uploads the audio file inline to Gemini and asks for a classification
plus a Vietnamese summary, in the same flavour as the image analyzer. We
deliberately do not run Whisper or compute acoustic heuristics: Gemini is
multimodal and can listen to the file directly.

For DB columns we still record cheap structural metadata via ``ffprobe``
(``duration_seconds``, ``has_audio``) but those values are not used to
influence the classification.
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path
from typing import Any

from skills._shared.pipeline_utils import (  # type: ignore
    env_value,
    media_metadata,
)
from tools.asset_index.embed import build_embed_source
from tools.asset_index.gemini_client import (
    DEFAULT_FALLBACKS,
    DEFAULT_MODEL,
    GeminiError,
    call_gemini_json,
)

WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_ENV = WORKSPACE_ROOT / ".env"

ALLOWED_ROLES = ("voice_over", "background_music", "sound_effect")
INLINE_LIMIT_BYTES = 18 * 1024 * 1024  # ~18 MB safety margin under Gemini's 20 MB inline limit

AUDIO_MIME_BY_SUFFIX = {
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".mp4": "audio/mp4",
    ".aac": "audio/aac",
    ".wav": "audio/wav",
    ".flac": "audio/flac",
    ".ogg": "audio/ogg",
    ".oga": "audio/ogg",
    ".webm": "audio/webm",
    ".aiff": "audio/aiff",
    ".aif": "audio/aiff",
}


class AudioAnalysisError(RuntimeError):
    pass


PROMPT_TEMPLATE = """Bạn là chuyên gia âm thanh hậu kỳ cho video vlog short-form (TikTok/Reels) tiếng Việt.

Bạn được cho 1 file âm thanh và metadata sau:
- file_path: {file_path}
- duration_seconds: {duration_seconds}
- has_audio: {has_audio}

Hãy NGHE file âm thanh rồi PHÂN LOẠI nó là MỘT trong ba vai trò: voice_over, background_music, sound_effect.

Yêu cầu output (CHỈ trả về 1 JSON object hợp lệ, không markdown, không text khác):

{{
  "audio_role": "voice_over | background_music | sound_effect",
  "summary": "1-2 câu tóm tắt nội dung & cảm giác âm thanh, tiếng Việt CÓ DẤU.",
  "language": "vi | en | unknown",
  "tags": ["3-7 tag lowercase kebab-case mô tả ngữ nghĩa"],
  "mood": ["1-3 mood lowercase kebab-case"],
  "tempo_bpm_estimate": null,
  "bg_music_genre": null,
  "transcript_excerpt": "trích 1 câu nếu là voice_over; chuỗi rỗng nếu không có lời nói",
  "recommended_uses": ["1-3 vai trò narrative phù hợp"],
  "avoid_uses": ["0-3 vai trò KHÔNG phù hợp"]
}}

Quy tắc bắt buộc:
- audio_role PHẢI là 1 trong 3 giá trị trên (snake_case).
- Nếu nghe rõ giọng người đọc/nói tiếng Việt hoặc tiếng nước ngoài → voice_over.
- Nếu là nhạc nền hoặc giai điệu, không có lời người nói → background_music.
- Nếu là tiếng động ngắn (cú đập, tiếng còi, bong bóng, click,…) hoặc < 3 giây → sound_effect.
- Trả về JSON HỢP LỆ duy nhất. Không kèm ```json hay text giải thích.
- Tiếng Việt phải có dấu, không asciify.
- Nếu không chắc một field, để chuỗi rỗng "" hoặc list rỗng [], KHÔNG bịa.
"""


def _mime_for(path: Path) -> str:
    return AUDIO_MIME_BY_SUFFIX.get(path.suffix.lower(), "audio/mpeg")


def analyze(
    path: str | Path,
    *,
    env_file: str | Path = DEFAULT_ENV,
    timeout: int = 180,
) -> dict[str, Any]:
    src = Path(path).resolve()
    if not src.exists():
        raise FileNotFoundError(f"audio not found: {src}")

    api_key = env_value(Path(env_file), "GEMINI_API_KEY", "GOOGLE_API_KEY")
    if not api_key:
        raise GeminiError("GEMINI_API_KEY missing in .env")

    metadata = media_metadata(src)
    duration = float(metadata.get("duration_seconds") or 0.0)
    stat = src.stat()
    if stat.st_size > INLINE_LIMIT_BYTES:
        raise AudioAnalysisError(
            f"audio file too large for inline upload ({stat.st_size / 1e6:.1f} MB > "
            f"{INLINE_LIMIT_BYTES / 1e6:.0f} MB); use a shorter clip."
        )

    payload_b64 = base64.b64encode(src.read_bytes()).decode("ascii")
    mime = _mime_for(src)
    prompt = PROMPT_TEMPLATE.format(
        file_path=str(src),
        duration_seconds=round(duration, 3),
        has_audio=bool(metadata.get("has_audio")),
    )
    parts: list[dict[str, Any]] = [
        {"text": prompt},
        {"inline_data": {"mime_type": mime, "data": payload_b64}},
    ]

    data, model_used = call_gemini_json(
        api_key,
        parts,
        models=[DEFAULT_MODEL, *DEFAULT_FALLBACKS],
        timeout=timeout,
        log_prefix="[audio-gemini]",
    )

    role = (data.get("audio_role") or "").strip()
    if role not in ALLOWED_ROLES:
        role = "sound_effect"
    summary = (data.get("summary") or "").strip()
    tags = list(data.get("tags") or [])
    mood = list(data.get("mood") or [])
    transcript_excerpt = (data.get("transcript_excerpt") or "").strip()
    embed_source = build_embed_source(
        [
            role,
            summary,
            *tags,
            *mood,
            transcript_excerpt or None,
        ]
    )

    record: dict[str, Any] = {
        "file_name": src.name,
        "media_type": "audio",
        "size_bytes": stat.st_size,
        "mtime": stat.st_mtime,
        "width": None,
        "height": None,
        "duration_seconds": duration,
        "fps": None,
        "has_audio": int(bool(metadata.get("has_audio"))),
        "style": None,
        "summary": summary,
        "transcript": transcript_excerpt or None,
        "audio_role": role,
        "tags_json": tags,
        "mood_json": mood,
        "scenes_json": None,
        "raw_json": json.dumps(
            {
                "gemini": data,
                "gemini_model": model_used,
                "metadata": metadata,
                "mime": mime,
            },
            ensure_ascii=False,
        ),
        "embed_source": embed_source,
        "embed_model": "text-embedding-3-small",
    }
    return record


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Analyze a single audio clip via Gemini multimodal")
    parser.add_argument("audio", type=Path)
    parser.add_argument("--env-file", type=Path, default=DEFAULT_ENV)
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args(argv)
    try:
        record = analyze(args.audio, env_file=args.env_file, timeout=args.timeout)
    except (FileNotFoundError, GeminiError, AudioAnalysisError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    printable = {k: v for k, v in record.items() if k != "raw_json"}
    printable["raw_json_chars"] = len(record["raw_json"] or "")
    print(json.dumps(printable, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(_main())
