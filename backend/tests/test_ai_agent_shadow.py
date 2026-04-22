from __future__ import annotations

from apps.worker.ai.types import AIDecision, AIResult
from core.ai.agent_contracts import TraderAgentShadowDecision
from core.ai.agent_clients import build_agent_router_config
from core.ai.trader_shadow import build_trader_agent_shadow
from core.ai.state_builder import build_agent_world_state


def test_trader_agent_shadow_maps_ai_result_to_structured_contract():
    ai_result = AIResult(
        decision=AIDecision.TAKE,
        confidence=82,
        reasoning='higher timeframe continuation remains valid',
        provider='deepseek',
        key_factors=['htf trend intact', 'entry near reclaim'],
    )

    shadow = build_trader_agent_shadow(
        ai_result=ai_result,
        signal_id='sig_1',
        instrument_id='TQBR:MOEX',
        final_decision='TAKE',
    )

    assert isinstance(shadow, TraderAgentShadowDecision)
    assert shadow.action == 'take'
    assert shadow.confidence == 82
    assert shadow.provider == 'deepseek'
    assert shadow.signal_id == 'sig_1'


def test_agent_world_state_collects_market_thesis_and_risk_context():
    payload = build_agent_world_state(
        instrument_id='TQBR:MOEX',
        sig_data={
            'side': 'SELL',
            'entry': 172.73,
            'sl': 173.56,
            'tp': 170.75,
            'r': 2.4,
            'meta': {
                'thesis_timeframe': '15m',
                'timeframe_selection_reason': 'requested',
                'review_readiness': {'thesis_type': 'continuation'},
            },
        },
        evaluation={'decision': 'TAKE', 'score': 84, 'reasons': ['HTF_ALIGNED']},
        portfolio_state={'open_positions': 1, 'gross_exposure': 0.24},
        risk_state={'policy_state': 'frozen', 'governor': {'suppressed': False}},
    )

    assert payload['instrument']['instrument_id'] == 'TQBR:MOEX'
    assert payload['signal']['thesis_timeframe'] == '15m'
    assert payload['signal']['thesis_type'] == 'continuation'
    assert payload['decision_engine']['decision'] == 'TAKE'
    assert payload['risk']['policy_state'] == 'frozen'


def test_build_agent_router_config_uses_cloud_model_preferences():
    cfg = build_agent_router_config(
        settings_obj=type('S', (), {'ai_primary_provider': 'openai', 'ai_fallback_providers': 'claude,deepseek,skip', 'ollama_url': 'http://localhost:11434'})(),
        runtime_config=type('R', (), {'OLLAMA_MODEL': 'llama3.1:8b', 'CLAUDE_MODEL': 'claude-opus-4-6', 'OPENAI_MODEL': 'gpt-5.4', 'DEEPSEEK_MODEL': 'deepseek-chat', 'DEEPSEEK_BASE_URL': 'https://api.deepseek.com'})(),
    )

    assert cfg.AI_PRIMARY_PROVIDER == 'openai'
    assert cfg.AI_FALLBACK_PROVIDERS == 'claude,deepseek,skip'
    assert cfg.OPENAI_MODEL == 'gpt-5.4'
