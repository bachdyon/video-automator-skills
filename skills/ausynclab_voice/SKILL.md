---
name: ausynclab-voice
description: Work with AusyncLab voice and Text-to-Speech APIs to list voices, recommend a voice for a creative plan, persist preferred voice settings, and generate mp3 or wav narration audio.
---

# AusyncLab Voice

## Script Environment Rule

Before running any bundled script from this skill, read the repo-root `.env` first. This file lives beside `jobs/`, `skills/`, and `env.example`. Confirm `AUSYNCLAB_API_KEY` exists, and confirm `AUSYNCLAB_VOICE_ID` or `--voice-id` before synthesis. Pass `.env` with `--env-file`; never print secret values in logs, terminal output, TOML artifacts, or responses. Use a non-root `--env-file` only when the user explicitly provides one.

## Goal

Manage voice selection and generate narration audio through AusyncLab.

Use this skill when the user asks to list voices, choose a suitable voice, save a preferred voice, or create narration audio from text/script using AusyncLab.

## API Facts

Consult the official docs when details matter:

- Voice Library: `https://docs.ausynclab.io/voices`
- Text-to-Speech: `https://docs.ausynclab.io/tts`

Known current endpoints:

- `GET https://api.ausynclab.io/api/v1/voices/list`
- `POST https://api.ausynclab.io/api/v1/speech/text-to-speech`
- `GET https://api.ausynclab.io/api/v1/speech/`
- `GET https://api.ausynclab.io/api/v1/speech/{audio_id}`

Authentication uses header:

```text
X-API-Key: <api key>
```

## Inputs

- API key from repo-root `.env`.
- Script text from `source/creative_plan.toml` or direct user input.
- Optional preferred voice config from `.env` in the repo root, beside `skills/`.

## Outputs

Default files:

```text
source/voice_selection.toml
source/voice.wav
```

When a video job exists, write to:

```text
jobs/<job_id>/source/voice_selection.toml
jobs/<job_id>/source/voice.wav
```

If the API returns another format or URL, download/persist the final audio path and record it in TOML.

## Workflow

1. Check `AUSYNCLAB_API_KEY` from `.env`. Do not print the key.
2. List voices when voice choice is unknown.
3. Recommend a voice based on language, tone, audience, VDS mood, and creative plan delivery.
4. If the user approves or has a saved preference, persist:

```text
.env
```

with values like:

```text
AUSYNCLAB_VOICE_ID=123
```

For job-scoped runs, keep using shared `.env` in the repo root for credentials and global voice defaults unless the user explicitly provides another env file.

5. Submit Text-to-Speech request with `audio_name`, `text`, `voice_id`, `speed`, `model_name`, and `language`.
6. If callback handling is unavailable, poll the speech list/detail endpoint until the audio state succeeds or fails.
7. Download the final audio URL to `source/voice.wav` or `source/voice.mp3`.
8. Write `source/voice_selection.toml`.

## TOML Contract

```toml
[voice]
provider = "ausynclab"
voice_id = 123
voice_name = "..."
language = "vi"
gender = "FEMALE"
age = "YOUNG"
use_case = "NARRATION"
model_name = "myna-2"
speed = 1.0
reason = "Warm narration voice fits the reflective VDS mood."

[audio]
audio_id = 456
file_path = "source/voice.wav"
audio_url = "https://..."
format = "wav"
sample_rate = 24000
duration_seconds = 0.0
state = "SUCCEED"

[source]
script_path = "source/creative_plan.toml"
text_hash = "optional"
```

## Quality Rules

- Never expose API keys in logs or output files.
- Ask for confirmation before overwriting an existing preferred voice unless the user requested replacement.
- Vietnamese content should default to `language = "vi"` and `model_name = "myna-2"` unless constraints say otherwise.
- Keep the generated audio path stable so Whisper and renderer skills can consume it.

## Utility Script

Use the bundled script instead of rewriting API calls:

```bash
python skills/ausynclab_voice/scripts/ausynclab_voice.py --env-file .env list --output source/voices.toml
python skills/ausynclab_voice/scripts/ausynclab_voice.py --env-file .env recommend --language vi --use-case NARRATION --save-preference
python skills/ausynclab_voice/scripts/ausynclab_voice.py --env-file .env synthesize --creative-plan source/creative_plan.toml
```

For a job-scoped run:

```bash
python skills/ausynclab_voice/scripts/ausynclab_voice.py --env-file .env synthesize \
  --creative-plan jobs/<job_id>/source/creative_plan.toml \
  --output-audio jobs/<job_id>/source/voice.wav \
  --output jobs/<job_id>/source/voice_selection.toml
```

The script handles `.env`, API key lookup, voice listing, simple recommendation, TTS submission, polling, audio download, and `source/voice_selection.toml`.
