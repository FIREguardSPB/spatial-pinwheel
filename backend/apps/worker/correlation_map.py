from __future__ import annotations

from sqlalchemy.orm import Session

from core.storage.models import Position


def build_correlation_candles_map(db: Session, aggregator, ticker: str, candle_history: list[dict]) -> dict[str, list[dict]] | None:
    if aggregator is None:
        return None
    instruments = {ticker}
    try:
        open_positions = (
            db.query(Position)
            .filter(Position.qty > 0, Position.instrument_id != ticker)
            .all()
        )
    except Exception:
        open_positions = []
    for pos in open_positions or []:
        instrument_id = str(getattr(pos, 'instrument_id', '') or '')
        if instrument_id:
            instruments.add(instrument_id)

    candles_map: dict[str, list[dict]] = {}
    for instrument_id in instruments:
        if instrument_id == ticker:
            candles_map[instrument_id] = candle_history
            continue
        candles_map[instrument_id] = aggregator.get_history(instrument_id)
    return candles_map
