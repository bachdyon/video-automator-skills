---
name: wavespeed-lipsync
description: Default low-cost lipsync workflow using WaveSpeedAI InfiniteTalk. Use when the user asks for lipsync, lip sync, talking photo/avatar, digital human from one image plus audio, cheap avatar video generation, or asks to animate a person speaking from an image and audio unless they explicitly choose another provider.
---

# WaveSpeed Lipsync

## Rules

- Use this skill as the default lipsync provider because WaveSpeedAI InfiniteTalk is the low-cost option for this repo.
- Read `.env` from the repo root before running scripts. Require `WAVESPEED_API_KEY`; never print the key.
- Inputs must be HTTPS URLs for `image`, `audio`, and optional `mask_image`. If the user gives local files, upload them to a stable public URL first, then pass those URLs to this skill.
- Default to `resolution=480p` and `seed=-1` unless the user asks otherwise. Use `720p` only when quality is explicitly more important than cost.
- Keep prompts short and in English. Omit `prompt` unless there is a concrete expression, pose, or style instruction.
- Download completed result URLs immediately into the job folder because generated URLs may be temporary.
- For Vietnamese user-facing output, write Vietnamese with accents. Keep API fields, model IDs, URLs, and enum values unchanged.

## Model

WaveSpeedAI endpoint:

```text
POST https://api.wavespeed.ai/api/v3/wavespeed-ai/infinitetalk
GET  https://api.wavespeed.ai/api/v3/predictions/<request_id>/result
Authorization: Bearer <WAVESPEED_API_KEY>
```

Submit body:

```json
{
  "image": "https://example.com/person.png",
  "audio": "https://example.com/voice.mp3",
  "mask_image": "https://example.com/mask.png",
  "prompt": "Natural speaking expression, subtle head movement",
  "resolution": "480p",
  "seed": -1
}
```

Only include `mask_image` and `prompt` when needed.

## Workflow

1. Confirm there is one person image URL and one audio URL.
2. Run the script with `generate`; it submits the task, polls result status, downloads `data.outputs[0]`, and writes a JSON report.
3. If polling times out, keep the task id from the report and resume later with `status`.
4. If status is `failed`, inspect `data.error` in the saved JSON report.

## Script

Generate, poll, and download:

```bash
python3 skills/wavespeed-lipsync/scripts/wavespeed_lipsync.py generate \
  --env-file .env \
  --image-url "https://example.com/person.png" \
  --audio-url "https://example.com/voice.mp3" \
  --output-dir jobs/<job_id>/input/raw_assets/videos/lipsync
```

With optional prompt and 720p:

```bash
python3 skills/wavespeed-lipsync/scripts/wavespeed_lipsync.py generate \
  --env-file .env \
  --image-url "https://example.com/person.png" \
  --audio-url "https://example.com/voice.mp3" \
  --prompt "Natural confident speaking, subtle head movement" \
  --resolution 720p \
  --output-dir jobs/<job_id>/input/raw_assets/videos/lipsync
```

Check an existing task:

```bash
python3 skills/wavespeed-lipsync/scripts/wavespeed_lipsync.py status \
  --env-file .env \
  --task-id "<request_id>" \
  --output-dir jobs/<job_id>/input/raw_assets/videos/lipsync \
  --download
```

## Outputs

The script writes:

```text
<output-dir>/wavespeed_lipsync_task_<request_id>.json
<output-dir>/wavespeed_lipsync_result_<request_id>_<n>.<ext>
```

Use downloaded videos as raw assets. After download, continue with the usual asset pipeline when the result should feed a video job:

```bash
.venv/bin/python -m tools.asset_index.exporter jobs/<job_id>/input/raw_assets/ --output jobs/<job_id>/source/asset_semantics.toml
```

## Troubleshooting

- `401`: missing or invalid `WAVESPEED_API_KEY`.
- `400` / `422`: missing `image` or `audio`, unsupported URL, invalid `resolution`, or malformed JSON.
- `failed`: read `data.error` from the saved report.
- `mask_image` makes the output black: the mask covered too much area; use a mask only for the moving person/region.
- Slow generation is expected. InfiniteTalk can take roughly 10-30 seconds of wall time for each second of output video depending on queue and resolution.

## Sources

- Model card: <https://wavespeed.ai/models/wavespeed-ai/infinitetalk>
- API reference: <https://wavespeed.ai/docs/docs-api/wavespeed-ai/infinitetalk>
