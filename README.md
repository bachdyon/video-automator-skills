# video-automator-skills

> Kho kỹ năng (skills) để xây pipeline sản xuất video ngắn bằng agent: lập kế hoạch, xử lý audio, tìm kiếm asset, dựng timeline và render video tự động.

Tài liệu đầy đủ: **https://vas.bachdyon.com/**

## Skills

- `$video-production-orchestrator` — điều phối toàn bộ pipeline từ brief/video mẫu/raw asset đến render cuối. [Chi tiết](https://vas.bachdyon.com/skills/video-production-orchestrator)
- `$video-job-manager` — tạo và quản lý job, metadata, input, artifact, status và stale state. [Chi tiết](https://vas.bachdyon.com/skills/video-job-manager)
- `$video-design-spec-builder` — phân tích video mẫu thành Video Design Specification tái sử dụng. [Chi tiết](https://vas.bachdyon.com/skills/video-design-spec-builder)
- `$video-creative-planner` — biến brief/VDS/asset context thành creative plan, script, scene intents và asset requirements. [Chi tiết](https://vas.bachdyon.com/skills/video-creative-planner)
- `$asset-semantic-extractor` — sinh `asset_semantics.toml` từ ảnh/video raw, ưu tiên đọc asset-index DB. [Chi tiết](https://vas.bachdyon.com/skills/asset-semantic-extractor)
- `$semantic-asset-mapper` — map transcript hoặc scene intents vào asset đã index để tạo timeline mapping. [Chi tiết](https://vas.bachdyon.com/skills/semantic-asset-mapper)
- `$shot-coverage-planner` — xử lý thiếu coverage và lặp asset bằng cutaway, slowdown, hold + Ken Burns. [Chi tiết](https://vas.bachdyon.com/skills/shot-coverage-planner)
- `$fal-image-generator` — sinh ảnh AI bằng fal.ai từ prompt/scene intents, hỗ trợ reference để giữ nhân vật. [Chi tiết](https://vas.bachdyon.com/skills/fal-image-generator)
- `$ausynclab-voice` — chọn voice và sinh narration audio bằng AusyncLab khi có `AUSYNCLAB_API_KEY`; fallback sang `$free-tts` khi thiếu key. [Chi tiết](https://vas.bachdyon.com/skills/ausynclab-voice)
- `$free-tts` — tạo giọng đọc miễn phí/local bằng VieNeu-TTS, hỗ trợ preset voice, voice clone, và registry `.shared`. [Chi tiết](https://vas.bachdyon.com/skills/free-tts)
- `$word-timestamps-extractor` — trích xuất transcript narration có timestamp cấp câu và cấp từ. [Chi tiết](https://vas.bachdyon.com/skills/word-timestamps-extractor)
- `$audio-deduplicate` — bỏ đoạn nói trùng lặp/restart/vấp trong file ghi âm. [Chi tiết](https://vas.bachdyon.com/skills/audio-deduplicate)
- `$video-audio-extractor` — tách audio track từ video sang WAV/MP3 để transcribe, deduplicate hoặc dùng làm nhạc nền. [Chi tiết](https://vas.bachdyon.com/skills/video-audio-extractor)
- `$video-downloader` — tải TikTok video/slideshow/audio qua TikWM vào `raw_assets/` hoặc `jobs/<id>/input/raw_assets/`. [Chi tiết](https://vas.bachdyon.com/skills/video-downloader)
- `$socialkit-api` — gọi SocialKit API bằng Python để lấy transcript, summary, stats, comments, search, channel stats và YouTube download. [Chi tiết](https://vas.bachdyon.com/skills/socialkit-api)
- `$subtitle-screen-splitter` — chia subtitle/transcript thành các page ngắn vừa màn hình cho karaoke captions hoặc render plan. [Chi tiết](https://vas.bachdyon.com/skills/subtitle-screen-splitter)
- `$video-render-plan-builder` — chuyển VDS, creative plan, transcript và semantic mapping thành render plan TOML. [Chi tiết](https://vas.bachdyon.com/skills/video-render-plan-builder)
- `$video-renderer` — render video cuối từ render plan, audio, asset, subtitle và style rules. [Chi tiết](https://vas.bachdyon.com/skills/video-renderer)
- `$video-quality-auditor` — audit Remotion source/render plan, ưu tiên overlay readability và safe-area, rồi xuất báo cáo TOML/HTML. [Chi tiết](https://vas.bachdyon.com/skills/video-quality-auditor)
- `$overlay-subject-placement` — phân tích frame bằng vision LLM để đề xuất vị trí overlay tránh che chủ thể và vùng unsafe. [Chi tiết](https://vas.bachdyon.com/skills/overlay-subject-placement)
- `$podcast-karaoke-frame-template` — instantiate template Podcast Karaoke Rounded Frame cho job đã có render plan, transcript và visual timeline. [Chi tiết](https://vas.bachdyon.com/skills/podcast-karaoke-frame-template)
- `$theanh28-template` — instantiate template Theanh28-style cho short video tiếng Việt với AI news intro overlay và source clip playback. [Chi tiết](https://vas.bachdyon.com/skills/theanh28-template)
- `$job-to-template` — chuyển job Remotion đã hoàn thiện thành template và project skill tái sử dụng. [Chi tiết](https://vas.bachdyon.com/skills/job-to-template)

Official third-party skill:

- `$remotion-best-practices` — skill chính thức từ `remotion-dev/skills`, bắt buộc dùng cho mọi task Remotion.

---

Nếu repo hữu ích cho bạn, hãy cân nhắc [donate](https://vas.bachdyon.com/donate) để dự án có kinh phí tiếp tục dùng AI tools cho phát triển và test tính năng mới.

---

## Tài liệu

- [Bắt đầu nhanh](https://vas.bachdyon.com/quickstart)
- [Cài đặt đầy đủ (macOS / Windows / Linux)](https://vas.bachdyon.com/installation/macos)
- [Cấu hình API keys](https://vas.bachdyon.com/configuration/env)
- [Asset Index nâng cao](https://vas.bachdyon.com/asset-index/architecture)
- [Khắc phục sự cố](https://vas.bachdyon.com/troubleshooting)

## Đóng góp

Đóng góp được hoan nghênh. Đọc [CONTRIBUTING.md](CONTRIBUTING.md) hoặc [hướng dẫn online](https://vas.bachdyon.com/contributing) để biết cách báo bug, đề xuất feature, hoặc viết skill mới.

## License

**PolyForm Noncommercial 1.0.0** — sử dụng cá nhân, học tập, nghiên cứu OK. Mọi mục đích thương mại cần xin phép tác giả ([@bachdyon](https://github.com/bachdyon)). Xem toàn văn: [LICENSE](LICENSE).
