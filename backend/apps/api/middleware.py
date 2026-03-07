"""
P3-07: API Middleware.

1. RequestIDMiddleware  — добавляет X-Request-ID в каждый запрос/ответ
2. SecurityHeadersMiddleware — OWASP security headers
3. LoggingMiddleware — логирует все 4xx/5xx с IP и request-id
"""
import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse

logger = logging.getLogger("api.middleware")


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach X-Request-ID to every request for distributed tracing."""

    async def dispatch(self, request: Request, call_next) -> Response:
        req_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
        request.state.request_id = req_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add OWASP-recommended security headers to every response."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers.update({
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            # Tight CSP — allow only same-origin and in-line scripts (Vite build)
            "Content-Security-Policy": (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline'; "
                "style-src 'self' 'unsafe-inline'; "
                "connect-src 'self'"
            ),
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
        })
        return response


class AccessLogMiddleware(BaseHTTPMiddleware):
    """
    Log every request with timing.
    Always log 4xx / 5xx responses with client IP for security auditing.
    In dev, log all requests at DEBUG level.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        client_ip = _get_client_ip(request)
        req_id = getattr(request.state, "request_id", "-")

        response = await call_next(request)

        duration_ms = (time.perf_counter() - start) * 1000
        status = response.status_code
        method = request.method
        path = request.url.path

        log_extra = {
            "method": method,
            "path": path,
            "status": status,
            "duration_ms": round(duration_ms, 1),
            "ip": client_ip,
            "req_id": req_id,
        }

        if status >= 500:
            logger.error("5xx %s %s  ip=%s req_id=%s  %.1fms",
                         method, path, client_ip, req_id, duration_ms, extra=log_extra)
        elif status >= 400:
            logger.warning("4xx %s %s  ip=%s req_id=%s  %.1fms",
                           method, path, client_ip, req_id, duration_ms, extra=log_extra)
        else:
            logger.debug("%s %s %d  ip=%s  %.1fms",
                         method, path, status, client_ip, duration_ms)

        return response


def _get_client_ip(request: Request) -> str:
    """Extract real IP respecting X-Forwarded-For (nginx proxy)."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "-"


# ─────────────────────────────────────────────────────────────────────────────
# P3-07: Simple in-memory rate limiter (no Redis dependency for this layer)
# For production, replace with slowapi + Redis backend.
# ─────────────────────────────────────────────────────────────────────────────
import time
import collections
import threading


class _RateLimiter:
    """Token-bucket rate limiter, thread-safe, in-process."""

    def __init__(self, max_calls: int, period: float):
        self._max = max_calls
        self._period = period
        self._calls: dict[str, list[float]] = collections.defaultdict(list)
        self._lock = threading.Lock()

    def is_allowed(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            calls = self._calls[key]
            # Remove expired
            cutoff = now - self._period
            self._calls[key] = [t for t in calls if t > cutoff]
            if len(self._calls[key]) >= self._max:
                return False
            self._calls[key].append(now)
            return True


# Sensitive endpoints: 20 requests / 60 s per IP
_control_limiter = _RateLimiter(max_calls=20, period=60.0)
# General API: 300 requests / 60 s per IP
_api_limiter = _RateLimiter(max_calls=300, period=60.0)

_SENSITIVE_PATHS = {"/api/v1/control", "/api/v1/signals"}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Apply rate limits to sensitive and general endpoints."""

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        path = request.url.path

        if any(path.startswith(p) for p in _SENSITIVE_PATHS):
            if not _control_limiter.is_allowed(client_ip):
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests. Please slow down."},
                    headers={"Retry-After": "60"},
                )
        elif path.startswith("/api/"):
            if not _api_limiter.is_allowed(client_ip):
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many requests."},
                    headers={"Retry-After": "60"},
                )

        return await call_next(request)
