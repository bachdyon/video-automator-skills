---
name: zernio-upload-direct
description: Upload local image, video, audio, or file attachments to Zernio using POST /v1/media/upload-direct with Bearer API key authentication. Use when Codex needs a publicly accessible temporary media URL for Zernio inbox messages, attachment_url/attachmentUrl fields, Messenger/WhatsApp/Telegram attachments, or programmatic media upload without browser upload tokens.
---

# Zernio Upload Direct

## Rules

- Use this skill for Zernio `POST /v1/media/upload-direct`, not the end-user upload-token flow.
- Prefer the bundled Python script over hand-written curl or ad hoc multipart code.
- Read `ZERNIO_API_KEY` from the shell environment first, then from repo-root `.env` when `--env-file .env` is passed. Never print or write the key.
- Reject files larger than 25 MB before calling the API.
- Treat returned URLs as temporary: Zernio stores files for 7 days.
- Use the returned `url` as `attachment_url` in the Zernio MCP `messages_send_inbox_message` tool, or as `attachmentUrl` in direct API payloads.

## API Contract

```text
POST https://zernio.com/api/v1/media/upload-direct
Authorization: Bearer <ZERNIO_API_KEY>
Content-Type: multipart/form-data
```

Multipart fields:

```text
file          binary, required, max 25 MB
contentType   string, optional MIME override such as image/jpeg
```

Successful response:

```json
{
  "url": "https://...",
  "filename": "example.jpg",
  "contentType": "image/jpeg",
  "size": 12345
}
```

## Script

Upload one file and print compact JSON. In this repo, prefer `.venv/bin/python` so `certifi` is available for HTTPS verification:

```bash
.venv/bin/python skills/zernio-upload-direct/scripts/upload_media_direct.py \
  --env-file .env \
  path/to/file.jpg
```

Upload and save the response:

```bash
.venv/bin/python skills/zernio-upload-direct/scripts/upload_media_direct.py \
  --env-file .env \
  --output jobs/<job_id>/source/zernio_upload.json \
  jobs/<job_id>/input/raw_assets/images/photo.jpg
```

Override MIME type when autodetection is wrong:

```bash
.venv/bin/python skills/zernio-upload-direct/scripts/upload_media_direct.py \
  --env-file .env \
  --content-type image/jpeg \
  path/to/photo.bin
```

## Workflow

1. Confirm the local file exists and is below 25 MB.
2. Run the script with `--env-file .env` unless the user explicitly wants another env source.
3. Capture the returned `url`.
4. When sending an inbox message through MCP, pass the URL as `attachment_url` and set `attachment_type` if the platform needs it.
5. If the API returns `401`, tell the user the Zernio API key is missing, invalid, or not loaded into the current process.
6. If system Python reports `CERTIFICATE_VERIFY_FAILED`, run with `.venv/bin/python`; the script uses `certifi` automatically when installed.

## Sources

- Zernio Upload media file: <https://docs.zernio.com/messages/upload-media-direct>
- API base URL: `https://zernio.com/api/v1`
