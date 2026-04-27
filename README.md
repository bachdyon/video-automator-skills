# Video Agent Skills Hub

Kho kỹ năng (skills) để xây dựng pipeline sản xuất video ngắn bằng agent: lập kế hoạch, xử lý audio, ánh xạ asset, dựng timeline và render.

README này là điểm bắt đầu nhanh cho người mới; chi tiết kỹ thuật chuyên sâu nằm trong từng file `SKILL.md`.

## Asset Index — Cài 3 bước cho người mới

1. Mở thư mục `setup/`, double-click **Install.command** (macOS) hoặc **Install.bat** (Windows).
2. Khi trình duyệt mở, tạo 2 key (OpenAI + Gemini) rồi quay lại dán vào cửa sổ cài đặt.
3. Thả file ảnh / video / audio vào `raw_assets/` — xong! Hệ thống tự phân tích trong nền và bật lại sau mỗi lần khởi động máy.

Tìm kiếm: double-click **Search.command** / **Search.bat** rồi gõ truy vấn tiếng Việt.
Trạng thái: **Status.command** / **Status.bat**. Gỡ cài: **Uninstall.command** / **Uninstall.bat**.

Chi tiết kỹ thuật của module nằm ở `tools/asset_index/` — xem mục [Asset Index nâng cao](#asset-index-nâng-cao) cuối README.

## Mục lục

- [Tổng quan dự án](#tổng-quan-dự-án)
- [Quick Start](#quick-start)
- [Workflow mẫu: audio-deduplicate](#workflow-mẫu-audio-deduplicate)
- [Danh sách skills chính](#danh-sách-skills-chính)
- [Cấu trúc thư mục quan trọng](#cấu-trúc-thư-mục-quan-trọng)
- [Troubleshooting và lưu ý chất lượng](#troubleshooting-và-lưu-ý-chất-lượng)
- [Asset Index nâng cao](#asset-index-nâng-cao)
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

## Asset Index nâng cao

Module `tools/asset_index/` đứng sau cơ chế "thả file → tự index" mô tả ở đầu README. Bên dưới là chi tiết kỹ thuật cho người muốn tuỳ biến.

### Kiến trúc

```
raw_assets/                      <- thư mục chính người dùng thả file
jobs/<job_id>/input/raw_assets/  <- (tuỳ chọn) thư mục theo từng job, bật bằng --include-jobs
            │
            ▼
watcher.py  ──debounce 1.5s──▶  router.py  ──┬─▶ analyzers/image_gemini.py  (Gemini Vision)
                                              ├─▶ analyzers/video_gemini.py  (probe + Gemini frame analysis)
                                              └─▶ analyzers/audio_gemini.py  (Gemini multimodal trên audio)
                                              │
                                              ▼
                                      embed.py (OpenAI text-embedding-3-small, 1536 dim)
                                              │
                                              ▼
                                      store.py (apsw + sqlite-vec)  →  .asset_index/index.db
```

### Lệnh CLI dành cho dev

```bash
.venv/bin/python -m tools.asset_index.router <file>...      # index thủ công
.venv/bin/python -m tools.asset_index.watcher --debounce-seconds 1.0 [--include-jobs] [--scan-on-start] [--polling]
.venv/bin/python -m tools.asset_index.search "phong cảnh núi" --top 5 [--media image|video|audio] [--source raw_assets|jobs]
.venv/bin/python -m tools.asset_index.service install|uninstall|status
.venv/bin/python tools/asset_index/bootstrap.py --non-interactive --skip-service   # CI-friendly
```

### File hệ thống

- `.asset_index/index.db` — SQLite + vec0 virtual table. Xoá tự rebuild lần sau.
- `.asset_index/state.json` — pid + thống kê watcher (ưu tiên đọc khi dev).
- `.asset_index/logs/watcher.{out,err}.log` — log từ launchd / Task Scheduler.
- macOS: `~/Library/LaunchAgents/com.video-agent.asset-index.plist` (KeepAlive=true).
- Windows: scheduled task `VideoAgentAssetIndex` (ONLOGON, retry).

### Idempotency

- Mỗi file được hash SHA-256. Nếu hash + path + mtime không đổi → skip, không tốn LLM call.
- File đổi tên giữ nguyên `id` vì bytes không đổi → record được cập nhật path tự động.

### Cross-platform notes

- macOS dùng FSEvents, tự fallback `PollingObserver` nếu emitter chết (sandbox, ổ mạng…).
- Windows ưu tiên `cp65001` để không vỡ tiếng Việt; bật Long Paths nếu đường dẫn > 260 ký tự (`Computer Configuration → Filesystem → Enable Win32 long paths`).
- `apsw` được dùng thay `sqlite3` để load `sqlite-vec` (bản built-in của python.org tắt `enable_load_extension`).
- `certifi` đảm bảo SSL OK trong `.venv` mới (đặc biệt python.org installer trên macOS).

### Mở rộng

- Thêm format mới: bổ sung suffix vào `MEDIA_*_EXTENSIONS` trong `skills/_shared/pipeline_utils.py` rồi viết analyzer mới.
- Thay model embed: chỉnh `OPENAI_EMBED_MODEL` (env) và cập nhật `EMBED_DIM` trong `store.py` + `schema.sql`.
- Search filter: dùng `--source jobs` hoặc `--job <job_id>` để giới hạn theo từng job.

