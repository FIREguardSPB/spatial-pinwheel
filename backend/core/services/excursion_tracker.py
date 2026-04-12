from __future__ import annotations

from decimal import Decimal
from typing import Any



def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _set_decimal_attr(obj: Any, name: str, value: float | None) -> None:
    if value is None:
        setattr(obj, name, None)
        return
    setattr(obj, name, Decimal(str(round(float(value), 6))))


def update_position_excursion(db: Any, position: Any, current_price: float, *, ts_ms: int, bar_index: int | None = None, phase: str = 'tick') -> dict[str, float | int | bool | None]:
    try:
        from core.storage.models import PositionExcursion
    except Exception:  # pragma: no cover - fallback for lightweight unit tests
        class PositionExcursion:  # type: ignore
            def __init__(self, **kwargs):
                for k, v in kwargs.items():
                    setattr(self, k, v)
    entry = _safe_float(getattr(position, 'avg_price', 0.0), 0.0)
    qty = _safe_float(getattr(position, 'qty', 0.0), 0.0)
    opened_qty = max(qty, _safe_float(getattr(position, 'opened_qty', qty), qty))
    realized = _safe_float(getattr(position, 'realized_pnl', 0.0), 0.0)
    sign = 1.0 if str(getattr(position, 'side', 'BUY') or 'BUY').upper() == 'BUY' else -1.0
    unreal = sign * qty * (float(current_price) - entry)
    lifecycle = realized + unreal
    notional = max(1e-9, abs(entry * max(opened_qty, 1e-9)))
    lifecycle_pct = (lifecycle / notional) * 100.0

    prev_mfe = _safe_float(getattr(position, 'mfe_total_pnl', None), lifecycle)
    prev_mae = _safe_float(getattr(position, 'mae_total_pnl', None), lifecycle)
    new_mfe = lifecycle if lifecycle > prev_mfe else prev_mfe
    new_mae = lifecycle if lifecycle < prev_mae else prev_mae
    mfe_pct = (new_mfe / notional) * 100.0
    mae_pct = (new_mae / notional) * 100.0

    best_price = _safe_float(getattr(position, 'best_price_seen', None), float(current_price))
    worst_price = _safe_float(getattr(position, 'worst_price_seen', None), float(current_price))
    if sign > 0:
        best_price = max(best_price, float(current_price))
        worst_price = min(worst_price, float(current_price))
    else:
        best_price = min(best_price, float(current_price)) if best_price else float(current_price)
        worst_price = max(worst_price, float(current_price))

    _set_decimal_attr(position, 'mfe_total_pnl', new_mfe)
    _set_decimal_attr(position, 'mae_total_pnl', new_mae)
    _set_decimal_attr(position, 'mfe_pct', mfe_pct)
    _set_decimal_attr(position, 'mae_pct', mae_pct)
    _set_decimal_attr(position, 'best_price_seen', best_price)
    _set_decimal_attr(position, 'worst_price_seen', worst_price)
    position.excursion_samples = int(getattr(position, 'excursion_samples', 0) or 0) + 1
    position.excursion_updated_ts = int(ts_ms)

    point_kwargs = {
        'trace_id': getattr(position, 'trace_id', None),
        'signal_id': getattr(position, 'opened_signal_id', None),
        'instrument_id': position.instrument_id,
        'ts': int(ts_ms),
        'phase': phase,
        'bar_index': bar_index,
        'mark_price': Decimal(str(round(float(current_price), 6))),
        'unrealized_pnl': Decimal(str(round(unreal, 6))),
        'realized_pnl': Decimal(str(round(realized, 6))),
        'lifecycle_pnl': Decimal(str(round(lifecycle, 6))),
        'mfe_total_pnl': Decimal(str(round(new_mfe, 6))),
        'mae_total_pnl': Decimal(str(round(new_mae, 6))),
        'mfe_pct': Decimal(str(round(mfe_pct, 4))),
        'mae_pct': Decimal(str(round(mae_pct, 4))),
        'is_new_mfe': bool(lifecycle > prev_mfe),
        'is_new_mae': bool(lifecycle < prev_mae),
    }
    try:
        point = PositionExcursion(**point_kwargs)
    except TypeError:  # pragma: no cover - lightweight tests may provide no-init stubs
        point = PositionExcursion()
        for key, value in point_kwargs.items():
            setattr(point, key, value)
    db.add(point)
    return {
        'current_lifecycle_pnl': round(lifecycle, 6),
        'current_lifecycle_pct': round(lifecycle_pct, 4),
        'mfe_total_pnl': round(new_mfe, 6),
        'mae_total_pnl': round(new_mae, 6),
        'mfe_pct': round(mfe_pct, 4),
        'mae_pct': round(mae_pct, 4),
        'excursion_samples': int(getattr(position, 'excursion_samples', 0) or 0),
        'is_new_mfe': bool(lifecycle > prev_mfe),
        'is_new_mae': bool(lifecycle < prev_mae),
    }
