---
name: klipy-meme-search
description: Search and download Klipy GIFs, stickers, clips, and memes for video reaction visuals. Use when Codex needs meme/reaction assets for Threads videos, editorial recap videos, short-form commentary, scene beats, or any request to find GIF/sticker/clip/meme media from Klipy.
---

# Klipy Meme Search

## Overview

Use Klipy as an on-demand meme/reaction asset source. Prefer this skill when a video beat needs a visual reaction and the local asset index does not already contain a good match.

## Workflow

1. Translate the scene beat into a short search phrase, usually in English for broad meme coverage. Keep a Vietnamese note in reports if the source beat is Vietnamese.
2. Search Klipy with `scripts/klipy_search.py`, using `.env` or `KLIPY_API_KEY` for authentication.
3. Download 3-8 candidate assets, then inspect thumbnails/metadata before choosing one for the video.
4. Keep the generated JSON report with local paths, source URLs, titles, tags, and content descriptions for attribution and future mapping.
5. If the asset will enter the video pipeline, store it under `raw_assets/memes/klipy/` or `jobs/<job_id>/input/raw_assets/memes/klipy/` so the asset index can pick it up.

## Quick Commands

Search and download GIF-style reaction assets:

```bash
python skills/klipy-meme-search/scripts/klipy_search.py \
  --query "confused office worker reaction" \
  --kind gif \
  --limit 6 \
  --download \
  --output-dir raw_assets/memes/klipy
```

Search transparent stickers:

```bash
python skills/klipy-meme-search/scripts/klipy_search.py \
  --query "happy celebration" \
  --kind sticker \
  --limit 6 \
  --download
```

Search for a job-specific Threads/short-form video:

```bash
python skills/klipy-meme-search/scripts/klipy_search.py \
  --query "saving money rich funny reaction" \
  --kind gif \
  --limit 8 \
  --download \
  --output-dir jobs/<job_id>/input/raw_assets/memes/klipy \
  --report jobs/<job_id>/source/klipy_meme_search.json
```

## Search Guidance

- Use concrete reaction words: `confused`, `shocked`, `proud`, `awkward`, `celebrating`, `crying`, `studying`, `working late`, `saving money`.
- For Vietnamese video beats, translate the intent rather than the literal words. Example: `học ngoại ngữ thật giỏi` -> `nerd studying language reaction`.
- Prefer `--kind gif` for general reaction media and short clips because the Tenor-compatible endpoint is verified.
- Use `--kind sticker` when the render needs transparent overlays.
- Use `--kind clip` or `--kind meme` with `--api-style product` only when the API key has access to Klipy product endpoints.
- Prefer downloaded `mp4`/`tinymp4` assets for Remotion video because they are smaller than GIFs.
- Keep `--contentfilter high` unless the user explicitly wants broader results. Do not use NSFW, hateful, violent, or copyrighted-looking assets when the video is for a brand-safe channel.

## API Key

Set the key in the environment or repo `.env`:

```text
KLIPY_API_KEY=...
```

Never hardcode the API key in prompts, skill files, scripts, reports, or committed code.

## Resources

- `scripts/klipy_search.py`: search Klipy, summarize results, optionally download the best media format, and write a JSON report.
- `references/klipy-api-notes.md`: concise notes from Klipy docs and verified endpoint probes. Read this only when changing API behavior.

## Output Rules

- Reports and user-facing notes in Vietnamese context must be Vietnamese with dấu.
- Do not print temporary CDN URLs with secrets if Klipy ever returns tokenized URLs. Print local paths and stable Klipy item URLs instead.
- Preserve attribution fields from Klipy: title, item URL, short URL, tags, content description, and selected media URL host.
