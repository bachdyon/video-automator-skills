---
name: overlay-video-preparer
description: Prepare effect/overlay videos so they can be composited over another video, especially stock overlays with black backgrounds, dust, light particles, petals, smoke, flares, or non-alpha MP4/MOV assets. Use when Codex needs to check whether overlay videos have real alpha, convert ordinary overlay footage into Remotion-ready assets, normalize fps/size, preserve color for screen blending, avoid black halos from bad alpha keying, or generate reusable overlay files and compositing snippets.
---

# Overlay Video Preparer

## Core Rule

Do not assume an effect video has transparency. Check alpha first.

If the source has no real alpha, prefer a color-preserving black-background workflow:

- convert to target resolution while keeping source fps by default;
- boost saturation/contrast lightly before blending;
- keep it as H.264 MP4 with black background;
- composite with `mixBlendMode: 'screen'` in Remotion or an equivalent screen/lighten blend;
- loop the overlay in the render layer, not by manually duplicating files.

Only create a transparent WebM/ProRes when the source actually has an alpha channel, or when the user explicitly accepts the visual risks of keying.

## Quick Start

Prepare one or more stock overlay videos for a 1024x1536 Remotion project, keeping each overlay's source fps:

```bash
python3 skills/overlay-video-preparer/scripts/prepare_overlay_video.py \
  /path/to/petals.mp4 /path/to/dust.mp4 \
  --output-dir jobs/<job_id>/remotion/public \
  --width 1024 \
  --height 1536
```

Override fps only when the final composition requires it:

```bash
python3 skills/overlay-video-preparer/scripts/prepare_overlay_video.py \
  /path/to/petals.mp4 \
  --output-dir jobs/<job_id>/remotion/public \
  --width 1024 \
  --height 1536 \
  --fps 30000/1001
```

Slower emotional overlays are a render-layer decision. In Remotion, keep `loop` and set `playbackRate`:

```tsx
<OffthreadVideo
  src={staticFile('petals_1024x1536_30fps_overlay.mp4')}
  muted
  loop
  playbackRate={0.55}
  style={{
    position: 'absolute',
    inset: 0,
    width: '100%',
    height: '100%',
    objectFit: 'cover',
    mixBlendMode: 'screen',
    opacity: 0.6,
    pointerEvents: 'none',
  }}
/>
```

## Workflow

1. Run the bundled script before writing ad hoc FFmpeg filters.
2. Read the JSON report beside each output.
3. If `has_real_alpha` is false, use the generated MP4 with `screen` blend. Do not alpha-key by default.
4. If `has_real_alpha` is true and the user wants true transparency, rerun with `--mode preserve-alpha`.
5. Render or extract preview frames after compositing to verify:
   - no black halos or dark blotches;
   - particle/petal colors remain visible;
   - frame rate matches the main composition;
   - overlay loops through the full final video;
   - subtitles and main subjects remain readable.

## Script Defaults

The script defaults are tuned for TikTok/Reels vertical videos:

```text
width: 1024
height: 1536
fps: source video fps unless --fps is passed
fit: cover
mode: screen
saturation: 1.8
contrast: 1.08
brightness: 0.01
codec: H.264 MP4
```

Use lower saturation for already colorful assets:

```bash
python3 skills/overlay-video-preparer/scripts/prepare_overlay_video.py \
  effect.mp4 \
  --output-dir jobs/<job_id>/remotion/public \
  --saturation 1.25 \
  --contrast 1.03
```

Prepare a real-alpha source as transparent WebM:

```bash
python3 skills/overlay-video-preparer/scripts/prepare_overlay_video.py \
  transparent_effect.mov \
  --output-dir jobs/<job_id>/remotion/public \
  --mode preserve-alpha
```

## Remotion Guidance

- Use `$remotion-best-practices` before editing or rendering a Remotion project.
- Prefer `OffthreadVideo` for rendered overlays when using Remotion server-side rendering.
- Keep overlays under captions unless the user explicitly wants foreground particles over text.
- Keep `loop` on the overlay component; do not make the overlay file longer just to cover a final video.
- Keep the prepared overlay fps sourced from the overlay video by default. Pass `--fps` only to intentionally match a known composition fps.
- Use `playbackRate` for mood:
  - `0.35-0.5` for slow dust/light particles;
  - `0.5-0.7` for petals;
  - `0.8-1.0` for energetic sparkles or confetti.

## Failure Cases

- If `alphaextract` fails, the file does not expose an alpha plane to FFmpeg. Treat it as a black-background overlay.
- If alpha-key output makes colors gray, removes lotus/petal detail, or creates dirty borders, reject it and switch back to screen blend.
- If motion jitters after compositing, check the prepared overlay fps in the JSON report, compare it with the Remotion composition fps, and use `OffthreadVideo`.
- If the overlay is too strong, reduce opacity in the render layer before lowering source saturation; opacity is easier to tune per scene.
