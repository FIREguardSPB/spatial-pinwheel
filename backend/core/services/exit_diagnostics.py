from __future__ import annotations

from typing import Any


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _hold_utilization_pct(bars_held: int | None, hold_limit_bars: int | None) -> float | None:
    bars = int(bars_held or 0)
    limit = int(hold_limit_bars or 0)
    if limit <= 0:
        return None
    return round((bars / max(1, limit)) * 100.0, 2)


def classify_edge_decay(*, reason: str, net_realized: float, bars_held: int | None = None, hold_limit_bars: int | None = None) -> str:
    reason_u = str(reason or '').upper()
    bars = int(bars_held or 0)
    limit = int(hold_limit_bars or 0)
    util = (bars / max(1, limit)) if limit > 0 else None

    if 'TIME_STOP' in reason_u or 'SESSION_END' in reason_u:
        return 'time_decay'
    if 'ADAPTIVE_PARTIAL' in reason_u:
        return 'managed_trim'
    if reason_u == 'TP':
        if util is not None and util <= 0.5:
            return 'fast_realization'
        return 'target_realization'
    if reason_u == 'SL':
        if util is not None and util <= 0.35:
            return 'early_failure'
        if util is not None and util >= 0.8:
            return 'late_failure'
        return 'stop_loss'
    if net_realized < 0 and util is not None and util >= 0.8:
        return 'late_failure'
    if net_realized > 0 and util is not None and util <= 0.5:
        return 'fast_realization'
    return 'neutral'


def build_exit_diagnostics(
    *,
    position: Any,
    requested_close_price: float | None,
    close_price: float,
    reason: str,
    bars_held: int | None = None,
    hold_limit_bars: int | None = None,
    gross_realized: float = 0.0,
    net_realized: float = 0.0,
    entry_fee: float = 0.0,
    exit_fee: float = 0.0,
    closed_qty: float | None = None,
    now_ms: int | None = None,
) -> dict[str, Any]:
    entry = _safe_float(getattr(position, 'avg_price', 0.0), 0.0)
    qty = _safe_float(closed_qty if closed_qty is not None else getattr(position, 'qty', 0.0), 0.0)
    opened_qty = _safe_float(getattr(position, 'opened_qty', qty), qty)
    sl = _safe_float(getattr(position, 'sl', None), 0.0)
    tp = _safe_float(getattr(position, 'tp', None), 0.0)
    opened_ts = int(getattr(position, 'opened_ts', 0) or 0)
    ts_now = int(now_ms or 0)
    hold_sec = round(max(0.0, (ts_now - opened_ts) / 1000.0), 2) if opened_ts and ts_now else 0.0
    notional = max(1e-9, abs(entry * qty))
    initial_risk_rub = abs(entry - sl) * qty if sl > 0 else 0.0
    intended_reward_rub = abs(tp - entry) * qty if tp > 0 else 0.0
    realized_move_rub = abs(close_price - entry) * qty
    hold_util_pct = _hold_utilization_pct(bars_held, hold_limit_bars)

    requested = _safe_float(requested_close_price, 0.0)
    slippage_bps = round((abs(close_price - requested) / requested) * 10000.0, 3) if requested > 0 else 0.0
    gross_return_pct = round((gross_realized / notional) * 100.0, 4)
    net_return_pct = round((net_realized / notional) * 100.0, 4)
    realized_rr_multiple = round(net_realized / initial_risk_rub, 4) if initial_risk_rub > 0 else None
    tp_capture_ratio = round(realized_move_rub / intended_reward_rub, 4) if intended_reward_rub > 0 else None
    fee_load_pct = round(((entry_fee + exit_fee) / notional) * 100.0, 4)
    edge_decay_state = classify_edge_decay(
        reason=reason,
        net_realized=net_realized,
        bars_held=bars_held,
        hold_limit_bars=hold_limit_bars,
    )
    mfe_total_pnl = _safe_float(getattr(position, 'mfe_total_pnl', None), net_realized)
    mae_total_pnl = _safe_float(getattr(position, 'mae_total_pnl', None), net_realized)
    mfe_pct = _safe_float(getattr(position, 'mfe_pct', None), 0.0)
    mae_pct = _safe_float(getattr(position, 'mae_pct', None), 0.0)
    mfe_capture_ratio = round(net_realized / mfe_total_pnl, 4) if mfe_total_pnl > 1e-9 else None
    mae_recovery_ratio = round(net_realized / abs(mae_total_pnl), 4) if mae_total_pnl < -1e-9 else None
    close_quality = 'neutral'
    if str(reason or '').upper() == 'TP' and (tp_capture_ratio or 0.0) >= 0.85:
        close_quality = 'excellent'
    elif net_realized > 0 and slippage_bps <= 6.0:
        close_quality = 'good'
    elif edge_decay_state in {'time_decay', 'late_failure'}:
        close_quality = 'weak'
    elif net_realized < 0:
        close_quality = 'poor'

    missed_tp_value = max(0.0, intended_reward_rub - realized_move_rub) if intended_reward_rub > 0 else 0.0
    missed_mfe_value = max(0.0, mfe_total_pnl - max(0.0, net_realized)) if mfe_total_pnl > 0 else 0.0
    exit_capture_grade = 'neutral_capture'
    if (tp_capture_ratio or 0.0) >= 0.9 or (mfe_capture_ratio or 0.0) >= 0.75:
        exit_capture_grade = 'excellent_capture'
    elif (tp_capture_ratio or 0.0) >= 0.7 or (mfe_capture_ratio or 0.0) >= 0.55:
        exit_capture_grade = 'strong_capture'
    elif edge_decay_state in {'time_decay', 'late_failure'} or (mfe_capture_ratio or 1.0) < 0.35:
        exit_capture_grade = 'weak_capture'
    elif net_realized < 0:
        exit_capture_grade = 'poor_capture'

    tp_capture_band = 'na' if tp_capture_ratio is None else ('high' if tp_capture_ratio >= 0.8 else ('medium' if tp_capture_ratio >= 0.55 else 'low'))
    mfe_capture_band = 'na' if mfe_capture_ratio is None else ('high' if mfe_capture_ratio >= 0.65 else ('medium' if mfe_capture_ratio >= 0.4 else 'low'))

    return {
        'holding_sec': hold_sec,
        'bars_held': int(bars_held or 0),
        'hold_limit_bars': int(hold_limit_bars or 0),
        'hold_utilization_pct': hold_util_pct,
        'gross_return_pct': gross_return_pct,
        'net_return_pct': net_return_pct,
        'realized_rr_multiple': realized_rr_multiple,
        'tp_capture_ratio': tp_capture_ratio,
        'initial_risk_rub': round(initial_risk_rub, 4),
        'intended_reward_rub': round(intended_reward_rub, 4),
        'realized_move_rub': round(realized_move_rub, 4),
        'fee_load_pct': fee_load_pct,
        'slippage_to_requested_close_bps': slippage_bps,
        'opened_qty': round(opened_qty, 6),
        'closed_qty': round(qty, 6),
        'mfe_total_pnl': round(mfe_total_pnl, 4),
        'mae_total_pnl': round(mae_total_pnl, 4),
        'mfe_pct': round(mfe_pct, 4),
        'mae_pct': round(mae_pct, 4),
        'realized_to_mfe_capture_ratio': mfe_capture_ratio,
        'mae_recovery_ratio': mae_recovery_ratio,
        'missed_tp_value_rub': round(missed_tp_value, 4),
        'missed_mfe_value_rub': round(missed_mfe_value, 4),
        'best_price_seen': round(_safe_float(getattr(position, 'best_price_seen', None), 0.0), 6),
        'worst_price_seen': round(_safe_float(getattr(position, 'worst_price_seen', None), 0.0), 6),
        'excursion_samples': int(getattr(position, 'excursion_samples', 0) or 0),
        'edge_decay_state': edge_decay_state,
        'close_quality': close_quality,
        'exit_capture_grade': exit_capture_grade,
        'tp_capture_band': tp_capture_band,
        'mfe_capture_band': mfe_capture_band,
    }
