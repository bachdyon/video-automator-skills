# Word Keep Editor (Zero-install)

UI local để chỉnh `keep=true|false` cho từng từ trong `words_timestamp.toml`.

## Mở nhanh

### Cách 1: mở trực tiếp

- Mở file `tools/word-keep-editor/index.html` bằng trình duyệt.

### Cách 2: chạy local server (ổn định hơn khi kéo-thả nhiều file)

```bash
cd /Users/bachdyon/video-agent
python3 -m http.server 8911
```

Sau đó vào:

- <http://localhost:8911/tools/word-keep-editor/index.html>

## Luồng thao tác

1. Import `words_timestamp.toml`.
2. Chọn các từ không muốn giữ:
   - Click/Shift+Click để chọn.
   - Bấm `Delete` hoặc nút **Xóa từ đã chọn (keep=false)**.
3. Export:
   - `words_timestamp.toml` (đã cập nhật cờ `keep`)
   - (legacy) `ai-cuts.toml` nếu vẫn cần cut-based workflow cũ

## Render audio sau khi chỉnh tay

```bash
python3 skills/audio-deduplicate/scripts/audio/render_from_keep_words.py input.wav \
  --words-toml words_timestamp.toml \
  --output cleaned.wav \
  --pad-before 0.03 \
  --pad-after 0.05 \
  --merge-gap 0.08 \
  --plan-json render_keep_plan.json
```
