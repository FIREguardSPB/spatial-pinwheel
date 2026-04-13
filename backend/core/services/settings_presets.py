from __future__ import annotations

import re
import time
from copy import deepcopy
from typing import Any

from core.models import schemas
from core.storage.models import Watchlist

SNAPSHOT_EXCLUDED_FIELDS = {'id', 'updated_ts', 'is_active', 'telegram_bot_token', 'telegram_chat_id', 'bot_enabled'}
SNAPSHOT_SPECIAL_FIELDS = {'watchlist'}
FIELD_LABELS = {
    'risk_profile': 'Профиль риска', 'risk_per_trade_pct': 'Риск на сделку, %', 'daily_loss_limit_pct': 'Дневной лимит потерь, %',
    'max_concurrent_positions': 'Макс. позиций', 'max_trades_per_day': 'Макс. сделок в день', 'trade_mode': 'Режим торговли',
    'ai_mode': 'Режим AI', 'ai_min_confidence': 'Мин. уверенность AI', 'decision_threshold': 'Decision threshold',
    'rr_min': 'Минимальный RR', 'rr_target': 'Целевой RR', 'ml_enabled': 'ML overlay',
    'ml_take_probability_threshold': 'ML take threshold', 'ml_fill_probability_threshold': 'ML fill threshold',
    'ml_allow_take_veto': 'ML take veto', 'signal_reentry_cooldown_sec': 'Cooldown re-entry', 'worker_bootstrap_limit': 'Worker bootstrap limit',
    'trading_session': 'Торговая сессия', 'watchlist': 'Watchlist',
}

def _now_ms() -> int:
    return int(time.time() * 1000)


def _default_schema_dict() -> dict[str, Any]:
    return schemas.RiskSettings(risk_profile='balanced', risk_per_trade_pct=0.25, daily_loss_limit_pct=1.5, max_concurrent_positions=4, max_trades_per_day=120, rr_target=1.4, time_stop_bars=12, close_before_session_end_minutes=5).model_dump(mode='json')


def allowed_snapshot_keys() -> set[str]:
    return set(_default_schema_dict().keys()) - SNAPSHOT_EXCLUDED_FIELDS


def normalize_instrument_id(value: str | None) -> str:
    raw = str(value or '').strip().upper()
    if not raw:
        return ''
    if ':' in raw:
        exchange, ticker = raw.split(':', 1)
        return f'{exchange or "TQBR"}:{ticker or raw}'
    return f'TQBR:{raw}'


def build_snapshot_from_settings_dict(settings_payload: dict[str, Any], watchlist: list[str] | None = None) -> dict[str, Any]:
    snapshot = {k: deepcopy(v) for k, v in settings_payload.items() if k in allowed_snapshot_keys()}
    if watchlist is not None:
        seen, items = set(), []
        for item in watchlist:
            instrument_id = normalize_instrument_id(item)
            if instrument_id and instrument_id not in seen:
                seen.add(instrument_id)
                items.append(instrument_id)
        snapshot['watchlist'] = items
    return snapshot


def validate_snapshot_payload(snapshot: dict[str, Any] | None) -> dict[str, Any]:
    if snapshot is None:
        return {}
    if not isinstance(snapshot, dict):
        raise ValueError('Preset snapshot must be a JSON object')
    allowed = allowed_snapshot_keys() | SNAPSHOT_SPECIAL_FIELDS
    unknown = sorted(k for k in snapshot if k not in allowed)
    if unknown:
        raise ValueError(f'Preset contains unsupported keys: {", ".join(unknown)}')
    normalized = deepcopy(snapshot)
    if 'watchlist' in normalized:
        if not isinstance(normalized['watchlist'], list):
            raise ValueError('Preset watchlist must be an array of instrument ids')
        normalized['watchlist'] = [normalize_instrument_id(str(item)) for item in normalized['watchlist'] if str(item).strip()]
    return normalized


def merge_snapshot_into_settings(current_settings: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    validate_snapshot_payload(snapshot)
    merged = deepcopy(current_settings)
    for key, value in snapshot.items():
        if key != 'watchlist':
            merged[key] = deepcopy(value)
    return merged


def apply_watchlist_snapshot(db, watchlist_snapshot: list[str] | None) -> dict[str, list[str]]:
    if watchlist_snapshot is None:
        return {'added': [], 'removed': [], 'kept': []}
    seen, desired = set(), []
    for item in watchlist_snapshot:
        instrument_id = normalize_instrument_id(item)
        if instrument_id and instrument_id not in seen:
            seen.add(instrument_id)
            desired.append(instrument_id)
    rows = list(db.query(Watchlist).all() or [])
    existing_map = {normalize_instrument_id(getattr(row, 'instrument_id', None)): row for row in rows}
    current_active = {iid for iid, row in existing_map.items() if bool(getattr(row, 'is_active', False))}
    desired_set = set(desired)
    added = sorted(desired_set - current_active)
    removed = sorted(current_active - desired_set)
    kept = sorted(current_active & desired_set)
    for iid, row in existing_map.items():
        row.is_active = iid in desired_set
    ts = _now_ms()
    for iid in desired:
        if iid not in existing_map:
            exchange, ticker = iid.split(':', 1) if ':' in iid else ('TQBR', iid)
            db.add(Watchlist(instrument_id=iid, ticker=ticker, name=ticker, exchange=exchange, is_active=True, added_ts=ts))
    db.commit()
    return {'added': added, 'removed': removed, 'kept': kept}


def _humanize_value(value: Any) -> str:
    if isinstance(value, bool):
        return 'on' if value else 'off'
    if isinstance(value, list):
        return ', '.join(map(str, value[:3])) if len(value) <= 3 else f'{len(value)} items'
    return '—' if value in (None, '') else str(value)


def build_diff_summary(current_snapshot: dict[str, Any], preset_snapshot: dict[str, Any], limit: int = 6) -> dict[str, Any]:
    validate_snapshot_payload(preset_snapshot)
    changed_keys, summary = [], []
    for key, value in preset_snapshot.items():
        current_value = current_snapshot.get(key)
        if current_value == value:
            continue
        changed_keys.append(key)
        if len(summary) < limit:
            label = FIELD_LABELS.get(key, key)
            if key == 'watchlist':
                summary.append(f'{label}: {len(list(current_value or []))} → {len(list(value or []))} бумаг')
            else:
                summary.append(f'{label}: {_humanize_value(current_value)} → {_humanize_value(value)}')
    return {'changed_keys': changed_keys, 'diff_summary': summary, 'changed_count': len(changed_keys)}


def build_system_presets() -> list[dict[str, Any]]:
    base = build_snapshot_from_settings_dict(_default_schema_dict(), watchlist=[])
    balanced = deepcopy(base); balanced.update({'risk_profile': 'balanced', 'trade_mode': 'auto_paper', 'ai_mode': 'advisory', 'decision_threshold': 70, 'rr_min': 1.5, 'rr_target': 1.4, 'ml_enabled': True, 'ml_take_probability_threshold': 0.55, 'ml_fill_probability_threshold': 0.45, 'max_trades_per_day': 120})
    sniper = deepcopy(base); sniper.update({'risk_profile': 'conservative', 'risk_per_trade_pct': 0.15, 'daily_loss_limit_pct': 1.0, 'max_concurrent_positions': 2, 'max_trades_per_day': 20, 'decision_threshold': 78, 'rr_min': 1.8, 'rr_target': 1.9, 'signal_reentry_cooldown_sec': 600, 'time_stop_bars': 8, 'ai_mode': 'advisory', 'ml_take_probability_threshold': 0.62, 'ml_fill_probability_threshold': 0.52, 'ml_allow_take_veto': True})
    machine = deepcopy(base); machine.update({'risk_profile': 'aggressive', 'risk_per_trade_pct': 0.4, 'daily_loss_limit_pct': 2.5, 'max_concurrent_positions': 6, 'max_trades_per_day': 220, 'decision_threshold': 62, 'rr_min': 1.25, 'rr_target': 1.3, 'signal_reentry_cooldown_sec': 120, 'time_stop_bars': 16, 'trade_mode': 'auto_paper', 'ai_mode': 'override', 'ml_take_probability_threshold': 0.5, 'ml_fill_probability_threshold': 0.38, 'ml_allow_take_veto': False})
    return [
        {'id': 'preset_system_sniper', 'name': 'Sniper', 'description': 'Жёсткие фильтры, высокий RR и низкая частота сделок.', 'settings_json': sniper, 'is_system': True},
        {'id': 'preset_system_machine_gunner', 'name': 'Machine-gunner', 'description': 'Более мягкие фильтры, больше сделок и агрессивный контур.', 'settings_json': machine, 'is_system': True},
        {'id': 'preset_system_balanced', 'name': 'Balanced', 'description': 'Сбалансированный baseline для production-like paper режима.', 'settings_json': balanced, 'is_system': True},
    ]


def slugify_preset_name(name: str) -> str:
    slug = re.sub(r'[^a-z0-9]+', '_', name.strip().lower()).strip('_') or 'preset'
    return slug[:48]
