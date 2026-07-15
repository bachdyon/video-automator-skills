---
name: facebook-reel-downloader
description: Download public Facebook Reel videos with yt-dlp into the repository raw asset pool or a specific video job. Use when a user provides a facebook.com/reel, facebook.com/watch, Facebook video, or fb.watch URL and asks to download, save, or ingest the video as a local asset.
---

# Facebook Reel Downloader

Tải Facebook Reel bằng script `scripts/download_facebook_reel.py`. Giữ URL tải trực tiếp và cookie ngoài log/report.

## Quy trình

1. Chỉ tải nội dung công khai hoặc nội dung người dùng có quyền truy cập và sử dụng. Không vượt DRM, paywall, hoặc quyền riêng tư.
2. Mặc định lưu vào `raw_assets/videos/downloaded/facebook/`:

   ```bash
   .venv/bin/python skills/facebook-reel-downloader/scripts/download_facebook_reel.py \
     --url "https://www.facebook.com/reel/123"
   ```

3. Khi Reel là đầu vào của một job, truyền `--job jobs/<job_id>` để lưu vào `jobs/<job_id>/input/raw_assets/videos/downloaded/facebook/`.
4. Nếu Facebook yêu cầu đăng nhập và người dùng có quyền xem Reel, chạy lại với `--cookies-from-browser chrome` (hoặc `safari`, `firefox`). Không sao chép hay in cookie.
5. Đọc `download_report.toml`, kiểm tra file tồn tại, rồi dùng `ffprobe` xác nhận duration, kích thước và codec.
6. Nếu asset sẽ được dùng ngay trong pipeline video, chạy `$asset-semantic-extractor`; nếu chưa dùng, để asset-index watcher tự nhận file.

## Tùy chọn chính

- `--url`: URL Facebook Reel/video cần tải.
- `--job`: thư mục job, ví dụ `jobs/2026-07-14_001-demo`.
- `--output-dir`: ghi đè thư mục đích.
- `--cookies-from-browser`: đọc phiên đăng nhập cục bộ qua yt-dlp.
- `--overwrite`: tải lại nếu file đã tồn tại.
- `--report-toml`: thay đổi vị trí report.

Script ưu tiên H.264 MP4 + M4A audio để tương thích tốt với trình phát và pipeline dựng, sau đó fallback sang MP4 tốt nhất hoặc định dạng tốt nhất mà Facebook cung cấp. Không dùng `--cookies-from-browser` trừ khi tải công khai thất bại vì đăng nhập.

## Xử lý lỗi

- `yt-dlp executable not found`: chạy `npm install` không giải quyết lỗi này; dùng `.venv/bin/pip install -U yt-dlp` nếu người dùng cho phép.
- `Login required` hoặc cookie lỗi: xác nhận Reel mở được trong browser profile rồi truyền đúng tên browser.
- Reel riêng tư, bị xóa, giới hạn vùng, hoặc không thuộc quyền truy cập của người dùng: dừng và báo rõ; không tìm cách bypass.
- Lỗi extractor do Facebook thay đổi: cập nhật yt-dlp trong `.venv`, rồi thử lại một lần.
