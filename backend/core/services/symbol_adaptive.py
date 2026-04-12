from __future__ import annotations

import json
import math
import time
import uuid
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean, pstdev
from tempfile import NamedTemporaryFile
from typing import Any

from sqlalchemy.orm import Session

from core.storage.models import CandleCache, DecisionLog, SymbolEventRegime, SymbolProfile, SymbolRegimeSnapshot, SymbolTrainingRun
from core.strategy.selector import StrategySelector
from core.services.timeframe_engine import max_timeframe, next_higher_timeframe, normalize_timeframe, timeframe_rank
from core.services.symbol_adaptive_timeframes import choose_strategy as _choose_strategy, low_price_instrument as _low_price_instrument, select_execution_timeframe as _select_execution_timeframe, select_timeframes as _select_timeframes_base
from core.services.trading_schedule import get_schedule_snapshot


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _safe_mean(values: list[float]) -> float | None:
    cleaned = [float(v) for v in values if v is not None]
    return mean(cleaned) if cleaned else None


def _safe_std(values: list[float]) -> float:
    cleaned = [float(v) for v in values if v is not None]
    return pstdev(cleaned) if len(cleaned) >= 2 else 0.0


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _json_store_path() -> Path:
    return _project_root() / 'docs' / 'symbol_profiles.runtime.json'


def _atomic_json_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile('w', delete=False, dir=str(path.parent), encoding='utf-8') as tmp:
        json.dump(payload, tmp, ensure_ascii=False, indent=2, sort_keys=True)
        tmp.flush()
        Path(tmp.name).replace(path)


def _file_store_load() -> dict[str, Any]:
    path = _json_store_path()
    if not path.exists():
        return {'version': 1, 'profiles': {}}
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {'version': 1, 'profiles': {}}


def _file_store_get(instrument_id: str) -> dict[str, Any] | None:
    payload = _file_store_load()
    profile = (payload.get('profiles') or {}).get(instrument_id)
    return dict(profile) if profile else None


def _file_store_upsert(instrument_id: str, patch: dict[str, Any]) -> dict[str, Any]:
    payload = _file_store_load()
    profiles = payload.setdefault('profiles', {})
    merged = dict(patch)
    merged['instrument_id'] = instrument_id
    merged['updated_ts'] = int(time.time() * 1000)
    profiles[instrument_id] = merged
    _atomic_json_write(_json_store_path(), payload)
    return merged


def _parse_jsonish(value: Any, fallback: list[Any] | dict[str, Any] | None = None) -> Any:
    if value is None:
        return [] if isinstance(fallback, list) else ({} if isinstance(fallback, dict) else fallback)
    if isinstance(value, (list, dict)):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return [] if isinstance(fallback, list) else ({} if isinstance(fallback, dict) else fallback)
        try:
            return json.loads(text)
        except Exception:
            return [] if isinstance(fallback, list) else ({} if isinstance(fallback, dict) else fallback)
    return fallback


def _profile_to_dict(row: SymbolProfile) -> dict[str, Any]:
    return {
        'instrument_id': row.instrument_id,
        'enabled': bool(row.enabled),
        'preferred_strategies': row.preferred_strategies,
        'decision_threshold_offset': int(row.decision_threshold_offset or 0),
        'hold_bars_base': int(row.hold_bars_base or 12),
        'hold_bars_min': int(row.hold_bars_min or 4),
        'hold_bars_max': int(row.hold_bars_max or 30),
        'reentry_cooldown_sec': int(row.reentry_cooldown_sec or 300),
        'risk_multiplier': float(row.risk_multiplier or 1.0),
        'aggressiveness': float(row.aggressiveness or 1.0),
        'autotune': bool(row.autotune),
        'session_bias': row.session_bias or 'all',
        'regime_bias': row.regime_bias or '',
        'preferred_side': row.preferred_side or 'both',
        'best_hours_json': _parse_jsonish(row.best_hours_json, []),
        'blocked_hours_json': _parse_jsonish(row.blocked_hours_json, []),
        'news_sensitivity': float(row.news_sensitivity or 1.0),
        'confidence_bias': float(row.confidence_bias or 1.0),
        'notes': row.notes,
        'source': row.source or 'runtime',
        'profile_version': int(row.profile_version or 1),
        'last_regime': row.last_regime,
        'last_strategy': row.last_strategy,
        'last_threshold': int(row.last_threshold) if row.last_threshold is not None else None,
        'last_hold_bars': int(row.last_hold_bars) if row.last_hold_bars is not None else None,
        'last_win_rate': float(row.last_win_rate) if row.last_win_rate is not None else None,
        'sample_size': int(row.sample_size or 0),
        'last_tuned_ts': int(row.last_tuned_ts or 0),
        'created_ts': int(row.created_ts or 0),
        'updated_ts': int(row.updated_ts or 0),
    }


def _seed_profile(instrument_id: str, *, preferred_strategies: str | None = None, base_hold_bars: int = 12, base_reentry_sec: int = 300) -> dict[str, Any]:
    ticker = instrument_id.split(':', 1)[-1].upper()
    blue_chip = ticker in {'SBER', 'GAZP', 'LKOH', 'NVTK', 'ROSN', 'YNDX', 'GMKN', 'TATN', 'MOEX', 'MTSS'}
    now_ms = int(time.time() * 1000)
    return {
        'instrument_id': instrument_id,
        'enabled': True,
        'preferred_strategies': preferred_strategies or 'breakout,mean_reversion,vwap_bounce',
        'decision_threshold_offset': -2 if blue_chip else 2,
        'hold_bars_base': int(base_hold_bars),
        'hold_bars_min': 4,
        'hold_bars_max': 30 if blue_chip else 22,
        'reentry_cooldown_sec': 10 if blue_chip else max(10, min(int(base_reentry_sec), 30)),
        'risk_multiplier': 1.0 if blue_chip else 0.9,
        'aggressiveness': 1.1 if blue_chip else 0.95,
        'autotune': True,
        'session_bias': 'all',
        'regime_bias': '',
        'preferred_side': 'both',
        'best_hours_json': [10, 11, 12, 14, 15] if blue_chip else [10, 11, 14, 15],
        'blocked_hours_json': [7, 8, 9, 18, 19, 20, 21, 22, 23],
        'news_sensitivity': 0.95 if blue_chip else 1.1,
        'confidence_bias': 1.0,
        'notes': 'auto-seeded profile',
        'source': 'runtime',
        'profile_version': 2,
        'last_regime': None,
        'last_strategy': None,
        'last_threshold': None,
        'last_hold_bars': None,
        'last_win_rate': None,
        'sample_size': 0,
        'last_tuned_ts': 0,
        'created_ts': now_ms,
        'updated_ts': now_ms,
    }


def _db_get_profile(db: Session, instrument_id: str) -> SymbolProfile | None:
    return db.query(SymbolProfile).filter(SymbolProfile.instrument_id == instrument_id).first()


def _ensure_profile_row(
    db: Session,
    instrument_id: str,
    *,
    preferred_strategies: str | None = None,
    base_hold_bars: int = 12,
    base_reentry_sec: int = 300,
) -> SymbolProfile:
    row = _db_get_profile(db, instrument_id)
    if row:
        return row
    file_profile = _file_store_get(instrument_id)
    payload = dict(file_profile or _seed_profile(
        instrument_id,
        preferred_strategies=preferred_strategies,
        base_hold_bars=base_hold_bars,
        base_reentry_sec=base_reentry_sec,
    ))
    row = SymbolProfile(
        instrument_id=instrument_id,
        enabled=bool(payload.get('enabled', True)),
        preferred_strategies=str(payload.get('preferred_strategies') or preferred_strategies or 'breakout,mean_reversion,vwap_bounce'),
        decision_threshold_offset=int(payload.get('decision_threshold_offset') or 0),
        hold_bars_base=int(payload.get('hold_bars_base') or base_hold_bars or 12),
        hold_bars_min=int(payload.get('hold_bars_min') or 4),
        hold_bars_max=int(payload.get('hold_bars_max') or 30),
        reentry_cooldown_sec=int(payload.get('reentry_cooldown_sec') or base_reentry_sec or 300),
        risk_multiplier=float(payload.get('risk_multiplier') or 1.0),
        aggressiveness=float(payload.get('aggressiveness') or 1.0),
        autotune=bool(payload.get('autotune', True)),
        session_bias=str(payload.get('session_bias') or 'all'),
        regime_bias=str(payload.get('regime_bias') or ''),
        preferred_side=str(payload.get('preferred_side') or 'both'),
        best_hours_json=list(_parse_jsonish(payload.get('best_hours_json'), [])),
        blocked_hours_json=list(_parse_jsonish(payload.get('blocked_hours_json'), [])),
        news_sensitivity=float(payload.get('news_sensitivity') or 1.0),
        confidence_bias=float(payload.get('confidence_bias') or 1.0),
        notes=payload.get('notes'),
        source=str(payload.get('source') or ('json_migrated' if file_profile else 'runtime')),
        profile_version=int(payload.get('profile_version') or 2),
        last_regime=payload.get('last_regime'),
        last_strategy=payload.get('last_strategy'),
        last_threshold=payload.get('last_threshold'),
        last_hold_bars=payload.get('last_hold_bars'),
        last_win_rate=payload.get('last_win_rate'),
        sample_size=int(payload.get('sample_size') or 0),
        last_tuned_ts=int(payload.get('last_tuned_ts') or 0),
        created_ts=int(payload.get('created_ts') or int(time.time() * 1000)),
        updated_ts=int(payload.get('updated_ts') or int(time.time() * 1000)),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _resolve_profile_payload(
    db: Session,
    instrument_id: str,
    *,
    preferred_strategies: str | None = None,
    base_hold_bars: int = 12,
    base_reentry_sec: int = 300,
    create_if_missing: bool = False,
) -> dict[str, Any]:
    if create_if_missing:
        return _profile_to_dict(_ensure_profile_row(
            db,
            instrument_id,
            preferred_strategies=preferred_strategies,
            base_hold_bars=base_hold_bars,
            base_reentry_sec=base_reentry_sec,
        ))
    row = _db_get_profile(db, instrument_id)
    if row is not None:
        return _profile_to_dict(row)
    file_profile = _file_store_get(instrument_id)
    if file_profile:
        return dict(file_profile)
    return _seed_profile(
        instrument_id,
        preferred_strategies=preferred_strategies,
        base_hold_bars=base_hold_bars,
        base_reentry_sec=base_reentry_sec,
    )


def _merge_profile_row(row: SymbolProfile, patch: dict[str, Any]) -> SymbolProfile:
    for key, value in patch.items():
        if value is None or not hasattr(row, key):
            continue
        setattr(row, key, value)
    row.updated_ts = int(time.time() * 1000)
    if getattr(row, 'profile_version', None) is None:
        row.profile_version = 2
    return row


@dataclass
class AdaptiveSymbolPlan:
    instrument_id: str
    strategy_name: str
    strategy_source: str
    regime: str
    decision_threshold: int
    threshold_offset: int
    hold_bars: int
    reentry_cooldown_sec: int
    risk_multiplier: float
    aggressiveness: float
    recent_win_rate: float | None
    recent_avg_bars: float | None
    sample_size: int
    analysis_timeframe: str = '1m'
    execution_timeframe: str = '1m'
    confirmation_timeframe: str | None = None
    timeframe_source: str = 'global'
    analysis_timeframe_floor: str = '1m'
    notes: list[str] | None = None

    def to_meta(self) -> dict[str, Any]:
        payload = asdict(self)
        payload['risk_multiplier'] = round(float(self.risk_multiplier), 4)
        payload['aggressiveness'] = round(float(self.aggressiveness), 4)
        payload['recent_win_rate'] = round(float(self.recent_win_rate), 4) if self.recent_win_rate is not None else None
        payload['recent_avg_bars'] = round(float(self.recent_avg_bars), 2) if self.recent_avg_bars is not None else None
        return payload


PLAN_CACHE_TTL_MS = 15_000
_PLAN_CACHE: dict[str, tuple[int, AdaptiveSymbolPlan]] = {}


def _parse_strategy_names(name: str | None) -> list[str]:
    return StrategySelector.parse_names(name)


def _extract_features(candles: list[dict[str, Any]]) -> dict[str, float | str | None]:
    if not candles:
        return {'regime': 'unknown', 'volatility_pct': 0.0, 'trend_strength': 0.0, 'chop_ratio': 0.0, 'body_ratio': 0.0}
    closes = [float(c.get('close', 0.0) or 0.0) for c in candles[-40:]]
    opens = [float(c.get('open', closes[idx] if idx < len(closes) else 0.0) or closes[idx]) for idx, c in enumerate(candles[-40:])]
    highs = [float(c.get('high', max(o, cl)) or max(o, cl)) for o, cl, c in zip(opens, closes, candles[-40:])]
    lows = [float(c.get('low', min(o, cl)) or min(o, cl)) for o, cl, c in zip(opens, closes, candles[-40:])]
    returns = []
    for prev, cur in zip(closes[:-1], closes[1:]):
        if prev:
            returns.append((cur - prev) / prev)
    volatility_pct = _safe_std(returns[-20:]) * 100.0
    net_move = abs(closes[-1] - closes[max(0, len(closes) - 11)]) if len(closes) >= 11 else abs(closes[-1] - closes[0])
    ranges = [max(1e-9, h - l) for h, l in zip(highs[-20:], lows[-20:])]
    avg_range = _safe_mean(ranges) or 1e-9
    trend_strength = float(_clamp((net_move / avg_range) if avg_range else 0.0, 0.0, 100.0))
    signs = [1 if r > 0 else (-1 if r < 0 else 0) for r in returns[-12:]]
    sign_flips = sum(1 for prev, cur in zip(signs[:-1], signs[1:]) if prev != 0 and cur != 0 and prev != cur)
    chop_ratio = float(sign_flips / max(1, len(signs) - 1))
    body_ratio = float(_safe_mean([
        abs(cl - op) / max(1e-9, hi - lo)
        for op, cl, hi, lo in zip(opens[-20:], closes[-20:], highs[-20:], lows[-20:])
    ]) or 0.0)
    if volatility_pct >= 0.85 and trend_strength >= 3.0:
        regime = 'expansion_trend'
    elif trend_strength >= 2.0 and chop_ratio <= 0.35:
        regime = 'trend'
    elif volatility_pct <= 0.22 and chop_ratio >= 0.45:
        regime = 'compression'
    elif chop_ratio >= 0.6:
        regime = 'chop'
    elif body_ratio <= 0.28:
        regime = 'grind'
    else:
        regime = 'balanced'
    return {
        'regime': regime,
        'volatility_pct': round(volatility_pct, 4),
        'trend_strength': round(trend_strength, 4),
        'chop_ratio': round(chop_ratio, 4),
        'body_ratio': round(body_ratio, 4),
    }


def _store_regime_snapshot(db: Session, instrument_id: str, candles: list[dict[str, Any]], features: dict[str, Any], timeframe: str = '1m') -> None:
    if not candles:
        return
    last_ts = int((candles[-1] or {}).get('time') or 0)
    exists = (
        db.query(SymbolRegimeSnapshot)
        .filter(
            SymbolRegimeSnapshot.instrument_id == instrument_id,
            SymbolRegimeSnapshot.timeframe == timeframe,
            SymbolRegimeSnapshot.ts == last_ts,
        )
        .first()
    )
    if exists:
        exists.regime = str(features.get('regime') or 'balanced')
        exists.volatility_pct = float(features.get('volatility_pct') or 0.0)
        exists.trend_strength = float(features.get('trend_strength') or 0.0)
        exists.chop_ratio = float(features.get('chop_ratio') or 0.0)
        exists.body_ratio = float(features.get('body_ratio') or 0.0)
        exists.payload = dict(features)
    else:
        db.add(SymbolRegimeSnapshot(
            instrument_id=instrument_id,
            ts=last_ts,
            timeframe=timeframe,
            regime=str(features.get('regime') or 'balanced'),
            volatility_pct=float(features.get('volatility_pct') or 0.0),
            trend_strength=float(features.get('trend_strength') or 0.0),
            chop_ratio=float(features.get('chop_ratio') or 0.0),
            body_ratio=float(features.get('body_ratio') or 0.0),
            payload=dict(features),
        ))
    try:
        db.flush()
    except Exception:
        pass



def _recent_performance(db: Session, instrument_id: str, *, limit: int = 16) -> dict[str, Any]:
    entries = (
        db.query(DecisionLog)
        .filter(DecisionLog.type == 'position_closed')
        .order_by(DecisionLog.ts.desc())
        .limit(400)
        .all()
    )
    samples: list[dict[str, Any]] = []
    for entry in entries:
        payload = entry.payload or {}
        if payload.get('instrument_id') != instrument_id:
            continue
        net_pnl = float(payload.get('net_pnl') or 0.0)
        opened_ts = int(payload.get('opened_ts') or 0)
        closed_ts = int(payload.get('closed_ts') or entry.ts or 0)
        bars = max(1.0, (closed_ts - opened_ts) / 60_000.0) if opened_ts and closed_ts else None
        samples.append({
            'net_pnl': net_pnl,
            'bars': bars,
            'strategy': str(payload.get('strategy_name') or ''),
            'reason': str(payload.get('reason') or ''),
        })
        if len(samples) >= limit:
            break
    if not samples:
        return {
            'sample_size': 0,
            'win_rate': None,
            'avg_bars': None,
            'avg_win_bars': None,
            'avg_loss_bars': None,
            'avg_pnl': None,
            'best_strategy': None,
        }
    wins = [s for s in samples if float(s['net_pnl']) > 0]
    losses = [s for s in samples if float(s['net_pnl']) <= 0]
    strategy_scores: dict[str, list[float]] = {}
    for sample in samples:
        strategy = sample['strategy'] or 'unknown'
        strategy_scores.setdefault(strategy, []).append(float(sample['net_pnl']))
    best_strategy = None
    if strategy_scores:
        ranked = sorted(strategy_scores.items(), key=lambda item: (_safe_mean(item[1]) or -1e9, len(item[1])), reverse=True)
        best_strategy = ranked[0][0]
    return {
        'sample_size': len(samples),
        'win_rate': len(wins) / len(samples),
        'avg_bars': _safe_mean([float(s['bars']) for s in samples if s['bars'] is not None]),
        'avg_win_bars': _safe_mean([float(s['bars']) for s in wins if s['bars'] is not None]),
        'avg_loss_bars': _safe_mean([float(s['bars']) for s in losses if s['bars'] is not None]),
        'avg_pnl': _safe_mean([float(s['net_pnl']) for s in samples]),
        'best_strategy': best_strategy,
    }


def _recent_event_regime(db: Session, instrument_id: str, *, max_age_ms: int = 6 * 60 * 60 * 1000) -> dict[str, Any] | None:
    now_ms = int(time.time() * 1000)
    row = (
        db.query(SymbolEventRegime)
        .filter(SymbolEventRegime.instrument_id == instrument_id, SymbolEventRegime.ts >= now_ms - max_age_ms)
        .order_by(SymbolEventRegime.ts.desc())
        .first()
    )
    if not row:
        return None
    return {
        'regime': row.regime,
        'severity': float(row.severity or 0.0),
        'direction': row.direction,
        'score_bias': int(row.score_bias or 0),
        'hold_bias': int(row.hold_bias or 0),
        'risk_bias': float(row.risk_bias or 1.0),
        'action': row.action or 'observe',
        'payload': row.payload or {},
        'ts': int(row.ts or 0),
    }


_MSK = ZoneInfo("Europe/Moscow")


def _session_low_vol_timeframe_floor(*, regime: str, settings: Any, candles: list[dict[str, Any]]) -> tuple[str, str | None]:
    features = _extract_features(candles)
    volatility_pct = float(features.get('volatility_pct') or 0.0)
    body_ratio = float(features.get('body_ratio') or 0.0)
    floor = '1m'
    reason = None

    session_type = getattr(settings, 'trading_session', None) or getattr(settings, 'session_type', None) or 'all'
    snapshot = get_schedule_snapshot(session_type=session_type)
    now_msk = datetime.now(timezone.utc).astimezone(_MSK)
    low_vol = volatility_pct <= 0.18 or (regime in {'compression', 'grind'} and volatility_pct <= 0.25) or body_ratio <= 0.18
    very_low_vol = volatility_pct <= 0.10 or (regime in {'compression', 'grind'} and body_ratio <= 0.14)
    premarket_like = False

    start_iso = snapshot.get('current_session_start')
    if snapshot.get('is_open') and start_iso:
        try:
            start_dt = datetime.fromisoformat(str(start_iso))
            minutes_since_open = max(0.0, (now_msk - start_dt.astimezone(_MSK)).total_seconds() / 60.0)
            premarket_like = minutes_since_open < max(10, int(getattr(settings, 'no_trade_opening_minutes', 10) or 10) + 5)
        except Exception:
            premarket_like = False
    elif snapshot.get('is_trading_day') and snapshot.get('next_open'):
        try:
            next_open = datetime.fromisoformat(str(snapshot.get('next_open'))).astimezone(_MSK)
            minutes_to_open = (next_open - now_msk).total_seconds() / 60.0
            premarket_like = 0.0 <= minutes_to_open <= 90.0
        except Exception:
            premarket_like = False

    if premarket_like:
        floor = '5m'
        reason = 'session_preopen_floor'
        if low_vol or regime in {'compression', 'grind'}:
            floor = '15m'
            reason = 'session_preopen_lowvol_floor'
    elif very_low_vol and regime in {'compression', 'grind', 'balanced'}:
        floor = '15m'
        reason = 'very_low_vol_floor'
    elif low_vol and regime in {'compression', 'grind', 'balanced'}:
        floor = '5m'
        reason = 'low_vol_floor'

    return floor, reason


def _select_timeframes(*, strategy_name: str, regime: str, settings: Any, candles: list[dict[str, Any]]) -> tuple[str, str, str | None, str, str | None]:
    session_floor, floor_reason = _session_low_vol_timeframe_floor(regime=regime, settings=settings, candles=candles)
    analysis_tf, execution_tf, confirmation_tf, timeframe_source = _select_timeframes_base(strategy_name=strategy_name, regime=regime, settings=settings, candles=candles, session_floor=session_floor)
    if floor_reason and 'vol' in floor_reason and timeframe_source == 'session':
        timeframe_source = 'volatility'
    return analysis_tf, execution_tf, confirmation_tf, timeframe_source, session_floor


def _build_plan_cache_key(
    instrument_id: str,
    candles: list[dict[str, Any]],
    settings: Any,
    profile: dict[str, Any],
    recent_event: dict[str, Any] | None,
    *,
    persist: bool,
) -> str:
    last_candle_ts = str((candles[-1] or {}).get('time') if candles else '')
    parts = [
        instrument_id,
        last_candle_ts,
        str(getattr(settings, 'decision_threshold', 70)),
        str(getattr(settings, 'time_stop_bars', 12)),
        str(getattr(settings, 'signal_reentry_cooldown_sec', 300)),
        str(getattr(settings, 'higher_timeframe', '15m')),
        str(getattr(settings, 'strategy_name', 'breakout,mean_reversion,vwap_bounce')),
        str(profile.get('preferred_strategies') or ''),
        str(profile.get('updated_ts') or 0),
        str(profile.get('last_tuned_ts') or 0),
        str(recent_event.get('ts') if recent_event else 0),
        'persist' if persist else 'readonly',
    ]
    return ':'.join(parts)



def build_symbol_plan(db: Session, instrument_id: str, candles: list[dict[str, Any]], settings: Any, *, persist: bool = True) -> AdaptiveSymbolPlan:
    base_hold_bars = int(getattr(settings, 'time_stop_bars', 12) or 12)
    base_reentry_sec = int(getattr(settings, 'signal_reentry_cooldown_sec', 300) or 300)
    preferred_strategies = getattr(settings, 'strategy_name', None) or 'breakout,mean_reversion,vwap_bounce'
    profile = _resolve_profile_payload(
        db,
        instrument_id,
        preferred_strategies=preferred_strategies,
        base_hold_bars=base_hold_bars,
        base_reentry_sec=base_reentry_sec,
        create_if_missing=persist,
    )
    recent_event = _recent_event_regime(db, instrument_id)
    cache_key = _build_plan_cache_key(instrument_id, candles, settings, profile, recent_event, persist=persist)
    cached = _PLAN_CACHE.get(cache_key)
    now_ms = int(time.time() * 1000)
    if cached and cached[0] + PLAN_CACHE_TTL_MS >= now_ms:
        return cached[1]

    features = _extract_features(candles)
    if persist:
        _store_regime_snapshot(db, instrument_id, candles, features)
    perf = _recent_performance(db, instrument_id)

    global_allowed = _parse_strategy_names(str(preferred_strategies))
    profile_allowed = _parse_strategy_names(str(profile.get('preferred_strategies') or preferred_strategies))
    regime = str(features.get('regime') or 'balanced')
    regime_allowed = list(profile_allowed or global_allowed)
    effective_allowed = [name for name in regime_allowed if name in global_allowed] or list(global_allowed or profile_allowed)
    strategy_name = _choose_strategy(effective_allowed, regime, perf.get('best_strategy'))
    if profile_allowed and strategy_name in profile_allowed and strategy_name not in global_allowed:
        strategy_name = _choose_strategy(list(global_allowed or ['breakout']), regime, perf.get('best_strategy'))
    if strategy_name in profile_allowed and strategy_name in global_allowed:
        strategy_source = 'symbol'
    elif strategy_name in global_allowed:
        strategy_source = 'global'
    else:
        strategy_source = 'regime'

    analysis_timeframe, execution_timeframe, confirmation_timeframe, timeframe_source, analysis_timeframe_floor = _select_timeframes(strategy_name=strategy_name, regime=regime, settings=settings, candles=candles)
    notes: list[str] = [
        f'regime={regime}',
        f'strategy={strategy_name}',
        f'strategy_source={strategy_source}',
        f'analysis_tf={analysis_timeframe}',
        f'analysis_floor={analysis_timeframe_floor}',
        f'execution_tf={execution_timeframe}',
        f'policy_effective={','.join(effective_allowed) if effective_allowed else strategy_name}',
    ]
    if set(profile_allowed) - set(global_allowed):
        notes.append('profile strategies constrained by global whitelist')

    base_threshold = int(getattr(settings, 'decision_threshold', 70) or 70)
    threshold_offset = int(profile.get('decision_threshold_offset') or 0)
    if regime == 'trend' and strategy_name == 'breakout':
        threshold_offset -= 8
        notes.append('trend breakout threshold lowered')
    elif regime == 'expansion_trend' and strategy_name in {'breakout', 'vwap_bounce'}:
        threshold_offset -= 10
        notes.append('expansion regime allows faster entries')
    elif regime in {'compression', 'chop'} and strategy_name == 'mean_reversion':
        threshold_offset -= 5
        notes.append('mean reversion favored in chop/compression')
    elif regime in {'compression', 'chop'}:
        threshold_offset += 6
        notes.append('breakout discouraged in chop/compression')
    elif regime == 'grind':
        threshold_offset -= 2
        notes.append('grind regime favors VWAP/bounce continuation')

    win_rate = perf.get('win_rate')
    sample_size = int(perf.get('sample_size') or 0)
    avg_pnl = float(perf.get('avg_pnl') or 0.0) if perf.get('avg_pnl') is not None else None
    if sample_size >= 4 and win_rate is not None:
        if win_rate >= 0.60 and (avg_pnl or 0.0) > 0:
            threshold_offset -= 4
            notes.append('recent positive edge lowers threshold')
        elif win_rate <= 0.35:
            threshold_offset += 6
            notes.append('recent weak edge raises threshold')

    aggressiveness = float(profile.get('aggressiveness') or 1.0)
    decision_threshold = int(round(_clamp(base_threshold + threshold_offset * aggressiveness, 15, 95)))

    base_hold = int(profile.get('hold_bars_base') or base_hold_bars)
    hold_bars = base_hold
    if regime == 'expansion_trend':
        hold_bars += 8
    elif regime == 'trend':
        hold_bars += 5
    elif regime == 'grind':
        hold_bars += 2
    elif regime == 'compression':
        hold_bars -= 3
    elif regime == 'chop':
        hold_bars -= 5
    avg_win_bars = perf.get('avg_win_bars')
    avg_loss_bars = perf.get('avg_loss_bars')
    if avg_win_bars is not None and sample_size >= 4:
        hold_bars = int(round((hold_bars * 0.6) + (float(avg_win_bars) * 0.4)))
    elif avg_loss_bars is not None and regime in {'chop', 'compression'}:
        hold_bars = int(round(min(hold_bars, float(avg_loss_bars) + 1)))
    hold_bars = int(_clamp(hold_bars, int(profile.get('hold_bars_min') or 4), int(profile.get('hold_bars_max') or 30)))

    base_reentry = int(profile.get('reentry_cooldown_sec') or base_reentry_sec)
    reentry = base_reentry
    if regime == 'expansion_trend':
        reentry = max(5, int(base_reentry * 0.25))
    elif regime == 'trend':
        reentry = max(5, int(base_reentry * 0.4))
    elif regime == 'compression':
        reentry = int(base_reentry * 0.75)
    elif regime == 'chop':
        reentry = int(base_reentry * 1.10)
    if str(getattr(settings, 'trade_mode', '') or '') == 'auto_paper':
        reentry = min(reentry, 10)
    reentry = int(_clamp(reentry, 5, 300))

    risk_multiplier = float(profile.get('risk_multiplier') or 1.0)
    if sample_size >= 4 and win_rate is not None:
        if win_rate >= 0.60 and (avg_pnl or 0.0) > 0:
            risk_multiplier *= 1.15
            notes.append('recent wins allow mild size increase')
        elif win_rate <= 0.35:
            risk_multiplier *= 0.75
            notes.append('recent weakness cuts size')
    if regime in {'compression', 'chop'} and strategy_name == 'breakout':
        risk_multiplier *= 0.8
    if regime in {'trend', 'expansion_trend'} and strategy_name in {'breakout', 'vwap_bounce'}:
        risk_multiplier *= 1.1

    if recent_event:
        event_bias = int(recent_event.get('score_bias') or 0)
        decision_threshold = int(_clamp(decision_threshold - event_bias, 15, 95))
        hold_bars = int(_clamp(hold_bars + int(recent_event.get('hold_bias') or 0), int(profile.get('hold_bars_min') or 4), int(profile.get('hold_bars_max') or 30)))
        risk_multiplier *= float(recent_event.get('risk_bias') or 1.0)
        notes.append(f"event={recent_event.get('regime')}:{recent_event.get('action')}")
        if str(recent_event.get('action') or 'observe') == 'de_risk' and float(recent_event.get('severity') or 0.0) >= 0.82:
            decision_threshold = int(_clamp(decision_threshold + 6, 15, 95))
            notes.append('event de-risk raised threshold')

    risk_multiplier = float(_clamp(risk_multiplier, 0.35, 1.50))

    should_persist = False
    tuned = dict(profile)
    tuned.update({
        'last_regime': regime,
        'last_strategy': strategy_name,
        'last_threshold': decision_threshold,
        'last_hold_bars': hold_bars,
        'last_win_rate': round(float(win_rate), 4) if win_rate is not None else None,
        'sample_size': sample_size,
    })
    last_tuned_ts = int(profile.get('last_tuned_ts') or 0)
    if sample_size >= 6 and bool(profile.get('autotune', True)) and now_ms - last_tuned_ts >= 30 * 60_000:
        tuned['hold_bars_base'] = int(round((int(profile.get('hold_bars_base') or base_hold) * 0.7) + (hold_bars * 0.3)))
        tuned['decision_threshold_offset'] = int(round((int(profile.get('decision_threshold_offset') or 0) * 0.7) + ((decision_threshold - base_threshold) * 0.3)))
        tuned['reentry_cooldown_sec'] = int(round((int(profile.get('reentry_cooldown_sec') or base_reentry) * 0.7) + (reentry * 0.3)))
        tuned['last_tuned_ts'] = now_ms
        tuned['notes'] = f'auto-tuned from {sample_size} recent closes'
        tuned['source'] = 'online_recalibration'
        tuned['profile_version'] = int(profile.get('profile_version') or 2)
        should_persist = persist
    elif persist and (profile.get('last_regime') != regime or profile.get('last_strategy') != strategy_name):
        should_persist = True

    if should_persist:
        upsert_symbol_profile(instrument_id, tuned, db=db)

    plan = AdaptiveSymbolPlan(
        instrument_id=instrument_id,
        strategy_name=strategy_name,
        strategy_source=strategy_source,
        regime=regime,
        decision_threshold=decision_threshold,
        threshold_offset=decision_threshold - base_threshold,
        hold_bars=hold_bars,
        reentry_cooldown_sec=reentry,
        risk_multiplier=risk_multiplier,
        aggressiveness=aggressiveness,
        recent_win_rate=win_rate,
        recent_avg_bars=perf.get('avg_bars'),
        sample_size=sample_size,
        analysis_timeframe=analysis_timeframe,
        execution_timeframe=execution_timeframe,
        confirmation_timeframe=confirmation_timeframe,
        timeframe_source=timeframe_source,
        analysis_timeframe_floor=analysis_timeframe_floor,
        notes=notes,
    )
    _PLAN_CACHE[cache_key] = (now_ms, plan)
    return plan



def build_symbol_plan_readonly(db: Session, instrument_id: str, candles: list[dict[str, Any]], settings: Any) -> AdaptiveSymbolPlan:
    return build_symbol_plan(db, instrument_id, candles, settings, persist=False)



def build_symbol_plan_persisting(db: Session, instrument_id: str, candles: list[dict[str, Any]], settings: Any) -> AdaptiveSymbolPlan:
    return build_symbol_plan(db, instrument_id, candles, settings, persist=True)



def _candles_for_training(db: Session, instrument_id: str, timeframe: str = '1m', lookback_days: int = 180) -> list[dict[str, Any]]:
    cutoff_ts = int(time.time() * 1000) - lookback_days * 86_400_000
    rows = (
        db.query(CandleCache)
        .filter(CandleCache.instrument_id == instrument_id, CandleCache.timeframe == timeframe, CandleCache.ts >= cutoff_ts)
        .order_by(CandleCache.ts.asc())
        .all()
    )
    return [
        {
            'time': int(c.ts),
            'open': float(c.open),
            'high': float(c.high),
            'low': float(c.low),
            'close': float(c.close),
            'volume': int(c.volume or 0),
        }
        for c in rows
    ]


def _hourly_returns(candles: list[dict[str, Any]]) -> dict[int, list[float]]:
    result: dict[int, list[float]] = {}
    for prev, cur in zip(candles[:-1], candles[1:]):
        ts = int(cur.get('time') or 0) / 1000.0
        hour = time.gmtime(ts).tm_hour
        prev_close = float(prev.get('close') or 0.0)
        cur_close = float(cur.get('close') or 0.0)
        if prev_close <= 0:
            continue
        result.setdefault(hour, []).append((cur_close - prev_close) / prev_close)
    return result


def _diagnostics_from_history(db: Session, instrument_id: str, candles: list[dict[str, Any]]) -> dict[str, Any]:
    features = _extract_features(candles)
    closes = [float(c.get('close') or 0.0) for c in candles if c.get('close') is not None]
    volumes = [float(c.get('volume') or 0.0) for c in candles]
    returns = []
    for prev, cur in zip(closes[:-1], closes[1:]):
        if prev > 0:
            returns.append((cur - prev) / prev)
    hourly = _hourly_returns(candles)
    ranked_hours = []
    for hour, vals in hourly.items():
        avg = _safe_mean(vals) or 0.0
        ranked_hours.append((avg, len(vals), hour))
    ranked_hours.sort(reverse=True)
    best_hours = [h for _, n, h in ranked_hours if n >= 20][:5]
    worst_hours = [h for _, n, h in sorted(ranked_hours) if n >= 20][:5]
    perf = _recent_performance(db, instrument_id, limit=40)
    return {
        'instrument_id': instrument_id,
        'candles_used': len(candles),
        'avg_close': round(_safe_mean(closes) or 0.0, 6),
        'avg_volume': round(_safe_mean(volumes) or 0.0, 2),
        'volatility_pct': round((_safe_std(returns) * 100.0) if returns else 0.0, 4),
        'regime': features.get('regime') or 'balanced',
        'trend_strength': features.get('trend_strength'),
        'chop_ratio': features.get('chop_ratio'),
        'body_ratio': features.get('body_ratio'),
        'best_hours': best_hours,
        'blocked_hours': worst_hours,
        'performance': perf,
    }


def _strategy_validation_score(result: dict[str, Any]) -> float:
    return (
        float(result.get('total_return_pct') or 0.0) * 0.32
        + float(result.get('win_rate') or 0.0) * 0.28
        + float(result.get('profit_factor') or 0.0) * 22.0
        - float(result.get('max_drawdown_pct') or 0.0) * 0.20
    )


def _walk_forward_validate(instrument_id: str, candles: list[dict[str, Any]], *, initial_balance: float = 100_000.0, risk_pct: float = 0.5) -> dict[str, Any]:
    if len(candles) < 320:
        return {'available': False, 'reason': 'not_enough_candles', 'candles_used': len(candles)}

    from apps.backtest.engine import BacktestEngine

    selector = StrategySelector()
    strategies = selector.available()
    fold_count = 4
    test_len = max(80, min(240, len(candles) // (fold_count + 2)))
    min_train = max(200, test_len * 2)
    if len(candles) < min_train + test_len:
        return {'available': False, 'reason': 'not_enough_walk_forward_history', 'candles_used': len(candles)}

    folds: list[dict[str, Any]] = []
    rankings: dict[str, list[float]] = {name: [] for name in strategies}
    for fold_idx in range(fold_count):
        train_end = min_train + fold_idx * test_len
        test_start = train_end
        test_end = min(len(candles), test_start + test_len)
        if test_end - test_start < 60:
            break
        test_slice = candles[test_start:test_end]
        fold_scores: list[dict[str, Any]] = []
        for strategy_name in strategies:
            strategy = selector.get(strategy_name)
            if len(test_slice) < strategy.lookback + 10:
                continue
            engine = BacktestEngine(
                strategy=strategy,
                settings=None,
                initial_balance=initial_balance,
                risk_pct=risk_pct,
                commission_pct=0.03,
                use_decision_engine=False,
            )
            try:
                result = engine.run(instrument_id, test_slice)
            except Exception:
                continue
            light = {
                'strategy': strategy_name,
                'total_return_pct': float(result.total_return_pct or 0.0),
                'win_rate': float(result.win_rate or 0.0),
                'profit_factor': float(result.profit_factor or 0.0),
                'max_drawdown_pct': float(result.max_drawdown_pct or 0.0),
                'total_trades': int(result.total_trades or 0),
            }
            light['validation_score'] = round(_strategy_validation_score(light), 4)
            rankings[strategy_name].append(light['validation_score'])
            fold_scores.append(light)
        if fold_scores:
            fold_scores.sort(key=lambda item: item['validation_score'], reverse=True)
            folds.append({
                'fold': fold_idx + 1,
                'test_from_ts': int(test_slice[0].get('time') or 0),
                'test_to_ts': int(test_slice[-1].get('time') or 0),
                'best_strategy': fold_scores[0]['strategy'],
                'scores': fold_scores,
            })

    aggregate = []
    for strategy_name, values in rankings.items():
        if not values:
            continue
        aggregate.append({
            'strategy': strategy_name,
            'avg_score': round(_safe_mean(values) or 0.0, 4),
            'std_score': round(_safe_std(values), 4),
            'folds': len(values),
            'robust_score': round((_safe_mean(values) or 0.0) - (_safe_std(values) * 0.8), 4),
        })
    aggregate.sort(key=lambda item: (item['robust_score'], item['avg_score']), reverse=True)
    return {
        'available': bool(aggregate),
        'folds': folds,
        'strategy_rankings': aggregate,
        'best_strategy': aggregate[0]['strategy'] if aggregate else None,
        'candles_used': len(candles),
        'fold_count': len(folds),
        'test_window_bars': test_len,
    }


def train_symbol_profile(
    db: Session,
    instrument_id: str,
    *,
    lookback_days: int = 180,
    timeframe: str = '1m',
    source: str = 'api',
) -> dict[str, Any]:
    candles = _candles_for_training(db, instrument_id, timeframe=timeframe, lookback_days=lookback_days)
    diagnostics = _diagnostics_from_history(db, instrument_id, candles)
    walk_forward = _walk_forward_validate(instrument_id, candles)
    diagnostics['walk_forward'] = walk_forward
    perf = diagnostics.get('performance') or {}
    regime = str(diagnostics.get('regime') or 'balanced')
    volatility_pct = float(diagnostics.get('volatility_pct') or 0.0)
    best_hours = diagnostics.get('best_hours') or []
    blocked_hours = diagnostics.get('blocked_hours') or []

    row = _ensure_profile_row(db, instrument_id)
    recommended: dict[str, Any] = {}
    current = _profile_to_dict(row)

    # Strategy family by observed regime.
    best_validated_strategy = (walk_forward.get('best_strategy') if isinstance(walk_forward, dict) else None) or None
    if best_validated_strategy:
        rankings = walk_forward.get('strategy_rankings') or []
        ordered = [str(item.get('strategy')) for item in rankings if item.get('strategy')]
        recommended['preferred_strategies'] = ','.join(ordered[:3]) if ordered else current.get('preferred_strategies')
        recommended['decision_threshold_offset'] = int(current.get('decision_threshold_offset') or 0)
    elif regime in {'trend', 'expansion_trend'}:
        recommended['preferred_strategies'] = 'breakout,vwap_bounce,mean_reversion'
        recommended['decision_threshold_offset'] = min(-4, int(current.get('decision_threshold_offset') or 0))
    elif regime in {'compression', 'chop'}:
        recommended['preferred_strategies'] = 'mean_reversion,vwap_bounce,breakout'
        recommended['decision_threshold_offset'] = max(2, int(current.get('decision_threshold_offset') or 0))
    else:
        recommended['preferred_strategies'] = current.get('preferred_strategies') or 'breakout,mean_reversion,vwap_bounce'

    avg_win_bars = perf.get('avg_win_bars')
    avg_loss_bars = perf.get('avg_loss_bars')
    if avg_win_bars is not None:
        recommended['hold_bars_base'] = int(_clamp(round(float(avg_win_bars) * 0.9), 4, 60))
    elif avg_loss_bars is not None:
        recommended['hold_bars_base'] = int(_clamp(round(float(avg_loss_bars) + 1), 4, 30))
    else:
        recommended['hold_bars_base'] = int(current.get('hold_bars_base') or 12)

    if volatility_pct >= 1.0:
        recommended['hold_bars_max'] = max(int(current.get('hold_bars_max') or 30), recommended['hold_bars_base'] + 12)
        recommended['reentry_cooldown_sec'] = max(1, int((current.get('reentry_cooldown_sec') or 300) * 0.55))
        recommended['risk_multiplier'] = round(min(1.25, float(current.get('risk_multiplier') or 1.0) * 1.05), 4)
    elif volatility_pct <= 0.2:
        recommended['hold_bars_max'] = max(int(current.get('hold_bars_max') or 20), recommended['hold_bars_base'] + 4)
        recommended['reentry_cooldown_sec'] = int((current.get('reentry_cooldown_sec') or 300) * 1.20)
        recommended['risk_multiplier'] = round(max(0.75, float(current.get('risk_multiplier') or 1.0) * 0.92), 4)
    else:
        recommended['hold_bars_max'] = max(int(current.get('hold_bars_max') or 24), recommended['hold_bars_base'] + 8)
        recommended['reentry_cooldown_sec'] = int(current.get('reentry_cooldown_sec') or 300)
        recommended['risk_multiplier'] = round(float(current.get('risk_multiplier') or 1.0), 4)

    win_rate = perf.get('win_rate')
    avg_pnl = perf.get('avg_pnl')
    if win_rate is not None and avg_pnl is not None:
        if float(win_rate) >= 0.58 and float(avg_pnl) > 0:
            recommended['aggressiveness'] = round(min(1.35, float(current.get('aggressiveness') or 1.0) * 1.05), 4)
            recommended['confidence_bias'] = 1.08
        elif float(win_rate) <= 0.42:
            recommended['aggressiveness'] = round(max(0.80, float(current.get('aggressiveness') or 1.0) * 0.94), 4)
            recommended['confidence_bias'] = 0.96

    if best_validated_strategy:
        recommended['notes'] = f"offline trainer + walk-forward ({lookback_days}d/{timeframe}) regime={regime} best={best_validated_strategy} candles={len(candles)}"
        top_rank = (walk_forward.get('strategy_rankings') or [{}])[0]
        robust_score = float(top_rank.get('robust_score') or 0.0)
        if robust_score > 16:
            recommended['aggressiveness'] = round(min(1.45, float(recommended.get('aggressiveness') or current.get('aggressiveness') or 1.0) * 1.05), 4)
            recommended['risk_multiplier'] = round(min(1.30, float(recommended.get('risk_multiplier') or current.get('risk_multiplier') or 1.0) * 1.05), 4)
        elif robust_score < 6:
            recommended['aggressiveness'] = round(max(0.75, float(recommended.get('aggressiveness') or current.get('aggressiveness') or 1.0) * 0.92), 4)
            recommended['risk_multiplier'] = round(max(0.65, float(recommended.get('risk_multiplier') or current.get('risk_multiplier') or 1.0) * 0.90), 4)

    recommended['best_hours_json'] = best_hours
    recommended['blocked_hours_json'] = blocked_hours
    recommended['session_bias'] = 'main'
    recommended['source'] = 'offline_training'
    recommended['profile_version'] = max(int(current.get('profile_version') or 1), 3)
    recommended['sample_size'] = int(perf.get('sample_size') or 0)
    recommended.setdefault('notes', f"offline trainer ({lookback_days}d/{timeframe}) regime={regime} candles={len(candles)}")

    profile = upsert_symbol_profile(instrument_id, recommended, db=db)

    run = SymbolTrainingRun(
        id=f"symtrain_{uuid.uuid4().hex[:10]}",
        ts=int(time.time() * 1000),
        instrument_id=instrument_id,
        mode='offline_walk_forward' if bool(walk_forward.get('available')) else 'offline',
        status='completed',
        source=source,
        candles_used=len(candles),
        trades_used=int(perf.get('sample_size') or 0),
        recommendations=dict(recommended),
        diagnostics=dict(diagnostics),
        notes=profile.get('notes'),
    )
    db.add(run)
    db.commit()

    return {'profile': profile, 'diagnostics': diagnostics, 'training_run_id': run.id}


def ensure_symbol_profiles(
    db: Session,
    instrument_ids: list[str],
    *,
    auto_train: bool = False,
    lookback_days: int = 180,
    timeframe: str = '1m',
    min_train_candles: int = 320,
    train_limit: int | None = None,
    source: str = 'ensure',
) -> dict[str, Any]:
    unique_ids = [iid for iid in dict.fromkeys(instrument_ids) if iid]
    seeded = 0
    existing = 0
    trained = 0
    errors: list[dict[str, Any]] = []
    train_budget = max(0, int(train_limit if train_limit is not None else len(unique_ids)))
    for instrument_id in unique_ids:
        row = _db_get_profile(db, instrument_id)
        if row is None:
            _ensure_profile_row(db, instrument_id)
            seeded += 1
            row = _db_get_profile(db, instrument_id)
        else:
            existing += 1
        if not row:
            errors.append({'instrument_id': instrument_id, 'error': 'profile_row_missing_after_seed'})
            continue
        if not auto_train or train_budget <= 0:
            continue
        needs_training = int(getattr(row, 'sample_size', 0) or 0) <= 0 or int(getattr(row, 'last_tuned_ts', 0) or 0) <= 0
        if not needs_training:
            continue
        candles = _candles_for_training(db, instrument_id, timeframe=timeframe, lookback_days=lookback_days)
        if len(candles) < min_train_candles:
            continue
        try:
            train_symbol_profile(db, instrument_id, lookback_days=lookback_days, timeframe=timeframe, source=source)
            trained += 1
            train_budget -= 1
        except Exception as exc:
            errors.append({'instrument_id': instrument_id, 'error': str(exc)})
    if seeded:
        db.commit()
    return {
        'items': unique_ids,
        'seeded': seeded,
        'existing': existing,
        'trained': trained,
        'errors': errors,
    }


def train_symbol_profiles_bulk(
    db: Session,
    instrument_ids: list[str],
    *,
    lookback_days: int = 180,
    timeframe: str = '1m',
    source: str = 'api_bulk',
) -> dict[str, Any]:
    items = []
    for instrument_id in instrument_ids:
        try:
            items.append(train_symbol_profile(db, instrument_id, lookback_days=lookback_days, timeframe=timeframe, source=source))
        except Exception as exc:
            items.append({'instrument_id': instrument_id, 'error': str(exc)})
    return {'items': items}


def get_symbol_diagnostics(db: Session, instrument_id: str, *, lookback_days: int = 180, timeframe: str = '1m') -> dict[str, Any]:
    candles = _candles_for_training(db, instrument_id, timeframe=timeframe, lookback_days=lookback_days)
    diagnostics = _diagnostics_from_history(db, instrument_id, candles)
    diagnostics['walk_forward'] = _walk_forward_validate(instrument_id, candles)
    snapshots = (
        db.query(SymbolRegimeSnapshot)
        .filter(SymbolRegimeSnapshot.instrument_id == instrument_id, SymbolRegimeSnapshot.timeframe == timeframe)
        .order_by(SymbolRegimeSnapshot.ts.desc())
        .limit(20)
        .all()
    )
    diagnostics['recent_regimes'] = [
        {'ts': int(s.ts), 'regime': s.regime, 'volatility_pct': float(s.volatility_pct or 0.0), 'trend_strength': float(s.trend_strength or 0.0)}
        for s in snapshots
    ]
    return diagnostics


def list_symbol_profiles(db: Session | None = None) -> list[dict[str, Any]]:
    if db is None:
        payload = _file_store_load()
        profiles = payload.get('profiles') or {}
        return [dict(v) for _, v in sorted(profiles.items(), key=lambda item: item[0])]
    rows = db.query(SymbolProfile).order_by(SymbolProfile.instrument_id.asc()).all()
    return [_profile_to_dict(row) for row in rows]


def get_symbol_profile(instrument_id: str, db: Session | None = None) -> dict[str, Any] | None:
    if db is None:
        return _file_store_get(instrument_id)
    return _resolve_profile_payload(db, instrument_id, create_if_missing=False)


def upsert_symbol_profile(instrument_id: str, patch: dict[str, Any], db: Session | None = None) -> dict[str, Any]:
    if db is None:
        current = _file_store_get(instrument_id) or _seed_profile(instrument_id)
        current.update({k: v for k, v in patch.items() if v is not None})
        return _file_store_upsert(instrument_id, current)

    row = _ensure_profile_row(db, instrument_id)
    _merge_profile_row(row, {k: v for k, v in patch.items() if v is not None})
    db.add(row)
    db.commit()
    db.refresh(row)
    # keep file export for transparency/debugging
    try:
        payload = _file_store_load()
        payload.setdefault('profiles', {})[instrument_id] = _profile_to_dict(row)
        _atomic_json_write(_json_store_path(), payload)
    except Exception:
        pass
    return _profile_to_dict(row)
