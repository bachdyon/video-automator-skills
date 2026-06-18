---
name: add-job-to-showcases
description: Add a finished VAS job to the public showcases repository by copying only its output/ folder. Use when the user asks to publish, mirror, archive, or document a job under showcases and update showcase docs.
---

# Add Job To Showcases

## Overview

Use this skill to create a public showcase entry from a finished `jobs/<job_id>/` folder. A showcase entry must contain only `output/`, especially `output/final_video.mp4`, so the public repo exposes rendered media without raw inputs, transcripts, private metadata, TTS task data, or internal planning files.

Do not copy `input/`, `source/`, `logs/`, `job.toml`, `remotion/`, `node_modules/`, `.git`, cache/build folders, TTS device/task metadata, Telegram responses, or any other non-output artifact into `showcases/`.

## Workflow

1. Identify the source job and showcase target.
   - Source must be `jobs/<job_id>/`.
   - Target should normally be `showcases/<job_id>/`.
   - If the user asks for a different public slug, confirm it will not hide the original job id from docs.
   - Check `output/final_video.mp4` exists before copying.

2. Inspect an existing showcase before copying if the pattern is unclear.
   - Every public showcase entry should have this shape:

```text
showcases/<job_id>/
└── output/
```

3. Copy only `output/` into `showcases/`.
   - Do not overwrite an existing showcase unless the user explicitly asks to refresh it.
   - A safe copy command is:

```bash
mkdir -p showcases/<job_id>
rsync -a --delete jobs/<job_id>/output/ showcases/<job_id>/output/
```

4. Verify the target.
   - Confirm the showcase has no top-level entries except `output/`:

```bash
find showcases/<job_id> -mindepth 1 -maxdepth 1 ! -name output -print
```

   - Check media metadata for the public video:

```bash
ffprobe -v error \
  -show_entries format=duration,size \
  -show_entries stream=codec_name,codec_type,width,height,avg_frame_rate \
  -of json \
  showcases/<job_id>/output/final_video.mp4
```

5. Update docs.
   - Add the video to the right section in `docs/showcases.mdx`, or create a new format section if the job demonstrates a new format.
   - Use this public raw URL pattern for embedded videos:

```text
https://github.com/bachdyon/vas-showcases/raw/refs/heads/main/<job_id>/output/final_video.mp4
```

   - If this skill itself is newly added or changed, keep `docs/skills/add-job-to-showcases.mdx`, `docs/skills/index.mdx`, and `docs/docs.json` in sync.

6. Check both repos.
   - `showcases/` and `docs/` are separate Git repositories.
   - Run status in the root, in `showcases/`, and in `docs/` so the final response can state exactly which repo has changes.

```bash
git status --short
git -C showcases status --short
git -C docs status --short
```

## Quality Gates

Before final response, confirm:

- `showcases/<job_id>/output/final_video.mp4` exists.
- `showcases/<job_id>/` contains only `output/` at top level.
- No `input/`, `source/`, `logs/`, `job.toml`, `remotion/`, TTS task metadata, or Telegram response JSON exists anywhere inside `showcases/<job_id>`.
- The docs embed URL points at `bachdyon/vas-showcases` and the same `<job_id>`.
- The final response mentions that `showcases/` and `docs/` may need their own commits or pushes if they are separate repos.

This skill does not create, edit, render, preview, or validate a Remotion project. Load `$remotion-best-practices` only if the task expands into Remotion work such as changing the source job render.
