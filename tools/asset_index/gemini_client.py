"""Tiny Gemini REST client used by the image and audio analyzers.

Behaviour matches ``skills/asset_semantic_extractor/scripts/analyze_with_gemini.py``
(model fallback, JSON parsing, retry on transient errors), but routes traffic
through the asset-index SSL context so HTTPS keeps working in fresh
virtualenvs without the user running ``Install Certificates.command``.
"""

from __future__ import annotations

import base64
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Iterable

from tools.asset_index.http_utils import ssl_context

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
)

DEFAULT_MODEL = "gemini-3-flash-preview"
DEFAULT_FALLBACKS = ("gemini-3-flash-preview", "gemini-2.5-pro", "gemini-2.5-flash")


class GeminiError(RuntimeError):
    pass


def encode_image_b64(path: str | Path) -> str:
    return base64.b64encode(Path(path).read_bytes()).decode("ascii")


def _http_post_json(url: str, body: dict[str, Any], timeout: int) -> dict[str, Any]:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout, context=ssl_context()) as resp:
        raw = resp.read().decode("utf-8")
        return json.loads(raw) if raw else {}


def _extract_text(response: dict[str, Any]) -> str:
    for candidate in response.get("candidates") or []:
        content = candidate.get("content") or {}
        for part in content.get("parts") or []:
            text = part.get("text")
            if text:
                return text
    return ""


def parse_json_strict(text: str) -> dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def call_gemini_json(
    api_key: str,
    parts: list[dict[str, Any]],
    *,
    models: Iterable[str] = (DEFAULT_MODEL, *DEFAULT_FALLBACKS),
    timeout: int = 120,
    temperature: float = 0.4,
    max_output_tokens: int = 4096,
    retries_per_model: int = 2,
    log_prefix: str = "[gemini]",
) -> tuple[dict[str, Any], str]:
    """POST a Gemini ``generateContent`` request and parse the JSON response.

    Tries each model in order, retrying transient HTTP errors per model. Raises
    ``GeminiError`` if all attempts fail. Returns ``(json, model_used)``.
    """
    errors: list[str] = []
    for model in models:
        url = GEMINI_URL.format(model=model, key=api_key)
        body = {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": temperature,
                "topP": 0.9,
                "maxOutputTokens": max_output_tokens,
            },
        }
        for attempt in range(retries_per_model):
            try:
                print(f"{log_prefix} model={model} parts={len(parts)} attempt={attempt + 1}", flush=True)
                response = _http_post_json(url, body, timeout=timeout)
                text = _extract_text(response)
                if not text:
                    errors.append(f"{model}: empty response")
                    break
                data = parse_json_strict(text)
                print(f"{log_prefix} model={model} ok", flush=True)
                return data, model
            except urllib.error.HTTPError as exc:
                try:
                    detail = exc.read().decode("utf-8", errors="replace")
                except Exception:
                    detail = ""
                errors.append(f"{model}: HTTP {exc.code} {detail[:240]}")
                if exc.code in (429, 500, 502, 503, 504) and attempt < retries_per_model - 1:
                    time.sleep(2 ** attempt)
                    continue
                break
            except urllib.error.URLError as exc:
                errors.append(f"{model}: URL {exc}")
                if attempt < retries_per_model - 1:
                    time.sleep(2 ** attempt)
                    continue
                break
            except json.JSONDecodeError as exc:
                errors.append(f"{model}: invalid JSON ({exc})")
                break
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{model}: {exc}")
                break
        print(f"{log_prefix} {errors[-1]}", file=sys.stderr, flush=True)
    raise GeminiError("all gemini models failed: " + " | ".join(errors))


__all__ = [
    "DEFAULT_MODEL",
    "DEFAULT_FALLBACKS",
    "GeminiError",
    "encode_image_b64",
    "parse_json_strict",
    "call_gemini_json",
]
