---
name: job-to-template
description: Convert a finished video job into a reusable project template and Codex skill. Use when the user asks to turn a Remotion job into a template, standardize a copied job, create a reusable video template skill, parameterize a job, or make future video requests token-light while preserving visual quality and render reliability.
---

# Job To Template

Use this skill to turn one successful job into:

- `templates/<template_id>/` containing the reusable Remotion shell and template contract.
- `skills/<template_id>-template/` containing the user-facing workflow and instantiate script.
- A verified sample job that proves the template still renders.

For any Remotion-specific work, first load `.agents/skills/remotion-best-practices/SKILL.md` and run:

```bash
scripts/ensure-remotion-skill.sh
```

## Ràng buộc beat trám (thi hành)

Mẫu đầy đủ ghi trong `templates/personal-brand-mat-overlay/template.toml` — mục **`[rules]`**, các khóa **`bat_buoc_*`**. Skill đi kèm: **`personal-brand-mat-overlay-template`**. Khi tạo thêm template có trám, nhúng cùng kiểu `[rules]` vào `template.toml` và nhắc trong skill sinh ra.

## Workflow

1. Inspect the source job.
   - Read `source/creative_plan.toml`, `source/render_plan.toml`, `remotion/src`, `remotion/public`, and the latest `output/final_video.mp4`.
   - Identify what is template DNA versus per-job input. Template DNA includes layout, typography, transitions, timing rules, and asset placement logic. Per-job input includes source clips, voice, music, headline, logo, colors, dates, credits, and duration.

2. Create `templates/<template_id>/`.
   - Copy only the Remotion project files needed to render.
   - Exclude `node_modules`, `.git`, `output`, `logs`, generated stills, large job-only assets, and downloaded source media.
   - Under `remotion/`, **never** leave `node_modules`, `build`, `out`, `output`, `.remotion`, or `dist` in the template tree—add `remotion/.gitignore` for those names and delete them after local `npm install` / render checks.
   - Add `template.toml` with stable defaults, render dimensions, composition id, style tokens, input contract, and rules.
   - Add `reference/vds.md` only when the visual design needs more detail than `template.toml`.

3. Parameterize the Remotion composition.
   - Move all job-specific values into `remotion/public/template-props.json`.
   - Import default props from that JSON in `Root.tsx`.
   - Keep source paths relative to Remotion `public`, usually `assets/<name>`.
   - Avoid absolute paths, `jobs/<job_id>` strings, hardcoded titles, hardcoded credits, and hardcoded logo files.
   - Use robust defaults for optional inputs so a missing logo or music file does not crash the composition.

4. Create `skills/<template_id>-template/`.
   - Write a compact `SKILL.md` with required inputs, optional style knobs, instantiate command, render command, and validation expectations.
   - Add `scripts/instantiate.py` when the template needs deterministic setup. It should copy inputs into canonical job paths, write `template-props.json`, and emit `source/template_params.toml`, `source/creative_plan.toml`, and `source/render_plan.toml`.
   - Keep backward-compatible aliases for knobs likely to change, such as music volume or font scale.

5. Validate before saying it works.
   - Run this skill's audit script.
   - Run `python3 -m py_compile` for template scripts.
   - Run `quick_validate.py` for the new skill.
   - Render a Remotion still.
   - Render a final video from a fresh or updated sample job.
   - Verify final media with `ffprobe`.

## Commands

Audit the template and generated skill:

```bash
python3 skills/job-to-template/scripts/audit_template.py \
  --template-id <template_id> \
  --template-skill <template_id>-template
```

Validate the generated skill:

```bash
python3 <path-to-skill-creator>/scripts/quick_validate.py \
  skills/<template_id>-template
```

Run a one-frame Remotion check from the sample job:

```bash
./node_modules/.bin/remotion still src/index.ts <CompositionId> ../output/preview_intro_frame.jpg --frame=30 --scale=0.25
```

Render from the sample job:

```bash
npm run render
```

Verify final media:

```bash
ffprobe -v error -show_entries format=duration,size -show_entries stream=codec_name,codec_type,width,height,avg_frame_rate -of json jobs/<job_id>/output/final_video.mp4
```

## Quality Gates

Before final response, confirm:

- **Trám:** nếu template có beat trám, `template.toml` có `[rules]` tương đương mẫu `personal-brand-mat-overlay` (không để trống các ràng buộc hai kiểu timing, meme, render xác nhận).

- A future user can instantiate the template by passing only source assets and style parameters.
- The template has no copied `node_modules`, output videos, logs, or job-only downloaded media; **`templates/<id>/remotion/` must not contain `node_modules`, `build`, `out`, `output`, or `.remotion`** (see `audit_template.py` and `.cursor/rules/templates-no-generated.mdc`).
- No Remotion source file contains absolute local paths or `jobs/<job_id>` references.
- `template-props.json` contains only portable relative public paths.
- A representative render succeeds and has expected dimensions, duration, video stream, and audio stream when audio is expected.
- `AGENTS.md` lists the new project skill, and `.claude/skills/<skill>` mirrors it when this repo uses Claude compatibility symlinks.

Load `references/template-contract.md` when deciding what belongs in `template.toml` or the instantiate script.
