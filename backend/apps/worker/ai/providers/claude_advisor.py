from __future__ import annotations
from core.config import get_token
"""
P4-03: Claude Advisor — Anthropic API adapter.

Uses claude-sonnet-4-6 (or configured model) with XML structured output.
Implements retry with exponential backoff on HTTP 429.
Logs full prompt + response to decision_log for audit and fine-tuning dataset.
"""

import asyncio
import hashlib
import logging
import time

import httpx

from core.utils.http_client import make_async_client

from apps.worker.ai.base import AIAdvisor
from apps.worker.ai.prompts import SYSTEM_PROMPT, build_user_prompt, parse_xml_response
from apps.worker.ai.types import AIContext, AIDecision, AIResult

logger = logging.getLogger(__name__)

_ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
_MAX_RETRIES = 3
_RETRY_BASE_SEC = 2.0


class ClaudeAdvisor(AIAdvisor):
    provider_name = "claude"

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6"):
        self.api_key = api_key
        self.model = model

    async def _call_provider(self, context: AIContext) -> str:
        user_prompt = build_user_prompt(context)

        payload = {
            "model": self.model,
            "max_tokens": 1024,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": user_prompt}],
        }
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        async with make_async_client(timeout=45.0) as client:
            for attempt in range(_MAX_RETRIES):
                resp = await client.post(_ANTHROPIC_URL, json=payload, headers=headers)

                if resp.status_code == 429:
                    wait = _RETRY_BASE_SEC * (2 ** attempt)
                    logger.warning("Claude rate limit — retry in %.1fs (attempt %d/%d)", wait, attempt + 1, _MAX_RETRIES)
                    await asyncio.sleep(wait)
                    continue

                resp.raise_for_status()
                data = resp.json()
                return data["content"][0]["text"]

        raise RuntimeError(f"Claude: max retries ({_MAX_RETRIES}) exceeded on rate limit")

    def _parse_response(self, raw: str, context: AIContext) -> AIResult:
        parsed = parse_xml_response(raw, self.provider_name, context)
        return AIResult(
            decision=parsed["decision"],
            confidence=parsed["confidence"],
            reasoning=parsed["reasoning"],
            key_factors=parsed["key_factors"],
            provider=self.provider_name,
        )
