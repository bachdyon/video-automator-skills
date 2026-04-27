"""Tiny HTTPS helpers for the asset index.

Provides an SSL context that prefers the bundled ``certifi`` CA store so that
HTTPS calls work inside virtualenvs on macOS where the python.org installer's
"Install Certificates.command" has not been run.
"""

from __future__ import annotations

import ssl
from functools import lru_cache


@lru_cache(maxsize=1)
def ssl_context() -> ssl.SSLContext:
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()
