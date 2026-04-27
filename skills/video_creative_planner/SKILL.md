---
name: video-creative-planner
description: Biến yêu cầu video mới (kèm Video Design Specification tùy chọn) thành creative plan, kịch bản, scene intents, overlay text và asset requirements ở mức sẵn sàng đưa vào pipeline video short-form.
---

# Video Creative Planner

## Mục tiêu

Chuyển ý tưởng video mới của user thành một creative plan có cấu trúc, để các skill phía sau (voice, asset mapping, render) có thể thực thi được.

Dùng skill này khi user đưa ra chủ đề, brief, ý tưởng sản phẩm, yêu cầu chiến dịch hoặc kịch bản nháp và muốn dựng một video TikTok/Reels/Shorts từ đó.

## Quy tắc đầu ra (BẮT BUỘC)

- Mọi nội dung do AI/LLM sinh ra (script, scene_intents, mô tả, mood, overlay text, lý do, summary) **bắt buộc viết bằng tiếng Việt CÓ DẤU**.
- Cấm asciify (vd KHÔNG được viết "cong truong" thay cho "công trường" trong script, visual_intent, hay mô tả).
- Tags và identifier kebab-case (mood, style_ref, narrative_role) vẫn lowercase ASCII (vd: `vat-va`, `chan-thuc`).
- Tên trường, tên CLI flag, file path, tên model, JSON/TOML key giữ nguyên tiếng Anh — không được dịch.
- Nếu user yêu cầu ngôn ngữ khác (vd `language = "en"` trong metadata), tuân theo yêu cầu đó.

## Quy tắc môi trường script

Trước khi chạy bất kỳ script nào trong skill này, đọc file `.env` ở repo-root trước. File này nằm cạnh `jobs/`, `skills/`, và `env.example`. Chỉ kiểm tra xem các key cần thiết có tồn tại hay không; tuyệt đối không in giá trị secret ra log, terminal, TOML artifact, hay phản hồi. Chỉ dùng `--env-file` không phải repo-root khi user yêu cầu rõ ràng.

## Đầu vào

- Yêu cầu hoặc brief sáng tạo của user.
- VDS tùy chọn từ `video-design-spec-builder`.
- Tùy chọn: nền tảng đích, thời lượng, ngôn ngữ, ràng buộc thương hiệu, CTA, ghi chú asset có sẵn.
- Tùy chọn: asset-index DB (`.asset_index/index.db`) — nên truy vấn trước khi soạn scene_intents để biết thực tế đang có footage gì.

## Khám phá footage có sẵn trước khi viết scene_intents

Khi watcher asset-index đang chạy, project đã biết sẵn raw asset nào tồn tại và chứa gì. Trước khi tự bịa scene_intents, nên đưa các phương án thật ra trước:

```bash
.venv/bin/python -m tools.asset_index.search "<mô tả ngắn cảnh muốn tìm bằng tiếng Việt>" --top 5
```

Hoặc gọi trong code agent:

```python
from tools.asset_index.search import search_assets
hits = search_assets("cảnh người làm việc tay chân ở quê", k=5, media_type="video")
for h in hits:
    print(h["score"], h["file_path"], h["summary"])
```

Dùng các summary trả về để bám sát thực tế khi điền `visual_intent`, `preferred_shot_types`, `asset_requirements`. Nếu một visual cần thiết không có match nào ổn (score < ~0.3 toàn bộ), giữ nó dưới dạng entry `asset_requirements` và nói rõ với user là asset đang thiếu — không bịa.

## Đầu ra

Ghi hoặc trả về TOML. Đường dẫn mặc định:

```text
source/creative_plan.toml
```

Khi đã có video job tồn tại, ghi vào:

```text
jobs/<job_id>/source/creative_plan.toml
```

## Quy trình

1. Xác định đối tượng đích, nền tảng, thời lượng, ngôn ngữ và emotional arc.
2. Nếu có VDS, bảo toàn DNA phong cách, logic timing, text system, motion system và scene blueprint.
3. Viết kịch bản voiceover sao cho đọc tự nhiên được.
4. Chia kịch bản thành scene_intents — không phải lựa chọn asset cuối cùng.
5. Định nghĩa overlay text, hành vi subtitle và CTA.
6. Định nghĩa asset_requirements để `asset-semantic-extractor` và `semantic-asset-mapper` biết tìm gì.
7. Giữ identifier, dữ liệu cá nhân, chi tiết riêng tư ở mức trừu tượng trừ khi user xác nhận sở hữu và yêu cầu rõ.

## Hợp đồng TOML

```toml
[metadata]
title = "Tiêu đề mô tả ngắn"
language = "vi"
platform = "tiktok"
target_duration_seconds = 45
aspect_ratio = "9:16"
source_vds = "path/to/vds.md"

[creative]
audience = "..."
goal = "..."
emotional_arc = ["hook", "tension", "turn", "resolution"]
tone = "reflective"
cta = "..."

[voiceover]
script = """
Toàn bộ kịch bản đọc.
"""
delivery = "ấm, rõ, hơi cinematic"

[[scene_intents]]
id = "SC_01"
start_hint = 0.0
end_hint = 6.0
narrative_role = "hook"
spoken_text = "Câu hoặc đoạn văn dự kiến nói trong scene này."
visual_intent = "Khán giả nên thấy gì, không chọn file cụ thể."
mood = "..."
preferred_shot_types = ["close-up", "slow push-in"]
asset_requirements = ["..."]

[[text_overlays]]
id = "TXT_01"
scene_id = "SC_01"
text = "Text ngắn hiển thị trên màn hình"
role = "hook"
timing = "sync_with_scene_start"
style_ref = "MAIN_TITLE"
```

## Giới hạn độ dài Text Overlay (1080×1920 dọc)

Text trên màn hình phải vừa với khung an toàn ~880px trên canvas rộng 1080px (~82%). Mỗi `style_ref` có ngưỡng `max_chars` cứng và mức khuyến nghị giúp text vừa 1–2 dòng mà không phải auto-shrink. **Tiếng Việt và các ngôn ngữ có dấu render rộng hơn ~10% so với Latin thuần; số đếm là 0.6 char mỗi ký tự.**

| `style_ref`      | `max_chars` (kể cả khoảng trắng) | khuyến nghị | vai trò điển hình         |
| ---------------- | -------------------------------: | ----------: | ------------------------- |
| `MAIN_TITLE`     |                               22 |       12–16 | hook, reveal callout      |
| `PUNCH_TAG`      |                               18 |       10–14 | punchline, viết hoa       |
| `STAT_TAG`       |                               14 |        6–10 | số, thống kê, giá tiền    |
| `SUBTITLE_BOLD`  |                               32 |       18–26 | callout phụ               |
| `QUOTE_TAG`      |                               36 |       22–30 | câu trích dẫn, in nghiêng |

Nếu một câu vượt `max_chars` của style đã chọn, áp dụng theo thứ tự:

1. **Rút gọn / viết tắt** trong khi giữ điểm punch (vd `"Săn lấp mặt bằng = Xúc đất"` → `"Săn lấp = Xúc đất"`).
2. **Tách thành hai overlay nối tiếp** với `start`/`end` ghép nhau (≥0.4s gap, cùng `style_ref` hoặc style được ghép cặp).
3. **Hạ `style_ref`** xuống preset nhỏ hơn (`MAIN_TITLE` → `SUBTITLE_BOLD`, `PUNCH_TAG` → `QUOTE_TAG`) chỉ khi vai trò cho phép.

Renderer có auto-shrink + word-break phòng thủ, nhưng planner chịu trách nhiệm cho mục tiêu fit. Overlay vượt `max_chars` sẽ phát warning `OVERLAY_TEXT_TOO_LONG` từ `video-render-plan-builder` và bị nhỏ/bóp khi render.

## Giới hạn mật độ Subtitle

Trang subtitle (kiểu TikTok highlight từng từ) target ≤ 26 ký tự/trang; renderer tự tách trang dài, nhưng planner nên giữ mỗi câu `voiceover` đọc trôi chảy, không có 8+ từ ngắn liên tiếp. Tránh số ghép quá dài trong narration (`"hai mươi ba triệu năm trăm nghìn"`); dùng overlay text thay thế và giữ narration ngắn.

## Quy tắc chất lượng

- Kịch bản phải đọc nói được; tránh mệnh đề lồng dài.
- Scene intent nên mang tính ngữ nghĩa và tái sử dụng, không gắn vào file path.
- Không bịa asset có sẵn. Thiếu visual nào thì cho vào `asset_requirements`.
- Nếu VDS xung đột với yêu cầu user, ưu tiên ý user và adapt VDS một cách bảo thủ.
- Với production đầy đủ, đọc và cập nhật path qua `video-job-manager` thay vì dùng `source/` chung.
- Mỗi `[[text_overlays]].text` phải thỏa `len(text) <= max_chars[style_ref]` (xem bảng trên).
