---
name: heygen-photo-avatar-video
description: Create HeyGen image-to-video/photo-avatar talking-head videos from a person's image plus custom audio. Use when the user wants a personal brand video, video nhân hiệu, talking avatar, lip-synced photo video, or a HeyGen video generated from one image and one audio file.
---

# HeyGen Photo Avatar Video

## Rules

- Use this skill when the user wants a personal brand talking video (`video nhân hiệu`) from an image and an audio file.
- This skill uses HeyGen Image to Video (`POST /v3/videos` with `type: "image"`). It does not create a reusable `avatar_id`; for repeated videos with the same person, note that HeyGen's reusable Photo Avatar flow may be better.
- Read `.env` from the repo root before running scripts. Require `HEYGEN_API_KEY`; never print the key.
- Required inputs: one person image and one narration audio. Local files are uploaded first via `POST /v3/assets`, then referenced as `asset_id`.
- Use `audio_asset_id` or `audio_url`; do not mix custom audio with `script`/`voice_id`.
- Poll `GET /v3/videos/{video_id}` until `completed` or `failed`. Download `video_url` immediately when available.
- For Vietnamese user-facing output, write Vietnamese with accents. Keep API fields, endpoint paths, and enum values unchanged.

## API

Create from uploaded image and uploaded audio:

```json
{
  "type": "image",
  "image": {
    "type": "asset_id",
    "asset_id": "asset_image..."
  },
  "audio_asset_id": "asset_audio...",
  "title": "Personal brand video",
  "resolution": "1080p",
  "aspect_ratio": "9:16"
}
```

Create from public URLs:

```json
{
  "type": "image",
  "image": {
    "type": "url",
    "url": "https://example.com/person.jpg"
  },
  "audio_url": "https://example.com/narration.mp3",
  "title": "Personal brand video"
}
```

Statuses: `pending`, `processing`, `completed`, `failed`. A completed response includes `video_url`.

## Script

Generate, poll, and download in one command:

```bash
python skills/heygen-photo-avatar-video/scripts/heygen_photo_avatar_video.py generate \
  --env-file .env \
  --image jobs/<job_id>/input/raw_assets/images/person.jpg \
  --audio jobs/<job_id>/input/raw_assets/audio/narration.mp3 \
  --title "Video nhân hiệu" \
  --aspect-ratio 9:16 \
  --resolution 1080p \
  --output-dir jobs/<job_id>/input/raw_assets/videos/heygen
```

Use already-uploaded asset IDs:

```bash
python skills/heygen-photo-avatar-video/scripts/heygen_photo_avatar_video.py generate \
  --env-file .env \
  --image-asset-id asset_image_123 \
  --audio-asset-id asset_audio_456 \
  --title "Video nhân hiệu" \
  --output-dir jobs/<job_id>/input/raw_assets/videos/heygen
```

Use public URLs:

```bash
python skills/heygen-photo-avatar-video/scripts/heygen_photo_avatar_video.py generate \
  --env-file .env \
  --image-url https://example.com/person.jpg \
  --audio-url https://example.com/narration.mp3 \
  --title "Video nhân hiệu" \
  --output-dir jobs/<job_id>/input/raw_assets/videos/heygen
```

Check a video later:

```bash
python skills/heygen-photo-avatar-video/scripts/heygen_photo_avatar_video.py status \
  --env-file .env \
  --video-id <video_id> \
  --output-dir jobs/<job_id>/input/raw_assets/videos/heygen \
  --download
```

## Outputs

The script writes:

```text
<output-dir>/heygen_video_<video_id>.json
<output-dir>/heygen_video_<video_id>.mp4
```

Use downloaded videos as raw assets. After download, continue with the usual pipeline:

```bash
.venv/bin/python -m tools.asset_index.exporter jobs/<job_id>/input/raw_assets/ --output jobs/<job_id>/source/asset_semantics.toml
```

## Creative Defaults

- TikTok/Reels/Shorts personal brand: `--aspect-ratio 9:16 --resolution 1080p`.
- Horizontal explainer: `--aspect-ratio 16:9 --resolution 1080p`.
- Keep titles short and traceable to the job.
- If the image has a busy background and the user wants a cleaner talking head, add `--remove-background` and optionally `--background-color "#ffffff"`.

## Troubleshooting

- `Missing HEYGEN_API_KEY`: add it to `.env` or export it in the shell.
- `script and audio are mutually exclusive`: this skill is for custom audio; use HeyGen script/voice only in a separate flow.
- `failed` status: inspect `failure_message` in the saved JSON report.
- `401`: invalid or inactive HeyGen API key.
- No downloaded video: inspect the saved JSON for the exact `video_url` field path and update the script if HeyGen changed the response shape.

## Sources

- HeyGen Image to Video: <https://developers.heygen.com/image-to-video-1>
- HeyGen Upload Assets: <https://developers.heygen.com/docs/upload-assets>
