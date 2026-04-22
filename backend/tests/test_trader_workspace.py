from __future__ import annotations

from core.ai.workspace_builder import build_trader_workspace


def test_build_trader_workspace_contains_required_sections():
    payload = build_trader_workspace(
        instrument_id='TQBR:MOEX',
        sig_data={
            'side': 'SELL',
            'entry': 172.73,
            'sl': 173.56,
            'tp': 170.75,
            'r': 2.4,
            'meta': {
                'thesis_timeframe': '15m',
                'execution_timeframe': '5m',
                'confirmation_timeframe': '15m',
                'timeframe_selection_reason': 'requested',
                'review_readiness': {'thesis_type': 'continuation'},
            },
        },
        evaluation={'decision': 'TAKE', 'score': 84, 'reasons': ['HTF_ALIGNED'], 'metrics': {'net_rr': 1.6, 'commission_dominance_ratio': 0.33}},
        market_context={'session_type': 'main', 'regime': 'trend', 'volume_quality': 'good'},
        portfolio_state={'open_positions': 2, 'gross_exposure': 0.31},
        risk_state={'policy_state': 'normal', 'hard_blocked': False},
        memory_state={'recent_similar_trades': 3, 'fast_failures': 1, 'thesis_lineage': ['attempt_1']},
        policy_context={'hard_blockers': [], 'soft_blockers': ['level_too_close'], 'advisories': ['watch commission dominance']},
    )

    assert payload['instrument']['instrument_id'] == 'TQBR:MOEX'
    assert payload['market_view']['regime'] == 'trend'
    assert payload['thesis_view']['thesis_timeframe'] == '15m'
    assert payload['trade_geometry']['entry'] == 172.73
    assert payload['portfolio_risk']['gross_exposure'] == 0.31
    assert payload['memory_lineage']['recent_similar_trades'] == 3
    assert payload['policy_context']['soft_blockers'] == ['level_too_close']


def test_build_trader_workspace_is_json_safe_with_missing_optional_context():
    payload = build_trader_workspace(
        instrument_id='TQBR:SBER',
        sig_data={'meta': {}},
        evaluation={},
        market_context=None,
        portfolio_state=None,
        risk_state=None,
        memory_state=None,
        policy_context=None,
    )

    assert payload['market_view'] == {}
    assert payload['portfolio_risk'] == {}
    assert payload['memory_lineage'] == {}
    assert payload['policy_context'] == {}
