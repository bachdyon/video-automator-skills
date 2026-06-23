---
name: telegram-send
description: Send Telegram bot messages and media through the official Bot API using channel-specific `.env.<channel>` files. Use when the user asks to send Telegram messages, videos, photos, documents, check bot identity, or inspect bot updates/chat IDs.
---

# Telegram Send

## Rules

- Use the bundled Python client before writing ad hoc HTTP calls.
- Read `TELEGRAM_BOT_TOKEN` from the shell environment first, then from the channel env file passed with `--env-file .env.<channel>`.
- For channel-specific prefixed credentials such as `<PREFIX>_TELEGRAM_BOT_TOKEN`, pass `--env-prefix <PREFIX>` instead of wrapping the command with `source` or shell variable assignments.
- Do not store Telegram credentials in repo-root `.env`; each channel must use its own `.env.<channel>` file.
- Use `TELEGRAM_CHAT_ID` from env unless `--chat-id` is provided.
- Never print or log the bot token.
- Do not put the token in URLs shown to the user.
- Prefer local multipart upload for videos/documents. Telegram bot uploads are currently limited to 50 MB for `sendVideo` and `sendDocument`.
- For remote URL sends, Telegram may apply lower URL fetch limits; if a URL send fails, upload the local file instead.
- Save JSON responses in `source/` or `jobs/<job_id>/source/` when the result needs to be reused.
- When the user asks to send multiple distinct pieces of content, send each piece as a separate Telegram message. Do not combine a file link, caption/copy text, status note, or other independent content into one message unless the user explicitly asks for one combined message.

## Environment

For each Telegram channel, store credentials in repo-root `.env.<channel>`:

```text
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

For another channel, create the corresponding `.env.<channel>` file and pass it with `--env-file .env.<channel>`.

For a channel that uses prefixed variables, pass the matching env prefix:

```bash
.venv/bin/python skills/telegram-send/scripts/telegram_send.py \
  --env-file .env.<channel> \
  --env-prefix <PREFIX> \
  send-message --text "Xin chào"
```

If `TELEGRAM_CHAT_ID` is unknown, send any message to the bot first, then run:

```bash
.venv/bin/python skills/telegram-send/scripts/telegram_send.py \
  updates
```

## Commands

Check bot identity:

```bash
.venv/bin/python skills/telegram-send/scripts/telegram_send.py \
  get-me
```

Send text:

```bash
.venv/bin/python skills/telegram-send/scripts/telegram_send.py \
  send-message --text "Xin chào"
```

Send text from a file:

```bash
.venv/bin/python skills/telegram-send/scripts/telegram_send.py \
  send-message --text-file source/post_caption.txt
```

Send a video:

```bash
.venv/bin/python skills/telegram-send/scripts/telegram_send.py \
  --output jobs/<job_id>/source/telegram_send_video.json \
  send-video jobs/<job_id>/output/final_video_filepost_under25mb_h264.mp4 \
  --caption-file jobs/<job_id>/source/post_caption.txt
```

Send a document:

```bash
.venv/bin/python skills/telegram-send/scripts/telegram_send.py \
  --env-file .env.<channel> \
  send-document path/to/file.zip --caption "File gửi qua bot"
```

## Workflow

1. Confirm `TELEGRAM_BOT_TOKEN` exists in environment or the target `.env.<channel>` file.
   - If credentials are prefixed, confirm `<PREFIX>_TELEGRAM_BOT_TOKEN` exists and pass `--env-prefix <PREFIX>`.
2. If no chat id is provided, confirm `TELEGRAM_CHAT_ID` exists or run `updates` after the user messages the bot.
   - If credentials are prefixed, the default chat id may be `<PREFIX>_TELEGRAM_CHAT_ID`.
3. For local media, check file exists and size is under 50 MB before upload.
4. Run the bundled script command.
5. Return only useful result fields: message id, chat id, file id if present, output JSON path, and any Telegram error description.

## References

- Telegram Bot API: https://core.telegram.org/bots/api
