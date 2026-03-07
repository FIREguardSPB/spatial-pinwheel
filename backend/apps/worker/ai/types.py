"""
P4-01: AI Advisor types.

AIMode controls how AI decision is merged with DecisionEngine result:
  OFF       — AI not called, DE result is final
  ADVISORY  — AI called, result stored in meta but DE decision is final
  OVERRIDE  — AI can change DE decision if confidence >= ai_min_confidence
  REQUIRED  — Signal is SKIP'd if AI is unavailable
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AIMode(str, Enum):
    OFF      = "off"
    ADVISORY = "advisory"
    OVERRIDE = "override"
    REQUIRED = "required"


class AIDecision(str, Enum):
    TAKE   = "TAKE"
    SKIP   = "SKIP"
    REJECT = "REJECT"


@dataclass
class NewsItem:
    title: str
    source: str
    url: str
    published_at: str       # ISO-8601
    sentiment: float = 0.0  # -1.0 .. 1.0


@dataclass
class MacroData:
    cbr_key_rate: float | None = None      # % ключевой ставки ЦБ РФ
    fed_funds_rate: float | None = None    # % ставки ФРС
    usd_rub: float | None = None           # Курс USD/RUB
    brent_usd: float | None = None         # Нефть Brent, $
    geopolitical_risk: float = 0.0         # 0.0..1.0 (субъективный индекс)
    data_ts: int = 0                       # Unix ms когда данные собраны


@dataclass
class InternetContext:
    """Собранные из интернета данные для AI-контекста."""
    ticker: str
    news: list[NewsItem] = field(default_factory=list)
    sentiment_score: float = 0.0           # -1.0 .. 1.0 (среднее по новостям)
    macro: MacroData = field(default_factory=MacroData)
    geopolitical_risk: float = 0.0         # 0.0 .. 1.0
    from_cache: bool = False


@dataclass
class AIContext:
    """Полный контекст для AI-провайдера."""
    signal_id: str
    instrument_id: str
    side: str
    entry: float
    sl: float
    tp: float
    r: float
    de_score: int
    de_decision: str
    de_reasons: list[dict]
    de_metrics: dict[str, Any]
    candles_summary: dict[str, Any]        # последние N свечей сводно
    internet: InternetContext | None = None


@dataclass
class AIResult:
    """Ответ AI-провайдера."""
    decision: AIDecision
    confidence: int                         # 0..100
    reasoning: str
    provider: str                           # "claude" | "ollama" | "openai"
    key_factors: list[str] = field(default_factory=list)
    raw_response: str = ""
    latency_ms: int = 0
    error: str | None = None               # Если провайдер недоступен

    @property
    def is_ok(self) -> bool:
        return self.error is None
