"""
P4-01: Abstract base class for all AI advisors.

All providers (Claude, Ollama, OpenAI) implement this interface.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from apps.worker.ai.types import AIContext, AIResult

logger = logging.getLogger(__name__)


class AIAdvisor(ABC):
    """
    Abstract AI trading advisor.

    Subclasses implement _call_provider() which performs the actual
    LLM call and returns raw text. Base class handles timing and error wrapping.
    """

    provider_name: str = "base"

    @abstractmethod
    async def _call_provider(self, context: AIContext) -> str:
        """
        Call the LLM provider and return the raw response string.
        Raise any exception on failure — base class will catch it.
        """
        ...

    @abstractmethod
    def _parse_response(self, raw: str, context: AIContext) -> AIResult:
        """Parse raw LLM response into AIResult."""
        ...

    async def analyze(self, context: AIContext) -> AIResult:
        """
        Top-level entry point. Call provider, parse, return AIResult.
        Never raises — always returns AIResult (with error field set on failure).
        """
        import time
        start = time.perf_counter()
        try:
            raw = await self._call_provider(context)
            result = self._parse_response(raw, context)
            result.latency_ms = int((time.perf_counter() - start) * 1000)
            result.raw_response = raw[:4000]  # cap stored response
            logger.info(
                "AI [%s] %s → %s (conf=%d, %.0fms)",
                self.provider_name, context.instrument_id,
                result.decision.value, result.confidence, result.latency_ms,
            )
            return result
        except Exception as e:
            latency = int((time.perf_counter() - start) * 1000)
            logger.warning("AI [%s] error: %s (%.0fms)", self.provider_name, e, latency)
            from apps.worker.ai.types import AIDecision
            return AIResult(
                decision=AIDecision.SKIP,
                confidence=0,
                reasoning=f"Provider error: {e}",
                provider=self.provider_name,
                latency_ms=latency,
                error=str(e),
            )
