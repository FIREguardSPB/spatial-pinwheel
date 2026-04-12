from __future__ import annotations
from core.config import get_token
"""
P4-05: OpenAI GPT Advisor.

Uses JSON mode for reliable structured output parsing.
Falls back to XML parsing if JSON mode not available.
"""

import json
import logging

import httpx

from core.utils.http_client import make_async_client

from apps.worker.ai.base import AIAdvisor
from apps.worker.ai.prompts import SYSTEM_PROMPT, build_user_prompt, parse_xml_response
from apps.worker.ai.types import AIContext, AIDecision, AIResult

logger = logging.getLogger(__name__)

_OPENAI_URL = "https://api.openai.com/v1/chat/completions"

_JSON_SYSTEM = SYSTEM_PROMPT + """

ВАЖНО: Отвечай строго в JSON формате:
{
  "decision": "TAKE" | "SKIP" | "REJECT",
  "confidence": 0-100,
  "reasoning": "текст обоснования",
  "key_factors": ["фактор 1", "фактор 2", "фактор 3"]
}
"""


class OpenAIAdvisor(AIAdvisor):
    provider_name = "openai"

    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self.api_key = api_key
        self.model = model

    async def _call_provider(self, context: AIContext) -> str:
        user_prompt = build_user_prompt(context)

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": _JSON_SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "max_tokens": 1024,
            "temperature": 0.1,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with make_async_client(timeout=30.0) as client:
            resp = await client.post(_OPENAI_URL, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    def _parse_response(self, raw: str, context: AIContext) -> AIResult:
        try:
            obj = json.loads(raw)
            decision_str = str(obj.get("decision", "SKIP")).upper()
            try:
                decision = AIDecision(decision_str)
            except ValueError:
                decision = AIDecision.SKIP
            confidence = max(0, min(100, int(obj.get("confidence", 50))))
            reasoning = str(obj.get("reasoning", ""))
            key_factors = [str(f) for f in obj.get("key_factors", [])]
        except (json.JSONDecodeError, TypeError):
            # Fallback to XML parsing (some models ignore json_object format)
            parsed = parse_xml_response(raw, self.provider_name, context)
            decision = parsed["decision"]
            confidence = parsed["confidence"]
            reasoning = parsed["reasoning"]
            key_factors = parsed["key_factors"]

        return AIResult(
            decision=decision,
            confidence=confidence,
            reasoning=reasoning,
            key_factors=key_factors,
            provider=self.provider_name,
        )
