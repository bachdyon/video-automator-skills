#!/usr/bin/env python3
"""Build Remotion template-props.json: words + punch_segments từ transcript_word_level.toml.

- **Chunking** (cửa sổ ``--chunk-size``): thủ tục thuần, deterministic.
- **Punch**: script **không** chọn punch — không heuristic, không từ khóa, không điểm số trong repo.
  Punch do **coding agent** (LLM) gán sau khi **đọc/nghe ngữ cảnh** từng chunk; agent ghi JSON
  và truyền ``--merge-punch``. Script chỉ merge + kiểm tra (subset chunk, liên tiếp).

Tùy chọn ``--write-agent-input``: xuất JSON liệt kê chunk + token (id/word/time) cho agent — không
chứa punch, không gợi ý punch bằng rule.
"""

from __future__ import annotations

import argparse
import json
import math
import tomllib
from pathlib import Path
from typing import Any

EMPTY_PUNCH_NOTE = (
    "Chưa gán punch — agent sẽ điền qua --merge-punch sau khi suy luận ngữ nghĩa trên từng chunk "
    "(punch_word_ids: các W_* liên tiếp trong chunk, hoặc []).",
)


def load_words(toml_path: Path) -> list[dict[str, Any]]:
    data = tomllib.loads(toml_path.read_text(encoding="utf-8"))
    raw = data.get("words") or []
    out: list[dict[str, Any]] = []
    for w in raw:
        out.append(
            {
                "id": str(w.get("id") or ""),
                "word": str(w.get("word") or ""),
                "start": float(w.get("start") or 0.0),
                "end": float(w.get("end") or 0.0),
            }
        )
    return [x for x in out if x["id"]]


def load_punch_merge(path: Path) -> dict[str, dict[str, Any]]:
    """Đọc JSON punch do agent soạn (merge thuần); không suy luận punch trong Python."""
    data_object = json.loads(path.read_text(encoding="utf-8"))
    chunks = data_object.get("chunks")
    if not isinstance(chunks, list):
        raise SystemExit("--merge-punch: cần object JSON có key 'chunks' là mảng")
    out: dict[str, dict[str, Any]] = {}
    for i, row in enumerate(chunks):
        if not isinstance(row, dict):
            continue
        cid = row.get("id")
        if not cid:
            continue
        pids = row.get("punch_word_ids")
        if pids is not None and not isinstance(pids, list):
            raise SystemExit(f"--merge-punch: chunks[{i}].punch_word_ids phải là mảng hoặc bỏ")
        rat = row.get("punch_rationale")
        out[str(cid)] = {
            "punch_word_ids": [str(x) for x in (pids or [])],
            "punch_rationale": str(rat) if rat is not None else "",
        }
    return out


def build_chunks(
    words: list[dict[str, Any]],
    chunk_size: int,
    merge: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    i = 0
    n = 0
    while i < len(words):
        seg = words[i : i + chunk_size]
        ids = [w["id"] for w in seg]
        cid = f"C_{n + 1:03d}"
        id_set = set(ids)
        punch_ids: list[str] = []
        rationale = EMPTY_PUNCH_NOTE
        if cid in merge:
            punch_ids = list(merge[cid]["punch_word_ids"])
            rationale = merge[cid]["punch_rationale"] or EMPTY_PUNCH_NOTE
            for pid in punch_ids:
                if pid not in id_set:
                    raise SystemExit(f"{cid}: punch_word_ids chứa {pid} không thuộc word_ids chunk")
            if punch_ids:
                idxs = [ids.index(p) for p in punch_ids]
                for a, b in zip(idxs, idxs[1:]):
                    if b != a + 1:
                        raise SystemExit(f"{cid}: punch_word_ids phải là các từ liên tiếp trong chunk")
        chunks.append(
            {
                "id": cid,
                "word_ids": ids,
                "punch_word_ids": punch_ids,
                "punch_rationale": rationale,
            }
        )
        i += chunk_size
        n += 1
    return chunks


def write_agent_chunk_input(path: Path, words: list[dict[str, Any]], chunk_size: int) -> None:
    """Xuất cấu trúc chunk + token cho agent đọc — không có punch, không scoring."""
    chunks_out: list[dict[str, Any]] = []
    i = 0
    n = 0
    while i < len(words):
        seg = words[i : i + chunk_size]
        cid = f"C_{n + 1:03d}"
        chunks_out.append(
            {
                "id": cid,
                "tokens": [
                    {"id": w["id"], "word": w["word"], "start": w["start"], "end": w["end"]} for w in seg
                ],
            }
        )
        i += chunk_size
        n += 1
    doc = {
        "schema": "punch_agent_input_v1",
        "chunk_word_size": chunk_size,
        "instruction": "Dành cho coding agent: đọc từng chunk như lời thoại; quyết định punch chỉ bằng suy luận ngữ nghĩa (không dùng rule/score trong code). "
        "Output: merge JSON với punch_word_ids là các id liên tiếp trong chunk hoặc [].",
        "chunks": chunks_out,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def validate_partition(words: list[dict[str, Any]], chunks: list[dict[str, Any]]) -> None:
    all_ids = [w["id"] for w in words]
    seen: set[str] = set()
    for c in chunks:
        for wid in c["word_ids"]:
            if wid in seen:
                raise SystemExit(f"duplicate word_id across chunks: {wid}")
            seen.add(wid)
    if seen != set(all_ids):
        missing = set(all_ids) - seen
        extra = seen - set(all_ids)
        raise SystemExit(f"partition mismatch missing={len(missing)} extra={len(extra)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transcript", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--duration-seconds", type=float, default=0.0, help="0 = từ end của từ cuối")
    parser.add_argument("--chunk-size", type=int, default=7)
    parser.add_argument(
        "--merge-punch",
        type=Path,
        default=None,
        help='JSON do agent soạn (suy luận ngữ nghĩa): { "chunks": [ { "id": "C_001", "punch_word_ids": [], "punch_rationale": "..." } ] }',
    )
    parser.add_argument(
        "--write-agent-input",
        type=Path,
        default=None,
        help="Ghi JSON chunk+token cho agent (không punch) — dùng bước trước khi agent sinh --merge-punch.",
    )
    parser.add_argument(
        "--source-video",
        default="assets/source.mp4",
        help="Trường sourceVideo trong JSON (staticFile path)",
    )
    parser.add_argument(
        "--voice-audio",
        default="assets/voice.wav",
        help="Trường voiceAudio trong JSON",
    )
    args = parser.parse_args()

    merge = load_punch_merge(args.merge_punch) if args.merge_punch else {}

    words = load_words(args.transcript)
    if not words:
        raise SystemExit("no words in transcript")

    if args.write_agent_input:
        write_agent_chunk_input(args.write_agent_input, words, args.chunk_size)

    chunks_out = build_chunks(words, args.chunk_size, merge)
    validate_partition(words, chunks_out)

    dur = args.duration_seconds
    if dur <= 0:
        dur = max(w["end"] for w in words) + 0.25
    frames = max(1, math.ceil(dur * args.fps))

    payload = {
        "fps": args.fps,
        "durationInFrames": frames,
        "sourceVideo": args.source_video,
        "voiceAudio": args.voice_audio,
        "words": [{"id": w["id"], "word": w["word"], "start": w["start"], "end": w["end"]} for w in words],
        "punch_segments": {
            "version": 1,
            "chunk_word_size": args.chunk_size,
            "note": "Chunk do script chia. punch_word_ids do agent (LLM) gán qua suy luận ngữ nghĩa, merge bằng --merge-punch; không có heuristic chọn punch trong code.",
            "chunks": chunks_out,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.output} words={len(words)} chunks={len(chunks_out)} durationInFrames={frames}")


if __name__ == "__main__":
    main()
