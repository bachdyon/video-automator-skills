---
name: semantic-asset-mapper
description: Match transcript or scene intents to semantically indexed image/video assets and produce a TOML timeline mapping with start, end, file_path, selected source segment, and reason.
---

# Semantic Asset Mapper

## Script Environment Rule

Before running any bundled script from this skill, read the repo-root `.env` first. This file lives beside `jobs/`, `skills/`, and `env.example`. Check only whether required keys exist; never print secret values in logs, terminal output, TOML artifacts, or responses. Use a non-root `--env-file` only when the user explicitly provides one.

## Goal

Map the spoken content and scene intent of a new video to the best matching assets. This skill decides which asset appears when and why.

Use this skill after transcript/scene intents and asset semantic index are available.

## Inputs

- `source/creative_plan.toml` from `video-creative-planner`.
- `source/transcript_word_level.toml` from `openai-whisper-word-timestamps`.
- `source/asset_semantics.toml` from `asset-semantic-extractor`.
- Optional VDS for pacing and scene role constraints.

## Output

Write or return TOML. Default path:

```text
source/semantic_mapping.toml
```

When a video job exists, write to:

```text
jobs/<job_id>/source/semantic_mapping.toml
```

## Workflow

1. Read scene intents, transcript sentences, and asset semantics.
2. Align scene boundaries to transcript timing when possible.
3. Choose assets based on semantic fit, mood fit, shot type, visual continuity, and quality constraints.
4. Prefer matching source video sub-scenes over entire clips.
5. Use still images only when they fit the pacing or no stronger video exists.
6. Fill gaps with the closest semantically compatible asset and mark the reason.
7. Do not specify final crop, transitions, text animation, or render parameters; leave that to `video-render-plan-builder`.

## Required Minimal Contract

The core list must include exactly these fields for every mapping:

```toml
[[mappings]]
start = 0.0
end = 5.2
file_path = "source/input/clip01.mp4"
reason = "Matches the opening line about a quiet morning routine."
```

## Extended Contract

Use the extended fields whenever source scene details are available:

```toml
[[mappings]]
id = "MAP_001"
scene_id = "SC_01"
asset_id = "AST_001"
asset_scene_id = "AST_001_SC_01"
start = 0.0
end = 5.2
file_path = "source/input/clip01.mp4"
source_start = 0.0
source_end = 5.8
fit_score = 0.86
fit_labels = ["semantic", "mood", "pacing"]
reason = "Matches the opening line about a quiet morning routine."
fallback = false
warnings = []
```

## Quality Rules

- Never map an asset segment marked unusable unless no alternative exists; then set `fallback = true`.
- Avoid repeating the same visual too often unless the VDS calls for repetition.
- Respect privacy notes from asset semantics.
- Keep timeline continuous unless intentional silence/black screen is specified.

## Utility Script

Use the bundled script for baseline mapping and validation:

```bash
python skills/semantic_asset_mapper/scripts/map_assets.py build \
  --creative-plan source/creative_plan.toml \
  --transcript source/transcript_word_level.toml \
  --asset-semantics source/asset_semantics.toml \
  --output source/semantic_mapping.toml

python skills/semantic_asset_mapper/scripts/map_assets.py validate \
  --mapping source/semantic_mapping.toml
```

For a job-scoped run, pass job paths explicitly:

```bash
python skills/semantic_asset_mapper/scripts/map_assets.py build \
  --creative-plan jobs/<job_id>/source/creative_plan.toml \
  --transcript jobs/<job_id>/source/transcript_word_level.toml \
  --asset-semantics jobs/<job_id>/source/asset_semantics.toml \
  --output jobs/<job_id>/source/semantic_mapping.toml
```

The script performs deterministic token/tag scoring, creates continuous mapping rows, and validates gaps, overlaps, invalid ranges, and missing files. Use LLM judgment to improve semantic choices and reasons after the baseline exists.
