---
name: youtube-fast-download
description: Download public YouTube videos or Shorts quickly with yt-dlp, always save an MP4 into raw_assets/videos/downloaded and a compatible MP3 audio file into raw_assets/audio/downloaded. Use when the user gives a YouTube URL and asks to download the video, get the audio, export MP3, or optimize the workflow for speed and low token usage.
---

# YouTube Fast Download

## Core Rule

Prefer the bundled script instead of reconstructing long `yt-dlp` and `ffmpeg` commands in chat.

Always output both files for YouTube/Shorts downloads:

- MP4 video in `raw_assets/videos/downloaded/`
- MP3 audio in `raw_assets/audio/downloaded/`

```bash
.venv/bin/python skills/youtube-fast-download/scripts/download_youtube_fast.py \
  "https://www.youtube.com/shorts/VIDEO_ID"
```

## Workflow

1. Use `yt-dlp` from `.venv` when available; avoid installing anything unless the module is missing.
2. Download best MP4-compatible output using fragment concurrency (`-N 16`) and merge to MP4.
3. Save video to `raw_assets/videos/downloaded/<id>_<title>.mp4`.
4. Always export MP3 to `raw_assets/audio/downloaded/<id>_<title>.mp3` with `ffmpeg` + `libmp3lame`.
5. Verify output with `ffprobe` only when the user needs confirmation or the downstream task depends on metadata.

## Fast Paths

- Video plus MP3:

```bash
.venv/bin/python skills/youtube-fast-download/scripts/download_youtube_fast.py "<url>"
```

- Backward-compatible explicit MP3 flag:

```bash
.venv/bin/python skills/youtube-fast-download/scripts/download_youtube_fast.py "<url>" --mp3
```

- MP3 from an existing local video, without redownloading:

```bash
.venv/bin/python skills/youtube-fast-download/scripts/download_youtube_fast.py \
  --from-video raw_assets/videos/downloaded/input.mp4
```

## Defaults

- Video output dir: `raw_assets/videos/downloaded`
- Audio output dir: `raw_assets/audio/downloaded`
- Format: `bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/best`
- Merge container: `mp4`
- MP3 bitrate: `192k`
- Fragment concurrency: `16`

Do not print signed direct media URLs. Report only local file paths, duration, codec, size, and any important warning.
