---
name: podcast-dong-phuong-template
description: Instantiate the Podcast Đông Phương full-width podcast render-style template for jobs that already have a render plan, word-level transcript, and visual timeline.
---

# Podcast Đông Phương Template

Use this when a job already has:

- `source/render_plan.toml`
- `source/transcript_word_level.toml`
- visual clip timeline chosen upstream

This is a render-style template only. It does not choose footage, run semantic mapping, or rewrite the narration.

## Instantiate

```bash
.venv/bin/python skills/podcast-dong-phuong-template/scripts/instantiate.py \
  --job jobs/<job_id> \
  --highlight-color "#f3dd3d"
```

The script copies the template Remotion project into `jobs/<job_id>/remotion`, copies timeline clips and voice audio into `remotion/public/assets`, and writes `remotion/public/template-props.json`.

## Render

```bash
cd jobs/<job_id>/remotion
npm install
npm run still
npm run render
```

## Style Contract

- Output is 1080x1920 at 30fps.
- Source footage is full-width in the 9:16 canvas and cropped from the bottom.
- Edges blend into a dark blurred background layer.
- Subtitle text is yellow Asimovian, no word highlight.
- Subtitle pages break after punctuation and before capitalized sentence starts.
- Each subtitle page has at most 6 words.
