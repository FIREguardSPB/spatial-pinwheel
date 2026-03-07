from __future__ import annotations
from core.config import get_token
"""
P4-06: AIProviderRouter — выбор провайдера + цепочка fallback.

При ошибке/таймауте основного провайдера автоматически пробует следующий.
"skip" в цепочке означает вернуть SKIP без ошибки.

Конфигурация через Settings:
  AI_PRIMARY_PROVIDER   = "claude"
  AI_FALLBACK_PROVIDERS = "ollama,skip"
"""

import logging

from apps.worker.ai.base import AIAdvisor
from apps.worker.ai.types import AIContext, AIDecision, AIMode, AIResult

logger = logging.getLogger(__name__)


def _build_advisor(name: str, config) -> AIAdvisor | None:
    """Instantiate an advisor by provider name. Returns None for 'skip'."""
    if name == "skip":
        return None

    if name == "claude":
        if not config.CLAUDE_API_KEY:
            logger.warning("Claude selected but CLAUDE_API_KEY not set")
            return None
        from apps.worker.ai.providers.claude_advisor import ClaudeAdvisor
        return ClaudeAdvisor(api_key=get_token("CLAUDE_API_KEY"), model=config.CLAUDE_MODEL)

    if name == "ollama":
        from apps.worker.ai.providers.ollama_advisor import OllamaAdvisor
        return OllamaAdvisor(base_url=config.OLLAMA_BASE_URL, model=config.OLLAMA_MODEL)

    if name == "openai":
        if not config.OPENAI_API_KEY:
            logger.warning("OpenAI selected but OPENAI_API_KEY not set")
            return None
        from apps.worker.ai.providers.openai_advisor import OpenAIAdvisor
        return OpenAIAdvisor(api_key=get_token("OPENAI_API_KEY"), model=config.OPENAI_MODEL)

    logger.warning("Unknown AI provider: %s", name)
    return None


def _skip_result(reason: str) -> AIResult:
    return AIResult(
        decision=AIDecision.SKIP,
        confidence=0,
        reasoning=reason,
        provider="skip",
    )


class AIProviderRouter:
    """
    Routes AI analysis requests through a chain of providers.

    Chain: [primary] → [fallback_1] → [fallback_2] → ... → skip
    """

    def __init__(self, config=None):
        from core.config import settings as cfg
        self._config = config or cfg
        self._chain: list[str] = self._build_chain()

    def _build_chain(self) -> list[str]:
        cfg = self._config
        primary = cfg.AI_PRIMARY_PROVIDER.strip()
        fallbacks = [p.strip() for p in cfg.AI_FALLBACK_PROVIDERS.split(",") if p.strip()]
        chain = [primary] + fallbacks
        if "skip" not in chain:
            chain.append("skip")
        logger.info("AI provider chain: %s", " → ".join(chain))
        return chain

    async def analyze(self, context: AIContext, ai_mode: AIMode) -> AIResult:
        """
        Run AI analysis.
        If ai_mode is OFF, return immediately without calling any provider.
        """
        if ai_mode == AIMode.OFF:
            return _skip_result("AI mode is OFF")

        for provider_name in self._chain:
            if provider_name == "skip":
                return _skip_result("All providers failed — defaulting to SKIP")

            advisor = _build_advisor(provider_name, self._config)
            if advisor is None:
                logger.info("Provider %s unavailable, trying next", provider_name)
                continue

            result = await advisor.analyze(context)

            if result.is_ok:
                return result

            logger.warning(
                "Provider %s failed (%s), trying next in chain",
                provider_name, result.error,
            )

        # Should never reach here (chain always ends with "skip")
        return _skip_result("Chain exhausted")

    def merge_decisions(
        self,
        de_decision: str,
        de_score: int,
        ai_result: AIResult,
        ai_mode: AIMode,
        ai_min_confidence: int,
    ) -> tuple[str, str]:
        """
        Merge DE and AI decisions according to ai_mode.

        Returns: (final_decision, merge_reason)
        """
        if ai_mode == AIMode.OFF or not ai_result.is_ok:
            return de_decision, "AI not used"

        if ai_mode == AIMode.ADVISORY:
            return de_decision, f"Advisory: AI={ai_result.decision.value} conf={ai_result.confidence}"

        if ai_mode == AIMode.OVERRIDE:
            if (ai_result.decision.value != de_decision
                    and ai_result.confidence >= ai_min_confidence):
                reason = (
                    f"AI OVERRIDE: DE={de_decision} → AI={ai_result.decision.value} "
                    f"(conf={ai_result.confidence} >= {ai_min_confidence})"
                )
                logger.info(reason)
                return ai_result.decision.value, reason
            return de_decision, f"AI agrees or low confidence ({ai_result.confidence}<{ai_min_confidence})"

        if ai_mode == AIMode.REQUIRED:
            if not ai_result.is_ok:
                return "SKIP", "AI REQUIRED but unavailable — forced SKIP"
            # In REQUIRED mode, AI decision wins regardless of confidence
            return ai_result.decision.value, f"AI REQUIRED: {ai_result.decision.value}"

        return de_decision, "unknown ai_mode"
