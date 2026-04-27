---
name: video-design-spec-builder
description: Xây dựng Video Design Specification (VDS) tái sử dụng được từ video gốc, giữ nguyên DNA phong cách và xóa thông tin nhận diện cá nhân. Dùng khi user yêu cầu tạo, chuyển đổi, chuẩn hóa, hoặc tái sử dụng phong cách video short-form cho TikTok/Reels/Shorts.
---

# Video Design Spec Builder

## Quy tắc đầu ra (BẮT BUỘC)

- Toàn bộ nội dung VDS do AI/LLM sinh ra **bắt buộc viết bằng tiếng Việt CÓ DẤU**.
- Cấm asciify (vd KHÔNG được viết "binh yen" thay cho "bình yên" trong mood description).
- Tên slot kỹ thuật như `[MAIN_CHARACTER]`, `SC_01`, `MAIN_TITLE` giữ ASCII để máy đọc ổn định; phần mô tả xung quanh vẫn phải là tiếng Việt có dấu.
- Tên trường, key TOML/JSON, model id Gemini, CLI flag giữ nguyên tiếng Anh — không dịch.

## Quy tắc môi trường script

Trước khi chạy bất kỳ script nào của skill này, đọc file `.env` ở repo-root trước. File này nằm cạnh `jobs/`, `skills/`, và `env.example`. Xác nhận `GEMINI_API_KEY` tồn tại và truyền `.env` qua `--env-file`; tuyệt đối không in giá trị secret. Chỉ dùng `--env-file` không phải repo-root khi user yêu cầu rõ ràng.

## Mục tiêu

Tạo một bản VDS có thể tái sử dụng cho video ngắn dọc, giữ nguyên tinh thần biên tập (nhịp dựng, mood, cấu trúc kể chuyện), đồng thời loại bỏ toàn bộ chi tiết định danh cá nhân và mọi thông số triển khai quá cụ thể của video mẫu.

## Khi nào dùng skill này

Dùng ngay khi user yêu cầu:

- Tạo VDS từ video gốc
- Chuẩn hóa quy trình dựng video ngắn
- Tái sử dụng phong cách kể chuyện cho nội dung mới
- Chuyển một concept video thành blueprint sáng tạo/biên tập có thể tái sử dụng

## Nguyên tắc cốt lõi

1. **Privacy-first**: Không giữ tên riêng, địa chỉ, quan hệ cụ thể, nghề nghiệp định danh, tiểu sử cá nhân, hoặc dữ liệu nhận diện khuôn mặt/giọng nói.
2. **Style-preserving**: Giữ lại nhịp kể, cảm xúc, mood thị giác, hệ text, motion, và audio behavior.
3. **Semantic abstraction**: Thay nội dung cụ thể bằng semantic slots (ví dụ: `[MAIN_CHARACTER]`, `[HOME_ENVIRONMENT]`).
4. **Sẵn sàng cho sản xuất nhưng không đóng cứng**: VDS phải đủ chi tiết để biên tập viên hoặc planner sử dụng, nhưng không biến thông số của video mẫu thành ràng buộc cố định.

## Quy tắc chống đóng cứng thông số

VDS là blueprint tái sử dụng, không phải render plan của video mẫu. Khi phân tích video gốc:

- Không đưa các giá trị timing cố định như tổng frame, frame start/end tuyệt đối, thời lượng chính xác từng cảnh, đường dẫn asset, hoặc tên file vào VDS.
- Được ghi FPS, tỉ lệ khung hình, và kích thước pixel trong `Metadata` hoặc phần khuyến nghị kỹ thuật vì đây là thông số định dạng cần thiết cho sản xuất video dọc.
- Nếu cần ghi thông số kỹ thuật của video mẫu, phân biệt rõ đâu là "tham chiếu mẫu" và đâu là "khuyến nghị tái sử dụng".
- Ưu tiên mô tả bằng phần trăm timeline, khoảng tương đối, nhịp dựng, vai trò cảnh, và quy tắc co giãn.
- Với timeline, dùng các dạng như "khoảng 5-8% mở đầu", "scene body chiếm 45-60% thời lượng", "mỗi shot thường 2-6 giây tùy footage".
- Có thể khuyến nghị FPS, tỉ lệ khung hình, và kích thước pixel; riêng timing cảnh phải là tỷ lệ/khoảng mềm, không hard-code từ video mẫu.
- Không viết các câu kiểu "Timeline tổng: 2120 frame" hoặc "duration 70.67s" như yêu cầu triển khai.
- Không yêu cầu timeline mới phải bằng video mẫu; chỉ giữ cấu trúc cảm xúc, nhịp kể, hệ thống chữ, chuyển động, và âm thanh.

## Quy trình tạo VDS

Sao chép checklist này khi làm việc:

```text
VDS Progress:
- [ ] B1. Xác định mục tiêu tái sử dụng và nền tảng xuất bản
- [ ] B2. Trích xuất cấu trúc tự sự và hành trình cảm xúc
- [ ] B3. Chuẩn hóa ngôn ngữ hình ảnh (Style DNA)
- [ ] B4. Thiết kế timeline/scene blueprint có thể thay thế nội dung
- [ ] B5. Xây semantic slots + text/audio/motion systems
- [ ] B6. Kiểm tra anonymization + tính tái sử dụng
```

### B1) Xác định phạm vi

- Ghi rõ: nền tảng (TikTok/Reels/Shorts), category, tỉ lệ khung hình khuyến nghị, và khoảng thời lượng tái sử dụng.
- Nếu có thông số video mẫu, ghi là dữ liệu tham chiếu, không biến thành thông số bắt buộc.
- Chốt mục tiêu cảm xúc (ví dụ: tension -> peace).

### B2) Trích xuất narrative

- Tách video thành 5-7 giai đoạn rõ ràng.
- Mỗi giai đoạn phải có:
  - mục đích tự sự
  - thời lượng tương đối (% timeline hoặc khoảng thời gian mềm)
  - vai trò nội dung có thể thay thế

### B3) Chuẩn hóa Style DNA

- Visual mood (tone màu, saturation, ánh sáng).
- Pacing (thời lượng trung bình mỗi shot).
- Typography và mật độ text.
- Energy index (1-10) và cinematic index (1-10).

### B4) Thiết kế timeline production-ready

- Timeline phải co giãn theo target duration của dự án mới.
- FPS có thể là khuyến nghị kỹ thuật; tổng duration và frame ranges phải là tham số triển khai, không lấy cứng từ video mẫu.
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

### B6) Kiểm tra chất lượng

Xác nhận các điều kiện sau:

- Không còn chi tiết nhận diện cá nhân.
- Nội dung mới có thể thay asset mà không vỡ cấu trúc.
- Mood và nhịp dựng nhất quán xuyên suốt.
- VDS chỉ mô tả style, narrative, timing tương đối, text/motion/audio system, asset slots, và quy tắc tái sử dụng.

## System modules bắt buộc

Bao gồm tối thiểu:

- `Text System`: `MAIN_TITLE`, `TIME_MARKER`, `SUBTITLES`, `HIGHLIGHT_TEXT`
- `Motion System`: camera behavior, text animation, zoom behavior
- `Audio System`: VO tone, BGM level, ambience SFX cues
- `Reusability Rules`: các phần được giữ, được thay, và không được đưa từ video gốc sang.

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
## 11. Quy tắc tái sử dụng (Reusability Rules)
```

## Quy tắc ẩn danh bắt buộc

- Thay tên riêng bằng vai trò trung tính.
- Thay chi tiết địa điểm cụ thể bằng bối cảnh loại (ví dụ: "góc bếp nhỏ", "ban công").
- Thay thông tin đời tư thành nhóm tình huống phổ quát (áp lực công việc, thay đổi lối sống, tìm cân bằng).
- Không tái hiện nguyên văn câu nói mang dấu vết nhận diện.

## Quy tắc tham số hóa VDS

- `Metadata` chỉ mô tả video mẫu ở mức tham chiếu và phải phân biệt rõ với khuyến nghị tái sử dụng.
- `Timing System` phải dùng `% timeline`, "khoảng", hoặc "tùy target duration"; không dùng frame tuyệt đối.
- `Scene Blueprint` có thể dùng timestamp mẫu nếu thật sự cần đối chiếu, nhưng phải có cột/ghi chú nhấn mạnh đây là tham chiếu mẫu; mặc định ưu tiên `% timeline`.
- Các ví dụ timing/schema phải được tham số hóa, tránh literal timing values như `2120`, `70.67`, hoặc timestamp/frame range tuyệt đối, trừ khi user yêu cầu rõ.

## Quy tắc xử lý lỗi

Nếu phát sinh lỗi hoặc mâu thuẫn yêu cầu, luôn theo thứ tự:

1. Phân tích nguyên nhân
2. Đưa ra phương án xử lý
3. Đánh giá tối ưu
4. Thực hiện phương án tối ưu nhất

## Guardrail chất lượng

- Không dùng hiệu ứng text/camera gây giật mạnh nếu mood là reflective/healing.
- Không đổi tông âm nhạc đột ngột giữa các đoạn.
- Không tạo narrative arc mâu thuẫn (ví dụ: mở đầu bình yên nhưng cao trào lại không có tension).
- Luôn ưu tiên ngôn ngữ chỉ dẫn rõ ràng, có thể triển khai ngay.
- Luôn kiểm tra cuối cùng: tiếng Việt có dấu đầy đủ, không có timing fix cứng của video mẫu trong phần triển khai, và mọi chi tiết nội dung cụ thể đã được trừu tượng hóa thành slot/quy tắc.

## Script tiện ích

Skill này có script upload video lên Gemini API để phân tích video dài/ngữ cảnh lớn:

- Cài dependency:
  - `pip install -r skills/video_design_spec_builder/scripts/requirements.txt`
- Thiết lập API key trong repo-root `.env`:
  - Copy `env.example` sang `.env` ở cùng cấp với `jobs/` và `skills/`, rồi điền `GEMINI_API_KEY`.
  - Không commit `.env`; chỉ commit `env.example`.
- Chạy script:
  - `python skills/video_design_spec_builder/scripts/upload_video_to_gemini.py --video-path /path/to/video.mp4 --env-file .env --model gemini-3-flash-preview`
  - Có thể override fallback chain:
    - `python skills/video_design_spec_builder/scripts/upload_video_to_gemini.py --video-path /path/to/video.mp4 --env-file .env --model gemini-3-flash-preview --fallback-models gemini-3-flash-preview,gemini-2.5-pro,gemini-2.5-flash`

Model gợi ý:

- `gemini-3-flash-preview`: ưu tiên chất lượng phân tích sâu cho VDS.
- `gemini-2.5-pro`: fallback ổn định cho production.
