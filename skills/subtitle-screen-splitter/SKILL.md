---
name: subtitle-screen-splitter
description: Split spoken subtitles/captions into screen-sized pages for karaoke or short-form video renderers. Use when Codex needs to paginate subtitle text or word-level transcripts, especially when pages must break after punctuation such as comma, period, exclamation mark, question mark, or before a newly capitalized word that starts a new sentence inside the same transcript line.
---

# Subtitle Screen Splitter

Use this skill to turn a continuous subtitle stream into small screen pages before rendering captions in Remotion or building a render plan.

## Core Rules

- Split after sentence or clause punctuation: `.`, `,`, `!`, `?`, `;`, `:`, `…`.
- Keep the punctuation on the page that came before it.
- Split before a token that looks like a new capitalized word when the current page already has words.
- Preserve Vietnamese diacritics exactly.
- Preserve word timing when the input is a word-level transcript.
- Keep pages short enough for the target layout with `--max-words` and `--max-chars`.

Examples:

```text
dang dở Bạn phát hiện ra
=> "dang dở" / "Bạn phát hiện ra"

không? Tôi không biết
=> "không?" / "Tôi không biết"
```

## Script

Use the bundled script for deterministic splitting:

```bash
python skills/subtitle-screen-splitter/scripts/split_subtitle_screens.py \
  --text "dang dở Bạn phát hiện ra"
```

For a project transcript:

```bash
python skills/subtitle-screen-splitter/scripts/split_subtitle_screens.py \
  --transcript jobs/<job_id>/source/transcript_word_level.toml \
  --output jobs/<job_id>/source/subtitle_screens.json \
  --max-words 2 \
  --max-chars 18
```

Output is JSON:

```json
{
  "pages": [
    {
      "id": "PAGE_0001",
      "text": "không?",
      "start": 0.0,
      "end": 0.4,
      "word_ids": ["W_0001"],
      "words": []
    }
  ]
}
```

## Renderer Integration

- In Remotion, load `pages` and select the active page by `now >= page.start && now <= page.end`.
- If using karaoke highlighting, render `page.words` and highlight the active word by its `start/end`.
- Do not re-join pages after the split; punctuation and capitalization boundaries are semantic boundaries.
- If a subtitle style requires exactly 1-2 words per page, run with `--max-words 2`.
