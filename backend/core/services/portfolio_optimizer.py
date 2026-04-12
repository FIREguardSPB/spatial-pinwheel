from __future__ import annotations

import math
from typing import Any

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _estimate_mark_price(position: Any) -> float:
    mark = _safe_float(getattr(position, "last_mark_price", 0.0), 0.0)
    if mark > 0:
        return mark
    avg = _safe_float(getattr(position, "avg_price", 0.0), 0.0)
    qty = _safe_float(getattr(position, "qty", 0.0), 0.0)
    if qty <= 0 or avg <= 0:
        return avg
    unreal = _safe_float(getattr(position, "unrealized_pnl", 0.0), 0.0)
    sign = 1.0 if str(getattr(position, "side", "BUY") or "BUY").upper() == "BUY" else -1.0
    derived = avg + unreal / max(1e-9, sign * qty)
    return derived if derived > 0 else avg


def _position_notional(position: Any) -> float:
    return max(0.0, _safe_float(getattr(position, "qty", 0.0), 0.0) * _estimate_mark_price(position))


def _load_recent_candles(db: Any, instrument_id: str, *, lookback_bars: int) -> list[dict[str, float]]:
    from core.storage.models import CandleCache
    rows = (
        db.query(CandleCache)
        .filter(CandleCache.instrument_id == instrument_id, CandleCache.timeframe == '5m')
        .order_by(CandleCache.ts.desc())
        .limit(max(lookback_bars, 20))
        .all()
    )
    if not rows:
        rows = (
            db.query(CandleCache)
            .filter(CandleCache.instrument_id == instrument_id, CandleCache.timeframe == '1m')
            .order_by(CandleCache.ts.desc())
            .limit(max(lookback_bars, 20))
            .all()
        )
    items = [
        {
            'ts': int(r.ts),
            'close': _safe_float(r.close, 0.0),
        }
        for r in reversed(rows)
        if _safe_float(r.close, 0.0) > 0
    ]
    return items


def _returns_from_candles(candles: list[dict[str, float]]) -> list[tuple[int, float]]:
    out: list[tuple[int, float]] = []
    prev = None
    for row in candles:
        close = _safe_float(row.get('close'), 0.0)
        if close <= 0:
            continue
        if prev and prev > 0:
            out.append((int(row.get('ts') or 0), (close / prev) - 1.0))
        prev = close
    return out


def _align_returns(series_by_instrument: dict[str, list[tuple[int, float]]], *, min_history_bars: int) -> tuple[list[str], list[list[float]], dict[tuple[str, str], float]]:
    if not series_by_instrument:
        return [], [], {}
    timestamp_sets = [set(ts for ts, _ in rows) for rows in series_by_instrument.values() if rows]
    if not timestamp_sets:
        return [], [], {}
    common = set.intersection(*timestamp_sets) if len(timestamp_sets) > 1 else timestamp_sets[0]
    ordered_ts = sorted(common)
    if len(ordered_ts) < min_history_bars:
        ordered_ts = []
        for rows in series_by_instrument.values():
            ordered_ts = sorted(ts for ts, _ in rows)
            if len(ordered_ts) >= min_history_bars:
                break
    instruments = list(series_by_instrument.keys())
    matrix: list[list[float]] = []
    pair_corr: dict[tuple[str, str], float] = {}
    value_maps = {k: {ts: ret for ts, ret in rows} for k, rows in series_by_instrument.items()}
    for instrument in instruments:
        if ordered_ts:
            vec = [value_maps[instrument][ts] for ts in ordered_ts if ts in value_maps[instrument]]
        else:
            vec = [ret for _, ret in series_by_instrument[instrument]]
        matrix.append(vec)
    for i, a in enumerate(instruments):
        for j, b in enumerate(instruments):
            if j < i:
                continue
            corr = _correlation(matrix[i], matrix[j]) if matrix[i] and matrix[j] else 0.0
            pair_corr[(a, b)] = corr
            pair_corr[(b, a)] = corr
    return instruments, matrix, pair_corr


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _variance(values: list[float]) -> float:
    if len(values) <= 1:
        return 0.0
    mu = _mean(values)
    return sum((v - mu) ** 2 for v in values) / (len(values) - 1)


def _std(values: list[float]) -> float:
    return math.sqrt(max(0.0, _variance(values)))


def _covariance(a: list[float], b: list[float]) -> float:
    n = min(len(a), len(b))
    if n <= 1:
        return 0.0
    a = a[-n:]
    b = b[-n:]
    ma = _mean(a)
    mb = _mean(b)
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (n - 1)


def _correlation(a: list[float], b: list[float]) -> float:
    sa = _std(a)
    sb = _std(b)
    if sa <= 1e-12 or sb <= 1e-12:
        return 0.0
    return _clamp(_covariance(a, b) / (sa * sb), -1.0, 1.0)


def _matrix_vec(cov: list[list[float]], weights: list[float]) -> list[float]:
    out = []
    for row in cov:
        out.append(sum(v * w for v, w in zip(row, weights)))
    return out


def _portfolio_vol(cov: list[list[float]], weights: list[float]) -> float:
    mv = _matrix_vec(cov, weights)
    variance = sum(w * m for w, m in zip(weights, mv))
    return math.sqrt(max(0.0, variance))


def _risk_contributions(cov: list[list[float]], weights: list[float]) -> list[float]:
    port_vol = _portfolio_vol(cov, weights)
    if port_vol <= 1e-12:
        return [0.0 for _ in weights]
    marginal = _matrix_vec(cov, weights)
    return [w * m / port_vol for w, m in zip(weights, marginal)]


def _normalize_positive(values: list[float]) -> list[float]:
    cleaned = [max(0.0, v) for v in values]
    total = sum(cleaned)
    if total <= 1e-12:
        n = max(1, len(values))
        return [1.0 / n for _ in values]
    return [v / total for v in cleaned]


def _latest_regime_multiplier(db: Any, instrument_id: str, *, settings: Any) -> float:
    from core.storage.models import SymbolEventRegime
    row = (
        db.query(SymbolEventRegime)
        .filter(SymbolEventRegime.instrument_id == instrument_id)
        .order_by(SymbolEventRegime.ts.desc())
        .first()
    )
    if not row:
        return 1.0
    action = str(getattr(row, 'action', '') or '').lower()
    severity = _safe_float(getattr(row, 'severity', 0.0), 0.0)
    risk_off = _safe_float(getattr(settings, 'portfolio_optimizer_regime_risk_off_multiplier', 0.70), 0.70)
    if action == 'de_risk':
        return max(0.35, risk_off - min(0.20, severity * 0.15))
    if action == 'trade_smaller':
        return max(0.45, risk_off + 0.10)
    if action == 'lean_with_catalyst':
        return min(1.25, 1.05 + min(0.20, severity * 0.12))
    return 1.0


def _incoming_regime_multiplier(signal_like: Any, settings: Any) -> float:
    meta = dict(getattr(signal_like, 'meta', None) or signal_like.get('meta') or {}) if isinstance(signal_like, dict) else dict(getattr(signal_like, 'meta', None) or {})
    regime = dict(meta.get('event_regime') or {})
    action = str(regime.get('action') or '').lower()
    severity = _safe_float(regime.get('severity'), 0.0)
    risk_off = _safe_float(getattr(settings, 'portfolio_optimizer_regime_risk_off_multiplier', 0.70), 0.70)
    if action == 'de_risk':
        return max(0.35, risk_off - min(0.20, severity * 0.15))
    if action == 'trade_smaller':
        return max(0.45, risk_off + 0.10)
    if action == 'lean_with_catalyst':
        return min(1.25, 1.05 + min(0.20, severity * 0.12))
    return 1.0


def build_portfolio_optimizer_overlay(db: Any, settings: Any, signal_like: Any) -> dict[str, Any]:
    from core.storage.models import Position
    enabled = bool(getattr(settings, 'portfolio_optimizer_enabled', True))
    if isinstance(signal_like, dict):
        instrument_id = str(signal_like.get('instrument_id') or '')
        meta = dict(signal_like.get('meta') or {})
    else:
        instrument_id = str(getattr(signal_like, 'instrument_id', '') or '')
        meta = dict(getattr(signal_like, 'meta', None) or {})
    if not enabled or not instrument_id:
        return {'enabled': False, 'instrument_id': instrument_id, 'optimizer_risk_multiplier': 1.0, 'trim_candidates': []}

    lookback_bars = max(40, int(getattr(settings, 'portfolio_optimizer_lookback_bars', 180) or 180))
    min_history_bars = max(20, int(getattr(settings, 'portfolio_optimizer_min_history_bars', 60) or 60))
    max_pair_corr = _safe_float(getattr(settings, 'portfolio_optimizer_max_pair_corr', 0.85), 0.85)
    target_buffer_pct = _safe_float(getattr(settings, 'portfolio_optimizer_target_weight_buffer_pct', 2.5), 2.5)
    balance = max(1.0, _safe_float(getattr(settings, 'account_balance', 100000), 100000.0))
    max_position_cap_pct = _safe_float(getattr(settings, 'max_position_notional_pct_balance', 10.0), 10.0)

    open_positions = db.query(Position).filter(Position.qty > 0).all()
    instrument_ids = [p.instrument_id for p in open_positions]
    if instrument_id not in instrument_ids:
        instrument_ids.append(instrument_id)

    histories = {iid: _returns_from_candles(_load_recent_candles(db, iid, lookback_bars=lookback_bars)) for iid in instrument_ids}
    instruments, matrix, pair_corr = _align_returns(histories, min_history_bars=min_history_bars)
    if not instruments:
        return {'enabled': False, 'instrument_id': instrument_id, 'optimizer_risk_multiplier': 1.0, 'trim_candidates': [], 'reason': 'insufficient_history'}

    vol_by_instrument = {iid: max(1e-5, _std(matrix[instruments.index(iid)])) for iid in instruments}
    current_weights: list[float] = []
    regime_mults: list[float] = []
    target_scores: list[float] = []
    weight_by_instrument: dict[str, float] = {}
    for iid in instruments:
        pos = next((p for p in open_positions if p.instrument_id == iid), None)
        current_weight = (_position_notional(pos) / balance) if pos is not None else 0.0
        weight_by_instrument[iid] = current_weight
        current_weights.append(current_weight)
        regime_mult = _incoming_regime_multiplier({'meta': meta}, settings) if iid == instrument_id else _latest_regime_multiplier(db, iid, settings=settings)
        regime_mults.append(regime_mult)
        target_scores.append(regime_mult / max(1e-5, vol_by_instrument[iid]))

    target_weights = _normalize_positive(target_scores)
    n = len(instruments)
    cov = [[0.0 for _ in range(n)] for _ in range(n)]
    for i in range(n):
        for j in range(n):
            cov[i][j] = _covariance(matrix[i], matrix[j])
            if i == j and cov[i][j] <= 1e-12:
                cov[i][j] = vol_by_instrument[instruments[i]] ** 2

    total_current = sum(current_weights)
    current_weight_norm = _normalize_positive(current_weights) if total_current > 1e-8 else [0.0 for _ in current_weights]
    if total_current <= 1e-8:
        current_weight_norm = [0.0 for _ in current_weights]
    current_portfolio_vol = _portfolio_vol(cov, current_weight_norm)
    target_portfolio_vol = _portfolio_vol(cov, target_weights)
    current_rc = _risk_contributions(cov, current_weight_norm)
    target_rc = _risk_contributions(cov, target_weights)
    current_rc_total = sum(abs(x) for x in current_rc) or 1.0
    target_rc_total = sum(abs(x) for x in target_rc) or 1.0

    incoming_idx = instruments.index(instrument_id)
    incoming_target_weight = target_weights[incoming_idx]
    incoming_weight_gap_pct = (incoming_target_weight * 100.0) - max_position_cap_pct
    incoming_regime_mult = regime_mults[incoming_idx]

    corr_to_book = 0.0
    if open_positions:
        denom = 0.0
        weighted = 0.0
        for pos in open_positions:
            weight = max(0.0, _position_notional(pos) / balance)
            corr = pair_corr.get((instrument_id, pos.instrument_id), 0.0)
            weighted += weight * corr
            denom += weight
        corr_to_book = (weighted / denom) if denom > 0 else 0.0

    optimizer_mult = min(1.0, incoming_target_weight / max(1e-9, max_position_cap_pct / 100.0))
    if corr_to_book > max_pair_corr:
        optimizer_mult *= max(0.45, 1.0 - (corr_to_book - max_pair_corr) * 1.2)
    optimizer_mult *= incoming_regime_mult
    optimizer_mult = _clamp(optimizer_mult, 0.35, 1.0)

    trim_candidates = []
    for idx, iid in enumerate(instruments):
        if iid == instrument_id:
            continue
        current_w_pct = current_weight_norm[idx] * 100.0 if total_current > 1e-8 else 0.0
        target_w_pct = target_weights[idx] * 100.0
        current_rc_pct = abs(current_rc[idx]) / current_rc_total * 100.0 if current_rc_total > 0 else 0.0
        target_rc_pct = abs(target_rc[idx]) / target_rc_total * 100.0 if target_rc_total > 0 else 0.0
        corr = pair_corr.get((iid, instrument_id), 0.0)
        excess_weight = current_w_pct - target_w_pct
        excess_rc = current_rc_pct - target_rc_pct
        pressure_score = max(0.0, excess_rc) * 0.65 + max(0.0, excess_weight) * 0.45 + max(0.0, corr) * 18.0
        if excess_weight < target_buffer_pct and excess_rc < target_buffer_pct and corr < max_pair_corr:
            continue
        qty_ratio = 0.18
        if excess_rc > target_buffer_pct:
            qty_ratio += min(0.22, excess_rc / 100.0)
        if excess_weight > target_buffer_pct:
            qty_ratio += min(0.20, excess_weight / 100.0)
        if corr > max_pair_corr:
            qty_ratio += min(0.15, (corr - max_pair_corr) * 0.5)
        qty_ratio = _clamp(qty_ratio, 0.15, 0.75)
        trim_candidates.append({
            'instrument_id': iid,
            'qty_ratio': round(qty_ratio, 4),
            'current_weight_pct': round(current_w_pct, 4),
            'target_weight_pct': round(target_w_pct, 4),
            'current_risk_contribution_pct': round(current_rc_pct, 4),
            'target_risk_budget_pct': round(target_rc_pct, 4),
            'corr_to_incoming': round(corr, 4),
            'pressure_score': round(pressure_score, 4),
        })
    trim_candidates.sort(key=lambda item: (-item['pressure_score'], -item['corr_to_incoming'], item['instrument_id']))

    return {
        'enabled': True,
        'instrument_id': instrument_id,
        'lookback_bars': lookback_bars,
        'min_history_bars': min_history_bars,
        'portfolio_vol': round(current_portfolio_vol, 6),
        'target_portfolio_vol': round(target_portfolio_vol, 6),
        'incoming_target_weight_pct': round(incoming_target_weight * 100.0, 4),
        'incoming_weight_gap_pct': round(incoming_weight_gap_pct, 4),
        'incoming_corr_to_book': round(corr_to_book, 4),
        'incoming_regime_multiplier': round(incoming_regime_mult, 4),
        'optimizer_risk_multiplier': round(optimizer_mult, 4),
        'current_weights_pct': {iid: round(weight_by_instrument.get(iid, 0.0) * 100.0, 4) for iid in instruments},
        'target_weights_pct': {iid: round(target_weights[instruments.index(iid)] * 100.0, 4) for iid in instruments},
        'vol_by_instrument': {iid: round(vol_by_instrument[iid], 6) for iid in instruments},
        'trim_candidates': trim_candidates[:5],
        'risk_budget_mode': 'regime_adjusted_inverse_vol',
    }
