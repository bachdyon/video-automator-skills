---
name: word-timestamps-extractor
description: Trích xuất transcript narration có timestamp cấp câu và cấp từ; script hiện dùng OpenAI Whisper hoặc API transcription tương thích.
---

# Word Timestamps Extractor

## Quy tắc đầu ra (BẮT BUỘC)

- Mọi nội dung do AI/LLM sinh ra từ transcribe (`sentence`, `word`) **bắt buộc giữ tiếng Việt CÓ DẤU** nếu audio là tiếng Việt — không asciify, không bỏ dấu.
- Cấm asciify (vd KHÔNG được viết "song cham" thay cho "sống chậm" trong transcript).
- Tên trường (`audio_path`, `sentence_id`, `confidence`...), tên model (`whisper-1`...), CLI flag, file path giữ nguyên tiếng Anh — không dịch.
- Mọi ghi chú/lý do warning do agent thêm vào TOML cũng phải là tiếng Việt có dấu.

## Quy tắc môi trường script

Trước khi chạy bất kỳ script nào của skill này, đọc file `.env` ở repo-root trước. File này nằm cạnh `jobs/`, `skills/`, và `env.example`. Xác nhận `OPENAI_API_KEY` tồn tại và truyền `.env` qua `--env-file`; tuyệt đối không in giá trị secret. Chỉ dùng `--env-file` không phải repo-root khi user yêu cầu rõ ràng.

## Mục tiêu

Trích xuất audio narration thành transcript có timestamp câu và từ để sinh subtitle, căn cảnh, và semantic asset mapping.

Dùng skill này khi user cung cấp file audio và cần timing cấp từ.

## Đầu vào

- File audio, thường là `source/voice.wav` hoặc `source/voice.mp3`.
- Hint ngôn ngữ tùy chọn.
- Script text tùy chọn để sửa lỗi/align.
- Nếu narration vừa được **hậu xử lý tốc độ** (skill `ausynclab-voice`, `speed-pydub` / `voice_speed_pydub.py`) và ghi đè `voice.wav`, phải **chạy lại** bước transcribe trên file âm thanh mới trước khi dùng transcript cho subtitle hoặc semantic mapping.

## Đầu ra

Ghi hoặc trả về TOML. Đường dẫn mặc định:

```text
source/transcript_word_level.toml
```

Khi đã có video job, ghi vào:

```text
jobs/<job_id>/source/transcript_word_level.toml
```

## Quy trình

1. Định vị file audio và giữ nguyên path.
2. Dùng OpenAI Whisper hoặc model transcription OpenAI tương thích có hỗ trợ timestamp.
3. Yêu cầu timestamp cấp từ khi hỗ trợ.
4. Gom từ thành câu đọc được.
5. Nếu có script gốc, chỉ dùng để sửa lỗi chính tả/dấu câu hiển nhiên, không bịa timing.
6. Validate timestamp tăng đều và phủ đủ câu.

## Hợp đồng TOML

```toml
[metadata]
audio_path = "source/voice.wav"
language = "vi"
duration_seconds = 45.0
model = "whisper-compatible"

[[sentences]]
id = "S_001"
start = 0.12
end = 4.8
sentence = "..."
word_ids = ["W_0001", "W_0002"]

[[words]]
id = "W_0001"
word = "..."
start = 0.12
end = 0.38
sentence_id = "S_001"
confidence = 0.0
```

Nếu yêu cầu nested words thay thế, cũng hỗ trợ:

```toml
[[sentences]]
start = 0.12
end = 4.8
sentence = "..."
words = [
  { word = "...", start = 0.12, end = 0.38 }
]
```

## Quy tắc chất lượng

- Timestamp là số thực (giây).
- Từ phải có thứ tự và không overlap trong cùng 1 câu.
- Không silently drop từ có timing không chắc chắn; giữ chúng kèm warning khi cần.
- Giữ dấu câu trong `sentence`, nhưng `word` giữ nguyên token được nói khi có thể.

## Script tiện ích

Dùng script đi kèm để gọi API deterministic và normalize TOML:

```bash
python skills/word_timestamps_extractor/scripts/transcribe_word_timestamps.py \
  --audio source/voice.wav \
  --output source/transcript_word_level.toml \
  --env-file .env \
  --language vi
```

Cho job-scoped run:

```bash
python skills/word_timestamps_extractor/scripts/transcribe_word_timestamps.py \
  --audio jobs/<job_id>/source/voice.wav \
  --output jobs/<job_id>/source/transcript_word_level.toml \
  --env-file .env \
  --language vi
```

Script dùng `whisper-1` với `response_format=verbose_json` và `timestamp_granularities[]=word`, vì hiện tại OpenAI chỉ hỗ trợ word timestamp granularities trên `whisper-1`.
