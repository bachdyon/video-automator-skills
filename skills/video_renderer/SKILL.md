---
name: video-renderer
description: Render a final short-form video from a TOML render plan, voice audio, source assets, subtitles, overlays, and VDS style rules using the project renderer such as Remotion or FFmpeg.
---

# Video Renderer

## Goal

Execute the final render from `source/render_plan.toml` and produce a video file.

Use this skill when the user asks to render, export, preview, or produce the final video after the render plan exists.

## Inputs

- `source/render_plan.toml`.
- Voice audio from `ausynclab-voice`.
- Source image/video assets.
- Optional VDS for style references.
- Project renderer implementation, usually Remotion, FFmpeg, or a local script.

## Output

Default final file:

```text
output/final_video.mp4
```

When a video job exists, write to:

```text
jobs/<job_id>/output/final_video.mp4
```

Also write a render report when useful:

```text
output/render_report.toml
```

For job-scoped runs:

```text
jobs/<job_id>/output/render_report.toml
```

## Workflow

1. Inspect the repository to identify the actual renderer stack.
2. Validate all files referenced by `render_plan.toml` exist.
3. Validate timeline duration, overlapping clips, missing audio, missing fonts, and unsupported formats.
4. Render a preview or final export using the existing project renderer.
5. If no renderer exists, create the smallest renderer module consistent with the repo and user request.
6. Verify the output file exists, has nonzero duration, and includes audio.
7. Report the output path and any render warnings.

## Render Report Contract

```toml
[render]
status = "success"
output_path = "output/final_video.mp4"
duration_seconds = 45.0
width = 1080
height = 1920
fps = 30
has_audio = true

[[warnings]]
code = "LOW_RES_ASSET"
message = "Asset source/input/image01.jpg was upscaled."
file_path = "source/input/image01.jpg"
```

## Quality Rules

- Prefer the repo's existing renderer over adding a new stack.
- Do not change semantic mapping during render; fix upstream files if mapping is wrong.
- Keep render implementation deterministic and reproducible from the TOML plan.
- If a browser/dev server is needed for visual verification, start it and verify the rendered page or preview before final handoff.
- For full video production, render from `jobs/<job_id>/source/render_plan.toml` and mark the `render` stage in `job.toml`.
