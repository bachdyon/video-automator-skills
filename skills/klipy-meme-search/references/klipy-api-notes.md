# Klipy API Notes

Source: `https://docs.klipy.com/llms.txt`, fetched 2026-07-01.

## Confirmed Domains

- `api.klipy.com`: API endpoint.
- `static.klipy.com`, `static1.klipy.com`, `static2.klipy.com`: media delivery.
- All are HTTPS on port 443.

## Verified Endpoint

Probe without a key confirmed this endpoint exists and returns an API-key error:

```text
https://api.klipy.com/v2/search
```

Klipy docs describe migration from Tenor as replacing `tenor.googleapis.com` with `api.klipy.com` and plugging in the Klipy API key. For the Tenor-compatible Search API:

- `key`: API key.
- `q`: query string.
- `limit`: result count.
- `pos`: pagination cursor from the previous response `next`.
- `locale`: locale such as `en_US` or `vi_VN`.
- `contentfilter`: MPA-style content filter. Keep `high` for brand-safe meme search.
- `media_filter`: comma-separated format list to reduce response size.
- `searchfilter=sticker`: retrieve stickers instead of GIFs.
- `random=true`: randomize result ordering.

## Product Endpoint Probe

Probe suggests product endpoints may be shaped like:

```text
https://api.klipy.com/api/v1/{api_key}/{product}/search
```

where `{product}` may include `gifs`, `stickers`, or `clips`. This is not the default because `/v2/search` is the verified stable route from the public migration docs.

## Response Fields

Tenor-compatible result objects may include:

- `id`
- `title`
- `content_description`
- `tags`
- `itemurl`
- `url`
- `media_formats`
- `hasaudio`
- `hascaption`
- `flags`
- `bg_color`

Each `media_formats` entry has:

- `url`
- `dims`
- `duration`
- `size`

## Useful Formats

For video editing, prefer:

- GIF/reaction: `mp4`, `tinymp4`, `nanomp4`, `webm`, `tinywebm`, `preview`.
- Sticker/transparent overlay: `webp_transparent`, `tinywebp_transparent`, `gif_transparent`, `tinygif_transparent`.

Klipy docs recommend `media_filter` because it can reduce response size significantly.
