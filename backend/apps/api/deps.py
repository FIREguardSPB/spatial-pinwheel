"""
P1-04: Auth dependency — Bearer Token verification.

Usage:
    from apps.api.deps import verify_token
    router.get("/route", dependencies=[Depends(verify_token)])

Behaviour:
  - If AUTH_TOKEN is empty (dev mode) → always allow, log a warning once.
  - If AUTH_TOKEN is set → require matching Bearer token in Authorization header.
  - SSE /stream endpoint: check ?token= query param instead (EventSource can't set headers).
"""

import logging
from functools import lru_cache

from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from core.config import settings

logger = logging.getLogger(__name__)

_no_auth_warned = False
_bearer_scheme = HTTPBearer(auto_error=False)


async def verify_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> None:
    """Verify Bearer token for standard HTTP endpoints."""
    global _no_auth_warned

    if not settings.AUTH_TOKEN:
        if not _no_auth_warned:
            logger.warning(
                "AUTH_TOKEN is not set — all API endpoints are unprotected. "
                "Set AUTH_TOKEN in .env for production."
            )
            _no_auth_warned = True
        return  # dev mode: allow all

    if credentials is None or credentials.credentials != settings.AUTH_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing Bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def verify_token_query(
    token: str | None = Query(default=None, description="Bearer token (for SSE endpoints)"),
) -> None:
    """
    Verify token from ?token= query param.
    Used for SSE /stream because EventSource API cannot set Authorization headers.
    """
    global _no_auth_warned

    if not settings.AUTH_TOKEN:
        if not _no_auth_warned:
            logger.warning(
                "AUTH_TOKEN is not set — SSE stream is unprotected."
            )
            _no_auth_warned = True
        return

    if token != settings.AUTH_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing token query parameter",
        )
