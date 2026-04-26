# Project Agent Instructions

This repository keeps reusable project skills in `skills/<skill>/SKILL.md`.
Official third-party agent skills installed by the `skills` CLI live in `.agents/skills/<skill>/SKILL.md`.

When a user request matches a project skill, load only that skill's `SKILL.md` first, then load referenced scripts or supporting files only as needed. Prefer bundled scripts over regenerating equivalent code.

For Claude Code compatibility, `.claude/skills/*` mirrors these project skills with symlinks so Claude can auto-discover them as project skills.

Hard rule: any task that creates, scaffolds, updates, previews, renders, or validates a Remotion project must load and explicitly reference the official `$remotion-best-practices` skill from `.agents/skills/remotion-best-practices` before making Remotion-specific decisions.

At the start of a new video/Remotion project, run `scripts/ensure-remotion-skill.sh` or otherwise verify `.agents/skills/remotion-best-practices/SKILL.md` exists. If it is missing, suggest installing it with `npx skills add remotion-dev/skills --yes`; if the task requires Remotion work now, ask for permission to run that install command, then continue after it succeeds.

## Project Skills

- `$asset-semantic-extractor`: Analyze image or video assets and produce a TOML semantic index for video assembly.
- `$audio-deduplicate`: Remove consecutive repeated speech from WAV or MP3 files using Whisper timestamps and export a cleaned audio file.
- `$ausynclab-voice`: Work with AusyncLab voices and generate narration audio.
- `$openai-whisper-word-timestamps`: Transcribe narration audio with sentence and word timestamps.
- `$remotion-best-practices`: Official Remotion skill installed from `remotion-dev/skills`; use for all Remotion code and project work.
- `$semantic-asset-mapper`: Match transcript or scene intents to indexed image and video assets.
- `$video-creative-planner`: Build a production-ready creative plan, script, scene intents, and asset requirements.
- `$video-design-spec-builder`: Build reusable Video Design Specifications from source videos.
- `$video-job-manager`: Create and manage isolated video production jobs and canonical paths.
- `$video-production-orchestrator`: Coordinate the complete short-form video pipeline across all stages.
- `$video-render-plan-builder`: Convert plans, transcripts, assets, and style rules into a TOML render plan.
- `$video-renderer`: Render the final video from a TOML render plan and source assets.
