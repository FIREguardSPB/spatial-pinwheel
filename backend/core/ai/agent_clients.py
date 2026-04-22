from __future__ import annotations

from types import SimpleNamespace

from apps.worker.ai.types import AIResult
from core.ai.challenger_shadow import build_challenger_agent_shadow


def build_agent_router_config(*, settings_obj, runtime_config):
    return SimpleNamespace(
        AI_PRIMARY_PROVIDER=getattr(settings_obj, 'ai_primary_provider', None) or 'deepseek',
        AI_FALLBACK_PROVIDERS=getattr(settings_obj, 'ai_fallback_providers', None) or 'deepseek,ollama,skip',
        OLLAMA_BASE_URL=getattr(settings_obj, 'ollama_url', None) or 'http://localhost:11434',
        OLLAMA_MODEL=getattr(runtime_config, 'OLLAMA_MODEL', 'llama3.1:8b'),
        CLAUDE_MODEL=getattr(runtime_config, 'CLAUDE_MODEL', 'claude-sonnet-4-6'),
        OPENAI_MODEL=getattr(runtime_config, 'OPENAI_MODEL', 'gpt-5.4'),
        DEEPSEEK_MODEL=getattr(runtime_config, 'DEEPSEEK_MODEL', 'deepseek-chat'),
        DEEPSEEK_BASE_URL=getattr(runtime_config, 'DEEPSEEK_BASE_URL', 'https://api.deepseek.com'),
    )


def build_challenger_shadow_from_ai_result(*, ai_result: AIResult, signal_id: str, instrument_id: str):
    return build_challenger_agent_shadow(
        signal_id=signal_id,
        instrument_id=instrument_id,
        stance='approve' if ai_result.decision.value == 'TAKE' else 'challenge',
        confidence=int(ai_result.confidence or 0),
        main_objections=list(ai_result.key_factors or []),
        recommended_adjustment='none' if ai_result.decision.value == 'TAKE' else 'wait_for_confirmation',
    )
