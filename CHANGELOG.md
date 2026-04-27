# Changelog

## v1.0.0 - 2026-04-27

Release đầu tiên của **video-automator-skills (VAS)**: bộ project skills và tooling để agent sản xuất video ngắn từ brief, video mẫu, raw assets, voice, transcript, semantic mapping đến render MP4.

### Added

- Thêm 13 project skills trong `skills/<skill>/SKILL.md`:
  - `$video-production-orchestrator`
  - `$video-job-manager`
  - `$video-design-spec-builder`
  - `$video-creative-planner`
  - `$asset-semantic-extractor`
  - `$semantic-asset-mapper`
  - `$shot-coverage-planner`
  - `$fal-image-generator`
  - `$ausynclab-voice`
  - `$word-timestamps-extractor`
  - `$audio-deduplicate`
  - `$video-render-plan-builder`
  - `$video-renderer`
- Thêm pipeline orchestration cho video short-form: job setup, VDS, creative plan, voice, transcript timing, asset semantics, semantic mapping, shot coverage, render plan và renderer.
- Thêm Asset Index trong `tools/asset_index/`:
  - Watcher theo dõi `raw_assets/`.
  - Analyzer cho image, video và audio.
  - SHA-256 content addressing để tránh phân tích lại cùng một file.
  - SQLite + sqlite-vec để search asset bằng ngôn ngữ tự nhiên.
  - Exporter để tạo `asset_semantics.toml` cho từng job.
- Thêm auto installer và tiện ích vận hành:
  - `setup/Install.command`, `setup/Install.bat`
  - `setup/Search.command`, `setup/Search.bat`
  - `setup/Status.command`, `setup/Status.bat`
  - `setup/Uninstall.command`, `setup/Uninstall.bat`
- Thêm hỗ trợ chạy watcher nền trên macOS, Windows và Linux/fallback polling.
- Thêm tích hợp cho Codex, Cursor và Claude Code qua `AGENTS.md`, `.claude/skills/` và skill metadata.
- Thêm integration với `$remotion-best-practices` cho các task Remotion.
- Thêm Fal image generation để sinh asset AI từ creative plan, có hỗ trợ reference image để giữ nhân vật.
- Thêm AusyncLab voice workflow để chọn voice và sinh narration audio.
- Thêm word-level transcript extraction bằng OpenAI Whisper/transcription API tương thích.
- Thêm audio deduplication workflow để loại đoạn nói lặp trong narration.
- Thêm GitHub issue template cho bug report, gồm OS, IDE/agent, model, cách cài, log và context.

### Documentation

- Thêm Mintlify docs cho quickstart, installation, usage, troubleshooting, architecture, glossary, features và từng skill.
- Thêm README với logo, danh sách skills và link tài liệu.
- Thêm glossary, gồm định nghĩa `Asset`, `Asset Index`, `Job`, `VDS`, `Render plan`, `EDL` và các khái niệm pipeline.
- Thêm docs Asset Index: architecture, CLI, runtime files, idempotency, cross-platform và extending.
- Thêm logo docs `180x23` và favicon SVG cho VAS.

### Changed

- Đổi tên skill `$openai-whisper-word-timestamps` thành `$word-timestamps-extractor` để ngắn và mô tả đúng vai trò hơn.
- Chuẩn hóa pipeline asset-driven: nếu có raw assets thì chạy asset semantics trước creative planning/mapping để creative plan bám footage thật.
- Chuẩn hóa wording trong docs: Whisper/OpenAI là backend implementation của transcript timing, không còn là tên skill.
