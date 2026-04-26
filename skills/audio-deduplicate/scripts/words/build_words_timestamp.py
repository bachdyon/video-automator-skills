#!/usr/bin/env python3
"""Build words_timestamp TOML from transcript word timestamps JSON."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "_shared"))
from pipeline_utils import die, format_sentences_multiline, write_toml_document


@dataclass(frozen=True)
class Word:
    id: str
    text: str
    start: float
    end: float
    keep: bool


def load_words(input_path: Path) -> list[Word]:
    raw = json.loads(input_path.read_text(encoding="utf-8"))
    words: list[Word] = []
    for idx, item in enumerate(raw, start=1):
        text = str(item.get("text") or item.get("word") or "").strip()
        if not text:
            continue
        words.append(
            Word(
                id=f"W_{idx:06d}",
                text=text,
                start=float(item.get("start", 0.0)),
                end=float(item.get("end", item.get("start", 0.0))),
                keep=bool(item.get("keep", True)),
            )
        )
    return words


def reconstruct_article(words: list[Word]) -> str:
    return " ".join(word.text for word in words).strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-words", type=Path, required=True, help="Input words JSON (from extract_words_timestamps.py)")
    parser.add_argument("--output-toml", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.input_words.exists():
        die(f"input words file not found: {args.input_words}")
    if args.input_words.suffix.lower() != ".json":
        die("input words file must be a .json transcript exported by extract_words_timestamps.py")
    words = load_words(args.input_words)
    if not words:
        die("word list is empty; cannot build words_timestamp.toml")

    reconstructed_article = format_sentences_multiline(reconstruct_article(words))
    sections: list[tuple[str, dict[str, Any] | list[dict[str, Any]]]] = [
        (
            "metadata",
            {
                "source_words_file": str(args.input_words),
                "mode": "two_phase_semantic_keep_review",
                "original_word_count": len(words),
                "rewrite_status": "pending",
            },
        ),
        (
            "reconstructed_article",
            {
                "text": reconstructed_article,
            },
        ),
        (
            "reconstructed_article_rewrite",
            {
                "text": "",
            },
        ),
        (
            "words",
            [
                {
                    "id": word.id,
                    "word": word.text,
                    "start": round(word.start, 3),
                    "end": round(word.end, 3),
                    "keep": word.keep,
                }
                for word in words
            ],
        ),
    ]
    write_toml_document(args.output_toml, sections)
    print(f"wrote {args.output_toml}")


if __name__ == "__main__":
    main()
