---
name: openai-whisper-word-timestamps
description: Use OpenAI Whisper or compatible transcription APIs to produce TOML transcript output with sentence-level timestamps and word-level timestamps for narration audio.
---

# OpenAI Whisper Word Timestamps

## Goal

Transcribe narration audio into sentence and word timestamps for subtitle generation, scene alignment, and semantic asset mapping.

Use this skill when the user provides an audio file and needs word-level timing.

## Inputs

- Audio file, normally `source/voice.wav` or `source/voice.mp3`.
- Optional language hint.
- Optional script text for correction/alignment.

## Output

Write or return TOML. Default path:

```text
source/transcript_word_level.toml
```

When a video job exists, write to:

```text
jobs/<job_id>/source/transcript_word_level.toml
```

## Workflow

1. Locate the audio file and preserve its path.
2. Use OpenAI Whisper or a compatible OpenAI transcription model that supports timestamps.
3. Request word-level timestamps when supported.
4. Group words into readable sentences.
5. If a source script exists, use it only to correct obvious transcription spelling and punctuation, not to fabricate timings.
6. Validate monotonic timestamps and sentence coverage.

## TOML Contract

```toml
[metadata]
audio_path = "source/voice.wav"
language = "vi"
duration_seconds = 45.0
model = "whisper-compatible"

[[sentences]]
id = "S_001"
start = 0.12
end = 4.8
sentence = "..."
word_ids = ["W_0001", "W_0002"]

[[words]]
id = "W_0001"
word = "..."
start = 0.12
end = 0.38
sentence_id = "S_001"
confidence = 0.0
```

If nested words are requested instead, also support:

```toml
[[sentences]]
start = 0.12
end = 4.8
sentence = "..."
words = [
  { word = "...", start = 0.12, end = 0.38 }
]
```

## Quality Rules

- Timestamps are seconds as floats.
- Words must be ordered and non-overlapping within a sentence.
- Do not silently drop words with uncertain timing; include them with warnings if needed.
- Keep punctuation in `sentence`, but keep `word` as the spoken token where possible.

## Utility Script

Use the bundled script for deterministic API calls and TOML normalization:

```bash
python skills/openai_whisper_word_timestamps/scripts/transcribe_word_timestamps.py \
  --audio source/voice.wav \
  --output source/transcript_word_level.toml \
  --language vi
```

For a job-scoped run:

```bash
python skills/openai_whisper_word_timestamps/scripts/transcribe_word_timestamps.py \
  --audio jobs/<job_id>/source/voice.wav \
  --output jobs/<job_id>/source/transcript_word_level.toml \
  --env-file jobs/<job_id>/source/.env \
  --language vi
```

The script uses `whisper-1` with `response_format=verbose_json` and `timestamp_granularities[]=word`, because OpenAI currently only supports word timestamp granularities on `whisper-1`.
