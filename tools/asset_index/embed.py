"""OpenAI text embeddings for the asset index.

Uses ``text-embedding-3-small`` (1536 dims) via the public REST API directly so
we do not pull in the heavy ``openai`` SDK. Network calls go through
``urllib.request`` to stay consistent with the rest of the project.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Iterable

from skills._shared.pipeline_utils import env_value  # type: ignore
from tools.asset_index.http_utils import ssl_context

MODEL = "text-embedding-3-small"
EMBED_DIM = 1536
ENDPOINT = "https://api.openai.com/v1/embeddings"
MAX_INPUT_CHARS = 8000

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENV = WORKSPACE_ROOT / ".env"


class EmbeddingError(RuntimeError):
    pass


def _request(api_key: str, text: str, timeout: int = 60) -> list[float]:
    body = json.dumps({"model": MODEL, "input": text}).encode("utf-8")
    req = urllib.request.Request(
        ENDPOINT,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout, context=ssl_context()) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    data = payload.get("data") or []
    if not data:
        raise EmbeddingError(f"empty embedding response: {payload}")
    embedding = data[0].get("embedding") or []
    if len(embedding) != EMBED_DIM:
        raise EmbeddingError(
            f"unexpected embedding dim {len(embedding)} (expected {EMBED_DIM})"
        )
    return [float(x) for x in embedding]


def embed_text(text: str, *, env_file: Path | str = DEFAULT_ENV, retries: int = 3) -> list[float]:
    """Embed ``text`` using OpenAI's ``text-embedding-3-small``.

    Truncates input above ``MAX_INPUT_CHARS`` to keep the request well under
    the model's 8k-token limit. Retries up to ``retries`` times on transient
    HTTP 429/5xx errors with exponential backoff.
    """
    api_key = env_value(Path(env_file), "OPENAI_API_KEY")
    if not api_key:
        raise EmbeddingError("OPENAI_API_KEY missing from .env")

    cleaned = (text or "").strip()
    if not cleaned:
        raise EmbeddingError("cannot embed empty text")
    if len(cleaned) > MAX_INPUT_CHARS:
        cleaned = cleaned[:MAX_INPUT_CHARS]

    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            return _request(api_key, cleaned)
        except urllib.error.HTTPError as exc:
            last_err = exc
            if exc.code in (408, 409, 425, 429, 500, 502, 503, 504) and attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            try:
                detail = exc.read().decode("utf-8", errors="replace")
            except Exception:
                detail = ""
            raise EmbeddingError(f"OpenAI HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            last_err = exc
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise EmbeddingError(f"network error talking to OpenAI: {exc}") from exc
        except (TimeoutError, ConnectionError) as exc:
            last_err = exc
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise EmbeddingError(f"timeout/connection error: {exc}") from exc
    raise EmbeddingError(f"embedding failed after {retries} attempts: {last_err}")


def build_embed_source(parts: Iterable[str | None]) -> str:
    """Concatenate the inputs that should be embedded for an asset."""
    cleaned: list[str] = []
    seen: set[str] = set()
    for part in parts:
        if not part:
            continue
        token = str(part).strip()
        if not token or token in seen:
            continue
        seen.add(token)
        cleaned.append(token)
    return " | ".join(cleaned)[:MAX_INPUT_CHARS]


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Embed a string with OpenAI text-embedding-3-small")
    parser.add_argument("text", nargs="?", help="text to embed (read from stdin if omitted)")
    parser.add_argument("--env-file", default=str(DEFAULT_ENV))
    parser.add_argument("--show-floats", type=int, default=5, help="how many leading floats to print")
    args = parser.parse_args(argv)

    text = args.text if args.text is not None else sys.stdin.read()
    try:
        vec = embed_text(text, env_file=args.env_file)
    except EmbeddingError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"length={len(vec)}")
    head = ", ".join(f"{x:.4f}" for x in vec[: args.show_floats])
    print(f"first {args.show_floats}: [{head}]")
    return 0


if __name__ == "__main__":
    sys.exit(_main())
