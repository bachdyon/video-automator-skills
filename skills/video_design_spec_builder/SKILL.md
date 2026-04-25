---
name: video-design-spec-builder
description: Build reusable Video Design Specifications (VDS) from source videos while preserving style DNA and removing personal identifiers. Use when the user asks to create, convert, standardize, or reuse a short-form video style for TikTok/Reels/Shorts.
---

# Video Design Spec Builder

## Mục tiêu

Tạo một bản VDS có thể tái sử dụng cho video ngắn dọc, giữ nguyên tinh thần biên tập (nhịp dựng, mood, cấu trúc kể chuyện), đồng thời loại bỏ toàn bộ chi tiết định danh cá nhân.

## Khi nào dùng skill này

Dùng ngay khi user yêu cầu:

- Tạo VDS từ video gốc
- Chuẩn hóa quy trình dựng video ngắn
- Tái sử dụng phong cách kể chuyện cho nội dung mới
- Chuyển một concept video thành blueprint cho Remotion/production

## Nguyên tắc cốt lõi

1. **Privacy-first**: Không giữ tên riêng, địa chỉ, quan hệ cụ thể, nghề nghiệp định danh, tiểu sử cá nhân, hoặc dữ liệu nhận diện khuôn mặt/giọng nói.
2. **Style-preserving**: Giữ lại nhịp kể, cảm xúc, mood thị giác, hệ text, motion, và audio behavior.
3. **Semantic abstraction**: Thay nội dung cụ thể bằng semantic slots (ví dụ: `[MAIN_CHARACTER]`, `[HOME_ENVIRONMENT]`).
4. **Production-ready**: VDS phải đủ chi tiết để editor hoặc Remotion dev triển khai ngay.

## Quy trình tạo VDS

Sao chép checklist này khi làm việc:

```text
VDS Progress:
- [ ] B1. Xác định mục tiêu tái sử dụng và nền tảng xuất bản
- [ ] B2. Trích xuất cấu trúc tự sự và hành trình cảm xúc
- [ ] B3. Chuẩn hóa ngôn ngữ hình ảnh (Style DNA)
- [ ] B4. Thiết kế timeline/scene blueprint có thể thay thế nội dung
- [ ] B5. Xây semantic slots + text/audio/motion systems
- [ ] B6. Viết hướng dẫn implement (Remotion/Code)
- [ ] B7. Kiểm tra anonymization + tính tái sử dụng
```

### B1) Xác định phạm vi

- Ghi rõ: thời lượng, tỉ lệ khung hình, nền tảng (TikTok/Reels/Shorts), category.
- Chốt mục tiêu cảm xúc (ví dụ: tension -> peace).

### B2) Trích xuất narrative

- Tách video thành 5-7 giai đoạn rõ ràng.
- Mỗi giai đoạn phải có:
  - mục đích tự sự
  - thời lượng (% hoặc frame range)
  - vai trò nội dung có thể thay thế

### B3) Chuẩn hóa Style DNA

- Visual mood (tone màu, saturation, ánh sáng).
- Pacing (thời lượng trung bình mỗi shot).
- Typography và mật độ text.
- Energy index (1-10) và cinematic index (1-10).

### B4) Thiết kế timeline production-ready

- Chuẩn FPS (mặc định 30 nếu user không chỉ định).
- Quy tắc cắt cảnh gắn với voiceover hoặc ambient cues.
- Quy tắc lệch pha subtitle so với VO (khuyến nghị 0.1s-0.3s).

### B5) Xây scene blueprint và semantic slots

- Tạo danh sách scene ID (`SC_01`, `SC_02`, ...).
- Mỗi scene có: vai trò, shot type ưu tiên, chức năng hình ảnh, text/motion cue.
- Tạo slot thay thế asset để loại bỏ chi tiết gốc:
  - nhân vật
  - bối cảnh
  - đạo cụ
  - nguồn áp lực xã hội
  - nhân vật phụ tùy chọn

### B6) Viết system modules

Bao gồm tối thiểu:

- `Text System`: `MAIN_TITLE`, `TIME_MARKER`, `SUBTITLES`, `HIGHLIGHT_TEXT`
- `Motion System`: camera behavior, text animation, zoom behavior
- `Audio System`: VO tone, BGM level, ambience SFX cues
- `Remotion/Code Hints`: component map + style tokens

### B7) Kiểm tra chất lượng

Xác nhận các điều kiện sau:

- Không còn chi tiết nhận diện cá nhân
- Nội dung mới có thể thay asset mà không vỡ cấu trúc
- Mood và nhịp dựng nhất quán xuyên suốt
- Có thể bàn giao trực tiếp cho editor/dev

## Mẫu output mặc định

Khi user không yêu cầu định dạng khác, xuất theo khung:

```markdown
# Reusable Video Design Specification (VDS)

## 0. Metadata
## 1. Mục đích tái sử dụng
## 2. Ý đồ sáng tạo (Creative Intent)
## 3. Cấu trúc tự sự (Narrative Structure)
## 4. Style DNA
## 5. Hệ thống thời gian (Timing System)
## 6. Scene Blueprint
## 7. Asset Semantic Slots
## 8. Hệ thống Text
## 9. Hệ thống chuyển động (Motion System)
## 10. Hệ thống âm thanh (Audio System)
## 11. Hướng dẫn thực hiện (Remotion/Code)
## 12. Quy tắc tái sử dụng (Reusability Rules)
```

## Quy tắc ẩn danh bắt buộc

- Thay tên riêng bằng vai trò trung tính.
- Thay chi tiết địa điểm cụ thể bằng bối cảnh loại (ví dụ: "góc bếp nhỏ", "ban công").
- Thay thông tin đời tư thành nhóm tình huống phổ quát (áp lực công việc, thay đổi lối sống, tìm cân bằng).
- Không tái hiện nguyên văn câu nói mang dấu vết nhận diện.

## Quy tắc xử lý lỗi

Nếu phát sinh lỗi hoặc mâu thuẫn yêu cầu, luôn theo thứ tự:

1. Phân tích nguyên nhân
2. Đưa ra phương án xử lý
3. Đánh giá tối ưu
4. Thực hiện phương án tối ưu nhất

## Guardrails chất lượng

- Không dùng hiệu ứng text/camera gây giật mạnh nếu mood là reflective/healing.
- Không đổi tông âm nhạc đột ngột giữa các đoạn.
- Không tạo narrative arc mâu thuẫn (ví dụ: mở đầu bình yên nhưng cao trào lại không có tension).
- Luôn ưu tiên ngôn ngữ chỉ dẫn rõ ràng, có thể triển khai ngay.

## Utility scripts

Skill này có script upload video lên Gemini API để phân tích video dài/ngữ cảnh lớn:

- Cài dependency:
  - `pip install -r skills/video_design_spec_builder/scripts/requirements.txt`
- Thiết lập API key trong `.env`:
  - Copy `env.example` sang `source/.env` hoặc `jobs/<job_id>/source/.env`, rồi điền `GEMINI_API_KEY`.
  - Không commit `.env`; chỉ commit `env.example`.
- Chạy script:
  - `python skills/video_design_spec_builder/scripts/upload_video_to_gemini.py --video-path /path/to/video.mp4 --env-file source/.env --model gemini-3.1-pro-preview`
  - Có thể override fallback chain:
    - `python skills/video_design_spec_builder/scripts/upload_video_to_gemini.py --video-path /path/to/video.mp4 --env-file source/.env --model gemini-3.1-pro-preview --fallback-models gemini-3-flash-preview,gemini-2.5-pro,gemini-2.5-flash`

Model gợi ý:

- `gemini-3.1-pro-preview`: ưu tiên chất lượng phân tích sâu cho VDS.
- `gemini-3-flash-preview`: nhanh hơn khi cần nhiều vòng thử.
- `gemini-2.5-pro`: fallback ổn định cho production.
