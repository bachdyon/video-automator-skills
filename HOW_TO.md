### Loại bỏ đoạn nói trùng lặp trong file ghi âm

Pipeline dùng skill `skills/audio-deduplicate`: Whisper (faster-whisper) trích timestamp từng từ → TOML `words_timestamp.toml` → **Phase 1** AI viết bản không lặp (`reconstructed_article_rewrite`) → **Phase 2** gán `keep=false` cho cụm bỏ và render nối các đoạn còn lại.

Khắc phục được khoảng 60% thời lượng lặp/restart/vấp trong bản ghi (tùy bài nói). Hiệu suất tốt nhất khi agent dùng model mạnh (ví dụ Opus 4.7) cho hai phase ngữ nghĩa, vì quyết định merge câu và range bỏ phụ thuộc AI, không heuristic tự động.

File trung gian nằm trong `jobs/<job_id>/input/audio/tmp/` (`words.json`, `words_timestamp.toml`, `render_keep_plan.json`). File xuất: `jobs/<job_id>/input/audio/<tên>_output.wav` (cùng thư mục với file `.wav` gốc).

Ví dụ sử dụng:

```
Chạy jobs/2026-04-25_001_clean-voice-repeats/input/audio/Máy ghi âm – 1522(1)_1.wav
với skills skills/audio-deduplicate lại từ đầu
```

Chi tiết từng bước, cờ script và tiêu chí rewrite (ví dụ mid-sentence restart) nằm trong `skills/audio-deduplicate/SKILL.md`.
