from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import List

_REMOTE_FETCH_COOLDOWN_SEC = 300
_REMOTE_FETCH_STATE: dict[str, float] = {}

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from apps.api.deps import verify_token
from core.models.schemas import Candle
from core.storage.repos import candles as candle_repo
from core.storage.session import get_db

router = APIRouter(dependencies=[Depends(verify_token)])
logger = logging.getLogger(__name__)


def _tf_seconds(tf: str) -> int:
    return {
        "1m": 60,
        "5m": 5 * 60,
        "15m": 15 * 60,
        "1h": 60 * 60,
        "4h": 4 * 60 * 60,
        "1d": 24 * 60 * 60,
        "1w": 7 * 24 * 60 * 60,
    }.get(tf, 60)


def _allow_remote_fetch(cache_key: str) -> bool:
    now = time.monotonic()
    allowed_at = float(_REMOTE_FETCH_STATE.get(cache_key) or 0.0)
    if allowed_at > now:
        return False
    _REMOTE_FETCH_STATE[cache_key] = now + _REMOTE_FETCH_COOLDOWN_SEC
    return True


@router.get("/{ticker}", response_model=List[Candle])
async def get_candles(ticker: str, tf: str = "15m", db: Session = Depends(get_db)):
    from core.config import get_token, settings

    try:
        cached = candle_repo.list_candles(db, ticker, tf, limit=500)
    except Exception as exc:
        logger.error("Failed to read candle cache for %s/%s", ticker, tf, exc_info=exc)
        cached = []

    runtime_tbank_token = get_token("TBANK_TOKEN") or settings.TBANK_TOKEN
    runtime_tbank_account = get_token("TBANK_ACCOUNT_ID") or settings.TBANK_ACCOUNT_ID
    can_fetch_market = bool(runtime_tbank_token)

    if cached:
        return cached

    cache_key = f"{ticker}:{tf}"
    if can_fetch_market and _allow_remote_fetch(cache_key):
        # Cold-start fallback only. If local cache already exists, we serve it as-is
        # and let the worker refresh market data, instead of hammering T-Bank every 15s.
        from apps.broker.tbank import TBankGrpcAdapter
        try:
            adapter = TBankGrpcAdapter(
                token=runtime_tbank_token,
                account_id=runtime_tbank_account,
                sandbox=settings.TBANK_SANDBOX,
            )
            to_dt = datetime.now(timezone.utc)
            from_dt = to_dt - timedelta(days=2 if tf in {"1h", "4h", "1d", "1w"} else 1)
            candles = await adapter.get_candles(ticker, from_dt, to_dt, interval_str=tf)
            await adapter.close()
            candles.sort(key=lambda x: x["time"])
            if candles:
                candle_repo.upsert_candles(db, instrument_id=ticker, timeframe=tf, candles=candles, source="api")
                return candles
        except Exception as e:
            logger.warning("Fallback fetch candles failed for %s: %s", ticker, e, exc_info=True)
    elif can_fetch_market:
        logger.info("Skip remote candle fetch for %s/%s, empty cache still under cooldown", ticker, tf)

    raise HTTPException(status_code=503, detail={'message': 'No real candle data available', 'instrument_id': ticker, 'timeframe': tf})

