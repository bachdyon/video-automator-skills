---
name: video-render-plan-builder
description: Convert VDS, creative plan, transcript, and semantic asset mapping into a detailed TOML edit decision list with crop, timing, text overlays, subtitles, motion, audio, transitions, and render instructions.
---

# Video Render Plan Builder

## Goal

Create the concrete edit decision list used by a renderer. This skill answers how each mapped asset should be edited.

Use this skill after `semantic-asset-mapper` has selected assets.

## Inputs

- VDS from `video-design-spec-builder`.
- `source/creative_plan.toml`.
- `source/transcript_word_level.toml`.
- `source/semantic_mapping.toml`.
- Optional music/SFX assets.

## Output

Write or return TOML. Default path:

```text
source/render_plan.toml
```

When a video job exists, write to:

```text
jobs/<job_id>/source/render_plan.toml
```

## Workflow

1. Set global render settings: fps, resolution, aspect ratio, duration.
2. Convert each semantic mapping into a render clip.
3. Decide crop/fit, source trim, playback speed, camera motion, transition, and color treatment.
4. Add subtitles from word-level transcript with style timing from VDS.
5. Add overlay text from creative plan.
6. Add audio plan: voice, BGM, ambience, ducking, fades.
7. Validate continuity, missing files, overlapping clips, and unreadable text timing.

## TOML Contract

```toml
[render]
fps = 30
width = 1080
height = 1920
duration_seconds = 45.0
background = "black"

[style]
vds_path = "source/vds.md"
subtitle_style = "SUBTITLES"
title_style = "MAIN_TITLE"
color_treatment = "match_vds"

[audio.voice]
file_path = "source/voice.wav"
start = 0.0
gain_db = 0.0

[audio.music]
file_path = ""
start = 0.0
gain_db = -18.0
duck_under_voice = true

[[clips]]
id = "CLIP_001"
mapping_id = "MAP_001"
file_path = "source/input/clip01.mp4"
type = "video"
timeline_start = 0.0
timeline_end = 5.2
source_start = 0.0
source_end = 5.8
fit = "cover"
crop_anchor = "center"
speed = 1.0
motion = "slow_push_in"
transition_in = "cut"
transition_out = "soft_cut"
color = "match_vds"

[[subtitles]]
start = 0.12
end = 2.4
text = "..."
words_ref = ["W_0001", "W_0002"]
style = "SUBTITLES"

[[overlays]]
id = "TXT_01"
start = 0.0
end = 3.2
text = "..."
style = "MAIN_TITLE"
position = "upper_third"
animation_in = "fade_slide"
animation_out = "fade"
```

## Quality Rules

- Render clips must not overlap unless a compositing layer is intended.
- Text must have enough on-screen time to read.
- Use word-level transcript for subtitles, not approximate script timing.
- Keep renderer-specific implementation out of this file unless the user requests one renderer only.

## Utility Script

Use the bundled script for deterministic EDL generation and validation:

```bash
python skills/video_render_plan_builder/scripts/build_render_plan.py build \
  --mapping source/semantic_mapping.toml \
  --transcript source/transcript_word_level.toml \
  --creative-plan source/creative_plan.toml \
  --voice-audio source/voice.wav \
  --output source/render_plan.toml

python skills/video_render_plan_builder/scripts/build_render_plan.py validate \
  --render-plan source/render_plan.toml
```

For a job-scoped run, pass job paths explicitly:

```bash
python skills/video_render_plan_builder/scripts/build_render_plan.py build \
  --mapping jobs/<job_id>/source/semantic_mapping.toml \
  --transcript jobs/<job_id>/source/transcript_word_level.toml \
  --creative-plan jobs/<job_id>/source/creative_plan.toml \
  --voice-audio jobs/<job_id>/source/voice.wav \
  --vds-path jobs/<job_id>/source/vds.md \
  --output jobs/<job_id>/source/render_plan.toml
```

The script converts semantic mappings into clips, creates subtitles from transcript sentences, carries overlay text from the creative plan, adds voice/music sections, and validates clip/subtitle timing.
