---
name: filepost-file-upload
description: "Work with FilePost files through the FilePost API: upload local files to permanent public CDN URLs, list uploaded files, get file details, and delete files. Use when Codex needs durable hosted media/file URLs beyond short-lived temporary upload services, or when the user asks for FilePost list/get/upload/delete operations."
---

# FilePost File Upload

## Rules

- Use the bundled Python client before writing ad hoc code.
- The client must use Python `requests` only. Do not use `curl`, subprocess upload helpers, or hand-written urllib multipart code for FilePost.
- Read `FILEPOST_API_KEY` from the shell environment first, then from repo-root `.env` when `--env-file .env` is passed.
- Never print, log, or write the API key.
- Auth uses `X-API-Key`, not Bearer auth.
- Uploaded file URLs are permanent CDN URLs unless the file is deleted.
- Check plan limits before promising upload size: free plan is 50 MB/file, starter 200 MB/file, pro 500 MB/file.
- Treat `delete` as destructive. Only delete a file when the user explicitly asks for that exact `file_id`.

## API

```text
Base URL: https://filepost.dev
Auth header: X-API-Key: <FILEPOST_API_KEY>
CDN URL host: https://cdn.filepost.dev
```

Core endpoints:

```text
POST   /v1/upload          multipart/form-data file=@path
GET    /v1/files           page, per_page
GET    /v1/files/{file_id}
DELETE /v1/files/{file_id}
```

Upload response:

```json
{
  "file_id": "abc123def456",
  "url": "https://cdn.filepost.dev/file/filepost/uploads/ab/abc123def456.jpg",
  "name": "photo.jpg",
  "size": 45321,
  "content_type": "image/jpeg"
}
```

## Script

Upload a file:

```bash
.venv/bin/python skills/filepost-file-upload/scripts/filepost_client.py \
  --env-file .env \
  upload path/to/file.mp4
```

List files:

```bash
.venv/bin/python skills/filepost-file-upload/scripts/filepost_client.py \
  --env-file .env \
  list --page 1 --per-page 50
```

Get file details:

```bash
.venv/bin/python skills/filepost-file-upload/scripts/filepost_client.py \
  --env-file .env \
  get abc123def456
```

Delete a file:

```bash
.venv/bin/python skills/filepost-file-upload/scripts/filepost_client.py \
  --env-file .env \
  delete abc123def456
```

Write JSON output:

```bash
.venv/bin/python skills/filepost-file-upload/scripts/filepost_client.py \
  --env-file .env \
  --output source/filepost_upload.json \
  upload jobs/<job_id>/output/final.mp4
```

## Workflow

1. Confirm `FILEPOST_API_KEY` exists in the current environment or `.env`.
2. For upload, confirm the input file exists and note its size.
3. Run the script operation requested by the user.
4. Return the important JSON fields, especially `file_id`, `url`, `size`, and `content_type`.
5. If an API call fails, report HTTP status and `detail` from the JSON response.

## Implementation Notes

- Uploads use `requests.post(..., files={"file": (filename, file_handle, mime_type)})`.
- The explicit MIME tuple keeps `content_type` stable for MP4, images, audio, and PDFs.

## Sources

- FilePost docs: <https://filepost.dev/docs>
- OpenAPI spec: <https://filepost.dev/openapi.json>
