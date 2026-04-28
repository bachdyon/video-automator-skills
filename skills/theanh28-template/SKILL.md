---
name: theanh28-template
description: "Use this when the user asks to create or render a short Vietnamese social video using the Theanh28-style Remotion template: AI news intro overlay, hard cut, then source clip playback. Also use when optimizing, instantiating, or parameterizing templates/theanh28."
---

# Theanh28 Template

Use this skill to produce a token-light Remotion job from `templates/theanh28`.
It reuses a fixed visual system and only varies the inputs.

Before Remotion-specific decisions, load `.agents/skills/remotion-best-practices/SKILL.md` and verify the skill exists with:

```bash
scripts/ensure-remotion-skill.sh
```

## Minimal Inputs

Required for a renderable job:

- `source_clip`: source video path.
- `intro_voice`: WAV/MP3 narration for the intro.
- `main_headline`: short hook shown in the lower news panel.
- `video_credit`: source credit text, for example `VIDEO: ...`.

Recommended:

- `intro_script`: the text read by the intro voice.
- `date_stamp`: display date; default is today in `DD/MM/YYYY`.

Optional style knobs:

- `brand_number` default `#28`
- `brand_label` default `TRENDING`
- `logo_path` path to a brand logo image; when provided it replaces the text brand lockup.
- `overlay_color` default `rgba(4, 102, 89, 0.9)`
- `headline_font_scale` default `1.0`
- `intro_object_position` default `center 18%`
- `intro_transform` default `translateY(-5%) scale(1.06)`

## Workflow

1. If the job has user raw assets and no `source/asset_semantics.toml`, follow the repo asset rule first: run `$asset-semantic-extractor`.
2. If `main_headline` or `intro_script` is missing, derive them from the user brief and asset semantics. Keep the intro short; do not re-plan the whole video unless the user asks.
3. Generate or receive `intro_voice` through the normal voice workflow.
4. Instantiate the template:

```bash
python3 skills/theanh28-template/scripts/instantiate.py \
  --job-dir jobs/<job_id> \
  --source-clip path/to/source.mp4 \
  --intro-voice path/to/voice.wav \
  --main-headline "..." \
  --intro-script "..." \
  --video-credit "VIDEO: ..." \
  --logo-path path/to/logo.png
```

5. Render from `jobs/<job_id>/remotion`:

```bash
npm run render
```

## Contract

The compact template contract is `templates/theanh28/template.toml`.
Load it for defaults and style tokens. Only load `templates/theanh28/reference/vds.md` when changing the visual DNA.

The script writes:

- `source/template_params.toml`
- `source/creative_plan.toml`
- `source/render_plan.toml`
- `remotion/public/template-props.json`
- `remotion/public/assets/source.mp4`
- `remotion/public/assets/voice.wav`

The Remotion bundle reads `template-props.json`; do not hardcode per-job headline, credit, source path, or duration in `Root.tsx`.
