# Project Agent Instructions

This repository keeps reusable project skills in `skills/<skill>/SKILL.md`.
Official third-party agent skills installed by the `skills` CLI live in `.agents/skills/<skill>/SKILL.md`.

When a user request matches a project skill, load only that skill's `SKILL.md` first, then load referenced scripts or supporting files only as needed. Prefer bundled scripts over regenerating equivalent code.

For Claude Code compatibility, `.claude/skills/*` mirrors these project skills with symlinks so Claude can auto-discover them as project skills.

Hard rule: any task that creates, scaffolds, updates, previews, renders, or validates a Remotion project must load and explicitly reference the official `$remotion-best-practices` skill from `.agents/skills/remotion-best-practices` before making Remotion-specific decisions.

At the start of a new video/Remotion project, run `scripts/ensure-remotion-skill.sh` or otherwise verify `.agents/skills/remotion-best-practices/SKILL.md` exists. If it is missing, suggest installing it with `npx skills add remotion-dev/skills --yes`; if the task requires Remotion work now, ask for permission to run that install command, then continue after it succeeds.

Remotion dependency rule: new `jobs/<job_id>/remotion/node_modules` paths must be symlinks to repo-root `../../../node_modules`. Do not run `npm install` inside individual job folders. If dependencies are missing, run `npm install` once at repo root and reuse that shared install for all future jobs.

## Voice Rule

For Threads Video jobs and short screenshot/commentary videos in this repository, only use `$capcut-tts` with CapCut voice `Cô Gái Hoạt Ngôn` unless the user explicitly asks to change voice.

Required voice settings:

- `speaker_id` / `--voice`: `BV074_streaming`
- `resource_id` / `--resource-id`: `7102355709945188865`

Do not use `$ausynclab-voice`, `$free-tts`, ElevenLabs, OpenAI TTS, or any other voice provider for these jobs when the user says “tạo voice”, “đọc ảnh”, “tạo job Threads video”, or otherwise leaves the voice unspecified.

## Threads Image Text Rule

For Threads Video jobs and short screenshot/commentary videos, every user-provided screenshot must be processed with vision/OCR before TTS. Do not rely only on the visible image in the chat, filenames, or manual paraphrase when creating narration.

Save each screenshot in numeric order and create a Markdown file with the same number:

```text
input/raw_assets/001.png
input/raw_assets/001.md
input/raw_assets/002.png
input/raw_assets/002.md
```

Each Markdown file must use this format:

```markdown
# 001

## Metadata nhìn thấy trong ảnh

...

## Text bóc từ ảnh

...

## Text đã chỉnh lý

...
```

`Text bóc từ ảnh` is the raw OCR/vision extraction. `Text đã chỉnh lý` is the narration-ready version: expand abbreviations and slang so TTS reads correctly, normalize punctuation, and keep the original meaning. Examples: `k`/`ko` -> `không`, `bt` -> `biết`, `sgk` -> `sách giáo khoa`, `ip` -> `iPhone`, `VN` -> `Việt Nam`, `dh` -> `đại học`, `nx` -> `nữa`, `dc` -> `được`, `ph` -> `phải`, `e` -> `em`, `t` -> `tôi` when context requires.

CapCut TTS audio must be generated from `Text đã chỉnh lý`, never from `Text bóc từ ảnh`, unless the user explicitly asks to preserve raw slang pronunciation.

## Template Skill Hard Rule

Hard rule: any task that creates, scaffolds, updates, previews, renders, validates, or reuses a video template under `templates/<template_id>/` must load the matching template skill before making template-specific decisions or editing/rendering files.

The agent must:

1. Read `skills/<matching-skill>/SKILL.md`.
2. Read `templates/<template_id>/template.toml`, especially `[rules]`.
3. Explicitly state which template skill is being used.
4. Follow the template skill workflow instead of copying or modifying template files ad hoc.
5. If no matching skill exists, stop and create or request a matching template skill before using that template.

Template-to-skill mapping:

- `templates/3d-knowledge-sharing/` → `$3d-knowledge-sharing-template`
- `templates/stickman/` → `$stickman-template`
- `templates/personal-brand-mat-overlay/` → `$personal-brand-mat-overlay-template`
- `templates/podcast-karaoke-frame/` → `$podcast-karaoke-frame-template`
- `templates/podcast-square-reveal-caption/` → `$podcast-square-reveal-caption-template`
- `templates/podcast-dong-phuong/` → `$podcast-dong-phuong-template`
- `templates/lao-bach-nien/` → `$lao-bach-nien-template`
- `templates/theanh28/` → `$theanh28-template`
- `templates/outfit-color-pairs/` → `$outfit-color-pairs-template`
- `templates/polo-outfit-breakdown/` → `$polo-outfit-breakdown-template`
- `templates/english-learning-split-subtitles/` → `$english-learning-split-subtitles-template`
- `templates/comment-screens-gameplay/` → `$threads-video-template`
- `templates/threads-xh-meme-commentary/` → `$threads-xh-meme-commentary-template`
- `templates/mindset-product-pitch/` → add/use matching `$mindset-product-pitch-template` before reuse

Forbidden:

- Do not instantiate a template by directly copying `templates/<id>/remotion` unless the matching skill instructs that flow.
- Do not edit template Remotion code before reading both the matching skill and `template.toml`.
- Do not mark template work done without applying its `[rules]` and running the required render/preview checks.

## Pipeline Order Rule: Assets Drive Creative Plan

Hard rule for any video job that has user-provided raw assets (`jobs/<job_id>/input/raw_assets/` is non-empty OR the global `raw_assets/` pool has indexed content):

1. Run `$asset-semantic-extractor` first to produce `source/asset_semantics.toml`. When the asset-index watcher is running this is a fast DB read (no Gemini cost); otherwise it falls back to a fresh probe + vision pass.
2. Then run `$video-creative-planner` with `asset_semantics.toml` (and optionally direct asset-index queries) as primary input so the creative plan, scene intents, and script are grounded in what footage actually exists.
3. Then run `$semantic-asset-mapper` to bind transcript/scene intents to those assets — pass `--use-vector-index` when the pool is large to delegate matching to the SQLite vector DB.

The reverse order (`creative_plan` before `asset_semantics`) is only allowed when the job has no `raw_assets` yet, e.g. a script-first project where assets will be generated/sourced from the plan. Never invent a creative plan that ignores the provided assets — doing so makes the user's footage meaningless and breaks downstream semantic mapping.

When in doubt, inspect `jobs/<job_id>/input/raw_assets/`:
- empty → `creative_plan` first is fine.
- non-empty → `asset_semantics` first, always.

If a `creative_plan.toml` was produced before `asset_semantics.toml` in an asset-driven job, mark it stale via `$video-job-manager` and rebuild it after the asset semantic index exists.

## Asset Index (always-on background watcher)

`tools/asset_index/` watches `raw_assets/` (the workspace-root drop zone) and optionally every `jobs/*/input/raw_assets/` (`--include-jobs` flag) for new or changed media. Each file is dispatched to a per-media-type Gemini analyzer, embedded with OpenAI `text-embedding-3-small`, and stored in `.asset_index/index.db` (SQLite + sqlite-vec via `apsw`).

The index is the **single source of truth** for asset semantics. Every video skill consumes from it instead of re-running Gemini per job:

- `$asset-semantic-extractor` exports DB rows to `source/asset_semantics.toml` via `python -m tools.asset_index.exporter`. Files not yet indexed are auto-indexed on demand. Net effect: each file is sent through Gemini at most once across the whole project lifetime.
- `$semantic-asset-mapper` accepts `--use-vector-index` and queries the DB per scene_intent via `tools.asset_index.exporter.export_for_creative_plan`.
- `$video-creative-planner` calls `tools.asset_index.search.search_assets` to discover available footage before drafting scene_intents.
- `$shot-coverage-planner` queries `search_assets` to find cutaway candidates beyond what the baseline mapper picked.

CLI / Python entry points:

- CLI search: `.venv/bin/python -m tools.asset_index.search "<query>" --top 5 [--media image|video|audio] [--source raw_assets|jobs]`
- CLI export: `.venv/bin/python -m tools.asset_index.exporter <folder> --output <toml>` or `--from-creative-plan <plan.toml> --top-per-intent 5`
- Python: `from tools.asset_index.search import search_assets` and `from tools.asset_index.exporter import export_paths, export_for_creative_plan`

The watcher service is auto-started at login by `tools/asset_index/service.py` (launchd on macOS, Task Scheduler on Windows). Inspect `.asset_index/state.json` for live `pid` / `processed_count` / `last_error`. Non-technical users install everything via `setup/Install.command` or `setup/Install.bat` — see top-level `README.md`.

This index is content-addressed (SHA-256), so re-running it on the same files is a no-op. Re-index a single file deterministically with: `.venv/bin/python -m tools.asset_index.router <path> --force`. Use this when the watcher captured a bad analysis (e.g. duplicate scene descriptions) and you need to refresh just that file before re-exporting.

## Zernio MCP

Zernio exposes a hosted MCP server at `https://mcp.zernio.com/mcp` for social publishing, account management, media upload flows, inbox/DM automation, ads, broadcasts, sequences, analytics, webhooks, and other Zernio API actions.

When the user asks to publish, schedule, cross-post, inspect connected accounts, manage inbox messages, or otherwise operate Zernio directly, prefer the Zernio MCP tools over ad hoc HTTP calls. The MCP server is configured in Codex via:

```toml
[mcp_servers.zernio]
url = "https://mcp.zernio.com/mcp"
bearer_token_env_var = "ZERNIO_API_KEY"
```

Authentication can use OAuth in clients that support hosted connectors, or an `Authorization: Bearer <ZERNIO_API_KEY>` header. If tools are unavailable or Zernio returns `Missing API key` / `Invalid API key`, check that `ZERNIO_API_KEY` is set in the active process or repo `.env`, then restart/reload the AI client if MCP configuration changed.

Core MCP tools documented by Zernio include:

- `accounts_list`: list connected social accounts and account IDs before posting, especially when multiple accounts exist on the same platform.
- `posts_create`: create a draft, scheduled post, or immediate post. For scheduling, use `schedule_minutes` when scheduling relative to now; use account/profile IDs when needed to disambiguate.
- `posts_publish_now`: publish immediately.
- `posts_cross_post`: publish or schedule the same content across multiple platforms.
- `posts_create_post`: use the full generated post API when per-platform customization, per-target `scheduledFor`, or platform-specific data is needed.
- `media_generate_upload_link` and `media_check_upload_status`: browser upload flow for large local media files supported by Zernio.
- Inbox tools such as `send_inbox_message` / `messages_send_inbox_message`: send messages with media URLs when available.

For local media that must be attached to Zernio posts or messages, prefer the MCP-native media flow with `media_generate_upload_link` and `media_check_upload_status`, then pass the resulting media URL or ID to post/message tools as appropriate.

Reference: `https://docs.zernio.com/mcp`.

## Project Skills

- `$3d-knowledge-sharing-template`: Instantiate the 3D Knowledge Sharing Template for vertical Vietnamese educational explainers with soft 3D isometric illustrations, Bricolage title highlights, max-4-word subtitles, and subtle bottom credit.
- `$add-job-to-showcases`: Publish a finished job to `showcases/<job_id>/` for public demos by copying only `jobs/<job_id>/output/`, verifying no other top-level artifacts remain, and updating showcase docs.
- `$asset-semantic-extractor`: Analyze image or video assets and produce a TOML semantic index for video assembly.
- `$audio-deduplicate`: Remove consecutive repeated speech from WAV or MP3 files using Whisper timestamps and export a cleaned audio file.
- `$animated-svg`: Create standalone animated HTML from local SVG artwork, preserving original style, grouping paths semantically, choosing motion that matches the drawing content, and verifying browser render output with no external assets.
- `$ausynclab-voice`: Work with AusyncLab voices and generate narration audio; optional pydub `speed-pydub` / `voice_speed_pydub.py` when the user asks to change narration speed after TTS without calling the API again.
- `$threads-video-template`: Instantiate the reusable Threads Video template: ordered Threads/comment screenshots centered over a looping muted gameplay background, one narration audio per screenshot, hard cuts at audio boundaries.
- `$threads-xh-meme-commentary-template`: Instantiate the Threads XH meme commentary template for Vietnamese article-led Threads videos with screenshot evidence, cartoon meme reactions, green Threads XH branding, and narration written by article logic instead of image order.
- `$create-edit-image-gpt-image-2`: Create or edit images with KIE.AI GPT Image 2 from text prompts and optional reference images; supports task polling and downloading generated result URLs.
- `$create-video-seedance-2-0`: Create videos with KIE.AI Bytedance Seedance 2.0 Fast from text, first/last frames, or multimodal references; supports task polling and downloading generated result URLs.
- `$fal-image-generator`: Synthesize AI images via fal.ai (default `fal-ai/nano-banana`) from prompts or scene_intents, with optional reference images for character lock; saves into `jobs/<id>/input/raw_assets/images/ai_generated/`.
- `$filepost-file-upload`: Upload local files to FilePost permanent CDN URLs and list, get, or delete uploaded FilePost files via the bundled API client.
- `$free-tts`: Generate free/local Vietnamese narration with VieNeu-TTS when `.env` has no `AUSYNCLAB_API_KEY`, or when the user explicitly asks for free/local/VieNeu TTS.
- `$capcut-tts`: Use the CapCut common task client (`capcut_common_task_client.py`) for explicit CapCut TTS task creation/querying, audio/video upload, or CapCut STT/subtitle recognition; this is a non-official reverse-engineered flow and is not the default narration provider.
- `$heygen-asset-upload`: Upload images, videos, audio, or PDFs to HeyGen and return reusable asset IDs.
- `$heygen-photo-avatar-video`: Create HeyGen image-to-video/photo-avatar talking-head videos from a person's image plus custom audio; use for video nhân hiệu.
- `$job-to-template`: Convert a finished Remotion video job into a reusable template directory and matching project skill, with portability audit and render validation.
- `$klipy-meme-search`: Search and download Klipy GIFs, stickers, clips, and memes as reaction assets for Threads videos, editorial recap videos, and short-form commentary.
- `$knowledge-share-video-content`: Viết hoặc cập nhật `video_content.md` cho video chia sẻ kiến thức, gồm voiceover kể chuyện, câu mở đầu kéo người xem vào vai chính, luận điểm có câu hỏi phụ, và gợi ý visual AI không chữ.
- `$png-to-svg-convertio`: Convert local PNG images to SVG files through Convertio API when an SVG asset is required.
- `$personal-brand-mat-overlay-template`: Personal brand vertical — person vs trám beats, punch + infographic mat overlay; **must follow** `templates/personal-brand-mat-overlay/template.toml` `[rules]`.
- `$overlay-subject-placement`: Analyze a frame with non-Gemini vision LLM and recommend safe overlay placement that avoids covering subjects and respects hard 9:16 unsafe padding.
- `$outfit-color-pairs-template`: Instantiate the Outfit Color Pairs template for vertical fashion shorts with a warning outfit scene, color-pair recommendation scenes, Google Sans pill captions, swatches, TTS per scene, and background music.
- `$polo-outfit-breakdown-template`: Instantiate the Polo Outfit Breakdown template from raw men's outfit images by using image_gen to create standardized full-body model cutouts and folded-clothing flat-lay ingredient images, then render a vertical Remotion video with CapCut narration.
- `$english-learning-split-subtitles-template`: Instantiate the English Learning Split Subtitles template for vertical English listening videos with a 35% top illustration video, 65% pink-beige plaid rolling bilingual subtitles, active-word yellow highlights, and a drifting brand watermark.
- `$overlay-video-preparer`: Prepare effect/overlay videos for compositing by checking real alpha, converting black-background stock overlays to H.264 MP4 assets for screen blending, preserving source fps and particle/petal color, and producing Remotion `OffthreadVideo` snippets.
- `$podcast-karaoke-frame-template`: Instantiate the Podcast Karaoke Rounded Frame render-style template for jobs that already have a render plan, word-level transcript, and visual timeline; semantic mapping stays upstream and job-specific.
- `$podcast-square-reveal-caption-template`: Instantiate the Podcast Square Reveal Caption render-style template for jobs that already have a render plan, word-level transcript, and visual timeline; renders 1:1 centered footage with Yomogi word-reveal captions, 4-5 words per line and max 4 lines.
- `$podcast-dong-phuong-template`: Instantiate the Podcast Đông Phương full-width podcast render-style template for jobs that already have a render plan, word-level transcript, and visual timeline.
- `$lao-bach-nien-template`: Instantiate the Lão Bách Niên vertical Vietnamese storytelling podcast template with Imagen-generated still-life background, approved voiceover script, forceful highlighted title, audio-reactive waveform, and sentence subtitles.
- `$socialkit-api`: Manage SocialKit APIs through the bundled Python client for transcripts, summaries, stats, comments, search, channel stats, video listing, and YouTube downloads; do not call SocialKit with curl.
- `$telegram-send`: Send Telegram bot messages, videos, photos, and documents through the official Bot API using `TELEGRAM_BOT_TOKEN` and optional `TELEGRAM_CHAT_ID` from channel-specific env files such as `.env.threads`.
- `$video-downloader`: Download TikTok videos, slideshow images, or audio through TikWM into `raw_assets/` or `jobs/<id>/input/raw_assets/`.
- `$youtube-fast-download`: Download public YouTube videos or Shorts quickly with yt-dlp, save MP4 video, and optionally export MP3 audio.
- `$video-audio-extractor`: Extract an audio track from video to WAV/MP3 for transcript, dedupe, or background-music reuse.
- `$word-timestamps-extractor`: Extract narration transcript with sentence and word timestamps.
- `$remotion-best-practices`: Official Remotion skill installed from `remotion-dev/skills`; use for all Remotion code and project work.
- `$semantic-asset-mapper`: Match transcript or scene intents to indexed image and video assets.
- `$shot-coverage-planner`: Resolve coverage shortage and asset repetition in baseline mappings via cutaway, slowdown, hold + Ken Burns decisions.
- `$stickman-template`: Instantiate the Stickman Template for vertical Remotion explainer videos with centered stickman highlights, black terminal-grid background, bold titles, subtitles, and optional process/chart cards.
- `$subtitle-screen-splitter`: Split subtitle text or word-level transcripts into screen-sized pages, breaking after punctuation and before capitalized sentence starts.
- `$subtitle-punch-tag-shortform`: Short-form captions with word-synced normal + PUNCH lines (~7–8 word chunks, semantic punch selection, no dropped words, no mid-token line breaks, two-layer punch text for shadow vs clean fill); see `skills/subtitle-punch-tag-shortform/SKILL.md`.
- `$theanh28-template`: Instantiate the reusable Theanh28-style Remotion template from a source clip, intro voice, headline, and credit.
- `$typography-style-selector`: Choose distinctive fonts, pairings, scale, and weight contrast for visual work; state the typography choice before coding or rendering.
- `$video-visual-aesthetics`: Direct distinctive frame composition, motion, background, safe area, and anti-template visual choices for videos rendered from HTML/CSS/JS or Remotion; use `$typography-style-selector` first for text-heavy scenes and `$remotion-best-practices` first for Remotion-specific work.
- `$video-compress-under-25mb`: Compress local videos under 25MB with H.264/AAC 2-pass encoding, preserving resolution/fps when possible, for upload limits such as Zernio upload-direct.
- `$video-creative-planner`: Build a production-ready creative plan, script, scene intents, and asset requirements.
- `$video-design-spec-builder`: Build reusable Video Design Specifications from source videos.
- `$video-job-manager`: Create and manage isolated video production jobs and canonical paths.
- `$video-production-orchestrator`: Coordinate the complete short-form video pipeline across all stages.
- `$video-render-plan-builder`: Convert plans, transcripts, assets, and style rules into a TOML render plan.
- `$video-renderer`: Render the final video from a TOML render plan and source assets.
- `$video-quality-auditor`: Audit Remotion source/render plans for overlay readability and safe-area issues, then produce TOML/HTML reports and optional batch fixes.
