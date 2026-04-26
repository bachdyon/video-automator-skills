---
name: asset-semantic-extractor
description: Analyze one or more image or video assets and produce a TOML semantic index describing visual content, style, scenes, timestamps, objects, mood, and reuse constraints for video assembly.
---

# Asset Semantic Extractor

## Script Environment Rule

Before running any bundled script from this skill, read the repo-root `.env` first. This file lives beside `jobs/`, `skills/`, and `env.example`. Check only whether required keys exist; never print secret values in logs, terminal output, TOML artifacts, or responses. Use a non-root `--env-file` only when the user explicitly provides one.

## Goal

Create a reusable semantic index for raw image and video assets. This skill does not choose where assets go in the final video; it only describes what each asset contains.

Use this skill when the user provides folders or files of raw images/videos and needs them prepared for semantic mapping.

## Inputs

- One or more image/video file paths.
- Optional VDS or creative plan for vocabulary alignment.

## Output

Write or return TOML. Default path:

```text
source/asset_semantics.toml
```

When a video job exists, write to:

```text
jobs/<job_id>/source/asset_semantics.toml
```

## Workflow

1. Inventory all assets and preserve absolute or workspace-relative paths.
2. For images: describe visible subjects, environment, action, mood, style, composition, colors, and possible usage.
3. For videos: describe global style and split into scenes with start/end seconds.
4. Label each scene with semantic tags useful for matching against script and voiceover.
5. Note constraints: low quality, shaky footage, text baked into video, faces, logos, privacy risks, unusable segments.
6. Do not assign assets to the final timeline; leave that to `semantic-asset-mapper`.

## TOML Contract

```toml
[[assets]]
id = "AST_001"
file_path = "source/input/clip01.mp4"
type = "video"
duration_seconds = 18.4
summary = "..."
visual_style = "handheld, natural light, warm color, shallow depth of field"
mood = ["calm", "intimate"]
tags = ["home", "morning", "routine"]
privacy_notes = []
quality_notes = []

[[assets.scenes]]
id = "AST_001_SC_01"
start = 0.0
end = 5.8
description = "..."
subjects = ["..."]
actions = ["..."]
environment = "..."
shot_type = "medium shot"
camera_motion = "slow handheld drift"
composition = "subject centered"
colors = ["warm white", "muted green"]
mood = ["quiet", "reflective"]
semantic_tags = ["routine", "before_state"]
recommended_uses = ["intro", "reflective beat"]
avoid_uses = ["high energy transition"]
```

For images, set `duration_seconds = 0.0` and create one scene from `0.0` to `0.0`.

## Quality Rules

- Scene timestamps are seconds as floats.
- Descriptions must be visual and factual before interpretive.
- Keep semantic tags stable and lowercase.
- Flag personal identifiers instead of copying them into reusable outputs.

## Utility Script

Use the bundled probe script for deterministic media inventory before semantic analysis:

```bash
python skills/asset_semantic_extractor/scripts/probe_assets.py source/input \
  --output source/asset_semantics.toml \
  --sample-frames 3 \
  --scene-window-seconds 8
```

For a job-scoped run:

```bash
python skills/asset_semantic_extractor/scripts/probe_assets.py jobs/<job_id>/input/raw_assets \
  --output jobs/<job_id>/source/asset_semantics.toml \
  --sample-dir jobs/<job_id>/source/asset_samples \
  --sample-frames 3 \
  --scene-window-seconds 8
```

The script scans folders, identifies images/videos, reads duration/resolution/fps with `ffprobe` when available, optionally extracts video sample frames with `ffmpeg`, and writes a TOML scaffold. After this, use visual analysis to fill `summary`, `description`, `mood`, `semantic_tags`, and scene details.
