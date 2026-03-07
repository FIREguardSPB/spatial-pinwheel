"""
P4-02: SentimentAnalyzer — оценка тональности новостей.

Лёгкая реализация без ML-зависимостей: словарный подход на русском языке.
Достаточно для MVP — негативные слова (санкции, падение, кризис) vs
позитивные (рост, прибыль, дивиденды, сделка).

Для production: можно подключить rubert-tiny или dostoevsky.
"""
from __future__ import annotations

from apps.worker.ai.types import NewsItem

# Расширяемые словари тональности
_POSITIVE = {
    "рост", "растёт", "растут", "вырос", "выросла", "прибыль", "прибыли",
    "дивиденды", "дивидендов", "сделка", "партнёрство", "договор", "контракт",
    "рекорд", "успех", "позитив", "повышение", "увеличение", "укрепление",
    "инвестиции", "расширение", "план", "перспектива", "лидер", "победа",
    "buyback", "выкуп", "одобрен", "утверждён", "поддержка",
}

_NEGATIVE = {
    "падение", "упал", "упала", "снижение", "снизился", "убыток", "убытки",
    "санкции", "санкций", "запрет", "запреты", "кризис", "риск", "риски",
    "потери", "потеря", "штраф", "проблема", "проблемы", "конфликт",
    "война", "обвал", "дефолт", "банкротство", "авария", "авариях",
    "негатив", "снижается", "ухудшение", "сокращение", "задержка",
    "расследование", "нарушение", "иск", "судебный",
}


def score_text(text: str) -> float:
    """
    Score a single text fragment: -1.0 (very negative) .. +1.0 (very positive).
    """
    words = set(text.lower().split())
    pos = len(words & _POSITIVE)
    neg = len(words & _NEGATIVE)
    total = pos + neg
    if total == 0:
        return 0.0
    return round((pos - neg) / total, 3)


def analyze(news_items: list[NewsItem]) -> list[NewsItem]:
    """
    Annotate NewsItem.sentiment for each item.
    Returns the same list with sentiment filled in.
    """
    for item in news_items:
        item.sentiment = score_text(item.title)
    return news_items


def aggregate_sentiment(news_items: list[NewsItem]) -> float:
    """
    Weighted average sentiment: recent articles weighted more heavily.
    Returns -1.0 .. 1.0.
    """
    if not news_items:
        return 0.0

    total_weight = 0.0
    weighted_sum = 0.0
    for i, item in enumerate(news_items):
        # Exponential decay: first (newest) item has weight 1.0, then 0.9, 0.8...
        weight = max(0.1, 1.0 - i * 0.1)
        weighted_sum += item.sentiment * weight
        total_weight += weight

    return round(weighted_sum / total_weight, 3) if total_weight > 0 else 0.0
