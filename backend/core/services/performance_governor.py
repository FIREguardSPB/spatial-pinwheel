from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from statistics import mean
from threading import Lock
from typing import Any
import time

try:
    from sqlalchemy.orm import Session
except Exception:  # pragma: no cover
    Session = Any  # type: ignore

from core.storage.models import DecisionLog, Position, Signal


_PERFORMANCE_GOVERNOR_CACHE_LOCK = Lock()
_PERFORMANCE_GOVERNOR_CACHE: dict[str, Any] = {
    'key': None,
    'expires_at': 0.0,
    'snapshot': None,
}


def _governor_cache_ttl_sec(settings: Any) -> int:
    try:
        ttl = int(_get_setting(settings, 'performance_governor_cache_ttl_sec', 30) or 30)
    except Exception:
        ttl = 30
    return max(5, min(ttl, 300))


def _governor_cache_key(settings: Any, days: int) -> tuple[int, int]:
    try:
        updated_ts = int(getattr(settings, 'updated_ts', 0) or 0)
    except Exception:
        updated_ts = 0
    return int(days), updated_ts


def _cutoff_ms(days: int) -> int:
    return int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp() * 1000)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _signal_meta(signal: Signal | None) -> dict[str, Any]:
    if signal is None:
        return {}
    meta = getattr(signal, 'meta', {}) or {}
    return dict(meta) if isinstance(meta, dict) else {}


def _extract_strategy(signal: Signal | None, position: Position | None = None) -> str:
    meta = _signal_meta(signal)
    multi = dict(meta.get('multi_strategy') or {}) if isinstance(meta.get('multi_strategy'), dict) else {}
    return str(
        multi.get('selected')
        or meta.get('strategy_name')
        or meta.get('strategy')
        or getattr(position, 'strategy', None)
        or 'unknown'
    )


def _extract_regime(signal: Signal | None) -> str:
    meta = _signal_meta(signal)
    adaptive = dict(meta.get('adaptive_plan') or {}) if isinstance(meta.get('adaptive_plan'), dict) else {}
    event_regime = dict(meta.get('event_regime') or {}) if isinstance(meta.get('event_regime'), dict) else {}
    for value in (
        event_regime.get('regime'),
        adaptive.get('regime'),
        meta.get('regime'),
        meta.get('market_regime'),
        meta.get('last_regime'),
    ):
        if value:
            return str(value)
    return 'unknown'


def _slice_key(strategy: str, regime: str) -> str:
    return f'{strategy} | {regime}'


def _get_setting(settings: Any, name: str, default: Any) -> Any:
    value = getattr(settings, name, None)
    return default if value is None else value


def _row_status(row: dict[str, Any], settings: Any) -> str:
    min_closed = int(_get_setting(settings, 'performance_governor_min_closed_trades', 3) or 3)
    max_execution_error_rate = float(_get_setting(settings, 'performance_governor_max_execution_error_rate', 0.35) or 0.35)
    min_take_fill_rate = float(_get_setting(settings, 'performance_governor_min_take_fill_rate', 0.20) or 0.20)
    closed_trades = int(row.get('closed_trades') or 0)
    takes = int(row.get('takes') or 0)
    pf = row.get('profit_factor')
    expectancy = _safe_float(row.get('expectancy_per_trade'))
    win_rate = _safe_float(row.get('win_rate'))
    fill_rate = _safe_float(row.get('take_fill_rate'))
    execution_error_rate = _safe_float(row.get('execution_error_rate'))

    if closed_trades < min_closed and takes < max(2, min_closed):
        return 'insufficient_data'
    if (
        closed_trades >= min_closed
        and (pf is not None and _safe_float(pf) >= 1.1)
        and expectancy >= 0.0
        and fill_rate >= max(0.2, min_take_fill_rate)
        and execution_error_rate <= max_execution_error_rate * 0.75
    ):
        return 'pass'
    if (
        (pf is not None and _safe_float(pf) >= 0.95)
        or expectancy >= -25.0
        or win_rate >= 45.0
        or fill_rate >= min_take_fill_rate
    ) and execution_error_rate <= max_execution_error_rate:
        return 'partial'
    return 'fail'


def _learning_multipliers(status: str, settings: Any) -> tuple[float, int, float, float]:
    pass_risk = float(_get_setting(settings, 'performance_governor_pass_risk_multiplier', 1.20) or 1.20)
    fail_risk = float(_get_setting(settings, 'performance_governor_fail_risk_multiplier', 0.60) or 0.60)
    threshold_bonus = int(_get_setting(settings, 'performance_governor_threshold_bonus', 6) or 6)
    threshold_penalty = int(_get_setting(settings, 'performance_governor_threshold_penalty', 10) or 10)
    exec_boost = float(_get_setting(settings, 'performance_governor_execution_priority_boost', 1.20) or 1.20)
    exec_penalty = float(_get_setting(settings, 'performance_governor_execution_priority_penalty', 0.70) or 0.70)
    alloc_boost = float(_get_setting(settings, 'performance_governor_allocator_boost', 1.15) or 1.15)
    alloc_penalty = float(_get_setting(settings, 'performance_governor_allocator_penalty', 0.80) or 0.80)

    if status == 'pass':
        return pass_risk, -threshold_bonus, exec_boost, alloc_boost
    if status == 'fail':
        return fail_risk, threshold_penalty, exec_penalty, alloc_penalty
    return 1.0, 0, 1.0, 1.0


def _finalize_row(key: str, strategy: str, regime: str, bucket: dict[str, Any], settings: Any) -> dict[str, Any]:
    closed_trades = int(bucket.get('closed_trades') or 0)
    wins = int(bucket.get('wins') or 0)
    losses = int(bucket.get('losses') or 0)
    takes = int(bucket.get('takes') or 0)
    filled = int(bucket.get('filled') or 0)
    execution_errors = int(bucket.get('execution_errors') or 0)
    pnls = list(bucket.get('pnls') or [])
    signals = int(bucket.get('signals') or 0)
    risk_rejects = int(bucket.get('risk_rejects') or 0)

    profit_factor: float | None
    if not pnls:
        profit_factor = None
    else:
        wins_sum = sum(value for value in pnls if value > 0)
        losses_sum = sum(value for value in pnls if value < 0)
        profit_factor = 999.0 if not losses_sum and wins_sum > 0 else (round(wins_sum / abs(losses_sum), 4) if losses_sum else None)

    expectancy = round(sum(pnls) / closed_trades, 4) if closed_trades else 0.0
    win_rate = round((wins / closed_trades) * 100.0, 2) if closed_trades else 0.0
    take_fill_rate = round(filled / takes, 4) if takes else 0.0
    execution_error_rate = round(execution_errors / max(1, takes), 4) if takes else 0.0
    risk_reject_rate = round(risk_rejects / max(1, takes), 4) if takes else 0.0
    avg_capture = round(mean(bucket.get('captures') or []), 4) if bucket.get('captures') else None
    status = _row_status({
        'closed_trades': closed_trades,
        'takes': takes,
        'profit_factor': profit_factor,
        'expectancy_per_trade': expectancy,
        'win_rate': win_rate,
        'take_fill_rate': take_fill_rate,
        'execution_error_rate': execution_error_rate,
    }, settings)
    risk_multiplier, threshold_adjustment, execution_priority, allocator_priority_multiplier = _learning_multipliers(status, settings)
    auto_suppress = bool(_get_setting(settings, 'performance_governor_auto_suppress', True))
    suppress = auto_suppress and status == 'fail' and (closed_trades >= int(_get_setting(settings, 'performance_governor_min_closed_trades', 3) or 3) or execution_error_rate >= float(_get_setting(settings, 'performance_governor_max_execution_error_rate', 0.35) or 0.35))
    return {
        'slice': key,
        'strategy': strategy,
        'regime': regime,
        'signals': signals,
        'takes': takes,
        'filled': filled,
        'closed_trades': closed_trades,
        'wins': wins,
        'losses': losses,
        'pnl': round(sum(pnls), 4),
        'profit_factor': profit_factor,
        'expectancy_per_trade': expectancy,
        'win_rate': win_rate,
        'take_fill_rate': take_fill_rate,
        'execution_errors': execution_errors,
        'execution_error_rate': execution_error_rate,
        'risk_rejects': risk_rejects,
        'risk_reject_rate': risk_reject_rate,
        'avg_mfe_capture_ratio': avg_capture,
        'status': status,
        'risk_multiplier': round(risk_multiplier, 4),
        'threshold_adjustment': int(threshold_adjustment),
        'execution_priority': round(execution_priority, 4),
        'allocator_priority_multiplier': round(allocator_priority_multiplier, 4),
        'action': 'suppress' if suppress else ('boost' if status == 'pass' else 'neutral'),
    }


def build_performance_governor(db: Session, *, settings: Any, days: int | None = None) -> dict[str, Any]:
    if days is None:
        days = int(_get_setting(settings, 'performance_governor_lookback_days', 45) or 45)
    days = max(7, min(int(days or 45), 180))
    cutoff = _cutoff_ms(days)
    cache_key = _governor_cache_key(settings, days)
    now = time.monotonic()

    with _PERFORMANCE_GOVERNOR_CACHE_LOCK:
        cached_snapshot = _PERFORMANCE_GOVERNOR_CACHE.get('snapshot')
        cached_key = _PERFORMANCE_GOVERNOR_CACHE.get('key')
        expires_at = float(_PERFORMANCE_GOVERNOR_CACHE.get('expires_at') or 0.0)
        if cached_snapshot is not None and cached_key == cache_key and now < expires_at:
            return cached_snapshot

    positions = (
        db.query(
            Position.opened_signal_id,
            Position.strategy,
            Position.realized_pnl,
        )
        .filter(Position.updated_ts >= cutoff, Position.qty == 0)
        .order_by(Position.updated_ts.asc())
        .all()
    )

    signal_ids = sorted({str(getattr(position, 'opened_signal_id', '') or '') for position in positions if getattr(position, 'opened_signal_id', None)})
    referenced_signals = []
    if signal_ids:
        referenced_signals = (
            db.query(
                Signal.id,
                Signal.instrument_id,
                Signal.status,
                Signal.meta,
            )
            .filter(Signal.id.in_(signal_ids))
            .all()
        )

    signal_rows: dict[str, dict[str, Any]] = {}
    for signal in referenced_signals:
        strategy = _extract_strategy(signal)
        regime = _extract_regime(signal)
        signal_rows[str(signal.id)] = {
            'signal_id': str(signal.id),
            'instrument_id': str(signal.instrument_id),
            'strategy': strategy,
            'regime': regime,
            'slice': _slice_key(strategy, regime),
            'status': str(getattr(signal, 'status', '') or ''),
        }

    slice_buckets: dict[str, dict[str, Any]] = defaultdict(lambda: {
        'signals': 0, 'takes': 0, 'filled': 0, 'closed_trades': 0, 'wins': 0, 'losses': 0,
        'pnls': [], 'captures': [], 'execution_errors': 0, 'risk_rejects': 0,
    })
    strategy_buckets: dict[str, dict[str, Any]] = defaultdict(lambda: {
        'signals': 0, 'takes': 0, 'filled': 0, 'closed_trades': 0, 'wins': 0, 'losses': 0,
        'pnls': [], 'captures': [], 'execution_errors': 0, 'risk_rejects': 0,
    })
    regime_buckets: dict[str, dict[str, Any]] = defaultdict(lambda: {
        'signals': 0, 'takes': 0, 'filled': 0, 'closed_trades': 0, 'wins': 0, 'losses': 0,
        'pnls': [], 'captures': [], 'execution_errors': 0, 'risk_rejects': 0,
    })

    for position in positions:
        signal_id = str(getattr(position, 'opened_signal_id', '') or '')
        signal = signal_rows.get(signal_id)
        if signal is None:
            strategy = str(getattr(position, 'strategy', None) or 'unknown')
            regime = 'unknown'
            slice_key = _slice_key(strategy, regime)
        else:
            strategy = signal['strategy']
            regime = signal['regime']
            slice_key = signal['slice']
        pnl = _safe_float(getattr(position, 'realized_pnl', 0.0))
        for bucket in (slice_buckets[slice_key], strategy_buckets[strategy], regime_buckets[regime]):
            bucket['signals'] += 1
            bucket['takes'] += 1
            bucket['filled'] += 1
            bucket['closed_trades'] += 1
            bucket['pnls'].append(pnl)
            if pnl > 0:
                bucket['wins'] += 1
            elif pnl < 0:
                bucket['losses'] += 1

    slice_rows: list[dict[str, Any]] = []
    for key, bucket in slice_buckets.items():
        strategy, regime = key.split(' | ', 1) if ' | ' in key else (key, 'unknown')
        slice_rows.append(_finalize_row(key, strategy, regime, bucket, settings))
    slice_rows.sort(key=lambda item: (-int(item.get('closed_trades') or 0), -_safe_float(item.get('pnl')), item.get('slice') or ''))

    strategy_rows: list[dict[str, Any]] = []
    for strategy, bucket in strategy_buckets.items():
        strategy_rows.append(_finalize_row(strategy, strategy, 'all', bucket, settings))
    strategy_rows.sort(key=lambda item: (-int(item.get('closed_trades') or 0), -_safe_float(item.get('pnl')), item.get('strategy') or ''))

    regime_rows: list[dict[str, Any]] = []
    for regime, bucket in regime_buckets.items():
        regime_rows.append(_finalize_row(regime, 'all', regime, bucket, settings))
    regime_rows.sort(key=lambda item: (-int(item.get('closed_trades') or 0), -_safe_float(item.get('pnl')), item.get('regime') or ''))

    whitelist_by_regime: dict[str, list[str]] = defaultdict(list)
    suppressed_slices: list[dict[str, Any]] = []
    boosted_slices: list[dict[str, Any]] = []
    for row in slice_rows:
        if row['status'] == 'pass':
            whitelist_by_regime[row['regime']].append(row['strategy'])
            boosted_slices.append(row)
        elif row['action'] == 'suppress':
            suppressed_slices.append(row)
    if not whitelist_by_regime:
        for row in slice_rows:
            if row['status'] == 'partial' and _safe_float(row.get('expectancy_per_trade')) >= 0.0:
                whitelist_by_regime[row['regime']].append(row['strategy'])

    summary_status = 'pass' if boosted_slices else ('partial' if slice_rows else 'insufficient_data')
    if summary_status == 'pass' and len(suppressed_slices) >= max(2, len(boosted_slices) + 1):
        summary_status = 'partial'
    if slice_rows and not boosted_slices and len(suppressed_slices) >= max(1, len(slice_rows) // 2):
        summary_status = 'fail'

    recommendations: list[str] = []
    for row in suppressed_slices[:3]:
        recommendations.append(
            f"Срез {row['slice']} слабый: PF={row.get('profit_factor')} expectancy={row.get('expectancy_per_trade')} fill={row.get('take_fill_rate')}. Его стоит подавлять автоматически."
        )
    for row in boosted_slices[:3]:
        recommendations.append(
            f"Срез {row['slice']} подтверждён: можно давать повышенный risk budget и execution priority."
        )

    snapshot = {
        'period_days': days,
        'summary': {
            'status': summary_status,
            'signals_count': len(positions),
            'closed_trades_count': len(positions),
            'validated_slices_count': len(boosted_slices),
            'suppressed_slices_count': len(suppressed_slices),
        },
        'settings': {
            'enabled': bool(_get_setting(settings, 'performance_governor_enabled', True)),
            'lookback_days': days,
            'min_closed_trades': int(_get_setting(settings, 'performance_governor_min_closed_trades', 3) or 3),
            'strict_whitelist': bool(_get_setting(settings, 'performance_governor_strict_whitelist', True)),
            'auto_suppress': bool(_get_setting(settings, 'performance_governor_auto_suppress', True)),
            'cache_ttl_sec': _governor_cache_ttl_sec(settings),
        },
        'slice_rows': slice_rows[:24],
        'strategy_rows': strategy_rows[:12],
        'regime_rows': regime_rows[:12],
        'whitelist_by_regime': {key: sorted(set(values)) for key, values in whitelist_by_regime.items()},
        'suppressed_slices': suppressed_slices[:12],
        'boosted_slices': boosted_slices[:12],
        'recommendations': recommendations,
    }
    with _PERFORMANCE_GOVERNOR_CACHE_LOCK:
        _PERFORMANCE_GOVERNOR_CACHE['key'] = cache_key
        _PERFORMANCE_GOVERNOR_CACHE['expires_at'] = time.monotonic() + _governor_cache_ttl_sec(settings)
        _PERFORMANCE_GOVERNOR_CACHE['snapshot'] = snapshot
    return snapshot


def evaluate_signal_governor(
    db: Session,
    settings: Any,
    *,
    instrument_id: str,
    strategy: str,
    regime: str,
) -> dict[str, Any]:
    enabled = bool(_get_setting(settings, 'performance_governor_enabled', True))
    base = {
        'enabled': enabled,
        'instrument_id': instrument_id,
        'strategy': strategy or 'unknown',
        'regime': regime or 'unknown',
        'slice': _slice_key(strategy or 'unknown', regime or 'unknown'),
        'status': 'neutral',
        'risk_multiplier': 1.0,
        'threshold_adjustment': 0,
        'execution_priority': 1.0,
        'allocator_priority_multiplier': 1.0,
        'suppressed': False,
        'allowed': True,
        'reasons': [],
        'whitelist_hit': None,
    }
    if not enabled:
        return base

    snapshot = build_performance_governor(db, settings=settings)
    slice_map = {str(row.get('slice')): row for row in snapshot.get('slice_rows') or []}
    strategy_map = {str(row.get('slice')): row for row in snapshot.get('strategy_rows') or []}
    regime_map = {str(row.get('slice')): row for row in snapshot.get('regime_rows') or []}

    row = slice_map.get(base['slice'])
    whitelist_by_regime = snapshot.get('whitelist_by_regime') or {}
    whitelist = list(whitelist_by_regime.get(regime or 'unknown') or [])
    strict_whitelist = bool(_get_setting(settings, 'performance_governor_strict_whitelist', True))
    if whitelist:
        base['whitelist_hit'] = strategy in whitelist
        if strategy not in whitelist:
            base['reasons'].append(f'strategy {strategy} is outside validated whitelist for regime {regime}')
            base['risk_multiplier'] *= float(_get_setting(settings, 'performance_governor_fail_risk_multiplier', 0.60) or 0.60)
            base['threshold_adjustment'] += int(_get_setting(settings, 'performance_governor_threshold_penalty', 10) or 10)
            base['execution_priority'] *= float(_get_setting(settings, 'performance_governor_execution_priority_penalty', 0.70) or 0.70)
            base['allocator_priority_multiplier'] *= float(_get_setting(settings, 'performance_governor_allocator_penalty', 0.80) or 0.80)
            if strict_whitelist:
                base['suppressed'] = True
                base['allowed'] = False
                base['status'] = 'blocked_by_whitelist'

    if row is not None:
        base['status'] = str(row.get('status') or 'neutral')
        base['risk_multiplier'] *= _safe_float(row.get('risk_multiplier'), 1.0)
        base['threshold_adjustment'] += int(row.get('threshold_adjustment') or 0)
        base['execution_priority'] *= _safe_float(row.get('execution_priority'), 1.0)
        base['allocator_priority_multiplier'] *= _safe_float(row.get('allocator_priority_multiplier'), 1.0)
        if row.get('action') == 'suppress':
            base['suppressed'] = True
            base['allowed'] = False
            base['reasons'].append(f"validated weak slice {base['slice']} is automatically suppressed")
    else:
        strategy_row = strategy_map.get(strategy)
        regime_row = regime_map.get(regime)
        if strategy_row and strategy_row.get('status') == 'pass' and regime_row and regime_row.get('status') in {'pass', 'partial'}:
            base['status'] = 'strategy_regime_support'
            base['risk_multiplier'] *= 1.08
            base['threshold_adjustment'] -= max(1, int(_get_setting(settings, 'performance_governor_threshold_bonus', 6) or 6) // 2)
            base['execution_priority'] *= 1.08
            base['allocator_priority_multiplier'] *= 1.05
        elif strategy_row and strategy_row.get('status') == 'fail':
            base['status'] = 'strategy_dragger'
            base['risk_multiplier'] *= 0.85
            base['threshold_adjustment'] += max(2, int(_get_setting(settings, 'performance_governor_threshold_penalty', 10) or 10) // 2)
            base['execution_priority'] *= 0.9
            base['allocator_priority_multiplier'] *= 0.9
            base['reasons'].append(f'strategy {strategy} is currently a dragger in post-trade learning loop')

    base['risk_multiplier'] = round(max(0.25, min(1.5, _safe_float(base['risk_multiplier'], 1.0))), 4)
    base['execution_priority'] = round(max(0.5, min(1.6, _safe_float(base['execution_priority'], 1.0))), 4)
    base['allocator_priority_multiplier'] = round(max(0.5, min(1.5, _safe_float(base['allocator_priority_multiplier'], 1.0))), 4)
    return base
