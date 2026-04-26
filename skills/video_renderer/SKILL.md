---
name: video-renderer
description: Render a final short-form video from a TOML render plan, voice audio, source assets, subtitles, overlays, and VDS style rules using the project renderer such as Remotion or FFmpeg.
---

# Video Renderer

## Goal

Execute the final render from `source/render_plan.toml` and produce a video file. For job-scoped production, create or update a dedicated Remotion project under `jobs/<job_id>/remotion/` and render that job independently.

Use this skill when the user asks to render, export, preview, or produce the final video after the render plan exists.

When this skill creates, updates, validates, previews, or renders a Remotion project, it must explicitly load and reference the official `$remotion-best-practices` skill before making Remotion-specific implementation decisions.

Before starting Remotion work, verify the official skill exists by running `scripts/ensure-remotion-skill.sh` from the repo root. If it is missing, install it with `npx skills add remotion-dev/skills --yes` after getting permission for network access.

## Script Environment Rule

Before running any renderer or bundled script from this skill, read the repo-root `.env` first. This file lives beside `jobs/`, `skills/`, and `env.example`. Check only whether required keys exist; never print secret values in logs, terminal output, TOML artifacts, or responses. Use a non-root `--env-file` only when the user explicitly provides one.

## Inputs

- `source/render_plan.toml`.
- Voice audio from `ausynclab-voice`.
- Source image/video assets.
- Optional VDS for style references.
- Project renderer implementation. For video jobs, default to a job-scoped Remotion project.

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

## Job-Scoped Remotion Layout

Each video job owns its own Remotion project:

```text
jobs/<job_id>/
  source/
    render_plan.toml
  remotion/
    package.json
    remotion.config.ts
    tsconfig.json
    src/
      Root.tsx
      Composition.tsx
      render-plan.generated.ts
      assets.generated.ts
      components/
        Scene.tsx
        MediaLayer.tsx
        SubtitleLayer.tsx
        OverlayText.tsx
        AudioLayer.tsx
        .....
      styles/
        tokens.generated.ts
        global.css
        ....
    public/
      assets/
  output/
    preview.mp4
    final_video.mp4
    thumbnail.jpg
    render_report.toml
  logs/
    render.log
    validation.log
```

Keep repo-root `.env` outside all job folders, beside `jobs/` and `skills/`. Do not create `jobs/<job_id>/source/.env` unless the user explicitly asks for a job-specific override.

## Workflow

1. Read repo-root `.env` when credentials or renderer settings are needed.
2. Validate all files referenced by `render_plan.toml` exist.
3. Validate timeline duration, overlapping clips, missing audio, missing fonts, and unsupported formats.
4. For a job-scoped run, verify/install `$remotion-best-practices`, load it, then create or update `jobs/<job_id>/remotion/` from the render plan.
5. Copy or symlink required media into `jobs/<job_id>/remotion/public/assets/`, then generate `render-plan.generated.ts` and `assets.generated.ts`.
6. Render preview or final export from inside the job's Remotion project.
7. Verify the output file exists, has nonzero duration, and includes audio.
8. Write `render_report.toml`, update `logs/render.log` when useful, and report warnings.

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
renderer = "remotion"
remotion_project_path = "jobs/<job_id>/remotion"
composition_id = "MainVideo"

[[warnings]]
code = "LOW_RES_ASSET"
message = "Asset source/input/image01.jpg was upscaled."
file_path = "source/input/image01.jpg"
```

## Quality Rules

- Prefer the repo's existing renderer over adding a new stack.
- For video jobs, prefer a dedicated Remotion project per job over a shared renderer project.
- Do not change semantic mapping during render; fix upstream files if mapping is wrong.
- Keep render implementation deterministic and reproducible from the TOML plan.
- If a browser/dev server is needed for visual verification, start it and verify the rendered page or preview before final handoff.
- For full video production, render from `jobs/<job_id>/source/render_plan.toml` and mark the `render` stage in `job.toml`.
