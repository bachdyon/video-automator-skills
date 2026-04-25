---
name: video-production-orchestrator
description: Coordinate the full long-term short-form video pipeline from sample video, new creative request, raw assets, voice generation, transcription, semantic mapping, render planning, and final rendering.
---

# Video Production Orchestrator

## Goal

Run the complete video-generation pipeline from:

- sample video
- new user request
- raw assets

to:

- final rendered short-form video

This skill coordinates other skills. It should not replace their specialized work.

## When To Use

Use this skill when the user asks to create, regenerate, preview, or produce a complete new video using a reference/sample style and new source material.

## Pipeline Order

0. **Job Workspace**
   - Use `video-job-manager`.
   - Input: user request, reference media, raw assets.
   - Output: `jobs/<job_id>/job.toml` and canonical job folders.
   - All later paths should be inside this job directory.

1. **Reference Style**
   - Use `video-design-spec-builder`.
   - Input: sample/reference video.
   - Output: reusable VDS at `jobs/<job_id>/source/vds.md`.

2. **Creative Plan**
   - Use `video-creative-planner`.
   - Input: user brief + VDS.
   - Output: `jobs/<job_id>/source/creative_plan.toml`.

3. **Voice**
   - Use `ausynclab-voice`.
   - Input: voiceover script from creative plan.
   - Output: `jobs/<job_id>/source/voice.wav` or `.mp3`, plus `jobs/<job_id>/source/voice_selection.toml`.

4. **Transcript Timing**
   - Use `openai-whisper-word-timestamps`.
   - Input: generated voice audio.
   - Output: `jobs/<job_id>/source/transcript_word_level.toml`.

5. **Asset Index**
   - Use `asset-semantic-extractor`.
   - Input: raw image/video assets.
   - Output: `jobs/<job_id>/source/asset_semantics.toml`.

6. **Semantic Mapping**
   - Use `semantic-asset-mapper`.
   - Input: creative plan + transcript + asset semantics + VDS.
   - Output: `jobs/<job_id>/source/semantic_mapping.toml`.

7. **Render Plan**
   - Use `video-render-plan-builder`.
   - Input: VDS + creative plan + transcript + semantic mapping.
   - Output: `jobs/<job_id>/source/render_plan.toml`.

8. **Render**
   - Use `video-renderer`.
   - Input: render plan + media files.
   - Output: `jobs/<job_id>/output/final_video.mp4`.

## Artifact Contract

Default workspace layout:

```text
jobs/<job_id>/
  job.toml
  input/
    reference/
    raw_assets/
    audio/
    brand/
  source/
    vds.md
    creative_plan.toml
    voice_selection.toml
    voice.wav
    transcript_word_level.toml
    asset_semantics.toml
    semantic_mapping.toml
    render_plan.toml
  output/
    final_video.mp4
    render_report.toml
```

## Checkpoints

Before moving to the next step, verify:

- Job exists and `job.toml` tracks the request and inputs.
- VDS exists and contains style/timing guidance.
- Creative plan has script and scene intents.
- Voice audio exists and is playable.
- Transcript covers the full voice duration.
- Asset semantics cover all provided assets.
- Semantic mapping is continuous and each row has `start`, `end`, `file_path`, and `reason`.
- Render plan references existing files only.
- Final render exists and has audio.

## Recovery Rules

- If request, reference, or raw inputs are registered/changed, use `video-job-manager` to mark affected downstream stages stale.
- If voice changes, rerun transcript, mapping, render plan, and render.
- If assets change, rerun asset semantics, mapping, render plan, and render.
- If VDS changes, rerun creative plan, mapping, render plan, and render.
- If only crop/transition/text styling changes, rerun render plan and render.
- If only renderer code changes, rerun render.

## Quality Rules

- Keep each stage's output on disk so the pipeline is debuggable.
- Do not hide failures by skipping stages.
- Prefer updating the smallest stale artifact rather than regenerating everything.
- Ask the user only for missing credentials, missing source media, or creative decisions that cannot be inferred safely.
- Mark each completed stage in `job.toml` via `video-job-manager`.
