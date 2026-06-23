---
name: fal-image-generator
description: Sinh ảnh AI bằng fal.ai (model nano-banana / flux) từ prompt, hỗ trợ multi-reference image để cố định nhân vật. Lưu ảnh vào jobs/<id>/input/raw_assets/images/ai_generated/ để watcher asset-index tự pickup và pipeline tiếp tục như asset thật.
---

# Fal Image Generator

## Quy tắc đầu ra (BẮT BUỘC)

- Mọi nội dung do AI/LLM sinh ra (`reason` chọn ảnh, ghi chú gửi user, mô tả prompt được rewrite) **bắt buộc viết bằng tiếng Việt CÓ DẤU** nếu context là tiếng Việt.
- Cấm asciify (vd KHÔNG được viết "co dinh nhan vat" thay cho "cố định nhân vật").
- Tên trường (`prompt`, `image_urls`, `num_images`...), enum API (`fal-ai/nano-banana`, `fal-ai/flux/dev`...), CLI flag, file path, model id, hash giữ nguyên tiếng Anh — không dịch.
- Prompt gửi lên fal.ai có thể là **tiếng Anh** (model hiểu Anh ổn định hơn). Nếu user yêu cầu tiếng Việt rõ ràng, dùng tiếng Việt có dấu.

## Quy tắc môi trường script

Trước khi chạy bất kỳ script nào của skill này, đọc file `.env` ở repo-root trước. File này nằm cạnh `jobs/`, `skills/`, và `env.example`. Xác nhận `FAL_API_KEY` tồn tại (script cũng chấp nhận tên cũ `FAL_KEY` để backward compatible với env mẫu của fal.ai); truyền `.env` qua `--env-file`. Tuyệt đối không in giá trị secret. Chỉ dùng `--env-file` không phải repo-root khi user yêu cầu rõ ràng.

## Mục tiêu

Lấp đầy "asset gap" trong pipeline video bằng ảnh AI khi user **không có raw footage thật**. Skill này:

- Sinh ảnh từ prompt thuần (text-to-image).
- Sinh ảnh có **cố định nhân vật** bằng cách truyền 1+ ảnh tham chiếu (`image_urls`) cho model nano-banana — model ưu tiên giữ identity nhân vật trong reference khi sinh.
- Output ảnh PNG/JPEG vào folder `raw_assets/` job-scoped để `tools/asset_index` watcher tự index → `$semantic-asset-mapper` chọn dùng như mọi asset khác.

Skill này KHÔNG quyết định scene nào dùng ảnh AI — đó là việc của `$video-creative-planner` (đánh dấu trong `asset_requirements`) hoặc user nói rõ.

## Khi nào dùng

- Pipeline có job mà `raw_assets/` rỗng / thiếu cảnh, user không định quay thêm.
- Cần lock 1 nhân vật xuyên suốt video (dùng reference image).
- User cung cấp prompt cụ thể từng scene và muốn render trước khi viết creative plan.

## Đầu vào

- `FAL_API_KEY` từ `.env` (alias `FAL_KEY` vẫn hoạt động).
- 1 trong 3 nguồn prompt:
  - Argument `--prompt "..."` cho 1 ảnh.
  - File `--prompts-toml jobs/<id>/source/image_prompts.toml` chứa nhiều prompt.
  - File `--from-creative-plan jobs/<id>/source/creative_plan.toml` để skill đọc `scene_intents[].visual_intent` và sinh ảnh cho mỗi scene flag là `ai_generated` (kiểm tra `asset_requirements` chứa `ai_generated` hoặc `ai_image`).
- `--reference-images path1,path2,...` tùy chọn — ảnh tham chiếu cố định nhân vật. Skill upload lên storage tạm của fal (qua `fal_client.upload_file`) hoặc dùng URL nếu user truyền sẵn URL.
- `--model` — mặc định `fal-ai/nano-banana` (Gemini 2.5 Flash Image; tốt nhất cho character lock và edit). Override sang `fal-ai/flux/dev` (tổng quát), `fal-ai/flux-pro` (chất lượng cao), hoặc model khác theo nhu cầu.

## Đầu ra

```text
jobs/<job_id>/input/raw_assets/images/ai_generated/SC_<id>_<idx>_<hash>.png
jobs/<job_id>/source/ai_image_generation.toml
```

`ai_image_generation.toml` log lại mỗi ảnh đã sinh kèm `prompt`, `model`, `reference_images`, `seed`, `scene_id`, để tái lập deterministic.

## API fal.ai (REST queue)

Skill dùng **REST queue API** của fal để tránh phụ thuộc SDK Python:

```text
POST https://queue.fal.run/<model>           # submit job, trả về request_id
GET  https://queue.fal.run/<model>/requests/<id>/status   # poll
GET  https://queue.fal.run/<model>/requests/<id>          # lấy result
```

Auth header:

```text
Authorization: Key <FAL_API_KEY>
```

Body cho `fal-ai/nano-banana`:

```json
{
  "prompt": "Portrait of a young Vietnamese woman...",
  "image_urls": ["https://..."],
  "num_images": 1,
  "output_format": "png"
}
```

Body cho `fal-ai/flux/dev`:

```json
{
  "prompt": "Portrait of...",
  "image_size": "portrait_16_9",
  "num_inference_steps": 28,
  "num_images": 1,
  "enable_safety_checker": true
}
```

Output:

```json
{
  "images": [{"url": "https://fal.media/files/.../out.png"}],
  "seed": 12345
}
```

Skill download URL về local trước khi return.

## Quy trình

1. Đọc `FAL_API_KEY` từ `.env` (fallback `FAL_KEY`). Không in key.
2. Resolve nguồn prompt:
   - Nếu `--from-creative-plan`: parse TOML, lọc scene cần AI generation, build prompt từ `visual_intent` + `mood` + `preferred_shot_types` + (nếu có VDS path) đoạn style guidance.
   - Nếu `--prompts-toml`: dùng nguyên prompt trong file.
   - Nếu `--prompt`: 1 prompt duy nhất.
3. Nếu có `--reference-images`, upload từng file lên fal storage (`POST https://rest.alpha.fal.ai/storage/upload/initiate` rồi `PUT` lên signed URL) hoặc dùng URL trực tiếp. Cache URL trả về để tái dùng giữa các prompt cùng job.
4. Với mỗi prompt: submit queue → poll status (interval 2s, timeout 120s) → lấy result → download ảnh.
5. Lưu file vào `jobs/<job_id>/input/raw_assets/images/ai_generated/` với tên ổn định:

   ```text
   SC_<scene_id_lower>_<idx>_<sha8(prompt+seed)>.png
   ```

6. Ghi `jobs/<job_id>/source/ai_image_generation.toml` log toàn bộ generation.
7. Báo user: số ảnh đã sinh + path. Khuyến nghị rerun `$asset-semantic-extractor` để index ảnh mới ngay (hoặc đợi watcher tự pickup).

## Hợp đồng TOML đầu vào (tùy chọn)

`jobs/<id>/source/image_prompts.toml`:

```toml
[metadata]
default_model = "fal-ai/nano-banana"
reference_images = ["jobs/<id>/input/reference/character_main.jpg"]
language = "vi"

[[prompts]]
id = "PROMPT_001"
scene_id = "SC_01"
prompt = "Portrait of a young Vietnamese woman in her early 30s, sitting at a small wooden desk in a sunlit balcony, soft morning light, natural skin tones, shallow depth of field, vertical composition"
num_images = 1

[[prompts]]
id = "PROMPT_002"
scene_id = "SC_03"
prompt = "..."
reference_images = ["jobs/<id>/input/reference/character_main.jpg"]
model = "fal-ai/flux-pro"
```

## Hợp đồng TOML đầu ra (luôn ghi)

`jobs/<id>/source/ai_image_generation.toml`:

```toml
[metadata]
generated_at = "2026-04-27T10:15:00+07:00"
job_id = "2026-04-25_001_morning-routine-ad"
default_model = "fal-ai/nano-banana"
total_images = 5

[[generations]]
id = "GEN_001"
scene_id = "SC_01"
prompt = """
Portrait of a young Vietnamese woman...
"""
model = "fal-ai/nano-banana"
reference_images = ["jobs/<id>/input/reference/character_main.jpg"]
reference_image_urls = ["https://fal.media/files/.../ref.jpg"]
seed = 12345
output_path = "jobs/<id>/input/raw_assets/images/ai_generated/sc_01_1_a3f2b1c8.png"
output_url = "https://fal.media/files/.../out.png"
duration_seconds = 8.42
status = "success"
```

## Quy tắc chất lượng

- **Cố định nhân vật**: với mỗi job có nhân vật xuyên suốt, dùng cùng `reference_images` cho mọi prompt → consistency cao nhất với nano-banana.
- **Vertical 9:16**: cho TikTok/Reels/Shorts, prompt nên chứa "vertical composition", "portrait orientation", hoặc với `flux/dev` set `image_size = "portrait_16_9"`. nano-banana không có flag size → mô tả trong prompt.
- **Không bịa identity**: nếu không có reference image, **không** ghi tên cá nhân vào prompt; dùng mô tả chung ("a young Vietnamese woman", "an office worker in his 30s").
- **Idempotent**: rerun cùng prompt + cùng seed cho cùng ảnh. Nếu output file đã tồn tại với hash khớp, skip generation (tiết kiệm quota fal).
- **Privacy**: cấm upload ảnh chứa minor / face thật của user khác lên fal storage trừ khi user xác nhận đồng ý.
- **Rate limit**: nano-banana ~$0.039/image, flux-pro ~$0.05/image. Cảnh báo user nếu generation > 20 ảnh / lần.

## Script tiện ích

```bash
# 1 prompt đơn lẻ + reference image (cố định nhân vật)
python skills/fal-image-generator/scripts/fal_image_generator.py generate \
  --env-file .env \
  --prompt "Portrait of a young woman in a sunlit kitchen, vertical composition" \
  --reference-images jobs/<id>/input/reference/character_main.jpg \
  --output-dir jobs/<id>/input/raw_assets/images/ai_generated \
  --report-toml jobs/<id>/source/ai_image_generation.toml

# Batch từ file prompts
python skills/fal-image-generator/scripts/fal_image_generator.py generate \
  --env-file .env \
  --prompts-toml jobs/<id>/source/image_prompts.toml \
  --output-dir jobs/<id>/input/raw_assets/images/ai_generated \
  --report-toml jobs/<id>/source/ai_image_generation.toml

# Tự đọc creative plan, sinh ảnh cho scene flag ai_generated
python skills/fal-image-generator/scripts/fal_image_generator.py generate \
  --env-file .env \
  --from-creative-plan jobs/<id>/source/creative_plan.toml \
  --reference-images jobs/<id>/input/reference/character_main.jpg \
  --vds-path jobs/<id>/source/vds.md \
  --output-dir jobs/<id>/input/raw_assets/images/ai_generated \
  --report-toml jobs/<id>/source/ai_image_generation.toml
```

## Kết nối với pipeline

Sau khi sinh ảnh:

1. Watcher `tools/asset_index` tự index ảnh mới (debounce 1.5s + Gemini Vision pass + embedding).
2. Hoặc force ngay: `python -m tools.asset_index.exporter jobs/<id>/input/raw_assets/ --output jobs/<id>/source/asset_semantics.toml`.
3. Tiếp tục pipeline bình thường: `$semantic-asset-mapper` → `$shot-coverage-planner` → `$video-render-plan-builder` → `$video-renderer`.

Ảnh AI generated được mapper coi như asset thật (đã có `recommended_uses`, `mood`, `colors`...) — không cần code đặc biệt downstream.

## Khắc phục sự cố

| Triệu chứng | Nguyên nhân | Xử lý |
| --- | --- | --- |
| `401 Unauthorized` | `FAL_API_KEY` sai/thiếu | Verify trong `.env` |
| `429 Rate limit` | Quota / concurrent quá cao | Giảm batch size, retry với backoff |
| Nhân vật khác giữa các ảnh | Reference image không đủ | Dùng nhiều reference từ nhiều góc, hoặc ảnh portrait sạch |
| Ảnh ngang (16:9) | Quên hint vertical | Thêm "vertical composition, portrait orientation" vào prompt |
| Watcher không pickup | File ngoài `raw_assets/` | Verify `--output-dir` nằm trong `jobs/<id>/input/raw_assets/` |
