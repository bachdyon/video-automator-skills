---
name: create-edit-image-gpt-image-2
description: Create or edit images with KIE.AI GPT Image 2. Use when the user wants text-to-image generation, image-to-image editing, or prompt-based image creation with optional reference images through the KIE Market API, including task polling and downloading generated images.
---

# Create Edit Image GPT Image 2

## Rules

- Use this skill for KIE.AI GPT Image 2 image creation and editing.
- Read `.env` from the repo root before running scripts. Require `KIE_API_KEY`; never print the key.
- If reference images are local files, upload them to KIE file storage first. Uploaded files are temporary and expire after 3 days.
- Generated result URLs are temporary; download finished images into the job folder immediately.
- Do not use `callBackUrl` in this repo. The local environment has no public callback receiver, so every task must be checked with a polling loop through `recordInfo`.
- For Vietnamese user-facing output, write Vietnamese with accents. Keep API fields, model IDs, paths, and enum values unchanged.

## Models

KIE Market endpoints:

```text
POST https://api.kie.ai/api/v1/jobs/createTask
GET  https://api.kie.ai/api/v1/jobs/recordInfo?taskId=<taskId>
Authorization: Bearer <KIE_API_KEY>
```

Use model by mode:

```text
gpt-image-2-text-to-image       # prompt only
gpt-image-2-image-to-image      # prompt + input_urls
```

Text-to-image body:

```json
{
  "model": "gpt-image-2-text-to-image",
  "input": {
    "prompt": "A cinematic night city poster with neon reflections on a rainy street.",
    "aspect_ratio": "auto"
  }
}
```

Image-to-image/edit body:

```json
{
  "model": "gpt-image-2-image-to-image",
  "input": {
    "prompt": "Turn this product photo into a premium studio ad, preserve product shape and labels.",
    "input_urls": ["https://..."],
    "aspect_ratio": "auto"
  }
}
```

## Mode Selection

- No `--input-images`: create from text using `gpt-image-2-text-to-image`.
- With `--input-images`: edit or create from references using `gpt-image-2-image-to-image`.
- Use clear edit instructions when preserving identity, product labels, proportions, or composition matters.
- Keep `aspect_ratio` as `auto` unless the user asks for a specific output ratio.

## Script

Create an image from text:

```bash
python skills/create-edit-image-gpt-image-2/scripts/create_edit_image_gpt_image_2.py generate \
  --env-file .env \
  --prompt "A premium skincare product photo on a clean glass pedestal, soft studio lighting, high-end cosmetic campaign" \
  --aspect-ratio auto \
  --output-dir jobs/<job_id>/input/raw_assets/images/gpt_image_2
```

Edit an image with one or more references:

```bash
python skills/create-edit-image-gpt-image-2/scripts/create_edit_image_gpt_image_2.py generate \
  --env-file .env \
  --prompt "Keep the product exactly the same, replace the background with a bright modern kitchen, natural morning light" \
  --input-images jobs/<job_id>/input/raw_assets/images/product.jpg \
  --aspect-ratio auto \
  --output-dir jobs/<job_id>/input/raw_assets/images/gpt_image_2
```

Use multiple references:

```bash
python skills/create-edit-image-gpt-image-2/scripts/create_edit_image_gpt_image_2.py generate \
  --env-file .env \
  --prompt "Combine the person from image 1 with the outfit style from image 2, photorealistic editorial portrait" \
  --input-images jobs/<job_id>/input/reference/person.jpg,jobs/<job_id>/input/reference/outfit.jpg \
  --output-dir jobs/<job_id>/input/raw_assets/images/gpt_image_2
```

Check a task later:

```bash
python skills/create-edit-image-gpt-image-2/scripts/create_edit_image_gpt_image_2.py status \
  --env-file .env \
  --task-id task_gptimage_1765180586443 \
  --output-dir jobs/<job_id>/input/raw_assets/images/gpt_image_2 \
  --download
```

## Outputs

The script writes:

```text
<output-dir>/gpt_image_2_task_<taskId>.json
<output-dir>/gpt_image_2_result_<taskId>_<n>.<ext>
```

Use generated images as raw assets. After download, continue with the usual pipeline:

```bash
.venv/bin/python -m tools.asset_index.exporter jobs/<job_id>/input/raw_assets/ --output jobs/<job_id>/source/asset_semantics.toml
```

## Prompt Guidance

- For product edits, explicitly say what must stay unchanged: shape, label text, color, logo, packaging, material.
- For people, explicitly say whether to preserve identity, expression, pose, clothing, or only use the image as loose style reference.
- For ads, include output use: "TikTok vertical ad", "e-commerce hero image", "thumbnail", "poster".
- Avoid vague prompts like "make it better"; specify background, lighting, camera angle, style, and preservation constraints.

## Troubleshooting

- `401`: missing or invalid `KIE_API_KEY`.
- `400` / `422`: invalid body fields or unsupported image URL; upload local images again if temporary URLs expired.
- `fail` state: read `failCode` and `failMsg` from the saved task JSON.
- No result file downloaded: inspect `resultJson`; if URLs are nested differently, download the returned result URL manually and update the script if this becomes a recurring shape.

## Sources

- Image-to-image docs: <https://docs.kie.ai/market/gpt/gpt-image-2-image-to-image>
- Text-to-image docs: <https://docs.kie.ai/market/gpt/gpt-image-2-text-to-image>
- Task status: <https://docs.kie.ai/market/common/get-task-detail>
- File upload: <https://docs.kie.ai/file-upload-api/quickstart>
