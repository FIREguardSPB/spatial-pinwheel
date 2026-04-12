from __future__ import annotations

from typing import Any

from core.services.timeframe_engine import max_timeframe, next_higher_timeframe, normalize_timeframe, timeframe_rank


def choose_strategy(allowed: list[str], regime: str, best_strategy: str | None) -> str:
    normalized = [item for item in allowed if item]
    if best_strategy and best_strategy in normalized:
        if regime in {'trend', 'expansion_trend'} and best_strategy in {'breakout', 'vwap_bounce'}:
            return best_strategy
        if regime in {'chop', 'compression', 'balanced'} and best_strategy in {'mean_reversion', 'vwap_bounce'}:
            return best_strategy
    if regime in {'trend', 'expansion_trend'}:
        for candidate in ('breakout', 'vwap_bounce', 'mean_reversion'):
            if candidate in normalized:
                return candidate
    if regime in {'chop', 'compression'}:
        for candidate in ('mean_reversion', 'vwap_bounce', 'breakout'):
            if candidate in normalized:
                return candidate
    if regime == 'grind':
        for candidate in ('vwap_bounce', 'breakout', 'mean_reversion'):
            if candidate in normalized:
                return candidate
    return normalized[0] if normalized else 'breakout'


def low_price_instrument(candles: list[dict[str, Any]]) -> bool:
    if not candles:
        return False
    close = float((candles[-1] or {}).get('close') or 0.0)
    return close > 0 and close < 10.0


def select_execution_timeframe(*, analysis_timeframe: str, session_floor: str | None, settings: Any, regime: str) -> str:
    analysis_tf = normalize_timeframe(analysis_timeframe, '1m')
    session_floor_tf = normalize_timeframe(session_floor or '1m', '1m')
    execution_tf = '1m'

    if timeframe_rank(analysis_tf) >= timeframe_rank('15m'):
        execution_tf = analysis_tf
    elif timeframe_rank(analysis_tf) >= timeframe_rank('5m') and timeframe_rank(session_floor_tf) >= timeframe_rank('5m'):
        execution_tf = '5m'

    if regime in {'compression', 'grind'} and timeframe_rank(session_floor_tf) >= timeframe_rank('15m'):
        execution_tf = max_timeframe(execution_tf, '5m')

    execution_floor = normalize_timeframe(getattr(settings, 'execution_timeframe_floor', None) or '1m', '1m')
    if timeframe_rank(execution_floor) > timeframe_rank(execution_tf):
        execution_tf = max_timeframe(execution_tf, execution_floor)

    if timeframe_rank(execution_tf) > timeframe_rank(analysis_tf):
        execution_tf = analysis_tf

    return normalize_timeframe(execution_tf, '1m')


def select_timeframes(*, strategy_name: str, regime: str, settings: Any, candles: list[dict[str, Any]], session_floor: str | None) -> tuple[str, str, str | None, str]:
    base_htf = normalize_timeframe(getattr(settings, 'higher_timeframe', '15m') or '15m', '15m')
    analysis_tf = '1m'
    timeframe_source = 'global'

    if strategy_name == 'mean_reversion':
        analysis_tf = '15m' if regime in {'compression', 'chop'} else '5m'
        timeframe_source = 'regime'
    elif strategy_name == 'breakout':
        analysis_tf = '5m' if regime in {'trend', 'expansion_trend', 'balanced'} else '15m'
        timeframe_source = 'regime'
    elif strategy_name == 'vwap_bounce':
        analysis_tf = '1m' if regime in {'grind', 'balanced'} else '5m'
        timeframe_source = 'regime'

    if low_price_instrument(candles):
        analysis_tf = max_timeframe(analysis_tf, '15m')
        timeframe_source = 'symbol'

    if timeframe_rank(normalize_timeframe(session_floor or '1m', '1m')) > timeframe_rank(analysis_tf):
        analysis_tf = max_timeframe(analysis_tf, session_floor or '1m')
        timeframe_source = 'session'

    confirmation_tf = max_timeframe(next_higher_timeframe(analysis_tf), base_htf)
    execution_tf = select_execution_timeframe(analysis_timeframe=analysis_tf, session_floor=session_floor, settings=settings, regime=regime)
    return normalize_timeframe(analysis_tf), normalize_timeframe(execution_tf), normalize_timeframe(confirmation_tf), timeframe_source
