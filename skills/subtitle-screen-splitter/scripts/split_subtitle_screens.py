#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from pathlib import Path
from typing import Any


WORD_RE = re.compile(r"\S+")
LEADING_TOKEN_CHARS = "\"'([“‘«"
TRAILING_TOKEN_CHARS = ",.!?;:…\"')]}»”"
SPLIT_PUNCTUATION = set(",.!?;:…")


def is_capitalized_word(text: str) -> bool:
    token = text.strip().lstrip("\"'([“‘«")
    if not token:
        return False
    first = token[0]
    if not first.isalpha():
        return False
    return first == first.upper() and first != first.lower()


def ends_with_split_punctuation(text: str) -> bool:
    token = text.strip().rstrip("\"')]}»”")
    return bool(token) and token[-1] in SPLIT_PUNCTUATION


def plain_text_words(text: str) -> list[dict[str, Any]]:
    return [
        {"id": f"W_{index:04d}", "word": match.group(0), "start": 0.0, "end": 0.0}
        for index, match in enumerate(WORD_RE.finditer(text), start=1)
    ]


def comparable_token(text: str) -> str:
    return text.strip().lstrip(LEADING_TOKEN_CHARS).rstrip(TRAILING_TOKEN_CHARS).casefold()


def transcript_words(path: Path) -> list[dict[str, Any]]:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    words = data.get("words") or []
    if not isinstance(words, list):
        raise SystemExit(f"error: {path} has no [[words]] array")
    full_text = str((data.get("metadata") or {}).get("text") or "")
    if not full_text:
        return words

    display_tokens = [match.group(0) for match in WORD_RE.finditer(full_text)]
    if not display_tokens:
        return words

    output: list[dict[str, Any]] = []
    display_index = 0
    for word in words:
        cloned = dict(word)
        base = comparable_token(str(word.get("word") or word.get("text") or ""))
        while display_index < len(display_tokens):
            candidate = display_tokens[display_index]
            display_index += 1
            if comparable_token(candidate) == base:
                cloned["word"] = candidate
                break
        output.append(cloned)
    return output



def split_pages(
    words: list[dict[str, Any]],
    *,
    max_words: int,
    max_chars: int,
    split_on_capitalized: bool,
    split_on_punctuation: bool,
) -> list[dict[str, Any]]:
    pages: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []

    def page_text(items: list[dict[str, Any]]) -> str:
        return " ".join(str(item.get("word") or item.get("text") or "").strip() for item in items).strip()

    def flush() -> None:
        nonlocal current
        if not current:
            return
        pages.append(
            {
                "id": f"PAGE_{len(pages) + 1:04d}",
                "text": page_text(current),
                "start": float(current[0].get("start") or 0.0),
                "end": float(current[-1].get("end") or current[-1].get("start") or 0.0),
                "word_ids": [str(item.get("id") or "") for item in current if item.get("id")],
                "words": [
                    {
                        "id": str(item.get("id") or ""),
                        "word": str(item.get("word") or item.get("text") or ""),
                        "start": float(item.get("start") or 0.0),
                        "end": float(item.get("end") or item.get("start") or 0.0),
                    }
                    for item in current
                ],
            }
        )
        current = []

    for word in words:
        text = str(word.get("word") or word.get("text") or "").strip()
        if not text:
            continue

        if split_on_capitalized and current and is_capitalized_word(text):
            flush()

        candidate = current + [word]
        if current and (len(candidate) > max_words or len(page_text(candidate)) > max_chars):
            flush()

        current.append(word)

        if split_on_punctuation and ends_with_split_punctuation(text):
            flush()

    flush()
    return pages


def main() -> int:
    parser = argparse.ArgumentParser(description="Split subtitles into screen-sized pages.")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--text", help="Plain subtitle text to split.")
    source.add_argument("--transcript", type=Path, help="Word-level transcript TOML with [[words]].")
    parser.add_argument("--output", type=Path, help="Write JSON pages to this path; defaults to stdout.")
    parser.add_argument("--max-words", type=int, default=7)
    parser.add_argument("--max-chars", type=int, default=26)
    parser.add_argument("--no-capitalized-split", action="store_true")
    parser.add_argument("--no-punctuation-split", action="store_true")
    args = parser.parse_args()

    words = plain_text_words(args.text) if args.text is not None else transcript_words(args.transcript)
    pages = split_pages(
        words,
        max_words=args.max_words,
        max_chars=args.max_chars,
        split_on_capitalized=not args.no_capitalized_split,
        split_on_punctuation=not args.no_punctuation_split,
    )
    output = json.dumps({"pages": pages}, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
