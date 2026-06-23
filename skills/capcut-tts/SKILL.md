---
name: capcut-tts
description: Dùng CapCut common task client (`K07VN/capcut-tts-api`, `capcut_common_task_client.py`) để tạo/query Text-to-Speech task, upload audio/video, hoặc chạy STT/subtitle recognition qua flow CapCut đã phân tích; dùng khi user yêu cầu rõ CapCut TTS, giọng CapCut, CapCut subtitle/STT, hoặc muốn thử workflow CapCut thay cho AusyncLab/free TTS.
---

# CapCut TTS

## Quy tắc bắt buộc

- Chỉ dùng skill này khi user yêu cầu rõ CapCut TTS/STT hoặc muốn kiểm thử client CapCut. Không tự chọn làm TTS mặc định của pipeline; nếu user chỉ nói "tạo voice" thì ưu tiên `$ausynclab-voice` hoặc `$free-tts` theo cấu hình repo.
- CapCut common task client là flow không chính thức/reverse-engineered, có thể hỏng khi CapCut đổi endpoint, signing, hoặc chính sách session. Nói rõ rủi ro này khi kết quả quan trọng.
- Chỉ dùng với tài khoản, thiết bị, session, text, audio/video mà user có quyền sử dụng.
- Không in device/session identifiers, token task, cookie, API response nhạy cảm, hoặc nội dung `device.json` đầy đủ vào final answer.
- Không gọi CapCut bằng `curl` thủ công khi có `capcut_common_task_client.py`; dùng script client trước.

## Nguồn client

Client tham chiếu:

```text
https://github.com/K07VN/capcut-tts-api
```

Script chính:

```text
capcut_common_task_client.py
```

Trước khi chạy, tìm script local:

```bash
rg --files | rg '(^|/)capcut_common_task_client\.py$'
```

Nếu chưa có script, hỏi user trước khi clone/download repo bên thứ ba. Không vendor code lớn vào skill này nếu user chỉ cần workflow.

## Môi trường

Yêu cầu client:

```bash
python3 -m pip install requests
```

Nếu repo có `.venv`, ưu tiên:

```bash
.venv/bin/python -m pip install requests
```

Nếu sandbox/network chặn cài dependency hoặc tải client, xin quyền chạy lại lệnh cần thiết rồi tiếp tục.

`device.json` là tùy chọn để override profile thiết bị/session:

```bash
python3 capcut_common_task_client.py tts-new \
  --device-json device.json \
  --text "Xin chào"
```

Treat `device.json` như thông tin nhạy cảm vừa phải: lưu trong `source/` hoặc job-local nếu cần, không commit nếu chứa định danh thật.

## TTS workflow

1. Xác định script text, ngôn ngữ, voice id, resource id, speed/rate.
2. Chạy `tts-new` và lưu JSON task response vào `source/` hoặc `jobs/<job_id>/source/`.
3. Đọc `data.tasks[0].id` và `data.tasks[0].token`.
4. Poll bằng `tts-query` cho tới khi task thành công hoặc lỗi.
5. Nếu response chứa URL/audio payload, download audio về path ổn định:

```text
source/voice.wav
source/capcut_tts_task.json
source/capcut_tts_result.json
```

Với video job:

```text
jobs/<job_id>/source/voice.wav
jobs/<job_id>/source/capcut_tts_task.json
jobs/<job_id>/source/capcut_tts_result.json
```

## Preset giọng

- `Cô Gái Hoạt Ngôn`: dùng cho video Threads/commentary ngắn khi template hoặc user yêu cầu CapCut TTS.
  - `speaker_id` / `--voice`: `BV074_streaming`
  - `resource_id` / `--resource-id`: `7102355709945188865`
  - `rate`: `1.0` mặc định; chỉ chỉnh khi user yêu cầu nhanh/chậm hơn.
- Khi một template skill yêu cầu `$capcut-tts` rõ ràng, dùng preset phù hợp ở mục này thay vì fallback sang `$ausynclab-voice` hoặc `$free-tts`.
- Với `templates/comment-screens-gameplay/` và `$threads-video-template`, preset mặc định bắt buộc là `Cô Gái Hoạt Ngôn` trừ khi user chỉ định giọng khác.

Tạo task TTS cơ bản:

```bash
python3 capcut_common_task_client.py tts-new \
  --text "Xin chào"
```

Tùy chỉnh voice:

```bash
python3 capcut_common_task_client.py tts-new \
  --text "Xin chào" \
  --voice BV074_streaming \
  --resource-id 7102355709945188865 \
  --rate 1.0
```

Query task:

```bash
python3 capcut_common_task_client.py tts-query \
  --task-id "TASK_ID" \
  --token "TOKEN" \
  --out source/capcut_tts_result.json
```

## STT/subtitle workflow

Dùng phần này khi user yêu cầu CapCut subtitle recognition, transcript, hoặc STT.

Upload rồi tạo STT bằng một lệnh:

```bash
python3 capcut_common_task_client.py stt-file \
  --audio-file input.mp4 \
  --language vi-VN
```

Hoặc upload trước:

```bash
python3 capcut_common_task_client.py upload-audio \
  --audio-file input.mp4
```

Tạo STT từ `vid` và `md5`:

```bash
python3 capcut_common_task_client.py stt-new \
  --audio-vid "VID_FROM_UPLOAD" \
  --audio-md5 "MD5_FROM_UPLOAD" \
  --duration-ms 1008 \
  --language vi-VN
```

Query STT:

```bash
python3 capcut_common_task_client.py stt-query \
  --task-id "TASK_ID" \
  --token "TOKEN" \
  --out source/capcut_stt_result.json
```

STT result thường chứa subtitles trong:

```text
data.tasks[0].payload
payload.utterances[].text
payload.utterances[].start_time
payload.utterances[].end_time
payload.utterances[].words[]
```

`payload` là JSON string, phải parse thêm một lần trước khi đọc `utterances`.

## Kiểm thử không gọi API

Khi cần kiểm tra payload/signing trước:

```bash
python3 capcut_common_task_client.py stt-new \
  --audio-vid "VID_FROM_UPLOAD" \
  --audio-md5 "MD5_FROM_UPLOAD" \
  --duration-ms 1000 \
  --language vi-VN \
  --dry-run
```

## Báo cáo kết quả

Trong final answer, báo ngắn gọn:

- Command chính đã chạy.
- File JSON/audio đã tạo.
- Task state cuối cùng nếu có.
- Nếu thất bại, nêu HTTP status/message hoặc task error mà không lộ token/session.
