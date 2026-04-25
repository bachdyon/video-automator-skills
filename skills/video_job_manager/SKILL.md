---
name: video-job-manager
description: Create and manage isolated video production jobs, including request metadata, input assets, stage artifacts, status, stale tracking, and canonical paths for the video pipeline.
---

# Video Job Manager

## Goal

Manage everything that belongs to one video-generation request as a reproducible job.

This skill does not create video content directly. It creates and maintains the job workspace that all other video skills read from and write to.

## When To Use

Use this skill when the user starts a new video request, adds reference/input assets, asks for job status, reruns part of the pipeline, or needs to locate artifacts for a specific video request.

## Default Layout

```text
jobs/
  <job_id>/
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
      previews/
      final_video.mp4
      render_report.toml
    logs/
      pipeline_status.toml
      todo.toml
```

## Responsibilities

1. Create a unique `jobs/<job_id>` directory.
2. Store the original request in `job.toml`.
3. Register reference videos, raw assets, audio, and brand files.
4. Track canonical artifact paths for every stage.
5. Mark pipeline stages as `pending`, `running`, `done`, `failed`, or `stale`.
6. Mark downstream stages stale when inputs change.
7. Provide paths that other skills should use.
8. Maintain `logs/todo.toml` as the always-current todo list for the job.

## Stage Order

```text
request
reference_style
creative_plan
voice
transcript
asset_semantics
semantic_mapping
render_plan
render
```

## Utility Script

Use the bundled script for deterministic job state management:

```bash
python skills/video_job_manager/scripts/manage_job.py create \
  --title "Morning routine ad" \
  --brief "Create a reflective 45s TikTok..." \
  --platform tiktok \
  --language vi \
  --target-duration 45

python skills/video_job_manager/scripts/manage_job.py register-input \
  --job jobs/2026-04-25_001_morning-routine-ad \
  --kind raw_assets \
  --path /path/to/clip.mp4 \
  --copy

python skills/video_job_manager/scripts/manage_job.py mark-stage \
  --job jobs/2026-04-25_001_morning-routine-ad \
  --stage creative_plan \
  --status done \
  --output source/creative_plan.toml

python skills/video_job_manager/scripts/manage_job.py stale-from \
  --job jobs/2026-04-25_001_morning-routine-ad \
  --stage voice \
  --reason "voice audio changed"

python skills/video_job_manager/scripts/manage_job.py status \
  --job jobs/2026-04-25_001_morning-routine-ad

python skills/video_job_manager/scripts/manage_job.py todo \
  --job jobs/2026-04-25_001_morning-routine-ad
```

## TOML Contract

`job.toml` must include:

```toml
[job]
id = "2026-04-25_001_morning-routine-ad"
title = "Morning routine ad"
status = "created"
created_at = "2026-04-25T10:00:00+07:00"
updated_at = "2026-04-25T10:00:00+07:00"

[request]
brief = "..."
platform = "tiktok"
language = "vi"
target_duration_seconds = 45

[paths]
job_dir = "jobs/2026-04-25_001_morning-routine-ad"
input_dir = "input"
reference_dir = "input/reference"
raw_assets_dir = "input/raw_assets"
source_dir = "source"
output_dir = "output"

[[inputs]]
kind = "raw_assets"
path = "input/raw_assets/clip01.mp4"
original_path = "/path/to/clip01.mp4"

[[stages]]
name = "creative_plan"
status = "done"
output = "source/creative_plan.toml"
updated_at = "..."
reason = ""
```

`logs/todo.toml` must be kept in sync with stage state:

```toml
[[todos]]
id = "TODO_003"
stage = "creative_plan"
title = "Create script, scene intents, and overlay plan"
status = "done"
output = "source/creative_plan.toml"
updated_at = "..."
reason = ""
```

Todo status mapping:

```text
pending -> todo
running -> doing
done -> done
failed -> blocked
stale -> todo
```

## Quality Rules

- Never use shared `source/` for a real video job when a job directory exists.
- Do not overwrite another job's artifacts.
- Register input changes before rerunning pipeline stages.
- When a stage's input changes, mark downstream stages stale instead of pretending they are valid.
- Keep all paths in `job.toml` relative to the job directory when possible.
- Every state-changing command must refresh `logs/todo.toml`.
