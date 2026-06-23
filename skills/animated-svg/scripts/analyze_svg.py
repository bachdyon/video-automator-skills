#!/usr/bin/env python3
"""Analyze SVG paths and optionally emit a colored debug HTML.

This is a lightweight helper for the animated-svg skill. It does not choose
semantic groups; it exposes path/subpath bounding boxes so the agent can group
the artwork safely.
"""

from __future__ import annotations

import argparse
import html
import re
from pathlib import Path


TOKEN_RE = re.compile(
    r"([MmZzLlHhVvCc])|([-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?)"
)


def fmt(value: float) -> str:
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    return f"{value:.4f}".rstrip("0").rstrip(".")


def split_path(d: str) -> list[tuple[str, tuple[float, float, float, float]]]:
    """Split a path at move commands and return normalized subpaths + raw bbox."""
    tokens = [m.group(1) or m.group(2) for m in TOKEN_RE.finditer(d.replace("\n", " "))]
    i = 0
    cmd: str | None = None
    x = y = sx = sy = 0.0
    parts: list[str] = []
    points: list[tuple[float, float]] = []
    segments: list[tuple[str, tuple[float, float, float, float]]] = []

    def is_cmd(token: str) -> bool:
        return re.fullmatch(r"[A-Za-z]", token) is not None

    def num() -> float:
        nonlocal i
        value = float(tokens[i])
        i += 1
        return value

    def add_point(px: float, py: float) -> None:
        points.append((px, py))

    def finish() -> None:
        nonlocal parts, points
        if parts and points:
            xs = [p[0] for p in points]
            ys = [p[1] for p in points]
            segments.append((" ".join(parts), (min(xs), min(ys), max(xs), max(ys))))
        parts = []
        points = []

    while i < len(tokens):
        if is_cmd(tokens[i]):
            cmd = tokens[i]
            i += 1

        if cmd in "Mm":
            first = True
            while i < len(tokens) and not is_cmd(tokens[i]):
                a, b = num(), num()
                if first:
                    finish()
                    x, y = (x + a, y + b) if cmd == "m" else (a, b)
                    sx, sy = x, y
                    parts = [f"M{fmt(x)} {fmt(y)}"]
                    add_point(x, y)
                    first = False
                    line_cmd = "l" if cmd == "m" else "L"
                else:
                    if line_cmd == "l":
                        x, y = x + a, y + b
                        parts.append(f"l{fmt(a)} {fmt(b)}")
                    else:
                        x, y = a, b
                        parts.append(f"L{fmt(x)} {fmt(y)}")
                    add_point(x, y)
        elif cmd in "Ll":
            while i < len(tokens) and not is_cmd(tokens[i]):
                a, b = num(), num()
                if cmd == "l":
                    x, y = x + a, y + b
                    parts.append(f"l{fmt(a)} {fmt(b)}")
                else:
                    x, y = a, b
                    parts.append(f"L{fmt(x)} {fmt(y)}")
                add_point(x, y)
        elif cmd in "Hh":
            while i < len(tokens) and not is_cmd(tokens[i]):
                a = num()
                x = x + a if cmd == "h" else a
                parts.append(f"{cmd}{fmt(a)}")
                add_point(x, y)
        elif cmd in "Vv":
            while i < len(tokens) and not is_cmd(tokens[i]):
                a = num()
                y = y + a if cmd == "v" else a
                parts.append(f"{cmd}{fmt(a)}")
                add_point(x, y)
        elif cmd in "Cc":
            while i < len(tokens) and not is_cmd(tokens[i]):
                vals = [num() for _ in range(6)]
                if cmd == "c":
                    cps = [
                        (x + vals[0], y + vals[1]),
                        (x + vals[2], y + vals[3]),
                        (x + vals[4], y + vals[5]),
                    ]
                    parts.append("c" + " ".join(fmt(v) for v in vals))
                else:
                    cps = [(vals[0], vals[1]), (vals[2], vals[3]), (vals[4], vals[5])]
                    parts.append("C" + " ".join(fmt(v) for v in vals))
                for px, py in cps:
                    add_point(px, py)
                x, y = cps[-1]
        elif cmd in "Zz":
            parts.append("z")
            x, y = sx, sy
            add_point(x, y)
            cmd = None
        else:
            raise ValueError(f"Unsupported SVG path command: {cmd!r}")

    finish()
    return segments


def extract_paths(svg: str) -> list[str]:
    return re.findall(r"<path\b[^>]*\bd=\"([^\"]+)\"[^>]*/?>", svg, re.S)


def make_debug_html(paths: list[str]) -> str:
    colors = [
        "#e41a1c",
        "#377eb8",
        "#4daf4a",
        "#984ea3",
        "#ff7f00",
        "#a65628",
        "#f781bf",
        "#999999",
        "#66c2a5",
        "#fc8d62",
        "#8da0cb",
        "#e78ac3",
    ]
    body = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1254" height="1254" viewBox="0 0 1254 1254">',
        '<rect width="1254" height="1254" fill="white"/>',
        '<g transform="translate(0,1254) scale(.1,-.1)" stroke="none">',
    ]
    color_index = 0
    for path_index, d in enumerate(paths):
        for sub_index, (sub_d, _) in enumerate(split_path(d)):
            color = colors[color_index % len(colors)]
            body.append(
                f'<path d="{html.escape(sub_d)}" fill="{color}" fill-opacity=".72">'
                f"<title>p{path_index}s{sub_index}</title></path>"
            )
            color_index += 1
    body.extend(["</g>", "</svg>"])
    return "\n".join(body)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("svg", type=Path)
    parser.add_argument("--debug-html", type=Path)
    args = parser.parse_args()

    svg = args.svg.read_text(errors="ignore")
    paths = extract_paths(svg)
    print(f"svg={args.svg}")
    print(f"paths={len(paths)}")
    print(f"groups={len(re.findall(r'<g\b', svg))}")
    print(f"masks={len(re.findall(r'<mask\b', svg))}")
    print(f"clipPaths={len(re.findall(r'<clipPath\b', svg))}")

    for path_index, d in enumerate(paths):
        segments = split_path(d)
        print(f"path {path_index}: segments={len(segments)}")
        for sub_index, (_, bbox) in enumerate(segments):
            print(f"  p{path_index}s{sub_index} bbox={tuple(round(v, 1) for v in bbox)}")

    if args.debug_html:
        args.debug_html.write_text(make_debug_html(paths))
        print(f"debug_html={args.debug_html}")


if __name__ == "__main__":
    main()
