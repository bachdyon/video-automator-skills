---
name: png-to-svg-convertio
description: Convert local PNG images to SVG files through the Convertio API. Use when Codex needs an SVG asset from a PNG source, especially for logos, icons, overlays, templates, or design assets where an SVG file is required and local conversion is not sufficient.
---

# PNG to SVG Convertio

## Rules

- Use the bundled Python script before writing ad hoc API calls.
- Read `CONVERTIO_API_KEY` from the shell environment first, then from repo-root `.env` when `--env-file .env` is passed. The script also accepts legacy lowercase `convertio_api_key`.
- Never print, log, or commit the API key.
- Only send PNG files unless the user explicitly asks to adapt the workflow for another input format.
- Prefer downloading the result through Convertio `/dl/base64`; output URLs are IP-bound and should not be treated as shareable public URLs.
- Delete the remote conversion after a successful download unless the user explicitly needs to keep it for debugging.
- Inspect the resulting SVG when vector editability matters. PNG-to-SVG services may produce an SVG wrapper around raster content depending on source complexity.

## API Contract

```text
POST   https://api.convertio.co/convert
PUT    https://api.convertio.co/convert/:id/:filename
GET    https://api.convertio.co/convert/:id/status
GET    https://api.convertio.co/convert/:id/dl/base64
DELETE https://api.convertio.co/convert/:id
```

Start payload for a local PNG upload:

```json
{
  "apikey": "<CONVERTIO_API_KEY>",
  "input": "upload",
  "outputformat": "svg"
}
```

The status endpoint reaches `data.step == "finish"` when the converted file is ready. Failed conversions may return `status: error` or a failed/unknown step with an `error` field.

## Script

Convert one PNG and write the SVG next to it:

```bash
.venv/bin/python skills/png-to-svg-convertio/scripts/convert_png_to_svg.py \
  --env-file .env \
  path/to/image.png
```

Choose an explicit output path:

```bash
.venv/bin/python skills/png-to-svg-convertio/scripts/convert_png_to_svg.py \
  --env-file .env \
  --output jobs/<job_id>/input/raw_assets/images/logo.svg \
  jobs/<job_id>/input/raw_assets/images/logo.png
```

Save conversion metadata:

```bash
.venv/bin/python skills/png-to-svg-convertio/scripts/convert_png_to_svg.py \
  --env-file .env \
  --output source/logo.svg \
  --metadata-output source/logo_convertio.json \
  raw_assets/images/logo.png
```

## Workflow

1. Confirm the input exists and has a `.png` extension.
2. Run the script with `--env-file .env` unless another env source is requested.
3. Use `--output` when the SVG must land in a specific asset folder; otherwise the script writes `<input>.svg`.
4. Open or inspect the SVG if downstream work depends on editable paths rather than an embedded bitmap.
5. Return the output path and conversion ID from the compact JSON.

## Troubleshooting

- `Missing CONVERTIO_API_KEY`: export it or add it to `.env`.
- `401`: the API key is invalid or not loaded.
- `422`: Convertio could not read or convert the PNG; check corruption, transparency, and file size.
- Timeout: rerun with a larger `--timeout-seconds` or inspect the saved metadata if `--metadata-output` was used.

## Sources

- Convertio API docs: <https://developers.convertio.co/vn/api/docs/>
