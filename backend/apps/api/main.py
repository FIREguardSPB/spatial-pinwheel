from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apps.api.routers import settings, signals, logs, state, stream, candles
from core.config import settings as config

from core.version import __version__

app = FastAPI(title="Trading Bot API", version=__version__)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For MVP
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health
@app.get(config.API_PREFIX + "/health")
async def health():
    import time
    import os

    # Broker Info
    broker_info = {
        "provider": config.BROKER_PROVIDER,
        "sandbox": config.TBANK_SANDBOX if config.BROKER_PROVIDER == "tbank" else False,
        "status": "connected",  # Ideally check adapter health
    }

    return {
        "status": "ok",
        "version": __version__,
        "commit": os.getenv("GIT_COMMIT", "HEAD")[:7],
        "ts": int(time.time() * 1000),
        "broker": broker_info,
    }


# Routers
app.include_router(settings.router, prefix=config.API_PREFIX + "/settings", tags=["settings"])
app.include_router(signals.router, prefix=config.API_PREFIX + "/signals", tags=["signals"])
app.include_router(logs.router, prefix=config.API_PREFIX + "/decision-log", tags=["logs"])
app.include_router(state.router, prefix=config.API_PREFIX + "/state", tags=["state"])
app.include_router(stream.router, prefix=config.API_PREFIX, tags=["stream"])
app.include_router(candles.router, prefix=config.API_PREFIX + "/candles", tags=["candles"])
