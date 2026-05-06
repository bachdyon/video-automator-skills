---
name: heygen-asset-upload
description: Upload images, videos, audio, or PDFs to HeyGen and return reusable asset IDs. Use when the user wants to upload local files for HeyGen, prepare assets for Video Agent, avatars, image-to-video, video translation, or any HeyGen endpoint that accepts asset_id file inputs.
---

# HeyGen Asset Upload

## Rules

- Use this skill for HeyGen `POST /v3/assets` uploads.
- Read `.env` from the repo root before running scripts. Require `HEYGEN_API_KEY`; never print the key.
- Prefer uploading local files once and reusing returned `asset_id` values for later HeyGen calls.
- Check file constraints before upload: max 32 MB; images `png`/`jpeg`; video `mp4`/`webm`; audio `mp3`/`wav`; PDFs supported.
- For Vietnamese user-facing output, write Vietnamese with accents. Keep API fields, endpoint paths, and enum values unchanged.

## API

```text
POST https://api.heygen.com/v3/assets
Header: X-Api-Key: <HEYGEN_API_KEY>
Body: multipart/form-data file=@<path>
```

Successful responses include:

```json
{
  "data": {
    "asset_id": "asset_abc123def456",
    "url": "https://files.heygen.ai/assets/asset_abc123def456.png",
    "mime_type": "image/png",
    "size_bytes": 245760
  }
}
```

## Script

Upload one or more files:

```bash
python skills/heygen-asset-upload/scripts/heygen_asset_upload.py upload \
  --env-file .env \
  --files jobs/<job_id>/input/raw_assets/images/person.jpg,jobs/<job_id>/input/raw_assets/audio/narration.mp3 \
  --output jobs/<job_id>/source/heygen_assets.json
```

Print only the compact JSON response:

```bash
python skills/heygen-asset-upload/scripts/heygen_asset_upload.py upload \
  --env-file .env \
  --files path/to/file.png
```

## Outputs

When `--output` is provided, the script writes:

```text
{
  "assets": [
    {
      "path": "...",
      "asset_id": "asset_...",
      "url": "https://...",
      "mime_type": "image/png",
      "size_bytes": 12345,
      "response": {}
    }
  ]
}
```

Use uploaded assets in HeyGen file inputs as:

```json
{ "type": "asset_id", "asset_id": "asset_..." }
```

## Troubleshooting

- `Missing HEYGEN_API_KEY`: add it to `.env` or export it in the shell.
- `File too large`: HeyGen limits uploads to 32 MB; compress or provide a public HTTPS URL instead.
- `Unsupported file type`: convert to a supported format before upload.
- `401`: invalid or inactive HeyGen API key.
- `400` / `422`: inspect the saved response; confirm the file field is named exactly `file`.

## Sources

- HeyGen Upload Assets: <https://developers.heygen.com/docs/upload-assets>
