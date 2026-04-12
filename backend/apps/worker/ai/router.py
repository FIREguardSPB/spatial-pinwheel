from __future__ import annotations
from core.config import get_token
"""
P4-06: AIProviderRouter — выбор провайдера + цепочка fallback.

При ошибке/таймауте основного провайдера автоматически пробует следующий.
"skip" в цепочке означает вернуть SKIP без ошибки.

Конфигурация через Settings:
  AI_PRIMARY_PROVIDER   = "claude"
  AI_FALLBACK_PROVIDERS = "deepseek,ollama,skip"
"""

import logging
import time

from apps.worker.ai.base import AIAdvisor
from apps.worker.ai.types import AIContext, AIDecision, AIMode, AIResult

logger = logging.getLogger(__name__)


def _normalize_provider_name(name: str) -> str:
    value = (name or "").strip().lower()
    aliases = {
        "deepseek-reason": "deepseek",
        "deepseek-reasoner": "deepseek",
        "deepseek_reasoner": "deepseek",
    }
    return aliases.get(value, value)


def _build_advisor(name: str, config) -> AIAdvisor | None:
    """Instantiate an advisor by provider name. Returns None for 'skip'."""
    normalized = _normalize_provider_name(name)
    if normalized == "skip":
        return None

    if normalized == "claude":
        api_key = get_token("CLAUDE_API_KEY")
        if not api_key:
            logger.warning("Claude selected but CLAUDE_API_KEY not set")
            return None
        from apps.worker.ai.providers.claude_advisor import ClaudeAdvisor
        return ClaudeAdvisor(api_key=api_key, model=config.CLAUDE_MODEL)

    if normalized == "ollama":
        from apps.worker.ai.providers.ollama_advisor import OllamaAdvisor
        return OllamaAdvisor(base_url=config.OLLAMA_BASE_URL, model=config.OLLAMA_MODEL)

    if normalized == "openai":
        api_key = get_token("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OpenAI selected but OPENAI_API_KEY not set")
            return None
        from apps.worker.ai.providers.openai_advisor import OpenAIAdvisor
        return OpenAIAdvisor(api_key=api_key, model=config.OPENAI_MODEL)

    if normalized == "deepseek":
        api_key = get_token("DEEPSEEK_API_KEY")
        if not api_key:
            logger.warning("DeepSeek selected but DEEPSEEK_API_KEY not set")
            return None
        from apps.worker.ai.providers.deepseek_advisor import DeepSeekAdvisor
        return DeepSeekAdvisor(
            api_key=api_key,
            model=config.DEEPSEEK_MODEL,
            base_url=config.DEEPSEEK_BASE_URL,
        )

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
        primary = _normalize_provider_name(cfg.AI_PRIMARY_PROVIDER)
        fallbacks = [_normalize_provider_name(p) for p in cfg.AI_FALLBACK_PROVIDERS.split(",") if p.strip()]
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

        logger.info("AI analyze start: instrument=%s mode=%s chain=%s", context.instrument_id, ai_mode.value, " -> ".join(self._chain))
        last_error: str | None = None
        for provider_name in self._chain:
            if provider_name == "skip":
                suffix = f" Last error: {last_error}" if last_error else ""
                return _skip_result(f"All providers failed — defaulting to SKIP.{suffix}")

            advisor = _build_advisor(provider_name, self._config)
            if advisor is None:
                last_error = f"{provider_name}: provider unavailable or not configured"
                logger.info("Provider %s unavailable, trying next", provider_name)
                continue

            started_at = time.perf_counter()
            try:
                result = await advisor.analyze(context)
            except Exception as exc:
                latency_ms = int((time.perf_counter() - started_at) * 1000)
                last_error = f"{provider_name}: {exc}"
                logger.warning(
                    "Provider %s raised for %s (%s) latency_ms=%s, trying next in chain",
                    provider_name,
                    context.instrument_id,
                    exc,
                    latency_ms,
                    exc_info=True,
                )
                continue

            latency_ms = int((time.perf_counter() - started_at) * 1000)

            if result.is_ok:
                logger.info(
                    "AI provider success: instrument=%s provider=%s decision=%s confidence=%s latency_ms=%s",
                    context.instrument_id,
                    provider_name,
                    result.decision.value,
                    result.confidence,
                    latency_ms,
                )
                return result

            last_error = f"{provider_name}: {result.error or result.reasoning or 'unknown error'}"
            logger.warning(
                "Provider %s failed for %s (%s) latency_ms=%s, trying next in chain",
                provider_name, context.instrument_id, result.error, latency_ms,
            )

        # Should never reach here (chain always ends with "skip")
        suffix = f" Last error: {last_error}" if last_error else ""
        return _skip_result(f"Chain exhausted.{suffix}")

    def merge_decisions(
        self,
        de_decision: str,
        de_score: int,
        ai_result: AIResult,
        ai_mode: AIMode,
        ai_min_confidence: int,
        de_has_blockers: bool = False,
        override_policy: str = "promote_only",
    ) -> tuple[str, str]:
        """
        Merge DE and AI decisions according to ai_mode.

        Returns: (final_decision, merge_reason)
        """
        if ai_mode == AIMode.OFF or not ai_result.is_ok:
            return de_decision, "AI not used"

        if de_has_blockers:
            return de_decision, "DE hard block — AI cannot override"

        if ai_mode == AIMode.ADVISORY:
            return de_decision, f"Advisory: AI={ai_result.decision.value} conf={ai_result.confidence}"

        if ai_mode == AIMode.OVERRIDE:
            if ai_result.confidence < ai_min_confidence:
                return de_decision, f"AI low confidence ({ai_result.confidence}<{ai_min_confidence})"
            if override_policy == "promote_only":
                if de_decision != "TAKE" and ai_result.decision.value == "TAKE":
                    reason = (
                        f"AI promote-only override: DE={de_decision} → AI=TAKE "
                        f"(conf={ai_result.confidence} >= {ai_min_confidence})"
                    )
                    logger.info(reason)
                    return "TAKE", reason
                return de_decision, f"Promote-only override kept DE={de_decision}"
            if ai_result.decision.value != de_decision:
                reason = (
                    f"AI OVERRIDE: DE={de_decision} → AI={ai_result.decision.value} "
                    f"(conf={ai_result.confidence} >= {ai_min_confidence})"
                )
                logger.info(reason)
                return ai_result.decision.value, reason
            return de_decision, "AI agrees with DE"

        if ai_mode == AIMode.REQUIRED:
            if not ai_result.is_ok:
                return "SKIP", "AI REQUIRED but unavailable — forced SKIP"
            # In REQUIRED mode, AI decision wins regardless of confidence
            return ai_result.decision.value, f"AI REQUIRED: {ai_result.decision.value}"

        return de_decision, "unknown ai_mode"
