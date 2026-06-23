---
name: video-compress-under-25mb
description: Compress local MP4/MOV videos to fit under 25MB for APIs and messaging platforms such as Zernio upload-direct, WhatsApp/Messenger inbox attachments, or other small-file upload limits. Use when Codex needs to reduce video file size while preserving duration, resolution, frame rate, and broad H.264/AAC compatibility when possible.
---

# Video Compress Under 25MB

## Rules

- Use the bundled script before hand-writing ffmpeg commands.
- Preserve original resolution and frame rate by default; reduce bitrate first.
- Default target is 24 MiB to leave room below a 25 MiB API limit.
- Use H.264/AAC MP4 by default for maximum compatibility.
- Use 2-pass H.264 when targeting an exact size; it is more reliable than CRF for file-size limits.
- Do not overwrite the input unless the user explicitly asks.
- After compression, verify actual output size, codec, resolution, duration, and bitrate.
- If the file cannot fit acceptably under the target at original resolution, tell the user and offer a lower resolution pass.

## Script

Compress to under 25 MiB:

```bash
.venv/bin/python skills/video-compress-under-25mb/scripts/compress_video_under_size.py \
  input.mp4
```

Write beside a specific job output:

```bash
.venv/bin/python skills/video-compress-under-25mb/scripts/compress_video_under_size.py \
  jobs/<job_id>/output/final_video.mp4 \
  --output jobs/<job_id>/output/final_video_under25mb_h264.mp4
```

Use a different limit or target:

```bash
.venv/bin/python skills/video-compress-under-25mb/scripts/compress_video_under_size.py \
  input.mp4 \
  --max-mib 25 \
  --target-mib 23.5 \
  --audio-bitrate-kbps 96
```

Optional HEVC pass for higher quality at the same size but lower compatibility:

```bash
.venv/bin/python skills/video-compress-under-25mb/scripts/compress_video_under_size.py \
  input.mp4 \
  --codec h265
```

## Output Files

The script writes:

```text
<input_stem>_under25mb_h264.mp4
<input_stem>_under25mb_h264.json
<input_stem>_under25mb_h264_preview.jpg
```

The JSON file contains input/output metadata, ffmpeg settings, computed target bitrate, and whether the output is under the requested max size.

## Workflow

1. Run the script with the original video path.
2. Review the JSON summary and `under_max_size` field.
3. Show the output path, size, and preview image to the user before upload when the user asks to approve quality.
4. If using the result for an upload target with a 25 MB limit, upload only after `under_max_size` is true.

## Notes

- 25 MiB equals `26,214,400` bytes. The script defaults to 24 MiB target to avoid edge-case API rejection.
- A 60-second vertical 1080p video under 25 MiB usually needs about `3.0-3.3 Mbps` total bitrate.
- This is not lossless compression; the practical goal is no obvious quality loss at mobile/social viewing size.
