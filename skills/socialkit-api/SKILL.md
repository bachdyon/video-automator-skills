---
name: socialkit-api
description: Làm việc với SocialKit API bằng Python để lấy transcript, summary, stats, comments, channel stats, search, video listing và YouTube download cho YouTube, TikTok, Instagram, Facebook hoặc video file URL; dùng script Python đi kèm, không dùng curl.
---

# SocialKit API

## Quy tắc bắt buộc

- Dùng Python cho mọi request SocialKit. Không dùng `curl` để gọi API SocialKit.
- Dùng script `skills/socialkit-api/scripts/socialkit_client.py` trước khi tự viết code gọi API.
- Không in hoặc ghi lộ `SOCIALKIT_API_KEY`.
- Mặc định đọc key từ `.env` ở repo root. Chỉ dùng env file khác khi user yêu cầu rõ.
- Ưu tiên auth bằng header `x-access-key`; không đưa key vào URL/log.
- Khi response có `success: false`, báo lỗi theo `message` và HTTP status nếu có.

## Mục tiêu

Quản lý toàn bộ SocialKit API từ một client Python thống nhất:

- Video file URL: summary, transcript.
- YouTube: summary, transcript, stats, comments, channel stats, search, videos, download.
- TikTok: summary, transcript, stats, comments, channel stats, search, hashtag search.
- Instagram: summary, transcript, stats, channel stats.
- Facebook: summary, transcript, stats, channel stats.

## Nguồn docs

Docs chính thức:

- `https://docs.socialkit.dev/`
- `https://docs.socialkit.dev/authentication`
- `https://docs.socialkit.dev/api-reference`

Khi cần tham số/endpoint nhanh, đọc `references/api_reference.md`.

## Môi trường

`.env` repo-root nên có:

```text
SOCIALKIT_API_KEY=...
```

Không commit key thật. Nếu thiếu key, dừng lại và yêu cầu user thêm key vào `.env` hoặc truyền env file phù hợp.

## Script Python

Liệt kê operation có sẵn:

```bash
python skills/socialkit-api/scripts/socialkit_client.py endpoints
```

Gọi API và ghi JSON:

```bash
python skills/socialkit-api/scripts/socialkit_client.py call youtube.transcript \
  --param url=https://youtube.com/watch?v=dQw4w9WgXcQ \
  --output source/socialkit_youtube_transcript.json
```

Gọi summary với custom response/prompt:

```bash
python skills/socialkit-api/scripts/socialkit_client.py call tiktok.summary \
  --param url=https://www.tiktok.com/@user/video/123 \
  --param custom_prompt="Tóm tắt bằng tiếng Việt, ngắn gọn." \
  --json-param custom_response='{"hook":"Câu mở đầu","topics":["Chủ đề chính"],"viral_angle":"Lý do dễ viral"}' \
  --output source/socialkit_tiktok_summary.json
```

Tìm kiếm TikTok có pagination:

```bash
python skills/socialkit-api/scripts/socialkit_client.py call tiktok.search \
  --param query="skincare review" \
  --param limit=20 \
  --param sortBy=likes \
  --param datePosted=month \
  --output source/socialkit_tiktok_search.json
```

YouTube download trả `downloadUrl`; có thể tải file bằng Python trong cùng script:

```bash
python skills/socialkit-api/scripts/socialkit_client.py call youtube.download \
  --param url=https://youtube.com/watch?v=dQw4w9WgXcQ \
  --param format=mp4 \
  --param quality=360p \
  --output source/socialkit_youtube_download.json \
  --download-to source/youtube_download.mp4
```

Import từ Python khác:

```python
from skills.socialkit-api.scripts.socialkit_client import SocialKitClient

client = SocialKitClient.from_env_file(".env")
data = client.request("youtube.stats", url="https://youtube.com/watch?v=dQw4w9WgXcQ")
```

## Quy trình làm việc

1. Xác định platform và operation từ user request.
2. Đọc `.env`; xác nhận `SOCIALKIT_API_KEY` tồn tại mà không in key.
3. Chạy `endpoints` nếu chưa chắc operation key.
4. Chạy `call <operation>` với `--param` / `--json-param`.
5. Ghi output JSON vào `source/` hoặc `jobs/<job_id>/source/` nếu request thuộc video job.
6. Nếu dùng kết quả cho pipeline video, chuẩn hóa transcript/summary/stats thành artifact rõ tên, không trộn vào creative plan nếu chưa được user yêu cầu.

## Ghi chú API

- SocialKit base URL: `https://api.socialkit.dev`.
- Docs nói GET hoặc POST đều được; script mặc định dùng GET cho đơn giản và dùng header auth.
- `cache` mặc định false; `cache_ttl` mặc định `2592000` giây, min `3600`, max `2592000`.
- Summary endpoint hỗ trợ `custom_response` và `custom_prompt`.
- Search/list comments/videos có `limit` tối đa 100; credit tính theo 50 kết quả với các endpoint đó.
- Video file summary/transcript tính credit theo phút video.
