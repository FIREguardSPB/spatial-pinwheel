from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
from typing import Any

from apps.worker.decision_engine.indicators import calc_atr


_ECON_BLOCK_CODES = {
    'COSTS_TOO_HIGH',
    'RR_TOO_LOW',
    'ECONOMIC_INVALID',
    'ECONOMIC_LOW_PRICE',
    'ECONOMIC_MICRO_LEVELS',
    'ECONOMIC_PROFIT_TOO_SMALL',
    'ECONOMIC_MIN_TRADE_VALUE',
    'ECONOMIC_COMMISSION_DOMINANCE',
}


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _num(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return float(default)
        return float(value)
    except Exception:
        return float(default)


def _pct_abs(entry: float, other: float) -> float:
    if entry <= 0:
        return 0.0
    return abs(entry - other) / entry * 100.0


@dataclass
class GeometryOptimizationResult:
    applied: bool
    phase: str
    geometry_source: str
    action: str
    notes: list[str]
    original_entry: float
    original_sl: float
    original_tp: float
    optimized_entry: float
    optimized_sl: float
    optimized_tp: float
    original_r: float
    optimized_r: float
    min_stop_pct: float
    target_rr: float
    atr14: float
    suggested_timeframe: str | None = None
    suggested_hold_bars: int | None = None

    def to_meta(self) -> dict[str, Any]:
        payload = asdict(self)
        payload['notes'] = list(self.notes or [])
        return payload


def _strategy_name(signal_data: dict[str, Any], adaptive_plan: dict[str, Any] | None) -> str:
    meta = dict(signal_data.get('meta') or {})
    return str(
        meta.get('strategy_name')
        or meta.get('strategy')
        or ((adaptive_plan or {}).get('strategy_name'))
        or 'unknown'
    )


def _regime_name(adaptive_plan: dict[str, Any] | None, event_regime: dict[str, Any] | None) -> str:
    return str((adaptive_plan or {}).get('regime') or (event_regime or {}).get('regime') or 'balanced')


def _target_rr(settings: Any, strategy_name: str, regime: str, event_regime: dict[str, Any] | None, evaluation_metrics: dict[str, Any] | None) -> float:
    configured = _num(getattr(settings, 'rr_target', None), 0.0)
    if configured > 0:
        rr_target = configured
    elif 'mean_reversion' in strategy_name:
        rr_target = 1.2
    elif 'vwap' in strategy_name:
        rr_target = 1.45
    else:
        rr_target = 1.6

    if regime in {'trend', 'expansion_trend'}:
        rr_target += 0.15
    elif regime in {'chop', 'compression'}:
        rr_target -= 0.1

    action = str((event_regime or {}).get('action') or 'observe')
    if action == 'lean_with_catalyst':
        rr_target += 0.1
    elif action == 'de_risk':
        rr_target -= 0.1

    metrics = evaluation_metrics or {}
    if _num(metrics.get('commission_dominance_ratio'), 0.0) >= 0.9:
        rr_target += 0.15
    if metrics.get('economic_filter_valid') is False:
        rr_target += 0.1
    if _num(metrics.get('expected_profit_after_costs_rub'), 1.0) <= 0:
        rr_target += 0.15

    return _clamp(rr_target, 1.05, 2.4)


def _minimum_stop_pct(settings: Any, entry: float, atr14: float, strategy_name: str, regime: str, evaluation_metrics: dict[str, Any] | None) -> float:
    configured_min = _num(getattr(settings, 'min_sl_distance_pct', None), 0.08)
    atr_pct = (atr14 / entry * 100.0) if entry > 0 and atr14 > 0 else 0.0
    if 'mean_reversion' in strategy_name:
        atr_floor = atr_pct * 0.42
    elif 'vwap' in strategy_name:
        atr_floor = atr_pct * 0.55
    else:
        atr_floor = atr_pct * 0.7

    if regime in {'trend', 'expansion_trend'}:
        atr_floor *= 1.1
    elif regime in {'chop', 'compression'}:
        atr_floor *= 0.85

    result = max(configured_min, atr_floor)
    metrics = evaluation_metrics or {}
    result = max(result, _num(metrics.get('min_required_sl_pct'), 0.0))
    if _num(metrics.get('commission_dominance_ratio'), 0.0) >= 1.0:
        result *= 1.18
    return _clamp(result, configured_min, max(configured_min, 3.0))


def should_retry_geometry(evaluation: Any) -> bool:
    metrics = dict(getattr(evaluation, 'metrics', {}) or {})
    if metrics.get('economic_filter_valid') is False:
        return True
    if _num(metrics.get('net_rr'), 1.0) < 1.0:
        return True
    if _num(metrics.get('commission_dominance_ratio'), 0.0) >= 0.9:
        return True
    reasons = list(getattr(evaluation, 'reasons', []) or [])
    for reason in reasons:
        code = str(getattr(reason, 'code', '') or '').upper()
        if code in _ECON_BLOCK_CODES:
            return True
    return False


def optimize_signal_geometry(
    signal_data: dict[str, Any],
    candles: list[dict[str, Any]],
    settings: Any,
    *,
    adaptive_plan: dict[str, Any] | None = None,
    event_regime: dict[str, Any] | None = None,
    evaluation_metrics: dict[str, Any] | None = None,
    phase: str = 'initial',
) -> tuple[dict[str, Any], GeometryOptimizationResult]:
    payload = deepcopy(signal_data)
    meta = dict(payload.get('meta') or {})
    side = str(payload.get('side') or '')
    entry = _num(payload.get('entry'), 0.0)
    sl = _num(payload.get('sl'), 0.0)
    tp = _num(payload.get('tp'), 0.0)
    original_r = _num(payload.get('r'), 0.0)

    closes = [float(c.get('close') or 0.0) for c in candles]
    highs = [float(c.get('high') or 0.0) for c in candles]
    lows = [float(c.get('low') or 0.0) for c in candles]
    atr14 = calc_atr(highs, lows, closes, 14) if closes else None
    atr14 = float(atr14 or 0.0)
    if atr14 <= 0 and entry > 0:
        atr14 = entry * 0.0045

    if entry <= 0 or sl <= 0 or tp <= 0 or side not in {'BUY', 'SELL'}:
        result = GeometryOptimizationResult(
            applied=False,
            phase=phase,
            geometry_source='strategy',
            action='invalid_signal',
            notes=['signal geometry invalid, optimizer skipped'],
            original_entry=entry,
            original_sl=sl,
            original_tp=tp,
            optimized_entry=entry,
            optimized_sl=sl,
            optimized_tp=tp,
            original_r=original_r,
            optimized_r=original_r,
            min_stop_pct=0.0,
            target_rr=0.0,
            atr14=atr14,
        )
        meta['geometry_optimizer'] = result.to_meta()
        payload['meta'] = meta
        return payload, result

    strategy_name = _strategy_name(payload, adaptive_plan)
    regime = _regime_name(adaptive_plan, event_regime)
    target_rr = _target_rr(settings, strategy_name, regime, event_regime, evaluation_metrics)
    min_stop_pct = _minimum_stop_pct(settings, entry, atr14, strategy_name, regime, evaluation_metrics)

    original_stop_abs = abs(entry - sl)
    original_target_abs = abs(tp - entry)
    desired_stop_abs = max(original_stop_abs, entry * (min_stop_pct / 100.0))
    desired_target_abs = max(original_target_abs, desired_stop_abs * target_rr)

    notes: list[str] = []
    action_bits: list[str] = []

    if desired_stop_abs > original_stop_abs * 1.02:
        action_bits.append('widened_sl')
        notes.append(f'stop widened from {original_stop_abs:.4f} to {desired_stop_abs:.4f}')
    if desired_target_abs > original_target_abs * 1.02:
        action_bits.append('extended_tp')
        notes.append(f'target extended from {original_target_abs:.4f} to {desired_target_abs:.4f}')

    if side == 'BUY':
        new_sl = entry - desired_stop_abs
        new_tp = entry + desired_target_abs
    else:
        new_sl = entry + desired_stop_abs
        new_tp = entry - desired_target_abs

    new_r = desired_target_abs / desired_stop_abs if desired_stop_abs > 1e-9 else original_r

    base_hold = int((adaptive_plan or {}).get('hold_bars') or getattr(settings, 'time_stop_bars', 12) or 12)
    hold_boost = max(0, int(round((desired_target_abs / max(original_target_abs, 1e-9)) - 1.0) * 4))
    if regime in {'trend', 'expansion_trend'} and desired_target_abs > original_target_abs * 1.05:
        hold_boost += 1
    suggested_hold = max(base_hold, min(base_hold + 8, base_hold + hold_boost))
    if suggested_hold > base_hold:
        action_bits.append('extended_hold')
        notes.append(f'hold extended from {base_hold} to {suggested_hold} bars')

    suggested_tf = None
    if phase == 'rescue' and desired_stop_abs > max(original_stop_abs * 1.35, atr14 * 0.9):
        suggested_tf = str(getattr(settings, 'higher_timeframe', '5m') or '5m')
        notes.append(f'geometry suggests slower confirmation on {suggested_tf}')

    applied = bool(action_bits)
    if adaptive_plan is not None and suggested_hold > int((adaptive_plan or {}).get('hold_bars') or 0):
        adaptive_plan = dict(adaptive_plan)
        adaptive_plan['hold_bars'] = suggested_hold
        meta['adaptive_plan'] = adaptive_plan

    payload['sl'] = round(float(new_sl), 6)
    payload['tp'] = round(float(new_tp), 6)
    payload['r'] = round(float(new_r), 4)
    meta['strategy_name'] = meta.get('strategy_name') or strategy_name
    meta['geometry_optimizer'] = GeometryOptimizationResult(
        applied=applied,
        phase=phase,
        geometry_source='optimizer' if applied else 'strategy',
        action='+'.join(action_bits) if action_bits else 'none',
        notes=notes or ['geometry left unchanged'],
        original_entry=entry,
        original_sl=sl,
        original_tp=tp,
        optimized_entry=entry,
        optimized_sl=float(payload['sl']),
        optimized_tp=float(payload['tp']),
        original_r=original_r,
        optimized_r=float(payload['r']),
        min_stop_pct=min_stop_pct,
        target_rr=target_rr,
        atr14=atr14,
        suggested_timeframe=suggested_tf,
        suggested_hold_bars=suggested_hold,
    ).to_meta()
    payload['meta'] = meta
    return payload, GeometryOptimizationResult(
        applied=applied,
        phase=phase,
        geometry_source='optimizer' if applied else 'strategy',
        action='+'.join(action_bits) if action_bits else 'none',
        notes=notes or ['geometry left unchanged'],
        original_entry=entry,
        original_sl=sl,
        original_tp=tp,
        optimized_entry=entry,
        optimized_sl=float(payload['sl']),
        optimized_tp=float(payload['tp']),
        original_r=original_r,
        optimized_r=float(payload['r']),
        min_stop_pct=min_stop_pct,
        target_rr=target_rr,
        atr14=atr14,
        suggested_timeframe=suggested_tf,
        suggested_hold_bars=suggested_hold,
    )
