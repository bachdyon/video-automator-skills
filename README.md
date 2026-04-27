# video-automator-skills

<p align="center">
  <img src="logo-dark.svg" alt="video automator skills" width="180" height="23">
</p>

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
- `$ausynclab-voice` — chọn voice và sinh narration audio bằng AusyncLab. [Chi tiết](https://vas.bachdyon.com/skills/ausynclab-voice)
- `$word-timestamps-extractor` — trích xuất transcript narration có timestamp cấp câu và cấp từ. [Chi tiết](https://vas.bachdyon.com/skills/word-timestamps-extractor)
- `$audio-deduplicate` — bỏ đoạn nói trùng lặp/restart/vấp trong file ghi âm. [Chi tiết](https://vas.bachdyon.com/skills/audio-deduplicate)
- `$video-render-plan-builder` — chuyển VDS, creative plan, transcript và semantic mapping thành render plan TOML. [Chi tiết](https://vas.bachdyon.com/skills/video-render-plan-builder)
- `$video-renderer` — render video cuối từ render plan, audio, asset, subtitle và style rules. [Chi tiết](https://vas.bachdyon.com/skills/video-renderer)

Official third-party skill:

- `$remotion-best-practices` — skill chính thức từ `remotion-dev/skills`, bắt buộc dùng cho mọi task Remotion.

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
