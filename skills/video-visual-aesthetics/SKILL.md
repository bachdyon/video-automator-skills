---
name: video-visual-aesthetics
description: Direct distinctive visual design for videos rendered from HTML, CSS, JavaScript, or Remotion. Use when creating or revising video visuals, scene layouts, motion systems, backgrounds, captions, design briefs, render plans, or HTML/CSS/JS video compositions where the output should avoid generic AI/template aesthetics and feel intentionally art-directed.
---

# Video Visual Aesthetics

Use this skill before making visual-design decisions for videos rendered from HTML, CSS, JavaScript, or Remotion. The output is a moving video, not an interactive website, so every design decision must serve readability, timing, safe area, frame composition, motion rhythm, and render stability.

## Required Dependencies

- If the work involves Remotion-specific code, rendering, previewing, or validation, load and follow `$remotion-best-practices` before making Remotion-specific decisions.
- If the video has captions, headlines, title cards, thumbnail text, kinetic typography, or any typography-heavy layout, load `$typography-style-selector` first and use its typography decision. Do not duplicate or override its font rules unless the project context clearly requires it.
- If overlays may cover people, products, or important footage, use `$overlay-subject-placement` before finalizing text or graphic placement.

## Design Brief First

Before coding, writing a render plan, or changing a composition, state a short design brief:

```text
Video visual brief:
- Visual concept:
- Intended mood:
- Typography decision: from $typography-style-selector, if text-heavy
- Color system:
- Composition strategy:
- Motion strategy:
- Scene structure:
- Background treatment:
- Safe-area/readability plan:
- Anti-default choices:
```

## Core Rules

- Design frame-by-frame. Each important frame needs one clear visual anchor, strong hierarchy, and intentional negative space.
- Optimize for the target aspect ratio. Do not simply scale a 9:16 layout into 1:1 or 16:9.
- Keep platform UI and mobile viewing in mind. In 9:16, keep critical text and subject detail inside a conservative center-safe area, and avoid placing essential text at the extreme top or bottom.
- Treat motion as direction, not decoration. Animation should guide attention, reveal meaning, transition scenes, or sync to voiceover/music.
- Prefer one or two memorable motion moments over many scattered fades.
- Use backgrounds to create atmosphere and depth: layered gradients, subtle texture/noise, grids, masks, light sweeps, paper grain, scanlines, blueprint lines, broadcast graphics, or contextual footage.
- Use CSS variables or shared constants for color, spacing, timing, and typography so the visual system stays consistent across scenes.
- Make animation deterministic for frame-by-frame rendering. Avoid unseeded randomness and runtime-dependent behavior.
- Ensure fonts and external assets load reliably before render. Prefer local or stable assets for production renders.

## Scene System

For multi-scene videos, define each scene by role, not just by layout:

- `hook`: immediate visual interest and one sharp idea.
- `explain`: clear hierarchy, controlled density, supportive visuals.
- `contrast`: split, compare, interrupt, or change rhythm.
- `proof`: evidence, examples, footage, charts, or concrete details.
- `transition`: motion bridge between ideas.
- `cta`: simple, decisive, and visually quieter than the hook unless the brief says otherwise.

Each scene should have a visual role, text density, motion in/out, and background treatment. Do not reuse one generic layout for every scene when the narrative role changes.

## Text And Caption Rules

- On-screen text should support the voiceover, not transcribe everything unless the task is explicitly caption-first.
- Keep each screen to one main idea.
- Captions need a stable zone and must not compete with headline text.
- Use emphasis selectively through scale, weight, color, masking, or timed motion. Do not highlight everything.
- Do not cover faces, products, hands, important UI, or key footage details with text or overlays.
- Use stroke, shadow, or a subtle backplate only when needed for contrast on complex footage.

## HTML/CSS/JS Render Constraints

- Use fixed output dimensions and explicit responsive constraints for the target render.
- Avoid layout shift from dynamic text, late-loading fonts, or content-dependent sizing.
- Avoid hover, scroll, input, and interaction states as the primary visual behavior; video playback has no user interaction.
- Drive timing from frame/time values, not from browser events.
- Keep effects performant enough for repeated rendering.
- Do not rely on unstable remote assets, runtime network calls, or non-deterministic browser behavior.

## Avoid Generic AI Video Aesthetics

Avoid:

- Generic purple/blue gradients.
- Floating rounded cards everywhere.
- Default fonts or typography without a clear visual role.
- Center-aligned text in every scene.
- Website landing-page layouts repurposed as video frames.
- Identical fade/scale animations across all elements.
- Decorative backgrounds unrelated to the topic.
- A visual system that could fit any video without change.

The goal is not to be weird. The goal is a controlled, context-specific visual direction that looks intentionally art-directed and remains readable while moving.
