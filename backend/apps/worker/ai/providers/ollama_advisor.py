"""
P4-04: Ollama Advisor — local LLM via Ollama REST API.

Supports: deepseek-r1:14b, llama3.3, qwen2.5
Streaming response for lower latency.
Timeout: 60s (local models can be slow on first token).
"""
from __future__ import annotations

import json
import logging

import httpx

from apps.worker.ai.base import AIAdvisor
from apps.worker.ai.prompts import SYSTEM_PROMPT, build_user_prompt, parse_xml_response
from apps.worker.ai.types import AIContext, AIResult

logger = logging.getLogger(__name__)


class OllamaAdvisor(AIAdvisor):
    provider_name = "ollama"

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "deepseek-r1:14b"):
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def _call_provider(self, context: AIContext) -> str:
        user_prompt = build_user_prompt(context)
        # Merge system + user for models that don't support system separately
        full_prompt = f"{SYSTEM_PROMPT}\n\n{user_prompt}"

        payload = {
            "model": self.model,
            "prompt": full_prompt,
            "stream": True,
            "options": {
                "temperature": 0.1,    # Low temperature for consistent structured output
                "num_predict": 512,
            },
        }

        url = f"{self.base_url}/api/generate"
        chunks: list[str] = []

        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream("POST", url, json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        chunks.append(obj.get("response", ""))
                        if obj.get("done"):
                            break
                    except json.JSONDecodeError:
                        continue

        return "".join(chunks)

    def _parse_response(self, raw: str, context: AIContext) -> AIResult:
        # DeepSeek-R1 wraps thinking in <think>...</think> — strip it
        import re
        clean = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
        parsed = parse_xml_response(clean or raw, self.provider_name, context)
        return AIResult(
            decision=parsed["decision"],
            confidence=parsed["confidence"],
            reasoning=parsed["reasoning"],
            key_factors=parsed["key_factors"],
            provider=self.provider_name,
        )
