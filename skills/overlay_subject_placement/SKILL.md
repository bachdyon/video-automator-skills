---
name: overlay-subject-placement
description: Phân tích khung hình bằng vision LLM không phải Gemini để đề xuất vị trí text/image/video overlay tránh che chủ thể và tránh vùng unsafe, dùng khi cần quyết định placement cho creative plan hoặc render plan.
---

# Overlay Subject Placement

## Quy tắc đầu ra (BẮT BUỘC)

- Mọi nội dung do AI/LLM sinh ra (`reason`, mô tả chủ thể, giải thích placement, ghi chú) bắt buộc viết bằng tiếng Việt có dấu.
- Tên field, enum, path, key JSON/TOML giữ nguyên tiếng Anh.
- Không đề xuất placement nếu chưa kiểm tra hard safe-area rule.

## Mục tiêu

Phân tích một frame ảnh cụ thể để chọn vị trí đặt text, image overlay, hoặc video overlay sao cho:

1. Không che chủ thể chính.
2. Không chạm vào vùng unsafe.
3. Tương thích contract hiện có của pipeline (`position` cho `text_overlays` / `overlays`).

Skill này không thay thế `asset-semantic-extractor` và không thay đổi schema bắt buộc của pipeline.

## Ràng buộc mô hình (BẮT BUỘC)

- Tuyệt đối không dùng Google Gemini cho bước phân tích placement này.
- Chỉ dùng vision LLM không phải Gemini (ví dụ: Claude multimodal trong Cursor, OpenAI GPT-4o hoặc tương đương do user cấu hình).
- Đầu vào cho model là ảnh chụp frame (screenshot) tại thời điểm cần đặt overlay.

## Hard Safe-Area Rule cho video 9:16 (1080x1920)

Định nghĩa vùng unsafe cố định theo pixel:

- `top = 100`
- `left = 100`
- `right = 100`
- `bottom = 200`

Suy ra mọi khối overlay hợp lệ phải nằm trọn trong vùng an toàn:

- `x >= 100`
- `y >= 100`
- `x + w <= 980`
- `y + h <= 1720`

Nếu placement chạm/chờm unsafe zone hoặc đè lên chủ thể, bắt buộc reject và chọn phương án khác (đổi vị trí, giảm kích thước, tách overlay, hoặc đổi shot/frame).

## Đầu vào

- Screenshot từ Remotion preview ở đúng thời điểm (`currentFrame`), hoặc
- Ảnh PNG/JPEG extract từ video:

```bash
ffmpeg -ss 00:00:05.200 -i input.mp4 -frames:v 1 frame_5_2s.png
```

- Ảnh tĩnh trong `jobs/<job_id>/input/raw_assets/`.

Ưu tiên dùng frame đúng tỉ lệ canvas cuối (9:16).

## Prompt mẫu cho Vision LLM (verbatim-friendly)

```text
Bạn là chuyên gia layout cho video dọc 1080x1920.
Nhiệm vụ: phân tích ảnh frame đính kèm để đề xuất vị trí đặt overlay (text/image/video) mà KHÔNG che chủ thể và KHÔNG vi phạm safe area cứng.

Ràng buộc:
- Safe area hợp lệ: x>=100, y>=100, x+w<=980, y+h<=1720.
- Chỉ trả position hỗ trợ bởi pipeline hiện tại: upper_third hoặc lower_third.
- Nếu cả hai position đều rủi ro, phải trả violates_safe_area=true và nêu phương án thay thế (giảm size, tách overlay, đổi frame).

Hãy trả JSON đúng schema sau:
{
  "recommended_position": "upper_third|lower_third",
  "subject_bbox_normalized": {"x": 0.0, "y": 0.0, "w": 0.0, "h": 0.0},
  "safe_text_band": "mô tả ngắn vùng đặt phù hợp",
  "safe_box_px": {"x": 0, "y": 0, "w": 0, "h": 0},
  "avoid_zones": [{"x": 0, "y": 0, "w": 0, "h": 0, "reason": "..." }],
  "violates_safe_area": false,
  "confidence": 0.0,
  "reason": "giải thích tiếng Việt có dấu"
}
```

## Đầu ra gợi ý

Có thể lưu artifact tại:

```text
jobs/<job_id>/source/overlay_placement.toml
```

Ví dụ TOML:

```toml
recommended_position = "lower_third"
violates_safe_area = false
confidence = 0.87
reason = "Chủ thể nằm nửa trên khung hình, vùng lower_third còn trống và nằm hoàn toàn trong safe area."

[subject_bbox_normalized]
x = 0.31
y = 0.14
w = 0.38
h = 0.52

[safe_box_px]
x = 120
y = 1120
w = 820
h = 420
```

## Handoff vào pipeline

1. Cập nhật `[[text_overlays]].position` trong `creative_plan.toml` (nếu đang ở bước planner).
2. Hoặc cập nhật `[[overlays]].position` trong `render_plan.toml` (nếu đang tinh chỉnh render plan).
3. Chỉ dùng giá trị `position` mà renderer/job hiện tại hỗ trợ; nếu không chắc, map về `upper_third` hoặc `lower_third`.

## Trình tự khuyến nghị

1. Chọn frame đúng thời điểm xuất hiện overlay.
2. Gọi vision LLM không phải Gemini để lấy placement JSON.
3. Gate kết quả theo hard safe-area rule.
4. Reject nếu `violates_safe_area = true` hoặc overlap chủ thể.
5. Ghi kết quả hợp lệ vào creative/render plan.

## Ngoài phạm vi skill này

- Không sửa renderer Remotion.
- Không tự thêm field schema bắt buộc mới cho toàn pipeline.
- Không thay thế bước semantic indexing của asset-index.
