---
name: lyricfind-lyrics
description: "Search LyricFind for song lyrics and lyric context, especially to correct Vietnamese music STT before writing subtitle captions; use the bundled Python client instead of generic web search when a song title or artist is known."
---

# LyricFind Lyrics

## Khi nào dùng

Dùng skill này khi cần lyric để sửa STT nghe sai, căn phụ đề nhạc, hoặc kiểm tra tên bài/ca sĩ:

- User đưa tên bài hát, ca sĩ, hoặc link video nhạc cần subtitle.
- Pipeline video cần đối chiếu transcript word-level với lyric chuẩn.
- Search web thường không ra lyric, nhưng LyricFind có `context`, `snippet`, `has_lrc`, `lrc_verified`.

## Quy tắc

- Dùng script `skills/lyricfind-lyrics/scripts/lyricfind_client.py` trước khi tự gọi API.
- Không dùng OCR để lấy lyric khi user yêu cầu STT + lyric source.
- Ghi full response/context vào file trong `source/` hoặc `jobs/<job_id>/source/`; stdout chỉ nên dùng summary.
- Không paste full lyric dài vào final answer. Chỉ báo file path, track match, score, và các dòng ngắn cần thiết cho caption nếu cần.
- Với video caption: lấy timing từ STT word-level, dùng lyric LyricFind để sửa từ sai, rồi viết `captions.json`.

## API

Base search endpoint:

```text
https://lyrics.lyricfind.com/api/v1/search
```

Tham số mặc định:

```text
reqtype=default
territory=VN
searchtype=track
all=<query>
alltracks=no
limit=25
output=json
useragent=<browser user agent>
```

## Script

Search theo tên bài:

```bash
.venv/bin/python skills/lyricfind-lyrics/scripts/lyricfind_client.py \
  search \
  --query "hành lý trên tay" \
  --artist "Kiều Chi" \
  --output jobs/<job_id>/source/lyricfind_search.json \
  --context-output jobs/<job_id>/source/lyricfind_best_context.txt
```

Search theo tên bài/ca sĩ rõ ràng:

```bash
.venv/bin/python skills/lyricfind-lyrics/scripts/lyricfind_client.py \
  search \
  --track "Hành Lý Trên Tay" \
  --artist "Kiều Chi" \
  --limit 10 \
  --output source/lyricfind_search.json \
  --context-output source/lyricfind_best_context.txt
```

## Workflow cho video nhạc

1. Chạy `$word-timestamps-extractor` để lấy transcript word-level từ audio.
2. Chạy `$lyricfind-lyrics` với `--track` và `--artist`.
3. Đọc `lyricfind_best_context.txt` để sửa các từ STT sai, không dùng OCR.
4. Giữ timing từ transcript word-level, gom lyric thành cue hoàn chỉnh, tối đa 2 dòng.
5. Ghi `source/captions.json` và render bằng template phù hợp.
