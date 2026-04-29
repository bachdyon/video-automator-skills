# Template Contract Reference

Keep the contract small and explicit. A good template contract lets a future agent use the template without reading the original job.

## `templates/<template_id>/template.toml`

Recommended sections:

- `[template]`: `id`, `name`, `version`, `description`, optional `reference_vds_path`.
- `[remotion]`: `composition_id`, `fps`, `width`, `height`, `background`, `template_project_path`, `props_path`.
- `[defaults]`: only values that may change per job, such as brand text, colors, font scale, music volume, source trim, and intro duration.
- `[style]`: stable design tokens and behavioral style, such as title style, transition style, object positions, panel colors, safe widths.
- `[rules]`: constraints the instantiate script or future agents must preserve.

## `remotion/public/template-props.json`

Use camelCase keys that map directly to React props. Store portable public paths only:

```json
{
  "sourceVideo": "assets/source.mp4",
  "introVoice": "assets/voice.wav",
  "backgroundMusic": "",
  "mainHeadline": "Sample headline",
  "overlayColor": "rgba(4, 102, 89, 0.9)"
}
```

Do not store:

- Absolute paths.
- `jobs/<job_id>` references.
- User-specific Downloads paths.
- URLs that should have been downloaded or copied into assets.

## Instantiate Script Responsibilities

The script should:

1. Copy the Remotion template into `jobs/<job_id>/remotion`.
2. Copy source assets into canonical job folders and `remotion/public/assets`.
3. Compute durations and frame counts with media metadata.
4. Write `template-props.json`.
5. Write `source/template_params.toml`, `source/creative_plan.toml`, and `source/render_plan.toml`.
6. Fail clearly when required assets are missing.

Do not make the instantiate script responsible for rendering; render from the job after inspection and optional parameter tweaks.
