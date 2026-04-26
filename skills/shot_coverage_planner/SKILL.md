---
name: shot-coverage-planner
description: Resolve coverage shortages and asset repetition in a baseline semantic mapping by making creative editor-style decisions (cutaway B-roll layering, hold + Ken Burns, slowdown). Designed for the AI agent (no internal LLM call) — the agent reads context, applies the decision framework, and writes a decisions JSON that a small helper script applies to the TOML.
---

# Shot Coverage Planner

## Script Environment Rule

Before running any bundled script, read the repo-root `.env` first. This file lives beside `jobs/`, `skills/`, and `env.example`. Check only whether required keys exist; never print secret values. This skill does NOT call any LLM API — all creative decisions are made by the agent itself.

## Goal

Take a baseline `semantic_mapping.toml` (1-1 scene → asset, produced by `semantic-asset-mapper` with `--no-cutaway`) plus the full creative context, and produce a **revised** `semantic_mapping.toml` where every scene either:

- Has source coverage ≥ timeline duration (no looping, no freezing), or
- Is intentionally subdivided into multiple sub-clips (cutaway / B-roll layering), or
- Uses a deliberately approved alternative (slowdown, hold-end-frame on still + Ken Burns) when subdivision would hurt the narrative.

**Critical:** the agent — not a Python heuristic — picks the strategy and the assets. The bundled scripts only do mechanical I/O and validation.

## When to invoke

After `semantic-asset-mapper` (run with `--no-cutaway`) and before `video-render-plan-builder`. Always invoke if any baseline mapping has source duration shorter than its timeline duration, or any asset_id has been used more than `--repetition-threshold` times across the timeline (default 3).

## Inputs (required for the agent to reason about)

| Path | What it tells the agent |
| --- | --- |
| `source/creative_plan.toml` | WHY each scene exists: `narrative_role`, `visual_intent`, `mood`, `preferred_shot_types`, `asset_requirements` |
| `source/transcript_word_level.toml` | WHEN each scene plays: sentence/word timestamps to anchor cutaway boundaries to natural speech beats |
| `source/asset_semantics.toml` | WHAT footage exists: every `asset_scenes[]` row has `description, subjects, actions, environment, shot_type, camera_motion, composition, colors, mood, semantic_tags, recommended_uses, avoid_uses, start, end` |
| `source/semantic_mapping.toml` (baseline) | CURRENT 1-1 mapping with `start, end, source_start, source_end, fit_score, fit_labels, fallback` |
| `source/vds.md` (optional) | STYLE constraints: pacing, tone, do/don't |

## Workflow

### Step 1 — Detect gaps (mechanical)

Run the helper to produce a `coverage_context.json` summarising every scene that needs a creative decision:

```bash
python skills/shot_coverage_planner/scripts/detect_gaps.py \
  --mapping jobs/<job_id>/source/semantic_mapping.toml \
  --asset-semantics jobs/<job_id>/source/asset_semantics.toml \
  --creative-plan jobs/<job_id>/source/creative_plan.toml \
  --transcript jobs/<job_id>/source/transcript_word_level.toml \
  --output jobs/<job_id>/source/coverage_context.json \
  --shortage-threshold 0.5 \
  --repetition-threshold 3
```

The JSON has two top-level keys:

- `gaps[]` — one entry per scene whose baseline mapping has `timeline_duration - source_duration > shortage_threshold` OR whose primary asset_id is over-used. Each entry includes the scene intent, the existing primary clip metadata, and ranked candidate `asset_scenes[]` annotated with `available_duration`, `times_used_in_baseline`, `recommended_uses`, `mood`, `colors`, `shot_type`, etc.
- `usage_stats` — repetition counts per `asset_id` and `asset_scene_id` from the baseline.

The script does not pick anything; it gives the agent a curated context pack so the agent does not have to re-read every file.

### Step 2 — Agent decides (CREATIVE — this is the whole point of the skill)

Open `coverage_context.json` and, for each gap, follow the **Decision Framework** below. Write `coverage_decisions.json` next to the context file with this shape:

```json
{
  "decisions": [
    {
      "scene_id": "SC_02",
      "strategy": "cutaway_subdivision",
      "rationale": "Primary clip is 4s but scene is 12s. Voice-over describes contrast between office and field; cutting between selfie talking-head and B-roll of women digging earth visually argues the contrast.",
      "sub_clips": [
        {
          "asset_scene_id": "AST_006_SC_01",
          "role": "primary",
          "timeline_start": 9.58,
          "timeline_end": 13.60,
          "source_start": 0.0,
          "source_end": 4.02,
          "reason": "Establishing the narrator on-camera tying mouth movement to the opening sentence."
        },
        {
          "asset_scene_id": "AST_005_SC_02",
          "role": "cutaway_1",
          "timeline_start": 13.60,
          "timeline_end": 17.60,
          "source_start": 8.0,
          "source_end": 12.0,
          "reason": "Cuts to bare feet swinging a hoe — visceral contrast with office-worker stereotype."
        }
      ]
    },
    {
      "scene_id": "SC_07",
      "strategy": "slowdown",
      "rationale": "Single-take shot of an emotional pause; cutting away would break the moment. Slow to 0.85x for breathing room.",
      "sub_clips": [
        {
          "asset_scene_id": "AST_001_SC_02",
          "role": "primary",
          "timeline_start": 72.02,
          "timeline_end": 79.90,
          "source_start": 0.0,
          "source_end": 6.7,
          "playback_rate": 0.85,
          "reason": "Hold the moment; slight slowdown extends 6.7s of source to 7.88s of timeline."
        }
      ]
    }
  ]
}
```

`strategy` MUST be one of: `cutaway_subdivision`, `slowdown`, `hold_and_kenburns`, `keep` (no change — gap is acceptable as-is).

### Step 3 — Apply patch (mechanical)

```bash
python skills/shot_coverage_planner/scripts/apply_patch.py \
  --mapping jobs/<job_id>/source/semantic_mapping.toml \
  --decisions jobs/<job_id>/source/coverage_decisions.json \
  --asset-semantics jobs/<job_id>/source/asset_semantics.toml \
  --output jobs/<job_id>/source/semantic_mapping.toml
```

The script:

1. Replaces every `[[mappings]]` row whose `scene_id` appears in a decision with the agent's sub-clips (renumbered, with `coverage_strategy`, `playback_rate`, `subdivision_role`, `subdivision_index`, `subdivision_total`, `gap_seconds` filled in).
2. Validates: timeline continuity (no gap, no overlap), `source_end <= asset_scene.end + asset.duration_seconds` clamp, file existence, sub-clip min duration ≥ 0.6s.
3. Refuses to write if any decision references a non-existent `asset_scene_id` or pushes `source_end` past the physical asset duration.

If the script reports errors, edit `coverage_decisions.json` and re-run — never edit the TOML by hand.

## Decision Framework (the creative core)

### A. Pick the strategy

Apply the **first matching rule** for each scene, using the gap size and narrative intent.

| Gap (`timeline_duration - source_duration`) | Default strategy | Override conditions |
| --- | --- | --- |
| ≤ 0.5s | `keep` (acceptable margin; clip will play short, render plan can hold last frame for ≤ 0.5s without artifact) | Never override |
| 0.5–1.5s | `slowdown` at 0.85–1.0x | Use `cutaway_subdivision` if scene is energetic / cut-driven (multiple subjects, pacing tags `fast`/`punchy`) |
| 1.5–4s | `cutaway_subdivision` (primary + 1 cutaway) | Use `slowdown` (≥0.7x) ONLY if the primary footage is single-take emotional/intimate (`mood` tags include `intimate`, `binh-yen`, `tinh-lang`) and cutting would break the moment. Use `hold_and_kenburns` if asset is a still image. |
| > 4s | `cutaway_subdivision` (primary + 2–4 cutaways) | Almost never override; very long held shots feel broken on social/short-form |

Slowdown lower bound: **0.65x** (anything slower looks artificial). If the math demands < 0.65x, switch to `cutaway_subdivision`.

### B. Pick assets for `cutaway_subdivision`

For each cutaway, score every candidate `asset_scene` against the parent scene intent and pick the best, applying these creative rules in order:

1. **Semantic relevance first.** The cutaway must visually advance, support, or contrast the spoken word in this scene. Reject candidates whose `description` is unrelated to the scene `visual_intent`.
2. **Diversity over repetition.** Never put two consecutive sub-clips from the same `asset_id`. If the candidate's `asset_id` matches the previous sub-clip's, demote it unless no alternative passes rule 1.
3. **Continuity OR contrast — pick on purpose.** Either match `mood`/`colors`/`shot_type` to the primary (continuity) for a smooth feel, or deliberately mismatch (contrast cut) when the script argues two ideas. Write which one you chose in `reason`.
4. **Honour `recommended_uses` / `avoid_uses`.** Prefer assets whose `recommended_uses` includes `b_roll`, `cutaway`, `insert`. Skip any whose `avoid_uses` blocks the role you're assigning (e.g. avoid `high-energy-cut` assets in a meditative scene).
5. **Watch over-use.** If `usage_stats.asset_id_counts[X] >= repetition_threshold`, only pick X again when it's irreplaceable.
6. **Keep min sub-clip ≥ 0.8s.** Aim 1.5–3s per cutaway for short-form; never below 0.8s (looks like a flicker on TikTok).

For each sub-clip, set `source_start` / `source_end` to the segment of the asset_scene that best matches the cutaway's intent (you can take a 2s slice from the middle of an 8s asset_scene — pick the most expressive moment).

### C. Pick parameters for `slowdown`

- `playback_rate = source_duration / timeline_duration`, clamped to `[0.65, 1.0]`.
- Source span: full asset_scene window (`source_start = scene.start`, `source_end = scene.end`).

### D. Pick parameters for `hold_and_kenburns` (still images only)

- `source_start = 0.0`, `source_end = 0.0` (or any 0-length placeholder — render plan handles still images).
- Note in `reason` the Ken Burns direction (`zoom_in_center`, `pan_left_to_right`, etc.) so render plan can pick it up.

### E. Repetition fix

If a baseline mapping passes the shortage check but is in `usage_stats.over_used_asset_ids`, replace it with a different asset only when a strictly-better-fit candidate exists; otherwise keep it but log `reason: "over-used but irreplaceable for this intent"`.

## Required Decision JSON Contract

Every decision row MUST include:

- `scene_id` (matches an existing `[[mappings]].scene_id` from baseline)
- `strategy` ∈ `{cutaway_subdivision, slowdown, hold_and_kenburns, keep}`
- `rationale` (1–3 sentences explaining the editorial choice — this is read by humans reviewing the cut)
- `sub_clips[]` (≥ 1 entry; `keep` may have exactly 1 entry mirroring the baseline)

Every sub-clip MUST include:

- `asset_scene_id` (must exist in `asset_semantics.toml`)
- `role` ∈ `{primary, cutaway_1, cutaway_2, …}` for `cutaway_subdivision`; `primary` otherwise
- `timeline_start`, `timeline_end` (continuous, no gap, no overlap inside the parent scene)
- `source_start`, `source_end` (within the asset_scene's `[start, end]` and clamped by asset duration)
- `playback_rate` (only for `slowdown`; default 1.0 elsewhere)
- `reason` (1 sentence — what this clip does for the viewer)

## Example Patches

### Cutaway subdivision (gap 4s split into 3 sub-clips)

Baseline:

```toml
[[mappings]]
scene_id = "SC_05"
asset_scene_id = "AST_005_SC_11"
start = 37.68
end = 51.34
source_start = 0.0
source_end = 4.55
```

After agent decision (3 sub-clips, mixed assets, contrast cuts):

```toml
[[mappings]]
scene_id = "SC_05"
subdivision_role = "primary"
subdivision_index = 1
subdivision_total = 3
asset_scene_id = "AST_005_SC_11"
start = 37.68
end = 42.23
source_start = 0.0
source_end = 4.55
coverage_strategy = "cutaway_subdivision"

[[mappings]]
scene_id = "SC_05"
subdivision_role = "cutaway_1"
subdivision_index = 2
subdivision_total = 3
asset_scene_id = "AST_006_SC_01"
start = 42.23
end = 46.79
source_start = 1.5
source_end = 6.0
coverage_strategy = "cutaway_subdivision"
```

### Slowdown (gap 1.2s, intimate moment kept whole)

```toml
[[mappings]]
scene_id = "SC_07"
subdivision_role = "primary"
subdivision_index = 1
subdivision_total = 1
asset_scene_id = "AST_001_SC_02"
start = 72.02
end = 79.90
source_start = 0.0
source_end = 6.70
coverage_strategy = "slowdown"
playback_rate = 0.8503
```

## Quality Rules

- Total replaced timeline span MUST equal the original baseline scene span exactly (no drift).
- Sub-clip continuity inside one scene must be hole-free (timeline_end of clip N == timeline_start of clip N+1).
- Never reference a missing file or an asset_scene_id that does not exist.
- `playback_rate` ∈ [0.65, 1.5]; outside this range the renderer will warn.
- `reason` and `rationale` should explain editorial intent in human language; do NOT just paste asset descriptions.
- The agent MUST process every gap reported by `detect_gaps.py`. Use `strategy: "keep"` to explicitly accept a gap rather than skipping silently.
