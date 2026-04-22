from __future__ import annotations

from typing import Any


def build_trader_workspace(*, instrument_id: str, sig_data: dict[str, Any], evaluation: dict[str, Any], market_context: dict[str, Any] | None = None, portfolio_state: dict[str, Any] | None = None, risk_state: dict[str, Any] | None = None, memory_state: dict[str, Any] | None = None, policy_context: dict[str, Any] | None = None) -> dict[str, Any]:
    meta = dict((sig_data or {}).get('meta') or {})
    review = dict(meta.get('review_readiness') or {})
    metrics = dict((evaluation or {}).get('metrics') or {})
    return {
        'instrument': {'instrument_id': instrument_id},
        'market_view': dict(market_context or {}),
        'thesis_view': {
            'execution_timeframe': meta.get('execution_timeframe'),
            'thesis_timeframe': meta.get('thesis_timeframe'),
            'confirmation_timeframe': meta.get('confirmation_timeframe'),
            'selection_reason': meta.get('timeframe_selection_reason'),
            'thesis_type': review.get('thesis_type'),
        },
        'trade_geometry': {
            'side': sig_data.get('side'),
            'entry': sig_data.get('entry'),
            'sl': sig_data.get('sl'),
            'tp': sig_data.get('tp'),
            'rr': sig_data.get('r'),
            'net_rr': metrics.get('net_rr'),
            'commission_dominance_ratio': metrics.get('commission_dominance_ratio'),
        },
        'decision_engine': dict(evaluation or {}),
        'portfolio_risk': dict(portfolio_state or {}),
        'memory_lineage': dict(memory_state or {}),
        'policy_context': dict(policy_context or {}),
    }
