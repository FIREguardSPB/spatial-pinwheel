from __future__ import annotations

from typing import Iterable

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from core.storage.models import CandleCache


def list_candles(db: Session, instrument_id: str, timeframe: str, limit: int = 500) -> list[dict]:
    rows = (
        db.query(CandleCache)
        .filter(CandleCache.instrument_id == instrument_id, CandleCache.timeframe == timeframe)
        .order_by(CandleCache.ts.desc())
        .limit(limit)
        .all()
    )
    rows.reverse()
    return [
        {
            "time": int(r.ts),
            "open": float(r.open),
            "high": float(r.high),
            "low": float(r.low),
            "close": float(r.close),
            "volume": int(r.volume or 0),
            "is_complete": True,
        }
        for r in rows
    ]


def _payload(instrument_id: str, timeframe: str, candle: dict, source: str) -> dict:
    return {
        "instrument_id": instrument_id,
        "timeframe": timeframe,
        "ts": int(candle["time"]),
        "open": float(candle["open"]),
        "high": float(candle["high"]),
        "low": float(candle["low"]),
        "close": float(candle["close"]),
        "volume": int(candle.get("volume", 0) or 0),
        "source": source,
    }


def upsert_candles(db: Session, *, instrument_id: str, timeframe: str, candles: Iterable[dict], source: str = "worker") -> int:
    rows = [_payload(instrument_id, timeframe, candle, source) for candle in candles]
    if not rows:
        return 0

    dialect = (getattr(getattr(db, 'bind', None), 'dialect', None) and db.bind.dialect.name) or ''
    if dialect == 'postgresql':
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        stmt = pg_insert(CandleCache).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=['instrument_id', 'timeframe', 'ts'],
            set_={
                'open': stmt.excluded.open,
                'high': stmt.excluded.high,
                'low': stmt.excluded.low,
                'close': stmt.excluded.close,
                'volume': stmt.excluded.volume,
                'source': stmt.excluded.source,
            },
        )
        db.execute(stmt)
        db.commit()
        return len(rows)

    count = 0
    for payload in rows:
        try:
            row = (
                db.query(CandleCache)
                .filter(
                    CandleCache.instrument_id == payload['instrument_id'],
                    CandleCache.timeframe == payload['timeframe'],
                    CandleCache.ts == payload['ts'],
                )
                .first()
            )
            if row is None:
                db.add(CandleCache(**payload))
            else:
                for key, value in payload.items():
                    setattr(row, key, value)
            db.commit()
            count += 1
        except IntegrityError:
            db.rollback()
            row = (
                db.query(CandleCache)
                .filter(
                    CandleCache.instrument_id == payload['instrument_id'],
                    CandleCache.timeframe == payload['timeframe'],
                    CandleCache.ts == payload['ts'],
                )
                .first()
            )
            if row is not None:
                for key, value in payload.items():
                    setattr(row, key, value)
                db.commit()
                count += 1
    return count
