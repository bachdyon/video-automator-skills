# Video Agent Skills Hub

Kho kỹ năng (skills) để xây dựng pipeline sản xuất video ngắn bằng agent: lập kế hoạch, xử lý audio, ánh xạ asset, dựng timeline và render.

README này là điểm bắt đầu nhanh cho người mới; chi tiết kỹ thuật chuyên sâu nằm trong từng file `SKILL.md`.

## Mục lục

- [Tổng quan dự án](#tổng-quan-dự-án)
- [Quick Start](#quick-start)
- [Workflow mẫu: audio-deduplicate](#workflow-mẫu-audio-deduplicate)
- [Danh sách skills chính](#danh-sách-skills-chính)
- [Cấu trúc thư mục quan trọng](#cấu-trúc-thư-mục-quan-trọng)
- [Troubleshooting và lưu ý chất lượng](#troubleshooting-và-lưu-ý-chất-lượng)
- [Tài liệu liên quan](#tài-liệu-liên-quan)

## Tổng quan dự án

- `skills/`: chứa các project skills dùng lại theo từng tác vụ.
- `jobs/`: mỗi job là một lần chạy pipeline thực tế, có input, artifact trung gian, log, output.
- `tools/`: công cụ hỗ trợ thao tác thủ công/kiểm tra nhanh (ví dụ editor cho keep-flag).
- `scripts/`: script tiện ích cấp project (ví dụ kiểm tra Remotion skill).

## Skills

### Loại bỏ đoạn nói trùng lặp trong file ghi âm

Pipeline dùng skill `skills/audio-deduplicate`: Whisper (faster-whisper) trích timestamp từng từ → TOML `words_timestamp.toml` → **Phase 1** AI viết bản không lặp (`reconstructed_article_rewrite`) → **Phase 2** gán `keep=false` cho cụm bỏ và render nối các đoạn còn lại.

**Nếu coi thời lượng lặp/restart/vấp trong bản ghi (tùy bài nói) là 100% thì skill có thể khắc phục được khoảng 60%.**

Hiệu suất tốt nhất khi agent dùng model mạnh (ví dụ Opus 4.7) cho hai phase ngữ nghĩa, vì quyết định merge câu và range bỏ phụ thuộc AI, không heuristic tự động.

File trung gian nằm trong `jobs/<job_id>/input/audio/tmp/` (`words.json`, `words_timestamp.toml`, `render_keep_plan.json`). File xuất: `jobs/<job_id>/input/audio/<tên>_output.wav` (cùng thư mục với file `.wav` gốc).

Ví dụ sử dụng:

```
Chạy jobs/2026-04-25_001_clean-voice-repeats/input/audio/Máy ghi âm – 1522(1)_1.wav
với skills skills/audio-deduplicate lại từ đầu
```

Chi tiết từng bước, cờ script và tiêu chí rewrite (ví dụ mid-sentence restart) nằm trong `skills/audio-deduplicate/SKILL.md`.

