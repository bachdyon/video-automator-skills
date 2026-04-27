---
name: ausynclab-voice
description: Làm việc với AusyncLab voice và Text-to-Speech API để liệt kê voice, gợi ý voice cho creative plan, lưu setting voice ưa thích, và sinh audio narration mp3 hoặc wav.
---

# AusyncLab Voice

## Quy tắc đầu ra (BẮT BUỘC)

- Mọi nội dung do AI/LLM sinh ra (`reason` chọn voice, ghi chú gửi user) **bắt buộc viết bằng tiếng Việt CÓ DẤU**.
- Cấm asciify (vd KHÔNG được viết "giong nu am ap" thay cho "giọng nữ ấm áp" trong reason).
- Tên trường (`voice_id`, `audio_id`...), enum giá trị API (`FEMALE`, `MALE`, `YOUNG`, `NARRATION`, `SUCCEED`...), CLI flag, file path, model id (`myna-2`...) giữ nguyên tiếng Anh — không dịch.
- Văn bản kịch bản voice (`text` gửi tới API) dĩ nhiên là tiếng Việt có dấu nếu user yêu cầu tiếng Việt.

## Quy tắc môi trường script

Trước khi chạy bất kỳ script nào của skill này, đọc file `.env` ở repo-root trước. File này nằm cạnh `jobs/`, `skills/`, và `env.example`. Xác nhận `AUSYNCLAB_API_KEY` tồn tại, và xác nhận `AUSYNCLAB_VOICE_ID` hoặc `--voice-id` trước khi synthesize. Truyền `.env` qua `--env-file`; tuyệt đối không in giá trị secret. Chỉ dùng `--env-file` không phải repo-root khi user yêu cầu rõ ràng.

## Mục tiêu

Quản lý lựa chọn voice và sinh audio narration qua AusyncLab.

Dùng skill này khi user yêu cầu liệt kê voice, chọn voice phù hợp, lưu voice ưa thích, hoặc tạo audio narration từ text/script bằng AusyncLab.

## Thông tin API

Tra docs chính thức khi cần chi tiết:

- Voice Library: `https://docs.ausynclab.io/voices`
- Text-to-Speech: `https://docs.ausynclab.io/tts`

Endpoint hiện đang dùng:

- `GET https://api.ausynclab.io/api/v1/voices/list`
- `POST https://api.ausynclab.io/api/v1/speech/text-to-speech`
- `GET https://api.ausynclab.io/api/v1/speech/`
- `GET https://api.ausynclab.io/api/v1/speech/{audio_id}`

Authentication dùng header:

```text
X-API-Key: <api key>
```

## Đầu vào

- API key từ `.env` ở repo-root.
- Script text từ `source/creative_plan.toml` hoặc input trực tiếp của user.
- Config voice ưa thích tùy chọn từ `.env` ở repo root, cạnh `skills/`.

## Đầu ra

File mặc định:

```text
source/voice_selection.toml
source/voice.wav
```

Khi đã có video job, ghi vào:

```text
jobs/<job_id>/source/voice_selection.toml
jobs/<job_id>/source/voice.wav
```

Nếu API trả về format hoặc URL khác, download/persist path audio cuối cùng và ghi lại trong TOML.

## Quy trình

1. Kiểm tra `AUSYNCLAB_API_KEY` từ `.env`. Không in key.
2. Liệt kê voice khi chưa biết chọn voice nào.
3. Gợi ý voice dựa trên ngôn ngữ, tone, audience, mood VDS, và delivery của creative plan.
4. Nếu user duyệt hoặc đã có preference đã lưu, persist:

```text
.env
```

với giá trị kiểu:

```text
AUSYNCLAB_VOICE_ID=123
```

Cho job-scoped run, vẫn dùng `.env` chung ở repo root cho credentials và voice default toàn cục trừ khi user cung cấp env file khác.

5. Gửi request Text-to-Speech với `audio_name`, `text`, `voice_id`, `speed`, `model_name`, và `language`.
6. Nếu không xử lý được callback, poll endpoint speech list/detail đến khi state audio thành công hoặc thất bại.
7. Download URL audio cuối cùng về `source/voice.wav` hoặc `source/voice.mp3`.
8. Ghi `source/voice_selection.toml`.

## Hợp đồng TOML

```toml
[voice]
provider = "ausynclab"
voice_id = 123
voice_name = "..."
language = "vi"
gender = "FEMALE"
age = "YOUNG"
use_case = "NARRATION"
model_name = "myna-2"
speed = 1.0
reason = "Giọng nữ ấm hợp với mood reflective của VDS."

[audio]
audio_id = 456
file_path = "source/voice.wav"
audio_url = "https://..."
format = "wav"
sample_rate = 24000
duration_seconds = 0.0
state = "SUCCEED"

[source]
script_path = "source/creative_plan.toml"
text_hash = "optional"
```

## Quy tắc chất lượng

- Không bao giờ lộ API key trong log hay file output.
- Hỏi xác nhận trước khi ghi đè voice ưa thích hiện có trừ khi user yêu cầu thay.
- Nội dung tiếng Việt mặc định `language = "vi"` và `model_name = "myna-2"` trừ khi ràng buộc khác.
- Giữ path audio sinh ra ổn định để Whisper và renderer skill tiêu thụ được.

## Script tiện ích

Dùng script đi kèm thay vì viết lại API call:

```bash
python skills/ausynclab_voice/scripts/ausynclab_voice.py --env-file .env list --output source/voices.toml
python skills/ausynclab_voice/scripts/ausynclab_voice.py --env-file .env recommend --language vi --use-case NARRATION --save-preference
python skills/ausynclab_voice/scripts/ausynclab_voice.py --env-file .env synthesize --creative-plan source/creative_plan.toml
```

Cho job-scoped run:

```bash
python skills/ausynclab_voice/scripts/ausynclab_voice.py --env-file .env synthesize \
  --creative-plan jobs/<job_id>/source/creative_plan.toml \
  --output-audio jobs/<job_id>/source/voice.wav \
  --output jobs/<job_id>/source/voice_selection.toml
```

Script xử lý `.env`, lookup API key, list voice, gợi ý đơn giản, submit TTS, poll, download audio, và sinh `source/voice_selection.toml`.
