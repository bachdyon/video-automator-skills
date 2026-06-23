#!/usr/bin/env python3
"""
Upload a video to Gemini Files API and run long-context video analysis.

Usage:
  python skills/video-design-spec-builder/scripts/upload_video_to_gemini.py \
    --video-path /absolute/path/video.mp4 \
    --env-file .env \
    --model gemini-3-flash-preview \
    --prompt "Create a reusable VDS from this video."
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from pipeline_utils import die, env_value

DEFAULT_MODEL = "gemini-3-flash-preview"
DEFAULT_FALLBACK_MODELS = [
    "gemini-3-flash-preview",
    "gemini-2.5-pro",
    "gemini-2.5-flash",
]


DEFAULT_PROMPT = (
    "Phân tích video ngắn dọc này và tạo một Video Design Specification (VDS) "
    "có thể tái sử dụng. Toàn bộ kết quả phải là tiếng Việt có dấu, trừ các "
    "mã slot kỹ thuật như [MAIN_CHARACTER], SC_01, MAIN_TITLE. Giữ lại cấu "
    "trúc kể chuyện, nhịp dựng, mood thị giác, hệ chữ, motion và audio "
    "behavior; loại bỏ hoặc trừu tượng hóa toàn bộ định danh cá nhân. VDS là "
    "blueprint tái sử dụng, không phải render plan của video mẫu: không đưa "
    "tổng frame, frame range tuyệt đối, duration chính xác, timestamp cứng, "
    "tên file, đường dẫn asset, hoặc thông số timing cụ thể của video mẫu vào "
    "phần hướng dẫn triển khai. Được ghi FPS, tỉ lệ khung hình, và kích thước "
    "pixel trong Metadata hoặc khuyến nghị kỹ thuật vì đây là thông số định "
    "dạng cần thiết. Nếu cần nhắc thông số mẫu, phân biệt rõ đâu là tham "
    "chiếu mẫu và đâu là khuyến nghị tái sử dụng. "
    "Timing phải dùng phần trăm timeline, khoảng mềm, scene weights, và quy "
    "tắc co giãn theo target duration. Được hard-code preset định dạng có chủ "
    "đích như 1080x1920 hoặc 30fps nếu đó là khuyến nghị xuất video dọc. "
    "Không tạo phần Remotion/Code, implementation notes, hướng dẫn code, "
    "component map, hoặc pseudocode triển khai. Xuất đúng các phần: metadata, "
    "mục đích tái sử dụng, creative intent, narrative structure, style DNA, "
    "timing system, scene blueprint, semantic slots, text system, motion "
    "system, audio system, và reusability rules."
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Upload video to Gemini and run long-context analysis."
    )
    parser.add_argument(
        "--video-path",
        required=True,
        help="Absolute or relative path to video file.",
    )
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Path to repo-root .env containing GEMINI_API_KEY.",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=(
            "Primary Gemini model. Recommended default: gemini-3-flash-preview"
            "for deep analysis."
        ),
    )
    parser.add_argument(
        "--fallback-models",
        default=",".join(DEFAULT_FALLBACK_MODELS),
        help=(
            "Comma-separated fallback models used when primary model fails. "
            "Example: gemini-3-flash-preview,gemini-2.5-pro,gemini-2.5-flash"
        ),
    )
    parser.add_argument(
        "--prompt",
        default=DEFAULT_PROMPT,
        help="Instruction prompt for model analysis.",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=3.0,
        help="Seconds between file processing status checks.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=900,
        help="Maximum seconds to wait for uploaded video to become ACTIVE.",
    )
    parser.add_argument(
        "--save-response",
        default="",
        help="Optional output path to save raw JSON response.",
    )
    parser.add_argument(
        "--delete-file-after-run",
        action="store_true",
        help="Delete uploaded Gemini file after inference.",
    )
    return parser.parse_args()


def get_api_key(env_file: str) -> str:
    key = env_value(env_file, "GEMINI_API_KEY")
    if not key:
        die("Missing API key. Set GEMINI_API_KEY in repo-root .env.")
    return key


def load_genai() -> Any:
    try:
        from google import genai
    except ModuleNotFoundError:
        die(
            "Missing dependency: google-genai. Install it with "
            "`pip install -r skills/video-design-spec-builder/scripts/requirements.txt`."
        )
    return genai


def state_name(file_obj: Any) -> str:
    state = getattr(file_obj, "state", None)
    if state is None:
        return "UNKNOWN"
    name = getattr(state, "name", None)
    if name:
        return str(name)
    return str(state)


def wait_until_active(
    client: Any,
    file_name: str,
    poll_interval: float,
    timeout_seconds: int,
) -> Any:
    start = time.time()
    while True:
        current = client.files.get(name=file_name)
        current_state = state_name(current)
        if current_state == "ACTIVE":
            return current
        if current_state == "FAILED":
            raise RuntimeError(f"Gemini failed to process file: {file_name}")

        elapsed = time.time() - start
        if elapsed > timeout_seconds:
            raise TimeoutError(
                f"Timeout waiting for ACTIVE state after {timeout_seconds}s "
                f"(last state: {current_state})."
            )

        print(
            f"[processing] state={current_state} elapsed={int(elapsed)}s; "
            f"waiting {poll_interval:.1f}s..."
        )
        time.sleep(poll_interval)


def maybe_save_response(raw_response: Any, output_path: str) -> None:
    if not output_path:
        return
    output = Path(output_path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    if hasattr(raw_response, "model_dump"):
        payload = raw_response.model_dump()
    else:
        payload = {"response": str(raw_response)}

    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print(f"[saved] Raw response JSON -> {output}")


def build_model_chain(primary_model: str, fallback_models_raw: str) -> list[str]:
    chain: list[str] = [primary_model.strip()]
    if fallback_models_raw.strip():
        for model in fallback_models_raw.split(","):
            model_name = model.strip()
            if model_name and model_name not in chain:
                chain.append(model_name)
    return chain


def generate_with_model_fallback(
    client: genai.Client,
    model_chain: list[str],
    contents: list[Any],
) -> tuple[Any, str]:
    errors: list[tuple[str, str]] = []
    for model_name in model_chain:
        try:
            print(f"[inference] Trying model: {model_name}")
            response = client.models.generate_content(
                model=model_name,
                contents=contents,
            )
            print(f"[inference] Success with model: {model_name}")
            return response, model_name
        except Exception as exc:  # noqa: BLE001
            message = str(exc)
            errors.append((model_name, message))
            print(f"[inference] Failed model {model_name}: {message}", file=sys.stderr)

    combined = " | ".join([f"{m}: {e}" for m, e in errors]) if errors else "Unknown error"
    raise RuntimeError(f"All models failed. Details: {combined}")


def main() -> int:
    args = parse_args()
    video_path = Path(args.video_path).expanduser().resolve()
    if not video_path.exists():
        print(f"[error] Video file not found: {video_path}", file=sys.stderr)
        return 2

    try:
        api_key = get_api_key(args.env_file)
        genai = load_genai()
        client = genai.Client(api_key=api_key)

        print(f"[upload] Uploading: {video_path}")
        uploaded = client.files.upload(file=str(video_path))
        print(f"[upload] Done. File name: {uploaded.name}")

        active_file = wait_until_active(
            client=client,
            file_name=uploaded.name,
            poll_interval=args.poll_interval,
            timeout_seconds=args.timeout_seconds,
        )
        print(f"[ready] File ACTIVE: {active_file.name}")

        model_chain = build_model_chain(args.model, args.fallback_models)
        print(f"[inference] Model chain: {model_chain}")

        response, selected_model = generate_with_model_fallback(
            client=client,
            model_chain=model_chain,
            contents=[active_file, args.prompt],
        )
        print(f"[inference] Selected model: {selected_model}")

        text = getattr(response, "text", None)
        if text:
            print("\n===== GEMINI RESPONSE (TEXT) =====\n")
            print(text)
        else:
            print("\n===== GEMINI RESPONSE (NON-TEXT) =====\n")
            print(response)

        maybe_save_response(response, args.save_response)

        if args.delete_file_after_run:
            client.files.delete(name=active_file.name)
            print(f"[cleanup] Deleted uploaded file: {active_file.name}")

        return 0

    except Exception as exc:  # noqa: BLE001
        print(f"[error] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
