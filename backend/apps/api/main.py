"""
API entrypoint.

P3-02: configure_logging() at startup
P3-06: /metrics endpoint (prometheus)
P3-07: RequestID + SecurityHeaders + AccessLog middleware
P3-08: FastAPI lifespan (startup/shutdown hooks)
P1-03: Restricted CORS from env
P1-04: Bearer Token auth on all routers
P1-07: Real health check
"""
import asyncio
import ctypes
import gc
import logging
import os
import threading
import uuid
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.background import BackgroundTask

from apps.api.deps import verify_token, verify_token_query
from apps.api.middleware import AccessLogMiddleware, RequestIDMiddleware, SecurityHeadersMiddleware, RateLimitMiddleware
from apps.api.routers import tokens as tokens_router
from apps.api.routers import candles, logs, settings, signals, state, stream, ai, backtest, trades, account, watchlist, orders_manual, bot, worker, metrics, risk, trace, tbank, symbol_profiles, event_regimes, paper, validation, forensics, ml, ui, sentiment
from core.config import get_token, settings as config
from core.logging import configure_logging
from core.metrics import setup_metrics_endpoint
from core.version import __version__

# Configure logging once at import time (uvicorn calls this module first)
configure_logging(
    level=os.getenv("LOG_LEVEL", "INFO"),
    json_format=(config.APP_ENV == "production"),
    log_dir=(config.LOG_DIR or os.getenv("LOG_DIR") or None),
)
logger = logging.getLogger(__name__)
_MSK = ZoneInfo("Europe/Moscow")
_FRONTEND_DIST = Path(__file__).resolve().parents[3] / "dist"

try:
    _LIBC = ctypes.CDLL("libc.so.6")
    _MALLOC_TRIM = getattr(_LIBC, "malloc_trim", None)
except Exception:
    _LIBC = None
    _MALLOC_TRIM = None

_TRIM_PATH_PREFIXES = (
    f"{config.API_PREFIX}/ui",
    f"{config.API_PREFIX}/candles",
    f"{config.API_PREFIX}/account",
    f"{config.API_PREFIX}/signals",
)
_RECYCLING_REQUEST_LIMIT = max(
    0,
    int(
        os.getenv(
            "API_HEAVY_READ_RECYCLE_LIMIT",
            "0" if config.APP_ENV == "dev" else "8",
        ) or ("0" if config.APP_ENV == "dev" else "8")
    ),
)
_HEAVY_READ_REQUESTS = 0
_RECYCLE_ARMED = False


# ── P3-08: Lifespan ───────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("API startup — version=%s env=%s", __version__, config.APP_ENV)

    loop = asyncio.get_running_loop()
    previous_exception_handler = loop.get_exception_handler()

    def _log_asyncio_exception(loop: asyncio.AbstractEventLoop, context: dict):
        exc = context.get("exception")
        logger.error("Unhandled asyncio exception: %s", context.get("message", "unknown"), exc_info=exc)
        if previous_exception_handler is not None:
            previous_exception_handler(loop, context)

    loop.set_exception_handler(_log_asyncio_exception)

    # Security: refuse to start in production without AUTH_TOKEN
    if config.APP_ENV == "production" and not config.AUTH_TOKEN:
        logger.critical(
            "AUTH_TOKEN is not set but APP_ENV=production. "
            "Refusing to start with unprotected API. "
            "Set AUTH_TOKEN in .env or environment variables."
        )
        raise RuntimeError("AUTH_TOKEN required in production mode")

    yield
    logger.info("API shutdown — closing resources")
    loop.set_exception_handler(previous_exception_handler)
    try:
        from core.events.bus import bus
        await bus.redis.aclose()
    except Exception as e:
        logger.warning("Redis close error on shutdown: %s", e)


app = FastAPI(
    title="Spatial Pinwheel API",
    description="Automated trading bot for MOEX equities. Paper + Live modes, AI signal analysis, Risk management.",
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


def _exit_worker_soon() -> None:
    logger.warning("Recycling API worker after heavy read limit to cap RSS growth")
    os._exit(0)


async def _trim_memory_background(existing_task=None, recycle_worker: bool = False):
    if existing_task is not None:
        await existing_task()
    try:
        gc.collect()
        if _MALLOC_TRIM is not None:
            _MALLOC_TRIM(0)
    except Exception:
        logger.debug("malloc_trim skipped", exc_info=True)
    if recycle_worker:
        threading.Timer(0.05, _exit_worker_soon).start()


@app.middleware("http")
async def trim_memory_after_heavy_reads(request, call_next):
    response = await call_next(request)
    if config.APP_ENV == "dev":
        return response
    path = request.url.path
    should_trim = request.method == "GET" and (
        path == "/health"
        or path == f"{config.API_PREFIX}/health"
        or any(path.startswith(prefix) for prefix in _TRIM_PATH_PREFIXES)
    )
    if should_trim:
        global _HEAVY_READ_REQUESTS, _RECYCLE_ARMED
        recycle_worker = False
        _HEAVY_READ_REQUESTS += 1
        if _RECYCLING_REQUEST_LIMIT > 0 and _HEAVY_READ_REQUESTS >= _RECYCLING_REQUEST_LIMIT and not _RECYCLE_ARMED:
            recycle_worker = True
            _RECYCLE_ARMED = True
        response.background = BackgroundTask(_trim_memory_background, response.background, recycle_worker)
    return response

# ── P3-07: Middleware (order matters — outermost first) ───────────────────────
app.add_middleware(RateLimitMiddleware)
app.add_middleware(AccessLogMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestIDMiddleware)

# ── P1-03: CORS ───────────────────────────────────────────────────────────────
_origins = [o.strip() for o in config.CORS_ORIGINS.split(",") if o.strip()]
if config.APP_ENV == "dev" and not _origins:
    _origins = ["*"]
    logger.warning("CORS_ORIGINS empty + APP_ENV=dev — allowing all origins")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── P3-06: Prometheus /metrics ────────────────────────────────────────────────
setup_metrics_endpoint(app)


# ── P1-07: Real health check ──────────────────────────────────────────────────
@app.get("/health", tags=["health"])
@app.get(config.API_PREFIX + "/health", tags=["health"])
async def health():
    components: dict = {}
    ok = True
    now_utc = datetime.now(timezone.utc)
    now_msk = now_utc.astimezone(_MSK)

    try:
        import sqlalchemy
        from core.storage.session import SessionLocal
        db = SessionLocal()
        db.execute(sqlalchemy.text("SELECT 1"))
        db.close()
        components["db"] = {"status": "ok"}
    except Exception as e:
        components["db"] = {"status": "error", "detail": str(e)}
        ok = False

    try:
        from core.events.bus import bus
        bus._ensure_client()
        await bus.redis.ping()
        components["redis"] = {"status": "ok"}
    except Exception as e:
        components["redis"] = {"status": "warning" if config.ALLOW_NO_REDIS else "error", "detail": str(e)}
        if not config.ALLOW_NO_REDIS:
            ok = False

    runtime_tbank_token = get_token("TBANK_TOKEN") or os.getenv("TBANK_TOKEN") or config.TBANK_TOKEN
    runtime_tbank_account = get_token("TBANK_ACCOUNT_ID") or os.getenv("TBANK_ACCOUNT_ID") or config.TBANK_ACCOUNT_ID

    # Read trade_mode from Settings for UI visibility and health semantics
    trade_mode = "review"
    try:
        from core.storage.session import SessionLocal as _SL2
        _db2 = _SL2()
        from core.storage.models import Settings as _Sett
        _s2 = _db2.query(_Sett).first()
        trade_mode = getattr(_s2, 'trade_mode', 'review') if _s2 else 'review'
        _db2.close()
    except Exception:
        trade_mode = "unknown"

    broker = {"provider": config.BROKER_PROVIDER,
               "sandbox": config.TBANK_SANDBOX if config.BROKER_PROVIDER == "tbank" else False,
               "trade_mode": trade_mode}
    if config.BROKER_PROVIDER == "tbank":
        broker["status"] = "configured" if runtime_tbank_token else "token_missing"
        broker["account_configured"] = bool(runtime_tbank_account)
        broker["live_trading_enabled"] = bool(config.LIVE_TRADING_ENABLED)
        broker["stream_mode"] = config.TBANK_STREAM_MODE
        broker["execution_mode"] = "rest_sandbox" if config.TBANK_SANDBOX else "rest_live"
        broker["transport"] = "rest"
        live_required = trade_mode == "auto_live"
        if live_required and not runtime_tbank_token:
            ok = False
            broker["warning"] = "TBANK_TOKEN is required only for auto_live mode."
        elif live_required and not runtime_tbank_account:
            ok = False
            broker["warning"] = "TBANK_ACCOUNT_ID is required for auto_live mode."
        elif live_required and not config.LIVE_TRADING_ENABLED:
            ok = False
            broker["warning"] = "LIVE_TRADING_ENABLED=false — auto live execution is disabled by configuration."
        elif not runtime_tbank_token:
            broker["warning"] = "TBANK token is not configured, so broker-backed features use static/offline fallbacks."
        elif not runtime_tbank_account:
            broker["warning"] = "TBANK_ACCOUNT_ID is not configured — live order placement will fail until the account is selected."
    else:
        broker["status"] = "paper"
        broker["execution_mode"] = "paper"

    components["broker"] = broker

    body = {
        "status": "ok" if ok else "degraded",
        "version": __version__,
        "commit": os.getenv("GIT_COMMIT", "HEAD")[:7],
        "ts": int(time.time() * 1000),
        "server_time_utc": now_utc.isoformat(),
        "server_time_msk": now_msk.isoformat(),
        "timezone": "Europe/Moscow",
        "components": components,
    }
    if not ok:
        return JSONResponse(status_code=503, content=body)
    return body


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc):
    req_id = getattr(getattr(request, "state", None), "request_id", "-")
    error_id = uuid.uuid4().hex[:10]
    logger.error("Unhandled API exception path=%s req_id=%s error_id=%s", request.url.path, req_id, error_id, exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error", "request_id": req_id, "error_id": error_id})


# ── P1-04: Routers with auth ──────────────────────────────────────────────────
_auth = [Depends(verify_token)]

app.include_router(settings.router,  prefix=config.API_PREFIX + "/settings",     tags=["settings"],    dependencies=_auth)
app.include_router(signals.router,   prefix=config.API_PREFIX + "/signals",      tags=["signals"],     dependencies=_auth)
app.include_router(logs.router,      prefix=config.API_PREFIX + "/decision-log", tags=["logs"],        dependencies=_auth)
app.include_router(state.router,     prefix=config.API_PREFIX + "/state",        tags=["state"],       dependencies=_auth)
app.include_router(candles.router,   prefix=config.API_PREFIX + "/candles",      tags=["candles"],     dependencies=_auth)
app.include_router(backtest.router, prefix=config.API_PREFIX + "/backtest",    tags=["backtest"], dependencies=_auth)
app.include_router(ai.router,        prefix=config.API_PREFIX + "/ai",           tags=["ai"],          dependencies=_auth)
app.include_router(ml.router,        prefix=config.API_PREFIX + "/ml",           tags=["ml"],          dependencies=_auth)
app.include_router(ui.router,        prefix=config.API_PREFIX + '/ui',           tags=['ui'],          dependencies=_auth)
app.include_router(sentiment.router, prefix=config.API_PREFIX + '/sentiment', tags=['sentiment'], dependencies=_auth)
app.include_router(sentiment.admin_router, prefix=config.API_PREFIX + '/admin/sentiment', tags=['admin-sentiment'], dependencies=_auth)
app.include_router(trades.router,    prefix=config.API_PREFIX + "/trades",       tags=["trades"],      dependencies=_auth)
app.include_router(account.router,   prefix=config.API_PREFIX + "/account",      tags=["account"],     dependencies=_auth)
app.include_router(bot.router,       prefix=config.API_PREFIX + "/bot",          tags=["bot"],         dependencies=_auth)
app.include_router(watchlist.router, prefix=config.API_PREFIX + "/watchlist",    tags=["watchlist"],   dependencies=_auth)
app.include_router(watchlist.router, prefix=config.API_PREFIX + "/instruments",  tags=["instruments"], dependencies=_auth)
app.include_router(worker.router, prefix=config.API_PREFIX + "/worker",       tags=["worker"],      dependencies=_auth)
app.include_router(metrics.router, prefix=config.API_PREFIX + "/metrics", tags=["metrics"], dependencies=_auth)
app.include_router(risk.router, prefix=config.API_PREFIX + "/risk", tags=["risk"], dependencies=_auth)
app.include_router(paper.router, prefix=config.API_PREFIX + "/paper", tags=["paper"], dependencies=_auth)
app.include_router(trace.router, prefix=config.API_PREFIX + "/trace", tags=["trace"], dependencies=_auth)
app.include_router(tbank.router, prefix=config.API_PREFIX + "/tbank", tags=["tbank"], dependencies=_auth)
app.include_router(symbol_profiles.router, prefix=config.API_PREFIX + "/symbol-profiles", tags=["symbol-profiles"], dependencies=_auth)
app.include_router(event_regimes.router, prefix=config.API_PREFIX + "/event-regimes", tags=["event-regimes"], dependencies=_auth)
app.include_router(validation.router, prefix=config.API_PREFIX + "/validation", tags=["validation"], dependencies=_auth)
app.include_router(forensics.router, prefix=config.API_PREFIX + "/forensics", tags=["forensics"], dependencies=_auth)
app.include_router(stream.router,    prefix=config.API_PREFIX,                   tags=["stream"],
                   dependencies=[Depends(verify_token_query)])
app.include_router(orders_manual.router, prefix=config.API_PREFIX + "/orders", tags=["orders"], dependencies=_auth)
app.include_router(tokens_router.router, prefix=config.API_PREFIX + "/tokens", tags=["tokens"])


if _FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=_FRONTEND_DIST / "assets"), name="frontend-assets")

    @app.get("/", include_in_schema=False)
    @app.get("/{full_path:path}", include_in_schema=False)
    async def frontend_spa(full_path: str = ""):
        if full_path.startswith("api/") or full_path in {"docs", "redoc", "openapi.json", "health", "metrics"}:
            return JSONResponse(status_code=404, content={"detail": "Not Found"})

        candidate = _FRONTEND_DIST / full_path
        if full_path and candidate.exists() and candidate.is_file():
            return FileResponse(candidate)

        return HTMLResponse((_FRONTEND_DIST / "index.html").read_text(encoding="utf-8"))
