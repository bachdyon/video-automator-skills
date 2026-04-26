---
name: video-creative-planner
description: Turn a new video request plus an optional Video Design Specification into a production-ready creative plan, script, scene intents, overlay text, and asset requirements for a short-form video pipeline.
---

# Video Creative Planner

## Goal

Convert a user's new video idea into a structured creative plan that downstream voice, asset mapping, and rendering skills can execute.

Use this skill when the user provides a topic, brief, product idea, campaign request, or rough script and wants a new TikTok/Reels/Shorts-style video built from it.

## Script Environment Rule

Before running any script as part of this skill, read the repo-root `.env` first. This file lives beside `jobs/`, `skills/`, and `env.example`. Check only whether required keys exist; never print secret values in logs, terminal output, TOML artifacts, or responses. Use a non-root `--env-file` only when the user explicitly provides one.

## Inputs

- User request or creative brief.
- Optional VDS from `video-design-spec-builder`.
- Optional target platform, duration, language, brand constraints, CTA, and available asset notes.

## Output

Write or return TOML. Default path:

```text
source/creative_plan.toml
```

When a video job exists, write to:

```text
jobs/<job_id>/source/creative_plan.toml
```

## Workflow

1. Identify target audience, platform, duration, language, and emotional arc.
2. If a VDS is provided, preserve its style DNA, timing logic, text system, motion system, and scene blueprint.
3. Build a voiceover script that can be spoken naturally.
4. Split the script into scene intents, not final asset choices.
5. Define overlay text, subtitle behavior, and CTA.
6. Define asset requirements so `asset-semantic-extractor` and `semantic-asset-mapper` know what to look for.
7. Keep identifiers, personal data, and private details abstract unless the user explicitly owns and requests them.

## TOML Contract

```toml
[metadata]
title = "Short descriptive title"
language = "vi"
platform = "tiktok"
target_duration_seconds = 45
aspect_ratio = "9:16"
source_vds = "path/to/vds.md"

[creative]
audience = "..."
goal = "..."
emotional_arc = ["hook", "tension", "turn", "resolution"]
tone = "reflective"
cta = "..."

[voiceover]
script = """
Full spoken script.
"""
delivery = "warm, clear, lightly cinematic"

[[scene_intents]]
id = "SC_01"
start_hint = 0.0
end_hint = 6.0
narrative_role = "hook"
spoken_text = "Sentence or paragraph expected in this scene."
visual_intent = "What the viewer should see, without choosing a specific file."
mood = "..."
preferred_shot_types = ["close-up", "slow push-in"]
asset_requirements = ["..."]

[[text_overlays]]
id = "TXT_01"
scene_id = "SC_01"
text = "Short on-screen text"
role = "hook"
timing = "sync_with_scene_start"
style_ref = "MAIN_TITLE"
```

## Quality Rules

- The script must be speakable; avoid long nested clauses.
- Scene intents should be semantic and reusable, not bound to file paths.
- Do not invent asset availability. Put missing visuals into `asset_requirements`.
- If VDS conflicts with user request, preserve the user's intent and adapt VDS style conservatively.
- For full video production, read and update paths through `video-job-manager` instead of shared `source/`.
