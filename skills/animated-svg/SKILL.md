---
name: animated-svg
description: Create standalone animated HTML from local SVG artwork. Use when Codex needs to animate an SVG with CSS/inline browser-safe code, preserve the original visual style, group paths semantically, choose motion that matches the drawing content, and verify the result in a browser without external assets.
---

# Animated SVG

## Output Contract

- Return one standalone `.html` file with inline SVG and no external images, fonts, scripts, or CDN references.
- Preserve the original artwork style first: fills, strokes, masks, viewBox, background color, and visual weight must remain recognizable.
- Group paths by visible semantic parts, not by arbitrary path order. Use IDs like `head`, `body`, `left_arm`, `right_arm`, `legs`, `sweat_drops`, `thought_cloud`, `ground_crack`, etc. based on the actual SVG content.
- Animation must fit the drawing's action or mood. Do not reuse a previous animation theme unless the new SVG has the same story.
- Prefer CSS keyframes for standalone delivery. Use GSAP only when the user explicitly allows an external dependency or provides a local GSAP source to inline.

## Workflow

1. Inspect the SVG source:
   - Count elements: `path`, `g`, `mask`, `clipPath`, `rect`, `circle`, `text`, images.
   - Preserve any existing top-level `viewBox`, `preserveAspectRatio`, `defs`, `mask`, and transform wrappers.
2. Render the original once before editing so the visible subject is clear.
3. Run the analyzer when the SVG is path-heavy or flattened:

```bash
python3 skills/animated-svg/scripts/analyze_svg.py path/to/source.svg --debug-html /private/tmp/svg_debug.html
```

Render the debug HTML if needed:

```bash
playwright screenshot --viewport-size=1000,1000 file:///private/tmp/svg_debug.html /private/tmp/svg_debug.png
```

4. Build semantic groups:
   - Keep compound paths together when their subpaths depend on `fill-rule`, masks, or white cutouts.
   - When splitting a compound path would fill holes black, draw the outer contour in the original fill and draw cutout contours in the background fill on top.
   - Keep duplicate overprint/shadow layers synchronized with the same class animation; avoid duplicate IDs.
5. Choose content-specific motion:
   - Characters: head tilt, body bob, limb swing, face pulse, sweat pop.
   - Thought/anxiety: cloud float, scribble jitter, bubbles pulse, stress marks pop.
   - Ground/crack/danger: crack jolt, debris drop, character brace/stumble.
   - Objects/tools: small rotation, button pulse, highlight shimmer, state-specific movement.
6. Verify:
   - HTML parser succeeds.
   - `rg 'src=|href=|url\\(https?:|<img|<script' output.html` returns no external assets.
   - IDs are unique.
   - Render with Playwright or the app browser and inspect the screenshot.
   - If path splitting breaks holes or masks, revise grouping before delivery.

## Implementation Notes

- For SVGs with a global transform like `translate(...) scale(...)`, apply that transform to an inner `<g>` and animate an outer semantic `<g>` so CSS transforms do not replace the original coordinate transform.
- Use `transform-box: fill-box` and explicit `transform-origin` for every animated group.
- Keep animations loopable, usually 4 seconds unless the user asks otherwise.
- At `0%` and `100%`, return to the original pose whenever style preservation matters.
- Do not introduce decorative backgrounds, gradients, fonts, or extra illustration elements unless the user asks.

## Verification Commands

```bash
python3 - <<'PY'
from html.parser import HTMLParser
from pathlib import Path
HTMLParser().feed(Path("output.html").read_text())
print("html parser ok")
PY
```

```bash
python3 - <<'PY'
from pathlib import Path
import re
s = Path("output.html").read_text()
ids = re.findall(r'id="([^"]+)"', s)
print("duplicate ids:", sorted({i for i in ids if ids.count(i) > 1}))
PY
```

