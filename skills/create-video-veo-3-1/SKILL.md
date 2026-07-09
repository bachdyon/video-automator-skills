---
name: create-video-veo-3-1
description: Create AI videos with KIE.AI Google Veo 3.1. Use when the user wants text-to-video, image-to-video with first/last frames, reference/material-to-video, extending Veo 3.1 tasks, polling status, or upgrading/downloading 1080p/4K results through the KIE Veo3 API.
---

# Create Video Veo 3.1

## Rules

- Use this skill for KIE.AI Veo 3.1 video generation, extension, polling, and resolution upgrade flows.
- Read `.env` from the repo root before running scripts. Require `KIE_API_KEY` or `KIEAI_API_KEY`; never print the key.
- For first/last-frame image-to-video, prefer image URLs already hosted by KIE playground / AIQuickDraw (`tempfileb.aiquickdraw.com/kieai/veo3-video/...`) when available. This path has been verified to work with `FIRST_AND_LAST_FRAMES_2_VIDEO`.
- Local image inputs are still supported by the script, but the KIE temporary upload endpoint and third-party CDN URLs such as FilePost can be accepted at submit time and still fail later inside `record-info`. If a task fails with backend `Internal Error`, retry with KIE playground-hosted first/last image URLs and the exact playground-compatible JSON body.
- Generated result URLs are temporary; download finished videos into the job folder immediately.
- For `generate`, keep `callBackUrl: "playground"` by default to match KIE playground requests. This is not a real callback receiver; still poll with `record-info`.
- For Vietnamese user-facing output, write Vietnamese with accents. Keep API fields, model IDs, paths, and enum values unchanged.
- Cost control: Veo tasks are expensive. After a `generate` task returns `successFlag=1` and the result downloads, stop and present the output for user review. Do not start another paid generation, retry, variation, extension, 1080p upgrade, or 4K upgrade based only on subjective quality judgment. Ask the user first.
- Automatic retry is allowed only for clear technical failures: task failed, output file is corrupt or missing, download failed, required hard constraint was violated (for example visible text/watermark when explicitly forbidden), or parameters were clearly wrong. State the reason before retrying.

## Endpoints

```text
POST https://api.kie.ai/api/v1/veo/generate
GET  https://api.kie.ai/api/v1/veo/record-info?taskId=<taskId>
POST https://api.kie.ai/api/v1/veo/extend
GET  https://api.kie.ai/api/v1/veo/get-1080p-video?taskId=<taskId>&index=<index>
POST https://api.kie.ai/api/v1/veo/get-4k-video
Authorization: Bearer <KIE_API_KEY>
```

Generate body:

```json
{
  "prompt": "A warm vertical cinematic shot...",
  "callBackUrl": "playground",
  "waterMark": "",
  "imageUrls": [
    "https://tempfileb.aiquickdraw.com/kieai/veo3-video/start.jpg",
    "https://tempfileb.aiquickdraw.com/kieai/veo3-video/end.jpg"
  ],
  "model": "veo3_fast",
  "resolution": "720p",
  "duration": 4,
  "aspectRatio": "9:16",
  "generationType": "FIRST_AND_LAST_FRAMES_2_VIDEO"
}
```

## Scenario Selection

Choose one generation type:

- **Text-to-video**: prompt only, `generationType=TEXT_2_VIDEO`.
- **First/last-frame image-to-video**: `--first-frame` and optional `--last-frame`, `generationType=FIRST_AND_LAST_FRAMES_2_VIDEO`.
- **Reference/material-to-video**: one or more `--reference-images`, `generationType=REFERENCE_2_VIDEO`.

If the user wants stable loopable footage, pass first and last image URLs that are visually identical or near-identical. For TikTok/Reels/Shorts, default to `--aspect-ratio 9:16`.

## Recommended Defaults

- Default model: `veo3_fast` for cost/speed. Use a quality model only when the user asks for maximum quality.
- Default aspect ratio: `9:16`.
- Default resolution: `720p`.
- Default callback marker: `playground`.
- Default watermark: empty string, sent as `waterMark: ""`.
- Default duration: `4` for `FIRST_AND_LAST_FRAMES_2_VIDEO`; `8` for `REFERENCE_2_VIDEO` because Veo 3.1 reference-to-video returned `Invalid duration` for 4 seconds.
- For first/last-frame Veo 3.1 tasks, use camelCase request fields matching KIE playground: `aspectRatio`, `waterMark`, `callBackUrl`.
- Only send `enableFallback` / `enableTranslation` when explicitly needed; keep the default payload close to the KIE playground body.

## Script

Generate and poll in one command:

```bash
python skills/create-video-veo-3-1/scripts/create_video_veo_3_1.py generate \
  --env-file .env \
  --prompt "A static camera shot of a Vietnamese mother and child sitting in a courtyard, gentle hand motion, warm afternoon light" \
  --aspect-ratio 9:16 \
  --output-dir jobs/<job_id>/input/raw_assets/videos/veo_3_1
```

First/last-frame image-to-video:

```bash
python skills/create-video-veo-3-1/scripts/create_video_veo_3_1.py generate \
  --env-file .env \
  --prompt "Locked-off static camera. The mother speaks softly while the child listens and nods once. Subtle natural hand movement." \
  --first-frame https://tempfileb.aiquickdraw.com/kieai/veo3-video/start.jpg \
  --last-frame https://tempfileb.aiquickdraw.com/kieai/veo3-video/end.jpg \
  --aspect-ratio 9:16 \
  --duration 4 \
  --output-dir jobs/<job_id>/input/raw_assets/videos/veo_3_1
```

Reference/material-to-video:

```bash
python skills/create-video-veo-3-1/scripts/create_video_veo_3_1.py generate \
  --env-file .env \
  --prompt "Create a warm realistic family conversation clip using these reference images for character and courtyard style." \
  --reference-images jobs/<job_id>/input/raw_assets/images/mother.png,jobs/<job_id>/input/raw_assets/images/courtyard.png \
  --aspect-ratio 9:16 \
  --output-dir jobs/<job_id>/input/raw_assets/videos/veo_3_1
```

Check a task later:

```bash
python skills/create-video-veo-3-1/scripts/create_video_veo_3_1.py status \
  --env-file .env \
  --task-id veo_task_id \
  --output-dir jobs/<job_id>/input/raw_assets/videos/veo_3_1 \
  --download
```

Extend a successful Veo 3.1 task:

```bash
python skills/create-video-veo-3-1/scripts/create_video_veo_3_1.py extend \
  --env-file .env \
  --task-id veo_task_id \
  --prompt "Continue the same static courtyard scene with the child replying softly." \
  --output-dir jobs/<job_id>/input/raw_assets/videos/veo_3_1
```

Request a higher-resolution result:

```bash
python skills/create-video-veo-3-1/scripts/create_video_veo_3_1.py get-1080p \
  --env-file .env \
  --task-id veo_task_id \
  --index 0 \
  --output-dir jobs/<job_id>/input/raw_assets/videos/veo_3_1
```

```bash
python skills/create-video-veo-3-1/scripts/create_video_veo_3_1.py get-4k \
  --env-file .env \
  --task-id veo_task_id \
  --index 0 \
  --output-dir jobs/<job_id>/input/raw_assets/videos/veo_3_1
```

## Outputs

The script writes:

```text
<output-dir>/veo_3_1_task_<taskId>.json
<output-dir>/veo_3_1_result_<taskId>_<n>.<ext>
<output-dir>/veo_3_1_1080p_<taskId>_<index>.<ext>
<output-dir>/veo_3_1_4k_<taskId>_<index>_<n>.<ext>
```

Use generated videos as raw assets. After download, continue with the usual asset index flow:

```bash
.venv/bin/python -m tools.asset_index.exporter jobs/<job_id>/input/raw_assets/ --output jobs/<job_id>/source/asset_semantics.toml
```

## Troubleshooting

- `401`: missing or invalid `KIE_API_KEY`.
- `400` / `422`: invalid parameter or unsupported field; compare the saved `request` JSON with the KIE playground body.
- Submit `code=200` only means the task was accepted. Always call `record-info`; final success is `successFlag=1`.
- `successFlag=0`: still generating. Keep polling.
- `successFlag=2` or `3`: generation failed; inspect the saved task JSON for `errorCode` / `errorMessage`.
- Task-level `errorCode=500` in `record-info` is not the same as HTTP 500. It means KIE accepted the task but generation failed internally.
- If first/last-frame generation fails with `Internal Error`, retry using KIE playground-hosted `tempfileb.aiquickdraw.com` image URLs, `callBackUrl: "playground"`, `waterMark: ""`, `aspectRatio`, `resolution: "720p"`, and `duration: 4`.
- `REFERENCE_2_VIDEO` with `duration: 4` returned `Invalid duration. Veo 3.1 reference-to-video currently only supports 8-second generation.` Use 8 seconds for that mode.
- No result file downloaded: inspect `data.response.resultUrls`, `originUrls`, and `fullResultUrls` in the saved JSON.

## Sources

- Product page: <https://kie.ai/veo-3-1>
- Generate: <https://docs.kie.ai/veo3-api/generate-veo-3-video>
- Record info: <https://docs.kie.ai/veo3-api/get-veo-3-video-details>
- Extend: <https://docs.kie.ai/veo3-api/extend-video>
- 1080p: <https://docs.kie.ai/veo3-api/get-veo-3-1080-p-video>
- 4K: <https://docs.kie.ai/veo3-api/get-veo-3-4k-video>
