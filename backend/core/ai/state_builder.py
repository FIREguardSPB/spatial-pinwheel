from __future__ import annotations

from typing import Any


def build_agent_world_state(*, instrument_id: str, sig_data: dict[str, Any], evaluation: dict[str, Any], portfolio_state: dict[str, Any] | None = None, risk_state: dict[str, Any] | None = None) -> dict[str, Any]:
    meta = dict((sig_data or {}).get('meta') or {})
    review = dict(meta.get('review_readiness') or {})
    return {
        'instrument': {'instrument_id': instrument_id},
        'signal': {
            'side': sig_data.get('side'),
            'entry': sig_data.get('entry'),
            'sl': sig_data.get('sl'),
            'tp': sig_data.get('tp'),
            'rr': sig_data.get('r'),
            'thesis_timeframe': meta.get('thesis_timeframe'),
            'selection_reason': meta.get('timeframe_selection_reason'),
            'thesis_type': review.get('thesis_type'),
        },
        'decision_engine': dict(evaluation or {}),
        'portfolio': dict(portfolio_state or {}),
        'risk': dict(risk_state or {}),
    }
