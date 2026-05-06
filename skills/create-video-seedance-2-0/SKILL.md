---
name: create-video-seedance-2-0
description: Create AI videos with KIE.AI Bytedance Seedance 2.0 Fast. Use when the user wants text-to-video, image-to-video with first/last frames, multimodal reference-to-video, optional generated audio, polling task status, or downloading Seedance results through the KIE Market API.
---

# Create Video Seedance 2.0

## Rules

- Use this skill for KIE.AI `bytedance/seedance-2-fast` video generation.
- Read `.env` from the repo root before running scripts. Require `KIE_API_KEY`; never print the key.
- If inputs are local files, upload them to KIE file storage first. Uploaded files are temporary and expire after 3 days.
- Generated result URLs are temporary; download finished videos into the job folder immediately.
- Do not use `callBackUrl` in this repo. The local environment has no public callback receiver, so every task must be checked with a polling loop through `recordInfo`.
- For Vietnamese user-facing output, write Vietnamese with accents. Keep API fields, model IDs, paths, and enum values unchanged.

## Model

KIE Market endpoint:

```text
POST https://api.kie.ai/api/v1/jobs/createTask
GET  https://api.kie.ai/api/v1/jobs/recordInfo?taskId=<taskId>
Authorization: Bearer <KIE_API_KEY>
```

Create body:

```json
{
  "model": "bytedance/seedance-2-fast",
  "input": {
    "prompt": "A cinematic vertical product shot...",
    "first_frame_url": "https://...",
    "last_frame_url": "https://...",
    "reference_image_urls": ["https://..."],
    "reference_video_urls": ["https://..."],
    "reference_audio_urls": ["https://..."],
    "return_last_frame": false,
    "generate_audio": false,
    "resolution": "720p",
    "aspect_ratio": "16:9",
    "duration": 15,
    "web_search": false
  }
}
```

## Scenario Selection

Choose exactly one generation mode:

- **Text-to-video**: prompt only, no media URLs.
- **Image-to-video first frame**: `first_frame_url` only.
- **Image-to-video first and last frames**: `first_frame_url` + `last_frame_url`.
- **Multimodal reference-to-video**: one or more `reference_image_urls`, `reference_video_urls`, or `reference_audio_urls`.

Do not mix first/last frame fields with `reference_*_urls`. KIE notes these scenarios are mutually exclusive. If strict first/last frame identity is required, prefer `first_frame_url` + `last_frame_url` over multimodal references.

## Recommended Defaults

- TikTok/Reels/Shorts: `--aspect-ratio 9:16 --resolution 720p`.
- General horizontal video: `--aspect-ratio 16:9 --resolution 720p`.
- Keep `--generate-audio` off unless the user asks for model-generated sound.
- Keep `--web-search` off unless the user asks for current/real-world grounding.
- The `generate` command always loops on `GET /api/v1/jobs/recordInfo?taskId=...` until `success` or `fail`.

## Script

Generate and poll in one command:

```bash
python skills/create-video-seedance-2-0/scripts/create_video_seedance_2_0.py generate \
  --env-file .env \
  --prompt "A cinematic vertical shot of a Vietnamese street food stall at night, handheld camera, warm practical lights" \
  --aspect-ratio 9:16 \
  --duration 15 \
  --output-dir jobs/<job_id>/input/raw_assets/videos/seedance
```

First/last-frame image-to-video:

```bash
python skills/create-video-seedance-2-0/scripts/create_video_seedance_2_0.py generate \
  --env-file .env \
  --prompt "Animate the subject with a slow dolly-in, natural cloth movement, realistic lighting" \
  --first-frame jobs/<job_id>/input/raw_assets/images/start.png \
  --last-frame jobs/<job_id>/input/raw_assets/images/end.png \
  --aspect-ratio 9:16 \
  --output-dir jobs/<job_id>/input/raw_assets/videos/seedance
```

Multimodal reference-to-video:

```bash
python skills/create-video-seedance-2-0/scripts/create_video_seedance_2_0.py generate \
  --env-file .env \
  --prompt "Create a polished product lifestyle clip using the reference product and the audio rhythm" \
  --reference-images jobs/<job_id>/input/raw_assets/images/product.jpg \
  --reference-audios jobs/<job_id>/input/raw_assets/audio/beat.mp3 \
  --aspect-ratio 9:16 \
  --output-dir jobs/<job_id>/input/raw_assets/videos/seedance
```

Check a task later:

```bash
python skills/create-video-seedance-2-0/scripts/create_video_seedance_2_0.py status \
  --env-file .env \
  --task-id task_bytedance_1765186743319 \
  --output-dir jobs/<job_id>/input/raw_assets/videos/seedance \
  --download
```

## Outputs

The script writes:

```text
<output-dir>/seedance_task_<taskId>.json
<output-dir>/seedance_result_<taskId>_<n>.<ext>
```

Use generated videos as raw assets. After download, continue with the usual pipeline:

```bash
.venv/bin/python -m tools.asset_index.exporter jobs/<job_id>/input/raw_assets/ --output jobs/<job_id>/source/asset_semantics.toml
```

## Troubleshooting

- `401`: missing or invalid `KIE_API_KEY`.
- `400` / `422`: invalid parameter combination; re-check scenario exclusivity.
- `fail` state: read `failCode` and `failMsg` from the saved task JSON.
- No result file downloaded: inspect `resultJson`; if URLs are nested differently, download the returned result URL manually and update the script if this becomes a recurring shape.

## Sources

- KIE docs: <https://docs.kie.ai/market/bytedance/seedance-2-fast>
- Task status: <https://docs.kie.ai/market/common/get-task-detail>
- File upload: <https://docs.kie.ai/file-upload-api/quickstart>
