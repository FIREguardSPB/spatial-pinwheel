"""
P5-06: Correlation filter — blocks new positions highly correlated with existing ones.

MOEX tickers like SBER, GAZP, LKOH often move in sync.
Opening multiple correlated positions multiplies risk without diversifying.

Integration in RiskManager.check_new_signal():
    ok, msg = check_correlation(db, signal.instrument_id, candles_map, threshold=0.8)
    if not ok: BLOCK
"""
from __future__ import annotations

import logging
import math

logger = logging.getLogger(__name__)


def _returns(closes: list[float]) -> list[float]:
    """Compute simple log-returns from a close price series."""
    result = []
    for i in range(1, len(closes)):
        prev = closes[i - 1]
        curr = closes[i]
        if prev > 1e-9:
            result.append(math.log(curr / prev))
        else:
            result.append(0.0)
    return result


def calc_correlation(returns_a: list[float], returns_b: list[float], period: int = 50) -> float:
    """
    Pearson correlation of the last `period` log-returns.
    Returns -1.0 .. 1.0, or 0.0 if not enough data.
    """
    n = min(len(returns_a), len(returns_b), period)
    if n < 10:
        return 0.0

    a = returns_a[-n:]
    b = returns_b[-n:]

    mean_a = sum(a) / n
    mean_b = sum(b) / n

    cov   = sum((a[i] - mean_a) * (b[i] - mean_b) for i in range(n)) / n
    std_a = math.sqrt(sum((x - mean_a) ** 2 for x in a) / n)
    std_b = math.sqrt(sum((x - mean_b) ** 2 for x in b) / n)

    if std_a < 1e-12 or std_b < 1e-12:
        return 0.0

    return round(cov / (std_a * std_b), 4)


def check_correlation(
    db,
    new_instrument_id: str,
    candles_map: dict[str, list[dict]],
    threshold: float = 0.8,
    max_correlated: int = 2,
    period: int = 50,
) -> tuple[bool, str]:
    """
    Check if opening a position in new_instrument_id would exceed correlation limits.

    Args:
        db:                SQLAlchemy session.
        new_instrument_id: Instrument being considered.
        candles_map:       {instrument_id: candles_list} for ALL instruments being tracked.
                           Must include new_instrument_id.
        threshold:         Max allowed correlation (e.g. 0.8).
        max_correlated:    Max existing positions allowed to be correlated above threshold.
        period:            Number of returns to use.

    Returns:
        (True, "OK") or (False, reason_string)
    """
    from core.storage.models import Position

    open_positions = (
        db.query(Position)
        .filter(Position.qty > 0, Position.instrument_id != new_instrument_id)
        .all()
    )

    if not open_positions:
        return True, "OK"

    new_candles = candles_map.get(new_instrument_id, [])
    if len(new_candles) < 15:
        return True, "Not enough data for correlation check"

    new_closes = [float(c["close"]) for c in new_candles]
    new_rets = _returns(new_closes)

    correlated_count = 0
    violations = []

    for pos in open_positions:
        existing_candles = candles_map.get(pos.instrument_id, [])
        if len(existing_candles) < 15:
            continue

        existing_closes = [float(c["close"]) for c in existing_candles]
        existing_rets = _returns(existing_closes)

        corr = calc_correlation(new_rets, existing_rets, period=period)
        logger.debug("Correlation %s vs %s = %.3f", new_instrument_id, pos.instrument_id, corr)

        if abs(corr) >= threshold:
            correlated_count += 1
            violations.append(f"{pos.instrument_id} (corr={corr:.2f})")

    if correlated_count >= max_correlated:
        return False, (
            f"Correlation limit: {new_instrument_id} correlates ≥{threshold} "
            f"with {correlated_count} open position(s): {', '.join(violations)}"
        )

    return True, "OK"
