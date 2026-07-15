#!/usr/bin/env python3
"""LyricFind search client for lyric context lookup."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from pipeline_utils import _ssl_context


BASE_URL = "https://lyrics.lyricfind.com/api/v1/search"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/149.0.0.0 Safari/537.36"
)


def strip_html(value: str) -> str:
    text = re.sub(r"</?em>", "", value or "")
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(text).strip()


def fold(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value or "")
    without_marks = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", without_marks.lower()).strip()


def request_json(params: dict[str, str], user_agent: str, timeout: int) -> dict[str, Any]:
    query = urllib.parse.urlencode(params)
    request = urllib.request.Request(
        f"{BASE_URL}?{query}",
        headers={
            "Accept": "application/json",
            "User-Agent": user_agent,
        },
    )
    urlopen_kw: dict[str, Any] = {"timeout": timeout}
    ctx = _ssl_context()
    if ctx is not None:
        urlopen_kw["context"] = ctx
    with urllib.request.urlopen(request, **urlopen_kw) as response:
        return json.loads(response.read().decode("utf-8"))


def artist_names(track: dict[str, Any]) -> list[str]:
    names: list[str] = []
    artist = track.get("artist") or {}
    if isinstance(artist, dict) and artist.get("name"):
        names.append(str(artist["name"]))
    for item in track.get("artists") or []:
        if isinstance(item, dict) and item.get("name"):
            names.append(str(item["name"]))
    return names


def best_track(data: dict[str, Any], wanted_track: str, wanted_artist: str) -> dict[str, Any] | None:
    tracks = data.get("tracks") or []
    if not tracks:
        return None

    wanted_track_fold = fold(wanted_track)
    wanted_artist_fold = fold(wanted_artist)

    def rank(track: dict[str, Any]) -> tuple[int, float]:
        title_candidates = [
            str(track.get("title") or ""),
            str(track.get("titleSimple") or ""),
            str(track.get("titleRomanized") or ""),
        ]
        title_match = any(fold(title) == wanted_track_fold for title in title_candidates if title)
        title_contains = any(wanted_track_fold and wanted_track_fold in fold(title) for title in title_candidates if title)
        artists_folded = [fold(name) for name in artist_names(track)]
        artist_match = any(wanted_artist_fold and wanted_artist_fold in name for name in artists_folded)
        verified = bool(track.get("lrc_verified"))
        has_lrc = bool(track.get("has_lrc"))
        score = float(track.get("score") or 0.0)
        priority = 0
        if title_match:
            priority += 100
        elif title_contains:
            priority += 50
        if artist_match:
            priority += 40
        if verified:
            priority += 5
        if has_lrc:
            priority += 2
        return (priority, score)

    return sorted(tracks, key=rank, reverse=True)[0]


def enrich_track(track: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(track)
    if "context" in enriched:
        enriched["context_plain"] = strip_html(str(enriched.get("context") or ""))
    if "snippet" in enriched:
        enriched["snippet_plain"] = strip_html(str(enriched.get("snippet") or ""))
    return enriched


def write_text(path: str | None, text: str) -> None:
    if not path:
        return
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text.rstrip() + "\n", encoding="utf-8")


def write_json(path: str | None, data: Any, pretty: bool) -> None:
    if not path:
        return
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2 if pretty else None) + "\n", encoding="utf-8")


def command_search(args: argparse.Namespace) -> int:
    query = args.query or " ".join(part for part in [args.track, args.artist] if part).strip()
    if not query:
        print("Missing query. Pass --query or --track/--artist.", file=sys.stderr)
        return 2

    params = {
        "reqtype": "default",
        "territory": args.territory,
        "searchtype": "track",
        "all": query,
        "alltracks": "yes" if args.alltracks else "no",
        "limit": str(args.limit),
        "output": "json",
        "useragent": args.user_agent,
    }
    data = request_json(params, args.user_agent, args.timeout_seconds)
    best = best_track(data, args.track or query, args.artist or "")
    enriched_best = enrich_track(best) if best else None

    output_data = dict(data)
    if enriched_best:
        output_data["best_track"] = enriched_best
    write_json(args.output, output_data, args.pretty)

    if enriched_best:
        context_plain = str(enriched_best.get("context_plain") or "")
        write_text(args.context_output, context_plain)

    summary = {
        "response": data.get("response"),
        "totalresults": data.get("totalresults"),
        "totalpages": data.get("totalpages"),
        "best": None,
        "output": args.output,
        "context_output": args.context_output,
    }
    if enriched_best:
        summary["best"] = {
            "lfid": enriched_best.get("lfid"),
            "title": enriched_best.get("title"),
            "artist": (enriched_best.get("artist") or {}).get("name") if isinstance(enriched_best.get("artist"), dict) else None,
            "artists": artist_names(enriched_best),
            "duration": enriched_best.get("duration"),
            "score": enriched_best.get("score"),
            "has_lrc": enriched_best.get("has_lrc"),
            "lrc_verified": enriched_best.get("lrc_verified"),
            "lyricfind_url": enriched_best.get("lyricfind_url"),
            "snippet": enriched_best.get("snippet_plain"),
        }
    print(json.dumps(summary, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    search = subparsers.add_parser("search", help="Search LyricFind track lyrics")
    search.add_argument("--query", default="", help="Free text query for LyricFind 'all' parameter")
    search.add_argument("--track", default="", help="Track title hint for best-match ranking")
    search.add_argument("--artist", default="", help="Artist hint for best-match ranking")
    search.add_argument("--territory", default="VN")
    search.add_argument("--limit", type=int, default=25)
    search.add_argument("--alltracks", action="store_true", help="Pass alltracks=yes")
    search.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    search.add_argument("--timeout-seconds", type=int, default=30)
    search.add_argument("--output", default="", help="Optional full JSON output path")
    search.add_argument("--context-output", default="", help="Optional best-track plain lyric context output path")
    search.add_argument("--pretty", action="store_true")
    search.set_defaults(func=command_search)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
