
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from apps.api.deps import verify_token
from core.models import schemas
from core.storage.repos import settings as settings_repo
from core.storage.repos import signals as repo
from core.storage.session import get_db
from core.strategy.selector import StrategySelector

router = APIRouter(dependencies=[Depends(verify_token)])
logger = logging.getLogger(__name__)


def _compact_meta(meta: dict[str, Any] | None) -> dict[str, Any]:
    meta = meta or {}
    decision = meta.get('decision') if isinstance(meta.get('decision'), dict) else {}
    auto_policy = meta.get('auto_policy') if isinstance(meta.get('auto_policy'), dict) else {}
    performance_governor = meta.get('performance_governor') if isinstance(meta.get('performance_governor'), dict) else {}
    ai_decision = meta.get('ai_decision') if isinstance(meta.get('ai_decision'), dict) else {}
    ml_overlay = meta.get('ml_overlay') if isinstance(meta.get('ml_overlay'), dict) else {}
    geometry_optimizer = meta.get('geometry_optimizer') if isinstance(meta.get('geometry_optimizer'), dict) else {}
    ai_fast_path = meta.get('ai_fast_path') if isinstance(meta.get('ai_fast_path'), dict) else {}

    compact: dict[str, Any] = {
        'final_decision': meta.get('final_decision'),
        'strategy_name': meta.get('strategy_name'),
        'strategy': meta.get('strategy'),
        'analysis_timeframe': meta.get('analysis_timeframe'),
        'execution_timeframe': meta.get('execution_timeframe'),
        'confirmation_timeframe': meta.get('confirmation_timeframe'),
        'timeframe_selection_reason': meta.get('timeframe_selection_reason'),
        'decision': {
            'decision': decision.get('decision'),
            'score': decision.get('score'),
            'reasons': decision.get('reasons') if isinstance(decision.get('reasons'), list) else [],
        },
        'ai_decision': {
            'provider': ai_decision.get('provider'),
            'decision': ai_decision.get('decision'),
            'confidence': ai_decision.get('confidence'),
            'reasoning': ai_decision.get('reasoning'),
            'key_factors': ai_decision.get('key_factors') if isinstance(ai_decision.get('key_factors'), list) else [],
        },
        'auto_policy': {
            'state': auto_policy.get('state'),
            'block_new_entries': auto_policy.get('block_new_entries'),
            'reasons': auto_policy.get('reasons') if isinstance(auto_policy.get('reasons'), list) else [],
        },
        'performance_governor': {
            'suppressed': performance_governor.get('suppressed'),
            'reasons': performance_governor.get('reasons') if isinstance(performance_governor.get('reasons'), list) else [],
        },
        'ml_overlay': {
            'target_probability': ml_overlay.get('target_probability'),
            'fill_probability': ml_overlay.get('fill_probability'),
            'reason': ml_overlay.get('reason'),
        },
        'geometry_optimizer': {
            'applied': geometry_optimizer.get('applied'),
            'phase': geometry_optimizer.get('phase'),
            'action': geometry_optimizer.get('action'),
            'notes': geometry_optimizer.get('notes') if isinstance(geometry_optimizer.get('notes'), list) else [],
            'original_sl': geometry_optimizer.get('original_sl'),
            'original_tp': geometry_optimizer.get('original_tp'),
            'suggested_timeframe': geometry_optimizer.get('suggested_timeframe'),
        },
        'ai_fast_path': {
            'applied': ai_fast_path.get('applied'),
            'final_decision': ai_fast_path.get('final_decision'),
            'pre_ai_decision': ai_fast_path.get('pre_ai_decision'),
            'reason': ai_fast_path.get('reason'),
            'triggers': ai_fast_path.get('triggers') if isinstance(ai_fast_path.get('triggers'), list) else [],
            'blocker_codes': ai_fast_path.get('blocker_codes') if isinstance(ai_fast_path.get('blocker_codes'), list) else [],
        },
    }
    return {key: value for key, value in compact.items() if value not in (None, {}, [])}


def serialize_signal(signal: Any, *, compact_meta: bool = False) -> dict[str, Any]:
    s_dict = {c.name: getattr(signal, c.name) for c in signal.__table__.columns}
    meta = s_dict.get('meta') or {}
    decision = meta.get('decision') if isinstance(meta, dict) else {}
    metrics = decision.get('metrics') if isinstance(decision, dict) else {}
    final_decision = _final_signal_decision(signal)
    s_dict['final_decision'] = final_decision
    if metrics:
        s_dict['economic_summary'] = {
            'entry_price_rub': metrics.get('entry_price_rub'),
            'position_qty': metrics.get('position_qty'),
            'position_value_rub': metrics.get('position_value_rub'),
            'sl_distance_rub': metrics.get('sl_distance_rub'),
            'sl_distance_pct': metrics.get('sl_distance_pct'),
            'tp_distance_rub': metrics.get('tp_distance_rub'),
            'tp_distance_pct': metrics.get('tp_distance_pct'),
            'round_trip_cost_rub': metrics.get('round_trip_cost_rub'),
            'round_trip_cost_pct': metrics.get('round_trip_cost_pct'),
            'min_required_sl_pct': metrics.get('min_required_sl_pct'),
            'min_required_sl_rub': metrics.get('min_required_sl_rub'),
            'min_required_profit_pct': metrics.get('min_required_profit_pct'),
            'min_required_profit_rub': metrics.get('min_required_profit_rub'),
            'expected_profit_after_costs_rub': metrics.get('expected_profit_after_costs_rub'),
            'breakeven_move_pct': metrics.get('breakeven_move_pct'),
            'commission_dominance_ratio': metrics.get('commission_dominance_ratio'),
            'economic_warning_flags': metrics.get('economic_warning_flags') or [],
            'economic_filter_valid': metrics.get('economic_filter_valid'),
        }
    strategy_name = _strategy_name_from_meta(meta)
    ai_influence = _ai_influence(meta, ai_influenced=bool(getattr(signal, 'ai_influenced', False)), ai_mode_used=getattr(signal, 'ai_mode_used', None))
    geometry = (meta.get('geometry_optimizer') if isinstance(meta, dict) else None) or {}
    s_dict['strategy_name'] = strategy_name
    return s_dict, meta, ai_influence, geometry


def _final_signal_decision(signal) -> str | None:
    meta = getattr(signal, 'meta', None) or {}
    final_decision = meta.get('final_decision')
    if isinstance(final_decision, str) and final_decision:
        return final_decision.upper()

    de = meta.get('decision') or {}
    if isinstance(de, dict):
        decision = de.get('decision')
        if isinstance(decision, str) and decision:
            return decision.upper()

    return None


_ECON_CODES = {
    'COSTS_TOO_HIGH', 'RR_TOO_LOW', 'ECONOMIC_INVALID', 'ECONOMIC_LOW_PRICE',
    'ECONOMIC_MICRO_LEVELS', 'ECONOMIC_PROFIT_TOO_SMALL', 'ECONOMIC_MIN_TRADE_VALUE',
    'ECONOMIC_COMMISSION_DOMINANCE',
}
_RISK_CODES = {
    'RISK_LIMIT_DAILY', 'RISK_MAX_POSITIONS', 'RISK_COOLDOWN_ACTIVE', 'RISK_MAX_TRADES_DAY',
}


def _parse_names(value: str | None) -> list[str]:
    return StrategySelector.parse_names(value)


def _strategy_name_from_meta(meta: dict[str, Any]) -> str | None:
    return (
        meta.get('strategy_name')
        or ((meta.get('adaptive_plan') or {}).get('strategy_name') if isinstance(meta.get('adaptive_plan'), dict) else None)
        or (((meta.get('multi_strategy') or {}).get('selected_strategy')) if isinstance(meta.get('multi_strategy'), dict) else None)
        or meta.get('strategy')
    )


def _strategy_source(meta: dict[str, Any], *, global_names: list[str]) -> str:
    strategy_name = _strategy_name_from_meta(meta)
    adaptive_plan = meta.get('adaptive_plan') or {}
    profile = ((meta.get('symbol_brain') or {}).get('symbol_profile') if isinstance(meta.get('symbol_brain'), dict) else None) or meta.get('symbol_profile') or {}
    profile_names = _parse_names(str((profile or {}).get('preferred_strategies') or ''))
    regime = str((adaptive_plan or {}).get('regime') or '')

    if strategy_name and global_names and strategy_name in global_names and len(global_names) == 1:
        return 'global'
    if strategy_name and profile_names and strategy_name in profile_names and strategy_name not in global_names:
        return 'symbol'
    if strategy_name and regime in {'trend', 'expansion_trend', 'compression', 'chop', 'grind', 'balanced'}:
        return 'regime'
    if strategy_name and global_names and strategy_name in global_names:
        return 'global'
    return 'unknown'


def _ai_influence(meta: dict[str, Any], *, ai_influenced: bool, ai_mode_used: str | None) -> str:
    if not ai_influenced or str(ai_mode_used or 'off').lower() == 'off':
        return 'off'
    final_decision = str(meta.get('final_decision') or '').upper()
    de_decision = str(((meta.get('decision') or {}).get('decision')) or '').upper()
    if final_decision and de_decision and final_decision != de_decision:
        return 'affected decision'
    if str(ai_mode_used or '').lower() in {'override', 'required'}:
        return 'affected decision'
    return 'advisory only'


def _reject_reason_priority(meta: dict[str, Any], *, ai_influence: str, global_names: list[str]) -> str | None:
    final_decision = str(meta.get('final_decision') or '').upper()
    if final_decision == 'TAKE':
        return None

    decision = meta.get('decision') or {}
    reasons = decision.get('reasons') if isinstance(decision, dict) else []
    reasons = reasons if isinstance(reasons, list) else []
    codes = {str((r or {}).get('code') or '').upper() for r in reasons if isinstance(r, dict)}
    messages = [str((r or {}).get('msg') or '').lower() for r in reasons if isinstance(r, dict)]
    econ = meta.get('decision', {}).get('metrics', {}) if isinstance(meta.get('decision'), dict) else {}

    strategy_name = _strategy_name_from_meta(meta)
    if strategy_name and global_names and len(global_names) == 1 and strategy_name not in global_names:
        return 'strategy mismatch'
    if ai_influence == 'affected decision':
        return 'ai'
    if codes & _ECON_CODES:
        return 'economics'
    if econ:
        expected_after_costs = econ.get('expected_profit_after_costs_rub')
        econ_valid = econ.get('economic_filter_valid')
        commission_dom = econ.get('commission_dominance_ratio')
        if econ_valid is False or (expected_after_costs is not None and float(expected_after_costs) <= 0) or (commission_dom is not None and float(commission_dom) >= 1.0):
            return 'economics'
    if codes & _RISK_CODES or any('risk' in msg or 'cooldown' in msg for msg in messages):
        return 'risk'
    if any('strategy' in msg or 'regime' in msg for msg in messages):
        return 'strategy mismatch'
    return 'other'


@router.get('', response_model=schemas.SignalList)
def list_signals(limit: int = 50, status: str = Query(None), compact_meta: bool = False, db: Session = Depends(get_db)):
    items = repo.list_signals(db, limit, status)
    settings_db = settings_repo.get_settings(db)
    global_names = _parse_names(getattr(settings_db, 'strategy_name', None) or 'breakout')
    transformed = []
    for s in items:
        s_dict, meta, ai_influence, geometry = serialize_signal(s, compact_meta=compact_meta)
        s_dict['strategy_source'] = _strategy_source(meta, global_names=global_names)
        s_dict['ai_influence'] = ai_influence
        s_dict['reject_reason_priority'] = _reject_reason_priority(meta, ai_influence=ai_influence, global_names=global_names)
        s_dict['geometry_optimized'] = bool(geometry.get('applied'))
        s_dict['geometry_phase'] = geometry.get('phase')
        s_dict['geometry_action'] = geometry.get('action')
        s_dict['geometry_source'] = geometry.get('geometry_source')
        s_dict['analysis_timeframe'] = meta.get('analysis_timeframe')
        s_dict['execution_timeframe'] = meta.get('execution_timeframe')
        s_dict['confirmation_timeframe'] = meta.get('confirmation_timeframe')
        s_dict['timeframe_selection_reason'] = meta.get('timeframe_selection_reason')
        if compact_meta:
            s_dict['meta'] = _compact_meta(meta)
        transformed.append(s_dict)
    return {'items': transformed, 'next_cursor': None}


@router.post('/{signal_id}/approve')
async def approve_signal(signal_id: str, payload: schemas.ApproveSignal, db: Session = Depends(get_db)):
    signal = repo.get_signal(db, signal_id)
    if not signal:
        raise HTTPException(status_code=404, detail='Signal not found')

    if signal.status != 'pending_review':
        raise HTTPException(status_code=409, detail=f'Signal status is {signal.status}, expected pending_review')

    final_decision = _final_signal_decision(signal)
    if final_decision and final_decision != 'TAKE':
        raise HTTPException(
            status_code=409,
            detail=f'Signal cannot be approved manually because final decision is {final_decision}',
        )

    repo.update_signal_status(db, signal_id, 'approved')

    try:
        from core.events.bus import bus
        import orjson

        await bus.publish('signal_updated', {'id': signal_id, 'status': 'approved'})
        await bus.redis.publish('cmd:execute_signal', orjson.dumps({'signal_id': signal_id}).decode())
    except Exception as exc:
        logger.warning('Redis publish failed for approve_signal(%s): %s', signal_id, exc, exc_info=True)

        from core.config import get_token, settings
        if not settings.ALLOW_NO_REDIS:
            repo.update_signal_status(db, signal_id, 'pending_review')
            raise HTTPException(
                status_code=503,
                detail='Redis unavailable and fallback disabled (ALLOW_NO_REDIS=False)',
            ) from exc

        from core.storage.models import Settings as RuntimeSettings
        runtime_settings = db.query(RuntimeSettings).first()
        if not runtime_settings or not bool(getattr(runtime_settings, 'bot_enabled', False)):
            repo.update_signal_status(db, signal_id, 'pending_review')
            raise HTTPException(status_code=409, detail='Bot is disabled. Start the bot before executing signals.')

        from core.execution.paper import PaperExecutionEngine
        from core.execution.tbank import TBankExecutionEngine

        trade_mode = getattr(runtime_settings, 'trade_mode', 'review') or 'review'
        if trade_mode == 'auto_live':
            engine = TBankExecutionEngine(
                db,
                token=get_token('TBANK_TOKEN') or settings.TBANK_TOKEN,
                account_id=get_token('TBANK_ACCOUNT_ID') or settings.TBANK_ACCOUNT_ID,
                sandbox=settings.TBANK_SANDBOX,
            )
        else:
            engine = PaperExecutionEngine(db)
        await engine.execute_approved_signal(signal_id)

    return {'status': 'ok'}


@router.post('/{signal_id}/reject')
async def reject_signal(signal_id: str, payload: schemas.RejectSignal, db: Session = Depends(get_db)):
    signal = repo.get_signal(db, signal_id)
    if not signal:
        raise HTTPException(status_code=404, detail='Signal not found')

    if signal.status != 'pending_review':
        raise HTTPException(status_code=409, detail=f'Signal status is {signal.status}, expected pending_review')

    repo.update_signal_status(db, signal_id, 'rejected')

    from core.events.bus import bus

    await bus.publish('signal_updated', {'id': signal_id, 'status': 'rejected'})
    return {'status': 'ok'}
