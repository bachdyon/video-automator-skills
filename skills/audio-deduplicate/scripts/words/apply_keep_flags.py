#!/usr/bin/env python3
"""Phase 2 helper for the audio-deduplicate skill.

Two modes:
1. APPLY mode (default): flip `keep` flags for the given W_xxxxxx ranges and
   rewrite the TOML on disk. Reformats `reconstructed_article*` text to one
   sentence per line. Preserves id/word/start/end.
2. INSPECT mode (`--print-kept`, `--diff-rewrite`, or `--dry-run`): read-only
   diagnostics for the Phase 2 exit gate.

The AI performs the semantic alignment (deciding which token spans correspond
to repeats / restarts not present in `reconstructed_article_rewrite`). This
script never decides ranges itself.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "_shared"))
from pipeline_utils import die, format_sentences_multiline, read_toml, write_toml_document  # noqa: E402


def parse_ranges(spec: str) -> set[int]:
    ids: set[int] = set()
    if not spec:
        return ids
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" in chunk:
            lo_s, hi_s = chunk.split("-", 1)
            lo = int(lo_s)
            hi = int(hi_s)
            if hi < lo:
                lo, hi = hi, lo
            for i in range(lo, hi + 1):
                ids.add(i)
        else:
            ids.add(int(chunk))
    return ids


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--words-toml", type=Path, required=True)
    parser.add_argument(
        "--remove",
        default="",
        help='ID ranges to flip keep=false. Example: "11-56,91-97,111,317-331".',
    )
    parser.add_argument(
        "--keep-only",
        default="",
        help="Inverse mode: comma-separated ranges to KEEP; everything else flipped to false.",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset all keep flags to true before applying --remove / --keep-only.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute changes but do not write the TOML. Prints flipped count.",
    )
    parser.add_argument(
        "--print-kept",
        action="store_true",
        help="After computing keep flags, print the joined kept words text and exit. Read-only when used alone.",
    )
    parser.add_argument(
        "--diff-rewrite",
        action="store_true",
        help="Print a normalized comparison: kept_text vs reconstructed_article_rewrite.text. Implies read-only.",
    )
    return parser.parse_args()


def normalise(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\wÀ-ỹ ]", " ", text or "", flags=re.UNICODE)).strip().lower()


def jaccard(a: str, b: str) -> float:
    sa = set(a.split())
    sb = set(b.split())
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def main() -> None:
    args = parse_args()
    if not args.words_toml.exists():
        die(f"words TOML not found: {args.words_toml}")

    inspect_only = args.print_kept or args.diff_rewrite
    if not inspect_only and not args.remove and not args.keep_only:
        die("must provide --remove, --keep-only, --print-kept, or --diff-rewrite")
    if args.remove and args.keep_only:
        die("provide only one of --remove or --keep-only")

    data = read_toml(args.words_toml)
    raw_words = data.get("words")
    if not isinstance(raw_words, list) or not raw_words:
        die("input TOML must contain non-empty [[words]] tables")

    remove_ids = parse_ranges(args.remove)
    keep_only_ids = parse_ranges(args.keep_only)

    flipped = 0
    kept_true = 0
    new_words: list[dict[str, Any]] = []
    for item in raw_words:
        if not isinstance(item, dict):
            die("each [[words]] entry must be a table")
        word_id = str(item.get("id") or "")
        if not word_id.startswith("W_"):
            die(f"unexpected word id format: {word_id!r}")
        try:
            num = int(word_id.split("_", 1)[1])
        except ValueError:
            die(f"unparseable word id: {word_id!r}")

        keep = True if args.reset else bool(item.get("keep", True))
        if remove_ids and num in remove_ids:
            keep = False
        if keep_only_ids and num not in keep_only_ids:
            keep = False

        if bool(item.get("keep", True)) != keep:
            flipped += 1
        if keep:
            kept_true += 1

        new_words.append(
            {
                "id": word_id,
                "word": str(item.get("word") or item.get("text") or ""),
                "start": float(item.get("start", 0.0)),
                "end": float(item.get("end", item.get("start", 0.0))),
                "keep": keep,
            }
        )

    if args.print_kept:
        kept_text = " ".join(w["word"] for w in new_words if w["keep"])
        print(kept_text)
        if not (args.remove or args.keep_only or args.reset):
            return

    if args.diff_rewrite:
        rewrite_obj = data.get("reconstructed_article_rewrite")
        rewrite_text = ""
        if isinstance(rewrite_obj, dict):
            rewrite_text = str(rewrite_obj.get("text") or "")
        kept_text = " ".join(w["word"] for w in new_words if w["keep"])
        norm_kept = normalise(kept_text)
        norm_rewrite = normalise(rewrite_text)
        score = jaccard(norm_kept, norm_rewrite)
        print(f"kept_words: {sum(1 for w in new_words if w['keep'])}/{len(new_words)}")
        print(f"jaccard(token_set): {score:.3f}")
        kept_only = sorted(set(norm_kept.split()) - set(norm_rewrite.split()))
        rewrite_only = sorted(set(norm_rewrite.split()) - set(norm_kept.split()))
        print(f"in kept only ({len(kept_only)}): {' '.join(kept_only[:30])}")
        print(f"in rewrite only ({len(rewrite_only)}): {' '.join(rewrite_only[:30])}")

    if inspect_only and not (args.remove or args.keep_only or args.reset):
        return

    if args.dry_run or inspect_only:
        print(f"DRY RUN: would flip {flipped} word(s); keep=true {kept_true}/{len(new_words)} (no file written)")
        return

    sections: list[tuple[str, dict[str, Any] | list[dict[str, Any]]]] = []
    metadata = dict(data.get("metadata") or {})
    if metadata:
        sections.append(("metadata", metadata))
    article = data.get("reconstructed_article")
    if isinstance(article, dict):
        sections.append(
            (
                "reconstructed_article",
                {**article, "text": format_sentences_multiline(str(article.get("text") or ""))},
            )
        )
    rewrite = data.get("reconstructed_article_rewrite")
    if isinstance(rewrite, dict):
        sections.append(
            (
                "reconstructed_article_rewrite",
                {**rewrite, "text": format_sentences_multiline(str(rewrite.get("text") or ""))},
            )
        )
    sections.append(("words", new_words))

    write_toml_document(args.words_toml, sections)

    print(f"flipped {flipped} word(s); keep=true count: {kept_true}/{len(new_words)}")


if __name__ == "__main__":
    main()
