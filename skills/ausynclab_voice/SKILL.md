---
name: ausynclab-voice
description: Làm việc với AusyncLab voice và Text-to-Speech API để liệt kê voice, gợi ý voice cho creative plan, lưu setting voice ưa thích, sinh audio narration mp3 hoặc wav, và (tùy chọn) hậu xử lý tăng/giảm tốc WAV sau TTS bằng pydub.
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

Dùng skill này khi user yêu cầu liệt kê voice, chọn voice phù hợp, lưu voice ưa thích, tạo audio narration từ text/script bằng AusyncLab, hoặc **sau TTS** muốn chỉnh tốc độ phát file WAV (pydub) mà không gọi lại API.

## Thông tin API

Tra docs chính thức khi cần chi tiết:

- Voice Library: `https://docs.ausynclab.io/voices`
- Text-to-Speech: `https://docs.ausynclab.io/tts`

Các endpoint/base URL đã được quản lý tập trung trong script `skills/ausynclab_voice/scripts/ausynclab_voice.py` (`VOICE_BASE`, `SPEECH_BASE`).
Trong workflow của skill này, agent chỉ chạy CLI script sẵn có; không tự viết CURL hay gọi API thủ công.

Authentication được script tự set từ `AUSYNCLAB_API_KEY` khi truyền `--env-file`.

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

## Hậu xử lý tốc độ WAV (pydub) — khi user yêu cầu

Sau khi đã có `voice.wav`, nếu user muốn nhịp nhanh/chậm hơn so với tham số `speed` của API (hoặc muốn thử nhiều hệ số), dùng **pydub** `speedup` (giữ pitch ổn định hơn so với chỉ đổi sample rate).

**Phụ thuộc:** cài một lần:

```bash
pip install -r skills/ausynclab_voice/scripts/requirements-voice-speed.txt
```

Trên **Python 3.13+**, gói `audioop-lts` là bắt buộc (stdlib đã bỏ `audioop` mà pydub cần).

**Cách 1 — subcommand cùng entrypoint AusyncLab:**

```bash
python skills/ausynclab_voice/scripts/ausynclab_voice.py speed-pydub \
  --input jobs/<job_id>/source/voice.wav \
  --in-place \
  --playback-speed 1.12 \
  --update-voice-selection jobs/<job_id>/source/voice_selection.toml
```

**Cách 2 — script độc lập:**

```bash
python skills/ausynclab_voice/scripts/voice_speed_pydub.py \
  --input jobs/<job_id>/source/voice.wav \
  --output jobs/<job_id>/source/voice_speed_preview.wav \
  --playback-speed 1.15
```

- `--in-place`: ghi đè đúng file `--input` (an toàn qua file tạm rồi `move`).
- `--update-voice-selection`: cập nhật `[audio].duration_seconds` và nối ghi chú vào `[voice].reason` (tiếng Việt có dấu). Chỉ nên dùng khi file đầu ra là narration chuẩn trong job (vd `source/voice.wav`); nếu xuất ra file preview khác path thì không bật flag này.
- `--playback-speed`: `> 1` nhanh hơn, `0 < x < 1` chậm hơn (pydub vẫn hỗ trợ nhưng ít dùng cho TikTok).

**Sau khi đổi tốc độ và ghi đè `voice.wav`**, pipeline phải tiếp tục đúng thứ tự nghiệp vụ (xem `video-production-orchestrator`): đo lại độ dài intro, chỉnh `render_plan.toml` + `Root.tsx` (+ copy asset Remotion), **chạy lại** `$word-timestamps-extractor` nếu transcript phải khớp audio mới, rồi render plan / render nếu phụ thuộc transcript.
