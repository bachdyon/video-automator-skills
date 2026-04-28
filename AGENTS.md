# Project Agent Instructions

This repository keeps reusable project skills in `skills/<skill>/SKILL.md`.
Official third-party agent skills installed by the `skills` CLI live in `.agents/skills/<skill>/SKILL.md`.

When a user request matches a project skill, load only that skill's `SKILL.md` first, then load referenced scripts or supporting files only as needed. Prefer bundled scripts over regenerating equivalent code.

For Claude Code compatibility, `.claude/skills/*` mirrors these project skills with symlinks so Claude can auto-discover them as project skills.

Hard rule: any task that creates, scaffolds, updates, previews, renders, or validates a Remotion project must load and explicitly reference the official `$remotion-best-practices` skill from `.agents/skills/remotion-best-practices` before making Remotion-specific decisions.

At the start of a new video/Remotion project, run `scripts/ensure-remotion-skill.sh` or otherwise verify `.agents/skills/remotion-best-practices/SKILL.md` exists. If it is missing, suggest installing it with `npx skills add remotion-dev/skills --yes`; if the task requires Remotion work now, ask for permission to run that install command, then continue after it succeeds.

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

## Project Skills

- `$asset-semantic-extractor`: Analyze image or video assets and produce a TOML semantic index for video assembly.
- `$audio-deduplicate`: Remove consecutive repeated speech from WAV or MP3 files using Whisper timestamps and export a cleaned audio file.
- `$ausynclab-voice`: Work with AusyncLab voices and generate narration audio; optional pydub `speed-pydub` / `voice_speed_pydub.py` when the user asks to change narration speed after TTS without calling the API again.
- `$fal-image-generator`: Synthesize AI images via fal.ai (default `fal-ai/nano-banana`) from prompts or scene_intents, with optional reference images for character lock; saves into `jobs/<id>/input/raw_assets/images/ai_generated/`.
- `$overlay-subject-placement`: Analyze a frame with non-Gemini vision LLM and recommend safe overlay placement that avoids covering subjects and respects hard 9:16 unsafe padding.
- `$video-downloader`: Download TikTok videos, slideshow images, or audio through TikWM into `raw_assets/` or `jobs/<id>/input/raw_assets/`.
- `$word-timestamps-extractor`: Extract narration transcript with sentence and word timestamps.
- `$remotion-best-practices`: Official Remotion skill installed from `remotion-dev/skills`; use for all Remotion code and project work.
- `$semantic-asset-mapper`: Match transcript or scene intents to indexed image and video assets.
- `$shot-coverage-planner`: Resolve coverage shortage and asset repetition in baseline mappings via cutaway, slowdown, hold + Ken Burns decisions.
- `$video-creative-planner`: Build a production-ready creative plan, script, scene intents, and asset requirements.
- `$video-design-spec-builder`: Build reusable Video Design Specifications from source videos.
- `$video-job-manager`: Create and manage isolated video production jobs and canonical paths.
- `$video-production-orchestrator`: Coordinate the complete short-form video pipeline across all stages.
- `$video-render-plan-builder`: Convert plans, transcripts, assets, and style rules into a TOML render plan.
- `$video-renderer`: Render the final video from a TOML render plan and source assets.
