"""Helpers for robust outbound HTTP requests.

We intentionally disable implicit proxy pickup from environment because a broken
ALL_PROXY/http_proxy setting can make the worker and API partially unusable.

For selected outbound integrations we may still want to use a *sanitized* proxy
URL from environment explicitly (for example HTTPS_PROXY), without enabling full
trust_env behavior.
"""
from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlparse

import httpx


def make_async_client(**kwargs: Any) -> httpx.AsyncClient:
    kwargs.setdefault("trust_env", False)
    return httpx.AsyncClient(**kwargs)


def get_env_http_proxy_url(preferred_scheme: str = "https") -> str | None:
    """Return a sanitized HTTP(S) proxy URL from env.

    Why this exists:
    - `trust_env=True` can explode on malformed/unsupported proxy vars
      (for example `ALL_PROXY=socks://...`).
    - Some hosts need outbound proxy access, but we don't want to globally apply
      env proxy behavior to every HTTP client.

    Strategy:
    - Prefer explicit HTTPS/HTTP proxy variables.
    - Ignore unsupported proxy schemes.
    - Fall back to ALL_PROXY only if it is HTTP(S).
    """
    preferred = (preferred_scheme or "https").lower()
    candidate_keys: list[str]
    if preferred == "http":
        candidate_keys = ["HTTP_PROXY", "http_proxy", "ALL_PROXY", "all_proxy"]
    else:
        candidate_keys = [
            "HTTPS_PROXY",
            "https_proxy",
            "HTTP_PROXY",
            "http_proxy",
            "ALL_PROXY",
            "all_proxy",
        ]

    for key in candidate_keys:
        raw = (os.getenv(key) or "").strip()
        if not raw:
            continue
        parsed = urlparse(raw)
        scheme = (parsed.scheme or "").lower()
        if scheme not in {"http", "https"}:
            continue
        return raw.rstrip("/")
    return None
