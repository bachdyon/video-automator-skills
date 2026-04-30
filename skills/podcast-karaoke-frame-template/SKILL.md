---
name: podcast-karaoke-frame-template
description: Instantiate the Podcast Karaoke Rounded Frame render-style template for jobs that already have a render plan, word-level transcript, and visual timeline; preserves the rule that semantic mapping is upstream and job-specific.
---

# Podcast Karaoke Frame Template

## Ranh giới quan trọng

Template này là **render-style template**, không phải semantic mapper.

Hard rule:

> Semantic mapping là pipeline stage trước template, không phải rule cứng trong template. Template này là render-style template; semantic mapper là phần job-specific.

Không thêm semantic slots bắt buộc như `RAIN_PRESSURE`, `URBAN_COMPARISON`, `WARM_ACCEPTANCE` vào template contract. Không quy định kênh khác phải dùng mưa, phố, gym, luxury, business, lifestyle hay bất kỳ nhóm asset cụ thể nào.

## Khi nào dùng

Dùng skill này khi job đã có:

- `source/render_plan.toml`
- `source/transcript_word_level.toml`
- Visual timeline/mapping đã được tạo bởi pipeline riêng của job.

## Không dùng khi

- Chưa có transcript word-level.
- Chưa có timeline clip/render plan.
- Người dùng đang yêu cầu quyết định asset nào khớp nội dung audio. Việc đó thuộc `$semantic-asset-mapper`, `$video-creative-planner`, hoặc mapper riêng của kênh.

## Inputs

```text
--job jobs/<job_id>
--brand "Động Lực Podcast"
--subtitle-top-pct 45
--highlight-color "#f3dd3d"
```

## Instantiate

```bash
.venv/bin/python skills/podcast-karaoke-frame-template/scripts/instantiate.py \
  --job jobs/<job_id> \
  --brand "Động Lực Podcast" \
  --subtitle-top-pct 45
```

Script sẽ:

1. Copy Remotion template vào `jobs/<job_id>/remotion`.
2. Copy các clip đã có trong `source/render_plan.toml` vào `remotion/public/assets`.
3. Copy voice audio đã có vào `remotion/public/assets`.
4. Chuyển word-level transcript thành `template-props.json`.
5. Ghi `source/template_params.toml`.

Script không chạy semantic mapper, không chọn asset mới, không tìm thêm footage.

## Render

```bash
cd jobs/<job_id>/remotion
npm install
npm run still
npm run render
```

Nếu job đã có `node_modules` hoặc repo đang tái dùng local dependencies, có thể bỏ qua `npm install`.

## Style knobs

- `brand`: chữ brand lockup ở đáy khung.
- `subtitleTopPct`: vị trí subtitle theo phần trăm chiều cao canvas, mặc định `45`.
- `highlightColor`: màu từ karaoke đang đọc, mặc định vàng `#f3dd3d`.

## Quality expectations

- Video output 1080x1920, 30fps.
- Footage muted; audio chính lấy từ `voiceSrc`.
- Subtitle tách page khi gặp từ bắt đầu bằng chữ hoa.
- Text render bằng Remotion, không dùng FFmpeg/ImageMagick/Python để burn chữ.
- Template không chứa path tuyệt đối, `jobs/<job_id>`, hoặc semantic slots cứng.
