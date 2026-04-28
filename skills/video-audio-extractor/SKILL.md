---
name: video-audio-extractor
description: Tách audio track từ file video sang WAV hoặc MP3 để dùng cho transcript, khử lặp lời nói, hoặc map nhạc nền trong render plan.
---

# Video Audio Extractor

## Quy tắc đầu ra (BẮT BUỘC)

- Mọi ghi chú do AI/LLM sinh ra (lý do chọn format, giải thích workflow) phải viết tiếng Việt có dấu.
- Tên trường (`input_video`, `output_audio`, `sample_rate`...), cờ CLI, đường dẫn file giữ nguyên tiếng Anh.
- Không đổi nội dung âm thanh bằng AI trong skill này; chỉ extract audio track từ video.

## Mục tiêu

Tách phần audio từ video thành file rời để dùng lại trong pipeline:

- Tạo transcript/timestamp bằng `$word-timestamps-extractor`.
- Làm sạch narration bị lặp bằng `$audio-deduplicate`.
- Dùng làm nền cho render plan (`audio.music`).

## Đầu vào

- File video nguồn, thường ở:
  - `jobs/<job_id>/input/raw_assets/...`
  - hoặc `jobs/<job_id>/output/final_video.mp4`
- Tuỳ chọn format output: `wav` (mặc định) hoặc `mp3`.
- Tuỳ chọn sample rate và bitrate.

## Đầu ra

Mặc định lưu vào:

```text
jobs/<job_id>/input/audio/<base>.wav
```

Nếu user yêu cầu MP3:

```text
jobs/<job_id>/input/audio/<base>.mp3
```

## Quy trình

1. Xác định file video nguồn và đảm bảo nằm trong job hiện tại.
2. Tạo thư mục `jobs/<job_id>/input/audio/` nếu chưa có.
3. Chạy `ffmpeg` để extract audio không tái mã hoá video (chỉ làm việc trên audio stream).
4. Validate file output tồn tại, thời lượng > 0, codec đúng theo format yêu cầu.
5. Trả về path output để skill downstream dùng trực tiếp.

## Quy ước mặc định

- Ưu tiên `wav` cho pipeline speech (transcribe/deduplicate) vì ổn định hơn khi xử lý timestamp.
- Dùng `mp3` khi mục tiêu là nhạc nền nhẹ dung lượng.
- Không trim/cắt đoạn trong skill này; nếu cần cắt timeline thì xử lý ở render plan.

## Script tiện ích

Extract WAV (khuyến nghị cho transcript):

```bash
ffmpeg -y \
  -i "jobs/<job_id>/input/raw_assets/<video>.mp4" \
  -vn \
  -ac 1 \
  -ar 44100 \
  -c:a pcm_s16le \
  "jobs/<job_id>/input/audio/<video>.wav"
```

Extract MP3 (khuyến nghị cho nhạc nền nhẹ):

```bash
ffmpeg -y \
  -i "jobs/<job_id>/input/raw_assets/<video>.mp4" \
  -vn \
  -c:a libmp3lame \
  -b:a 192k \
  "jobs/<job_id>/input/audio/<video>.mp3"
```

## Liên thông với skill khác

Sau khi extract xong:

1. Narration/speech:
   - Chạy `$word-timestamps-extractor` để tạo `transcript_word_level.toml`.
   - Nếu audio có lặp lời nói, chạy tiếp `$audio-deduplicate`.
2. Nhạc nền:
   - Dùng file output làm `audio.music.path` trong render plan (`$video-render-plan-builder`).

## Quy tắc chất lượng

- Không tạo file ngoài `jobs/<job_id>/input/audio/` trừ khi user chỉ định rõ.
- Nếu video không có audio stream, fail sớm và báo rõ nguyên nhân.
- Không overwrite file quan trọng ngoài output đích đã xác nhận.
- Luôn trả về đường dẫn output tuyệt đối hoặc job-relative để downstream gọi lại được.
