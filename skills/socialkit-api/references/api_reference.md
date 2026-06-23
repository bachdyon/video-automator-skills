# SocialKit API Reference

Official docs checked from `https://docs.socialkit.dev/` on 2026-04-28.

Base URL: `https://api.socialkit.dev`

Auth:

- Prefer header: `x-access-key: <SOCIALKIT_API_KEY>`
- Docs also allow `access_key` as GET/POST parameter, but do not use that by default because URLs/logs can leak.

Common optional params:

- `cache`: boolean, default `false`
- `cache_ttl`: number in seconds, default `2592000`, min `3600`, max `2592000`

Summary params:

- Required: `url`
- Optional: `custom_response` object/string, `custom_prompt` string, `cache`, `cache_ttl`
- Response usually includes `summary`, `mainTopics`, `keyPoints`, `tone`, `targetAudience`, `quotes`, `timeline`; platform endpoints may add ids.

Transcript params:

- Required: `url`
- Optional: `cache`, `cache_ttl`
- Response usually includes `transcript`, `transcriptSegments`, `wordCount`, `segments`; TikTok may include `subtitleInfos`.

## Operations

| Operation key | Endpoint | Main params |
| --- | --- | --- |
| `video.summary` | `/video/summarize` | `url`, `custom_response`, `custom_prompt`, `cache`, `cache_ttl` |
| `video.transcript` | `/video/transcript` | `url`, `cache`, `cache_ttl` |
| `youtube.summary` | `/youtube/summarize` | `url`, `custom_response`, `custom_prompt`, `cache`, `cache_ttl` |
| `youtube.transcript` | `/youtube/transcript` | `url`, `cache`, `cache_ttl` |
| `youtube.stats` | `/youtube/stats` | `url`, `cache`, `cache_ttl` |
| `youtube.comments` | `/youtube/comments` | `url`, `limit`, `sortBy` (`top` or `new`) |
| `youtube.channel_stats` | `/youtube/channel-stats` | `url`, `cache`, `cache_ttl` |
| `youtube.search` | `/youtube/search` | `query`, `limit` |
| `youtube.videos` | `/youtube/videos` | `url`, `limit`, `cache`, `cache_ttl` |
| `youtube.download` | `/youtube/download` | `url`, `format`, `quality` |
| `tiktok.summary` | `/tiktok/summarize` | `url`, `custom_response`, `custom_prompt`, `cache`, `cache_ttl` |
| `tiktok.transcript` | `/tiktok/transcript` | `url`, `cache`, `cache_ttl` |
| `tiktok.stats` | `/tiktok/stats` | `url`, `cache`, `cache_ttl` |
| `tiktok.comments` | `/tiktok/comments` | `url`, `limit` |
| `tiktok.channel_stats` | `/tiktok/channel-stats` | `url`, `cache`, `cache_ttl` |
| `tiktok.search` | `/tiktok/search` | `query`, `limit`, `cursor`, `sortBy`, `datePosted`, `cache`, `cache_ttl` |
| `tiktok.hashtag_search` | `/tiktok/hashtag-search` | `hashtag`, `limit`, `cursor`, `cache`, `cache_ttl` |
| `instagram.summary` | `/instagram/summarize` | `url`, `custom_response`, `custom_prompt`, `cache`, `cache_ttl` |
| `instagram.transcript` | `/instagram/transcript` | `url`, `cache`, `cache_ttl` |
| `instagram.stats` | `/instagram/stats` | `url`, `cache`, `cache_ttl` |
| `instagram.channel_stats` | `/instagram/channel-stats` | `url`, `cache`, `cache_ttl` |
| `facebook.summary` | `/facebook/summarize` | `url`, `custom_response`, `custom_prompt`, `cache`, `cache_ttl` |
| `facebook.transcript` | `/facebook/transcript` | `url`, `cache`, `cache_ttl` |
| `facebook.stats` | `/facebook/stats` | `url`, `cache`, `cache_ttl` |
| `facebook.channel_stats` | `/facebook/channel-stats` | `url`, `cache`, `cache_ttl` |

Aliases accepted by the Python client:

- `.summarize` maps to `.summary`.
- `channel-stats` maps to `channel_stats`.
- `hashtag-search` maps to `hashtag_search`.

## Endpoint Notes

YouTube comments:

- `limit` default 10, max 100.
- `sortBy`: `top` or `new`; docs default to `new`.
- Credit: 1 credit per 50 results.

YouTube videos:

- Accepts channel URLs and playlist URLs.
- `limit` default 10, max 100.
- Response `type` is `playlist` or `channel`.
- Credit: 1 credit per 50 results.

YouTube download:

- `format` default `mp4`; supported `mp4`, `mp3`, `avi`, `webm`, `m4a`, `ogg`, `wav`.
- `quality` default `360p`; supported `240p`, `360p`, `480p`, `720p`, `1080p`.
- Response contains a temporary `downloadUrl`, usually expiring after 1 hour.
- Docs note maximum file size per download is 10MB.

TikTok search:

- `limit` default 10, max 100.
- `cursor` paginates when response `hasMore` is true.
- `sortBy`: `relevance`, `likes`, `date`.
- `datePosted`: `day`, `week`, `month`, `3months`, `6months`; omitted means all time.
- Credit: 1 credit per 50 results.

TikTok hashtag search:

- `hashtag` is required and should not include `#`.
- `limit` default 10, max 100.
- `cursor` paginates when `hasMore` is true.
- Credit: 1 credit per 50 results.

Errors:

- `400`: malformed request or missing required parameters.
- `401`: access key missing.
- `403`: invalid key, request limit exceeded, or transcript access denied.
- `404`: video not found or transcript unavailable.
- `408`: request timeout, often for long videos.
- `422`: invalid URL/video ID format.
- `429`: rate limit exceeded.
- `500`: server/internal Lambda error.

Error response format usually includes:

```json
{"success": false, "message": "Error description"}
```
