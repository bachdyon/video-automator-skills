# asset_index

Watch a folder, run semantic analysis on every new image/video/audio, and store the result in a single SQLite + sqlite-vec database for semantic search.

This README is a stub; the user-facing README at the workspace root explains the 3-step double-click workflow. See `Bước 11` in the implementation plan for full content.

## Overview

- Default watch path: `raw_assets/` at workspace root.
- Optional: `--include-jobs` to also watch every `jobs/*/input/raw_assets/`.
- Per-media analyzers:
  - image -> Gemini Vision (single frame metadata)
  - video -> reuses `skills/asset_semantic_extractor/scripts/probe_assets.py` + `analyze_with_gemini.py`
  - audio -> Whisper transcript + Gemini classification (voice_over / background_music / sound_effect)
- Embeddings: OpenAI `text-embedding-3-small` (1536 dims).
- Storage: `.asset_index/index.db` (SQLite with `sqlite-vec` virtual table).

## Module entry points

```bash
python -m tools.asset_index.watcher --scan-on-start
python -m tools.asset_index.search "query in Vietnamese or English"
python -m tools.asset_index.service install
python -m tools.asset_index.bootstrap install
```

For full beginner instructions, double-click the `Install.command` (macOS) or `Install.bat` (Windows) wrapper at the workspace root.
