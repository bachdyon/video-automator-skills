---
name: video-downloader
description: Download TikTok videos or slide images through the TikWM form API and save them into raw_assets/ or jobs/<id>/input/raw_assets/ for the video pipeline.
---

# Video Downloader

## Quy tắc đầu ra (BẮT BUỘC)

- Mọi ghi chú do AI/LLM sinh ra cho user hoặc report ngắn phải viết bằng tiếng Việt CÓ DẤU khi context là tiếng Việt.
- URL, API header, CLI flag, file path, enum (`video`, `images`, `audio`, `all`) giữ nguyên tiếng Anh.
- Không in full URL tải trực tiếp nếu URL có token ngắn hạn; chỉ báo file path local và metadata cần thiết.

## Mục tiêu

Tải video TikTok / ảnh slideshow / audio gốc thành asset local để pipeline dùng như footage thật. Skill này dùng endpoint TikWM:

```text
POST https://www.tikwm.com/api/
Content-Type: application/x-www-form-urlencoded; charset=UTF-8
```

Body tối thiểu:

```text
url=<tiktok_url>&count=12&cursor=0&web=1&hd=1
```

## Khi nào dùng

- User đưa link TikTok và muốn tải về làm raw asset.
- User đưa curl TikWM đã chạy được và muốn chuẩn hóa thành workflow lặp lại.
- Pipeline cần đưa TikTok clip vào `raw_assets/videos/downloaded/` hoặc `jobs/<id>/input/raw_assets/videos/downloaded/`.

## Quy tắc pháp lý / quyền sử dụng

- Chỉ tải nội dung khi user có quyền dùng nội dung đó hoặc nội dung được phép sử dụng cho mục đích hiện tại.
- Không dùng skill này để né paywall, truy cập nội dung riêng tư, hoặc bypass cơ chế bảo vệ trái phép.
- Nếu user định dùng thương mại, nhắc họ xác nhận quyền sử dụng footage/audio trước khi render final.

## Đầu vào

- `--url`: 1 URL TikTok.
- `--urls-file`: file text chứa nhiều URL, mỗi dòng 1 URL; dòng trống và dòng bắt đầu bằng `#` bị bỏ qua.
- `--job jobs/<id>`: nếu có, output mặc định vào `jobs/<id>/input/raw_assets/...`.
- `--output-dir`: override thư mục lưu asset. Nếu không truyền:
  - có `--job` → `jobs/<id>/input/raw_assets/videos/downloaded`
  - không có `--job` → `raw_assets/videos/downloaded`
- `--mode video|images|audio|all`: mặc định `video`.
- `--hd`: ưu tiên `hdplay` nếu API trả về.
- `--report-toml`: mặc định `download_report.toml` trong `output-dir`, hoặc `jobs/<id>/source/download_report.toml` khi có `--job`.

## Đầu ra

```text
raw_assets/videos/downloaded/<id>_<slug>.mp4
raw_assets/audio/downloaded/<id>_<slug>.mp3
raw_assets/images/downloaded/<id>_image_001.jpg
```

Report TOML ghi lại URL nguồn, provider, asset path, title, author, media type, byte size, duration/dimensions nếu `ffprobe` có sẵn.

## Script tiện ích

```bash
# Tải 1 video vào global raw_assets pool
python skills/video-downloader/scripts/download_video.py \
  --url "https://www.tiktok.com/@user/video/123" \
  --hd

# Tải vào job hiện có để watcher asset-index pickup
python skills/video-downloader/scripts/download_video.py \
  --url "https://www.tiktok.com/@user/video/123" \
  --job jobs/<id> \
  --hd

# Batch nhiều URL
python skills/video-downloader/scripts/download_video.py \
  --urls-file urls.txt \
  --job jobs/<id> \
  --mode all
```

## Quy trình

1. Xác nhận user có quyền dùng nội dung nếu mục đích không rõ.
2. Chạy script với `--url` hoặc `--urls-file`; dùng `--job` khi đây là asset cho một video job cụ thể.
3. Kiểm tra report TOML và số file đã tải.
4. Nếu dùng cho pipeline ngay, chạy `$asset-semantic-extractor` hoặc exporter asset-index để cập nhật `source/asset_semantics.toml`; nếu không, watcher sẽ tự pickup.

## Ghi chú triển khai

- Script gửi các header browser-like tương tự curl mẫu để TikWM chấp nhận request từ workflow hiện tại.
- Với video thường, chọn URL theo thứ tự: `hdplay` (khi `--hd`) → `play` → `wmplay`.
- Với slideshow, `images[]` được tải khi `--mode images` hoặc `--mode all`.
- Audio nhạc/narration được tải từ `music` hoặc `music_info.play` khi `--mode audio` hoặc `--mode all`.
- File name ổn định theo `aweme_id/id` và slug title; rerun sẽ skip file đã tồn tại trừ khi truyền `--overwrite`.
