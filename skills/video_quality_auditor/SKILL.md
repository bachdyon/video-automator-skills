---
name: video-quality-auditor
description: Audit code-first cho Remotion source và render plan (ưu tiên overlay readability + safe-area), gom toàn bộ lỗi mỗi pass rồi áp dụng batch fix một thể, lặp tối đa 3 pass và xuất báo cáo TOML + HTML tiếng Việt.
---

# Video Quality Auditor

## Quy tắc đầu ra (BẮT BUỘC)

- Mọi mô tả do AI sinh ra trong report phải viết bằng tiếng Việt có dấu.
- Key, enum, path, tên field TOML/JSON giữ nguyên tiếng Anh.
- Mỗi pass phải gom đủ lỗi trước khi fix (`fix_mode = batch_all_findings`).
- Không vượt quá `max_audit_passes = 3`.

## Mục tiêu

Audit theo hướng code-first trên source Remotion và plan hiện có để cải thiện chất lượng overlay:

1. Audit toàn bộ vấn đề của pass hiện tại.
2. Tạo 1 gói fix duy nhất cho cả pass.
3. Áp dụng fix + render lại.
4. Lặp cho đến khi đạt chuẩn hoặc tối đa 3 pass.

## Khi nào dùng

- User yêu cầu kiểm tra/chỉnh chất lượng overlay nhanh trước khi render full video.
- Cần tự cân lại `font_size`, `top_percent`, `offset`, `tilt` để tránh lỗi hiển thị.
- Cần báo cáo tiếng Việt để review nhanh trước khi chốt final.

## Input tối thiểu

- `--job jobs/<job_id>`
- `source/render_plan.toml`
- `remotion/src/composition.tsx`
- `remotion/src/Root.tsx`
- (khuyến nghị) `source/audit_config.toml`

## Artifact đầu ra

- `logs/audit_pass_0N.toml` (machine-readable findings + batch fix)
- `logs/audit_report_vi_pass_0N.html` (human-readable tiếng Việt)
- `logs/audit_report_vi_final.html` (tổng hợp cuối)

## Quy tắc pass/fix

1. Chạy `audit_video.py` để ghi findings (rule cứng + tính toán deterministic).
2. Chỉ khi có lỗi `severity = "error"` mới chạy `apply_fix_batch.py`.
3. Mỗi pass chỉ áp dụng **một** batch fix.
4. Sau fix có thể chạy lint/typecheck trước; render full chỉ khi cần xác nhận cuối.
5. Dừng nếu:
   - Không còn lỗi mức `error`, hoặc
   - Đã đến pass 3.

## Script tiện ích

```bash
# Pass 1: Audit deterministic + HTML
.venv/bin/python skills/video_quality_auditor/scripts/audit_video.py \
  --job jobs/<job_id> \
  --pass-index 1

.venv/bin/python skills/video_quality_auditor/scripts/render_html_report.py \
  --job jobs/<job_id> \
  --pass-index 1

# Áp dụng batch fix (nếu còn lỗi error)
.venv/bin/python skills/video_quality_auditor/scripts/apply_fix_batch.py \
  --job jobs/<job_id> \
  --pass-index 1
```

## Mô hình hybrid (khuyến nghị)

- Script xử lý phần cứng: validate schema, safe-area math, range checks, xuất report chuẩn.
- AI Agent xử lý phần mềm: chọn chiến lược fix tối ưu, patch code đồng bộ giữa `render_plan.toml`, `Root.tsx`, `composition.tsx`.

## Quy ước đánh giá

- `error`: phải fix trước khi coi là pass.
- `warning`: ghi nhận để người vận hành quyết định.
- `info`: chỉ ghi chú.

## Scope mặc định profile `overlay_readability_safearea`

- Safe-area cứng 9:16:
  - `x >= 100`, `y >= 100`, `x + w <= 980`, `y + h <= 1720`
- Font size hợp lý cho short-form:
  - `28 <= font_size <= 72`
- Tilt hợp lý:
  - `abs(tilt_deg) <= 15`
- Contrast tối thiểu:
  - text trắng nền đen hoặc text đen nền trắng (mức cơ bản)

## Ngoài phạm vi

- Không thay đổi nội dung script/storyline.
- Không tự thay đổi asset nguồn.
- Không tự thêm stage mới ngoài pipeline chuẩn.
