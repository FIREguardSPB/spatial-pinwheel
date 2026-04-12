from __future__ import annotations

from dataclasses import dataclass
import threading
import time
from typing import Any

try:
    from core.storage.models import Signal
except Exception:  # pragma: no cover
    Signal = None

try:
    from core.services.business_metrics import build_metrics as _build_metrics
except Exception:  # pragma: no cover - lightweight test env without sqlalchemy
    _build_metrics = None


@dataclass(slots=True)
class DegradePolicyResult:
    state: str
    reasons: list[str]
    lookback_days: int
    metrics: dict[str, Any]
    risk_multiplier_override: float = 1.0
    threshold_penalty: int = 0
    block_new_entries: bool = False

    def to_meta(self) -> dict[str, Any]:
        return {
            'state': self.state,
            'reasons': list(self.reasons),
            'lookback_days': int(self.lookback_days),
            'risk_multiplier_override': float(self.risk_multiplier_override),
            'threshold_penalty': int(self.threshold_penalty),
            'block_new_entries': bool(self.block_new_entries),
            'metrics': dict(self.metrics or {}),
        }


def _int(value: Any, default: int) -> int:
    try:
        if value is None:
            raise ValueError
        return int(value)
    except Exception:
        return int(default)


def _float(value: Any, default: float) -> float:
    try:
        if value is None:
            raise ValueError
        return float(value)
    except Exception:
        return float(default)





def _build_freeze_analytics(db, *, lookback_days: int) -> dict[str, Any]:
    if Signal is None:
        return {}
    try:
        rows = (
            db.query(Signal)
            .order_by(Signal.created_ts.desc())
            .limit(max(20, int(lookback_days) * 25))
            .all()
        )
    except Exception:
        return {}
    execution_error_streak = 0
    rejection_streak = 0
    recent_execution_errors: list[dict[str, Any]] = []
    recent_statuses: list[str] = []
    for row in rows:
        status = str(getattr(row, 'status', '') or '')
        recent_statuses.append(status)
        if status == 'execution_error':
            execution_error_streak += 1
            meta = getattr(row, 'meta', None) or {}
            exec_meta = meta.get('execution_error') if isinstance(meta, dict) else None
            recent_execution_errors.append({
                'signal_id': getattr(row, 'id', None),
                'instrument_id': getattr(row, 'instrument_id', None),
                'reason': (exec_meta or {}).get('reason') if isinstance(exec_meta, dict) else None,
                'ts': (exec_meta or {}).get('ts') if isinstance(exec_meta, dict) else None,
            })
        else:
            break
    for row in rows:
        status = str(getattr(row, 'status', '') or '')
        if status in {'rejected', 'execution_error'}:
            rejection_streak += 1
        else:
            break
    return {
        'recent_statuses': recent_statuses[:10],
        'execution_error_streak': execution_error_streak,
        'rejection_streak': rejection_streak,
        'recent_execution_errors': recent_execution_errors[:5],
    }


_POLICY_CACHE_TTL_SEC = 45.0
_POLICY_CACHE_STALE_SEC = 600.0
_POLICY_CACHE_LOCK = threading.Lock()
_POLICY_CACHE: dict[str, Any] = {
    'key': None,
    'expires_at': 0.0,
    'stale_expires_at': 0.0,
    'computed_at': 0.0,
    'result': None,
    'last_error': None,
    'last_error_at': 0.0,
    'warming_started_at': 0.0,
}
_POLICY_WARMING_KEYS: set[tuple[Any, ...]] = set()
_POLICY_MAX_WARMING_SEC = 15.0


def _result_to_payload(result: DegradePolicyResult, *, status: str) -> dict[str, Any]:
    payload = result.to_meta()
    payload['status'] = status
    return payload


def _build_loading_policy_payload(settings: Any) -> dict[str, Any]:
    return {
        'state': 'unknown',
        'reasons': ['auto policy runtime is warming cache'],
        'lookback_days': _int(getattr(settings, 'auto_policy_lookback_days', None), DEFAULTS['auto_policy_lookback_days']),
        'risk_multiplier_override': 1.0,
        'threshold_penalty': 0,
        'block_new_entries': False,
        'metrics': {},
        'status': 'loading',
    }


def _build_error_policy_payload(settings: Any, *, reason: str) -> dict[str, Any]:
    return {
        'state': 'unknown',
        'reasons': [reason],
        'lookback_days': _int(getattr(settings, 'auto_policy_lookback_days', None), DEFAULTS['auto_policy_lookback_days']),
        'risk_multiplier_override': 1.0,
        'threshold_penalty': 0,
        'block_new_entries': False,
        'metrics': {},
        'status': 'error',
        'error': reason,
    }


def _refresh_policy_cache_worker() -> None:
    settings_db = None
    db = None
    try:
        from core.storage.session import SessionLocal
        from core.storage.repos import settings as settings_repo

        db = SessionLocal()
        settings_db = settings_repo.get_settings(db)
        evaluate_degrade_policy(db, settings_db)
        with _POLICY_CACHE_LOCK:
            _POLICY_CACHE['last_error'] = None
            _POLICY_CACHE['last_error_at'] = 0.0
    except Exception as exc:
        with _POLICY_CACHE_LOCK:
            _POLICY_CACHE['last_error'] = str(exc)
            _POLICY_CACHE['last_error_at'] = time.monotonic()
    finally:
        try:
            if db is not None:
                db.close()
        finally:
            with _POLICY_CACHE_LOCK:
                if settings_db is not None:
                    _POLICY_WARMING_KEYS.discard(_policy_cache_key(settings_db))
                _POLICY_CACHE['warming_started_at'] = 0.0


def _schedule_policy_cache_refresh(settings: Any) -> None:
    cache_key = _policy_cache_key(settings)
    now = time.monotonic()
    with _POLICY_CACHE_LOCK:
        warming_started_at = float(_POLICY_CACHE.get('warming_started_at') or 0.0)
        if cache_key in _POLICY_WARMING_KEYS and (now - warming_started_at) < _POLICY_MAX_WARMING_SEC:
            return
        _POLICY_WARMING_KEYS.add(cache_key)
        _POLICY_CACHE['warming_started_at'] = now
    thread = threading.Thread(target=_refresh_policy_cache_worker, name='policy-cache-refresh', daemon=True)
    thread.start()


def build_policy_runtime_payload_ui_safe(settings: Any) -> dict[str, Any]:
    fresh = _get_cached_policy_result(settings)
    if fresh is not None:
        payload = _result_to_payload(fresh, status='ready')
    else:
        stale = _get_cached_policy_result(settings, allow_stale=True)
        if stale is not None:
            payload = _result_to_payload(stale, status='stale-cache')
        else:
            _schedule_policy_cache_refresh(settings)
            with _POLICY_CACHE_LOCK:
                last_error = _POLICY_CACHE.get('last_error')
                last_error_at = float(_POLICY_CACHE.get('last_error_at') or 0.0)
                warming_started_at = float(_POLICY_CACHE.get('warming_started_at') or 0.0)
            now = time.monotonic()
            if last_error and (now - last_error_at) < _POLICY_CACHE_TTL_SEC:
                payload = _build_error_policy_payload(settings, reason=str(last_error))
            elif warming_started_at and (now - warming_started_at) > _POLICY_MAX_WARMING_SEC:
                payload = _build_error_policy_payload(settings, reason='auto policy runtime warmup timed out')
            else:
                payload = _build_loading_policy_payload(settings)
    cache_meta = _policy_cache_meta(settings)
    if cache_meta is not None:
        payload['cache_ttl_sec'] = int(_POLICY_CACHE_TTL_SEC)
        payload['cache_age_sec'] = max(0.0, round(time.monotonic() - cache_meta['computed_at'], 3))
        payload['cache_expires_in_sec'] = max(0.0, round(cache_meta['expires_at'] - time.monotonic(), 3))
    payload['enabled'] = bool(getattr(settings, 'auto_degrade_enabled', DEFAULTS['auto_degrade_enabled']))
    payload['freeze_enabled'] = bool(getattr(settings, 'auto_freeze_enabled', DEFAULTS['auto_freeze_enabled']))
    payload['thresholds'] = {
        'degrade_max_execution_errors': _int(getattr(settings, 'auto_degrade_max_execution_errors', None), DEFAULTS['auto_degrade_max_execution_errors']),
        'freeze_max_execution_errors': _int(getattr(settings, 'auto_freeze_max_execution_errors', None), DEFAULTS['auto_freeze_max_execution_errors']),
        'degrade_min_profit_factor': _float(getattr(settings, 'auto_degrade_min_profit_factor', None), DEFAULTS['auto_degrade_min_profit_factor']),
        'freeze_min_profit_factor': _float(getattr(settings, 'auto_freeze_min_profit_factor', None), DEFAULTS['auto_freeze_min_profit_factor']),
        'degrade_min_expectancy': _float(getattr(settings, 'auto_degrade_min_expectancy', None), DEFAULTS['auto_degrade_min_expectancy']),
        'freeze_min_expectancy': _float(getattr(settings, 'auto_freeze_min_expectancy', None), DEFAULTS['auto_freeze_min_expectancy']),
        'degrade_drawdown_pct': _float(getattr(settings, 'auto_degrade_drawdown_pct', None), DEFAULTS['auto_degrade_drawdown_pct']),
        'freeze_drawdown_pct': _float(getattr(settings, 'auto_freeze_drawdown_pct', None), DEFAULTS['auto_freeze_drawdown_pct']),
        'degrade_risk_multiplier': _float(getattr(settings, 'auto_degrade_risk_multiplier', None), DEFAULTS['auto_degrade_risk_multiplier']),
        'degrade_threshold_penalty': _int(getattr(settings, 'auto_degrade_threshold_penalty', None), DEFAULTS['auto_degrade_threshold_penalty']),
        'freeze_new_entries': bool(getattr(settings, 'auto_freeze_new_entries', DEFAULTS['auto_freeze_new_entries'])),
    }
    return payload


def _policy_cache_key(settings: Any) -> tuple[Any, ...]:
    return (
        getattr(settings, 'updated_ts', None),
        getattr(settings, 'auto_degrade_enabled', None),
        getattr(settings, 'auto_freeze_enabled', None),
        getattr(settings, 'auto_policy_lookback_days', None),
        getattr(settings, 'auto_degrade_max_execution_errors', None),
        getattr(settings, 'auto_freeze_max_execution_errors', None),
        getattr(settings, 'auto_degrade_min_profit_factor', None),
        getattr(settings, 'auto_freeze_min_profit_factor', None),
        getattr(settings, 'auto_degrade_min_expectancy', None),
        getattr(settings, 'auto_freeze_min_expectancy', None),
        getattr(settings, 'auto_degrade_drawdown_pct', None),
        getattr(settings, 'auto_freeze_drawdown_pct', None),
        getattr(settings, 'auto_degrade_risk_multiplier', None),
        getattr(settings, 'auto_degrade_threshold_penalty', None),
        getattr(settings, 'auto_freeze_new_entries', None),
    )


def _get_cached_policy_result(settings: Any, *, allow_stale: bool = False) -> DegradePolicyResult | None:
    key = _policy_cache_key(settings)
    now = time.monotonic()
    with _POLICY_CACHE_LOCK:
        if _POLICY_CACHE.get('key') != key:
            return None
        expires_at = float(_POLICY_CACHE.get('expires_at') or 0.0)
        stale_expires_at = float(_POLICY_CACHE.get('stale_expires_at') or 0.0)
        if expires_at > now or (allow_stale and stale_expires_at > now):
            return _POLICY_CACHE.get('result')
    return None


def _policy_cache_meta(settings: Any) -> dict[str, float] | None:
    key = _policy_cache_key(settings)
    now = time.monotonic()
    with _POLICY_CACHE_LOCK:
        if _POLICY_CACHE.get('key') != key:
            return None
        stale_expires_at = float(_POLICY_CACHE.get('stale_expires_at') or 0.0)
        if stale_expires_at <= now:
            return None
        return {
            'computed_at': float(_POLICY_CACHE.get('computed_at') or 0.0),
            'expires_at': float(_POLICY_CACHE.get('expires_at') or 0.0),
            'stale_expires_at': stale_expires_at,
        }


def _store_cached_policy_result(settings: Any, result: DegradePolicyResult) -> None:
    now = time.monotonic()
    with _POLICY_CACHE_LOCK:
        _POLICY_CACHE['key'] = _policy_cache_key(settings)
        _POLICY_CACHE['expires_at'] = now + _POLICY_CACHE_TTL_SEC
        _POLICY_CACHE['stale_expires_at'] = now + _POLICY_CACHE_STALE_SEC
        _POLICY_CACHE['computed_at'] = now
        _POLICY_CACHE['result'] = result
        _POLICY_CACHE['last_error'] = None
        _POLICY_CACHE['last_error_at'] = 0.0
        _POLICY_CACHE['warming_started_at'] = 0.0

DEFAULTS = {
    'auto_degrade_enabled': True,
    'auto_freeze_enabled': True,
    'auto_policy_lookback_days': 14,
    'auto_degrade_max_execution_errors': 4,
    'auto_freeze_max_execution_errors': 10,
    'auto_degrade_min_profit_factor': 0.95,
    'auto_freeze_min_profit_factor': 0.70,
    'auto_degrade_min_expectancy': -50.0,
    'auto_freeze_min_expectancy': -250.0,
    'auto_degrade_drawdown_pct': 2.5,
    'auto_freeze_drawdown_pct': 5.0,
    'auto_degrade_risk_multiplier': 0.55,
    'auto_degrade_threshold_penalty': 8,
    'auto_freeze_new_entries': True,
}


def evaluate_degrade_policy(db, settings: Any) -> DegradePolicyResult:
    cached = _get_cached_policy_result(settings)
    if cached is not None:
        return cached

    enabled = bool(getattr(settings, 'auto_degrade_enabled', DEFAULTS['auto_degrade_enabled']))
    freeze_enabled = bool(getattr(settings, 'auto_freeze_enabled', DEFAULTS['auto_freeze_enabled']))
    lookback_days = _int(getattr(settings, 'auto_policy_lookback_days', None), DEFAULTS['auto_policy_lookback_days'])

    if not enabled:
        result = DegradePolicyResult(
            state='disabled',
            reasons=['auto degrade/freeze policy disabled'],
            lookback_days=lookback_days,
            metrics={},
        )
        _store_cached_policy_result(settings, result)
        return result

    if _build_metrics is None:  # pragma: no cover
        raise RuntimeError('business_metrics unavailable')
    metrics = _build_metrics(db, days=lookback_days)
    freeze_analytics = _build_freeze_analytics(db, lookback_days=lookback_days)
    reasons_degrade: list[str] = []
    reasons_freeze: list[str] = []

    execution_errors = _int(metrics.get('execution_error_count'), 0)
    execution_error_streak = _int(freeze_analytics.get('execution_error_streak'), 0)
    profit_factor = metrics.get('profit_factor')
    expectancy = _float(metrics.get('expectancy_per_trade'), 0.0)
    drawdown_pct = _float(metrics.get('max_drawdown_pct'), 0.0)
    trades_count = _int(metrics.get('trades_count'), 0)
    total_pnl = _float(metrics.get('total_pnl'), 0.0)

    degrade_max_execution_errors = _int(getattr(settings, 'auto_degrade_max_execution_errors', None), DEFAULTS['auto_degrade_max_execution_errors'])
    freeze_max_execution_errors = _int(getattr(settings, 'auto_freeze_max_execution_errors', None), DEFAULTS['auto_freeze_max_execution_errors'])
    degrade_min_profit_factor = _float(getattr(settings, 'auto_degrade_min_profit_factor', None), DEFAULTS['auto_degrade_min_profit_factor'])
    freeze_min_profit_factor = _float(getattr(settings, 'auto_freeze_min_profit_factor', None), DEFAULTS['auto_freeze_min_profit_factor'])
    degrade_min_expectancy = _float(getattr(settings, 'auto_degrade_min_expectancy', None), DEFAULTS['auto_degrade_min_expectancy'])
    freeze_min_expectancy = _float(getattr(settings, 'auto_freeze_min_expectancy', None), DEFAULTS['auto_freeze_min_expectancy'])
    degrade_drawdown_pct = _float(getattr(settings, 'auto_degrade_drawdown_pct', None), DEFAULTS['auto_degrade_drawdown_pct'])
    freeze_drawdown_pct = _float(getattr(settings, 'auto_freeze_drawdown_pct', None), DEFAULTS['auto_freeze_drawdown_pct'])
    degrade_risk_multiplier = _float(getattr(settings, 'auto_degrade_risk_multiplier', None), DEFAULTS['auto_degrade_risk_multiplier'])
    degrade_threshold_penalty = _int(getattr(settings, 'auto_degrade_threshold_penalty', None), DEFAULTS['auto_degrade_threshold_penalty'])
    freeze_new_entries = bool(getattr(settings, 'auto_freeze_new_entries', DEFAULTS['auto_freeze_new_entries']))

    if execution_error_streak >= max(2, degrade_max_execution_errors // 2):
        reasons_degrade.append(f'execution error streak {execution_error_streak}')
        reasons_degrade.append(f'execution errors {execution_errors} >= {degrade_max_execution_errors}')
    if trades_count >= 3 and profit_factor is not None and float(profit_factor) < degrade_min_profit_factor:
        reasons_degrade.append(f'profit factor {float(profit_factor):.2f} < {degrade_min_profit_factor:.2f}')
    if trades_count >= 3 and expectancy < degrade_min_expectancy:
        reasons_degrade.append(f'expectancy {expectancy:.2f} < {degrade_min_expectancy:.2f}')
    if drawdown_pct >= degrade_drawdown_pct:
        reasons_degrade.append(f'drawdown {drawdown_pct:.2f}% >= {degrade_drawdown_pct:.2f}%')

    if freeze_enabled:
        if execution_error_streak >= max(3, freeze_max_execution_errors // 3):
            reasons_freeze.append(f'execution error streak {execution_error_streak}')
            reasons_freeze.append(f'execution errors {execution_errors} >= {freeze_max_execution_errors}')
        if trades_count >= 5 and profit_factor is not None and float(profit_factor) < freeze_min_profit_factor:
            reasons_freeze.append(f'profit factor {float(profit_factor):.2f} < {freeze_min_profit_factor:.2f}')
        if trades_count >= 5 and expectancy < freeze_min_expectancy:
            reasons_freeze.append(f'expectancy {expectancy:.2f} < {freeze_min_expectancy:.2f}')
        if drawdown_pct >= freeze_drawdown_pct:
            reasons_freeze.append(f'drawdown {drawdown_pct:.2f}% >= {freeze_drawdown_pct:.2f}%')
        if trades_count >= 8 and total_pnl < 0 and profit_factor is not None and float(profit_factor) < max(0.8, freeze_min_profit_factor + 0.05):
            reasons_freeze.append('persistent negative paper-run quality across lookback window')

    if reasons_freeze:
        result = DegradePolicyResult(
            state='frozen',
            reasons=reasons_freeze,
            lookback_days=lookback_days,
            metrics={**metrics, 'freeze_analytics': freeze_analytics},
            risk_multiplier_override=0.0,
            threshold_penalty=max(20, degrade_threshold_penalty),
            block_new_entries=freeze_new_entries,
        )
        _store_cached_policy_result(settings, result)
        return result
    if reasons_degrade:
        result = DegradePolicyResult(
            state='degraded',
            reasons=reasons_degrade,
            lookback_days=lookback_days,
            metrics={**metrics, 'freeze_analytics': freeze_analytics},
            risk_multiplier_override=max(0.05, min(1.0, degrade_risk_multiplier)),
            threshold_penalty=max(0, degrade_threshold_penalty),
            block_new_entries=False,
        )
        _store_cached_policy_result(settings, result)
        return result
    result = DegradePolicyResult(
        state='normal',
        reasons=['auto degrade/freeze policy sees no active issues'],
        lookback_days=lookback_days,
        metrics={**metrics, 'freeze_analytics': freeze_analytics},
    )
    _store_cached_policy_result(settings, result)
    return result


def build_policy_runtime_payload(db, settings: Any) -> dict[str, Any]:
    try:
        result = evaluate_degrade_policy(db, settings)
        payload = _result_to_payload(result, status='ready')
    except Exception as exc:
        cached = _get_cached_policy_result(settings, allow_stale=True)
        if cached is not None:
            payload = _result_to_payload(cached, status='stale-cache')
            payload['warning'] = str(exc)
        else:
            payload = {
                'state': 'unknown',
                'reasons': ['auto policy runtime unavailable'],
                'lookback_days': _int(getattr(settings, 'auto_policy_lookback_days', None), DEFAULTS['auto_policy_lookback_days']),
                'risk_multiplier_override': 1.0,
                'threshold_penalty': 0,
                'block_new_entries': False,
                'metrics': {},
                'status': 'error',
                'error': str(exc),
            }
    cache_meta = _policy_cache_meta(settings)
    if cache_meta is not None:
        payload['cache_ttl_sec'] = int(_POLICY_CACHE_TTL_SEC)
        payload['cache_age_sec'] = max(0.0, round(time.monotonic() - cache_meta['computed_at'], 3))
        payload['cache_expires_in_sec'] = max(0.0, round(cache_meta['expires_at'] - time.monotonic(), 3))
    payload['enabled'] = bool(getattr(settings, 'auto_degrade_enabled', DEFAULTS['auto_degrade_enabled']))
    payload['freeze_enabled'] = bool(getattr(settings, 'auto_freeze_enabled', DEFAULTS['auto_freeze_enabled']))
    payload['thresholds'] = {
        'degrade_max_execution_errors': _int(getattr(settings, 'auto_degrade_max_execution_errors', None), DEFAULTS['auto_degrade_max_execution_errors']),
        'freeze_max_execution_errors': _int(getattr(settings, 'auto_freeze_max_execution_errors', None), DEFAULTS['auto_freeze_max_execution_errors']),
        'degrade_min_profit_factor': _float(getattr(settings, 'auto_degrade_min_profit_factor', None), DEFAULTS['auto_degrade_min_profit_factor']),
        'freeze_min_profit_factor': _float(getattr(settings, 'auto_freeze_min_profit_factor', None), DEFAULTS['auto_freeze_min_profit_factor']),
        'degrade_min_expectancy': _float(getattr(settings, 'auto_degrade_min_expectancy', None), DEFAULTS['auto_degrade_min_expectancy']),
        'freeze_min_expectancy': _float(getattr(settings, 'auto_freeze_min_expectancy', None), DEFAULTS['auto_freeze_min_expectancy']),
        'degrade_drawdown_pct': _float(getattr(settings, 'auto_degrade_drawdown_pct', None), DEFAULTS['auto_degrade_drawdown_pct']),
        'freeze_drawdown_pct': _float(getattr(settings, 'auto_freeze_drawdown_pct', None), DEFAULTS['auto_freeze_drawdown_pct']),
        'degrade_risk_multiplier': _float(getattr(settings, 'auto_degrade_risk_multiplier', None), DEFAULTS['auto_degrade_risk_multiplier']),
        'degrade_threshold_penalty': _int(getattr(settings, 'auto_degrade_threshold_penalty', None), DEFAULTS['auto_degrade_threshold_penalty']),
        'freeze_new_entries': bool(getattr(settings, 'auto_freeze_new_entries', DEFAULTS['auto_freeze_new_entries'])),
    }
    return payload
