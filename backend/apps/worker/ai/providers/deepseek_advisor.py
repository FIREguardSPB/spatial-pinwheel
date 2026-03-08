from __future__ import annotations

"""DeepSeek Reasoner advisor using the OpenAI-compatible DeepSeek API."""

import json
import logging

import httpx

from apps.worker.ai.base import AIAdvisor
from apps.worker.ai.prompts import SYSTEM_PROMPT, build_user_prompt, parse_xml_response
from apps.worker.ai.types import AIContext, AIDecision, AIResult

logger = logging.getLogger(__name__)

_JSON_SYSTEM = SYSTEM_PROMPT + """

ВАЖНО: Отвечай строго в JSON формате:
{
  \"decision\": \"TAKE\" | \"SKIP\" | \"REJECT\",
  \"confidence\": 0-100,
  \"reasoning\": \"текст обоснования\",
  \"key_factors\": [\"фактор 1\", \"фактор 2\", \"фактор 3\"]
}
"""


class DeepSeekAdvisor(AIAdvisor):
    provider_name = "deepseek"

    def __init__(self, api_key: str, model: str = "deepseek-reasoner", base_url: str = "https://api.deepseek.com"):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")

    async def _call_provider(self, context: AIContext) -> str:
        user_prompt = build_user_prompt(context)
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": _JSON_SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "max_tokens": 2048,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self.base_url}/chat/completions"

        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            message = data["choices"][0]["message"]
            return message.get("content") or ""

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
        except (json.JSONDecodeError, TypeError, ValueError):
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
