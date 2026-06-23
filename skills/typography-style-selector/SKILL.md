---
name: typography-style-selector
description: Choose distinctive, high-quality typography for visual work. Use when creating or revising websites, apps, Remotion videos, captions, thumbnails, social posts, decks, landing pages, brand visuals, or any artifact where font choice, font pairing, scale, weight, or typographic style affects perceived quality.
---

# Typography Style Selector

Use this skill before making typography-specific design decisions. Typography should signal intent and quality immediately.

## Rules

- Avoid boring, generic typography.
- Never use: `Inter`, `Roboto`, `Open Sans`, `Lato`, or default system fonts as the primary visual style.
- Pick one distinctive font direction and use it decisively.
- Load from Google Fonts when the target runtime supports web fonts.
- State the font choice and rationale before coding or rendering typography-heavy output.
- Prefer strong contrast: display + monospace, serif + geometric sans, or a variable font used across extreme weights.
- Use extremes: `100/200` vs `800/900`, not `400` vs `600`.
- Use meaningful size jumps of `3x+` for hierarchy when the layout can support it.

## Font Directions

- **Code aesthetic:** `JetBrains Mono`, `Fira Code`, `Space Grotesk`
- **Editorial:** `Playfair Display`, `Crimson Pro`, `Fraunces`
- **Startup:** `Clash Display`, `Satoshi`, `Cabinet Grotesk`
- **Technical:** `IBM Plex Sans`, `IBM Plex Mono`, `IBM Plex Serif`, `Source Sans 3`
- **Distinctive:** `Bricolage Grotesque`, `Obviously`, `Newsreader`

## Selection Workflow

1. Identify the artifact context: video caption, UI, hero, dashboard, deck, thumbnail, or brand graphic.
2. Choose one font direction from the list above based on the audience and tone.
3. Pick one primary distinctive font. Add a secondary font only when contrast improves clarity.
4. Define hierarchy before implementation: primary display size, body/support size, emphasis weight, and line-height.
5. Check that font licensing/loading works for the runtime. If a listed font is not on Google Fonts, choose the closest Google Fonts substitute and state the substitution.
6. Implement typography consistently; do not mix many display fonts in one artifact.

## Quick Choices

- AI/tooling/productivity content: `Space Grotesk` + `JetBrains Mono`
- Founder/startup/personal brand: `Cabinet Grotesk` or `Satoshi` with a monospace accent
- Premium editorial/storytelling: `Fraunces` or `Newsreader` with a clean sans
- Technical explainer/data: `IBM Plex Sans` + `IBM Plex Mono`
- Bold social short/video hook: `Bricolage Grotesque` with `800/900` display weight

## Output Contract

Before coding, include one short sentence like:

```text
Typography choice: Space Grotesk for the main voice, JetBrains Mono for technical accents, using 800 vs 200 weight contrast.
```

Then implement the typography choice in CSS, Remotion style objects, Tailwind config/classes, or the target design system.
