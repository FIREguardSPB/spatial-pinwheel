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
import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from apps.api.deps import verify_token, verify_token_query
from apps.api.middleware import AccessLogMiddleware, RequestIDMiddleware, SecurityHeadersMiddleware, RateLimitMiddleware
from apps.api.routers import tokens as tokens_router
from apps.api.routers import candles, logs, settings, signals, state, stream, ai, backtest, trades, account, watchlist, bot
from core.config import get_token, settings as config
from core.logging import configure_logging
from core.metrics import setup_metrics_endpoint
from core.version import __version__

# Configure logging once at import time (uvicorn calls this module first)
configure_logging(
    level=os.getenv("LOG_LEVEL", "INFO"),
    json_format=(config.APP_ENV == "production"),
)
logger = logging.getLogger(__name__)


# ── P3-08: Lifespan ───────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("API startup — version=%s env=%s", __version__, config.APP_ENV)

    # Security: refuse to start in production without AUTH_TOKEN
    if config.APP_ENV == "production" and not config.AUTH_TOKEN:
        logger.critical(
            "AUTH_TOKEN is not set but APP_ENV=production. "
            "Refusing to start with unprotected API. "
            "Set AUTH_TOKEN in .env or environment variables."
        )
        raise RuntimeError("AUTH_TOKEN required in production mode")

    if config.APP_ENV == "production" and not config.TOKEN_ENCRYPTION_KEY:
        logger.critical("TOKEN_ENCRYPTION_KEY is required in production mode")
        raise RuntimeError("TOKEN_ENCRYPTION_KEY required in production mode")

    yield
    logger.info("API shutdown — closing resources")
    try:
        from core.events.bus import bus
        await bus.redis.aclose()
    except Exception as e:
        logger.warning("Redis close error on shutdown: %s", e)


app = FastAPI(
    title="Spatial Pinwheel API",
    description="Automated trading bot for MOEX equities. Review + auto-paper modes, AI signal analysis, risk management.",
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

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
@app.get(config.API_PREFIX + "/health", tags=["health"])
async def health():
    components: dict = {}
    ok = True

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
        await bus.redis.ping()
        components["redis"] = {"status": "ok"}
    except Exception as e:
        components["redis"] = {"status": "error", "detail": str(e)}
        if not config.ALLOW_NO_REDIS:
            ok = False

    broker = {"provider": config.BROKER_PROVIDER,
               "sandbox": config.TBANK_SANDBOX if config.BROKER_PROVIDER == "tbank" else False}
    if config.BROKER_PROVIDER == "tbank":
        _tbank_token = get_token("TBANK_TOKEN") or config.TBANK_TOKEN
        _tbank_account = get_token("TBANK_ACCOUNT_ID") or config.TBANK_ACCOUNT_ID
        broker["status"] = "configured" if _tbank_token else "token_missing"
        broker["execution_mode"] = "live_enabled" if config.LIVE_TRADING_ENABLED else "live_disabled"
        broker["live_trading_enabled"] = bool(config.LIVE_TRADING_ENABLED)
        broker["account_id_configured"] = bool(_tbank_account)
        if not _tbank_token or (config.LIVE_TRADING_ENABLED and not _tbank_account):
            ok = False
    else:
        broker["status"] = "paper"
        broker["execution_mode"] = "paper"

    # Read trade_mode from Settings for UI visibility
    try:
        from core.storage.session import SessionLocal as _SL2
        _db2 = _SL2()
        from core.storage.models import Settings as _Sett
        _s2 = _db2.query(_Sett).first()
        from apps.api.status import normalize_trade_mode
        broker["trade_mode"] = normalize_trade_mode(getattr(_s2, 'trade_mode', 'review') if _s2 else 'review')
        _db2.close()
    except Exception:
        broker["trade_mode"] = "unknown"

    components["broker"] = broker

    body = {
        "status": "ok" if ok else "degraded",
        "version": __version__,
        "commit": os.getenv("GIT_COMMIT", "HEAD")[:7],
        "ts": int(time.time() * 1000),
        "components": components,
    }
    if not ok:
        return JSONResponse(status_code=503, content=body)
    return body


# ── P1-04: Routers with auth ──────────────────────────────────────────────────
_auth = [Depends(verify_token)]

app.include_router(settings.router,  prefix=config.API_PREFIX + "/settings",     tags=["settings"],    dependencies=_auth)
app.include_router(signals.router,   prefix=config.API_PREFIX + "/signals",      tags=["signals"],     dependencies=_auth)
app.include_router(logs.router,      prefix=config.API_PREFIX + "/decision-log", tags=["logs"],        dependencies=_auth)
app.include_router(state.router,     prefix=config.API_PREFIX + "/state",        tags=["state"],       dependencies=_auth)
app.include_router(candles.router,   prefix=config.API_PREFIX + "/candles",      tags=["candles"],     dependencies=_auth)
app.include_router(backtest.router, prefix=config.API_PREFIX + "/backtest",    tags=["backtest"], dependencies=_auth)
app.include_router(ai.router,        prefix=config.API_PREFIX + "/ai",           tags=["ai"],          dependencies=_auth)
app.include_router(trades.router,    prefix=config.API_PREFIX + "/trades",       tags=["trades"],      dependencies=_auth)
app.include_router(account.router,   prefix=config.API_PREFIX + "/account",      tags=["account"],     dependencies=_auth)
app.include_router(watchlist.router, prefix=config.API_PREFIX + "/watchlist",    tags=["watchlist"],   dependencies=_auth)
app.include_router(watchlist.router, prefix=config.API_PREFIX + "/instruments",  tags=["instruments"], dependencies=_auth)
app.include_router(bot.router,       prefix=config.API_PREFIX + "/bot",          tags=["bot"],         dependencies=_auth)
app.include_router(stream.router,    prefix=config.API_PREFIX,                   tags=["stream"],
                   dependencies=[Depends(verify_token_query)])
app.include_router(tokens_router.router, prefix=config.API_PREFIX + "/tokens", tags=["tokens"])
