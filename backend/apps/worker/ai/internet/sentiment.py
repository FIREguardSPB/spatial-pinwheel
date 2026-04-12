"""
P4-02: SentimentAnalyzer — оценка тональности новостей.

Улучшенная rule-based реализация без тяжёлых ML-зависимостей.
Цель — не только искать отдельные слова, но и учитывать контекст:
- военный/санкционный фон должен давать сильный негатив;
- сообщения о смягчении санкций / росте прибыли — позитив;
- шоки на нефтяном рынке обычно несут mixed/negative market sentiment,
  а уже в company-level prompt интерпретируются как плюс для нефтяников.
"""
from __future__ import annotations

import re

from apps.worker.ai.types import NewsItem

_POSITIVE_PATTERNS: tuple[tuple[str, float], ...] = (
    (r"\bрост\w*\b", 0.18),
    (r"\bprofit\w*\b|\bприбыл\w*\b", 0.35),
    (r"\bdividend\w*\b|\bдивиденд\w*\b", 0.28),
    (r"\bbuyback\b|\bвыкуп\w*\b", 0.22),
    (r"\brecord\w*\b|\bрекорд\w*\b", 0.18),
    (r"\bdeal\w*\b|\bсделк\w*\b|\bagreement\b|\bдоговор\w*\b", 0.18),
    (r"\bподдержк\w*\b|\bsupport\w*\b", 0.14),
    (r"\bease\w* sanctions\b|\blift\w* sanctions\b|\bослаблен\w* санкц\w*\b|\bсняти\w* санкц\w*\b", 0.48),
    (r"\bдоступ\w* к рынк\w*\b|\bmarket access\b", 0.20),
)

_NEGATIVE_PATTERNS: tuple[tuple[str, float], ...] = (
    (r"\bwar\b|\bвойн\w*\b", 0.60),
    (r"\bconflict\w*\b|\bконфликт\w*\b", 0.42),
    (r"\battack\w*\b|\bstrike\w*\b|\bатака\w*\b|\bудар\w*\b", 0.48),
    (r"\bsanction\w*\b|\bсанкц\w*\b|\bembargo\b|\bэмбарго\b", 0.48),
    (r"\brisk\w*\b|\bриск\w*\b", 0.18),
    (r"\bcrisis\b|\bкризис\w*\b", 0.35),
    (r"\bfall\w*\b|\bdrop\w*\b|\bпадени\w*\b|\bснижени\w*\b", 0.22),
    (r"\bloss\w*\b|\bубыт\w*\b", 0.35),
    (r"\bbankrupt\w*\b|\bдефолт\w*\b|\bбанкрот\w*\b", 0.55),
    (r"\btariff\w*\b|\bпошлин\w*\b", 0.18),
    (r"\bprice spike\b|\b\$200\b|\b200 a barrel\b|\bрост цен на нефть из-за страха\b", 0.20),
)

_INTENSIFIERS: tuple[tuple[str, float], ...] = (
    (r"\bmajor\b|\bрезк\w*\b|\bsharp\b", 0.08),
    (r"\bmax(?:imum)?\b|\bмаксим\w*\b", 0.12),
    (r"\brecord\b|\bрекорд\w*\b", 0.08),
    (r"\bthreat\w*\b|\bугроз\w*\b", 0.10),
)

_NEGATIONS = ("no ", "not ", "без ", "нет ")


def _normalize(text: str) -> str:
    text = text.lower().replace("ё", "е")
    text = re.sub(r"\s+", " ", text)
    return f" {text.strip()} "


def _score_patterns(text: str, patterns: tuple[tuple[str, float], ...]) -> float:
    score = 0.0
    for pattern, weight in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            score += weight
    return score


def score_text(text: str) -> float:
    """
    Score a single text fragment: -1.0 (very negative) .. +1.0 (very positive).

    We intentionally model market/systemic tone, not sector-specific upside.
    Example: war + oil shock => overall negative / risk-off headline.
    """
    if not text:
        return 0.0

    normalized = _normalize(text)
    pos = _score_patterns(normalized, _POSITIVE_PATTERNS)
    neg = _score_patterns(normalized, _NEGATIVE_PATTERNS)

    easing_sanctions = bool(
        re.search(r"\b(ease|lift|relax)\w* sanctions\b", normalized, re.IGNORECASE)
        or re.search(r"\b(ослаблен|сняти|смягчен)\w* санкц\w*\b", normalized, re.IGNORECASE)
    )
    if easing_sanctions:
        pos += 0.22
        neg *= 0.55

    intensifier = _score_patterns(normalized, _INTENSIFIERS)
    if neg > pos:
        neg += intensifier
    elif pos > neg:
        pos += intensifier * 0.5

    for negation in _NEGATIONS:
        if negation in normalized:
            pos *= 0.8
            neg *= 0.9

    raw = pos - neg
    if raw == 0:
        return 0.0
    raw = max(-1.0, min(1.0, raw))
    return round(raw, 3)


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
        # Exponential-like decay: newest titles weigh more heavily.
        weight = max(0.15, 1.0 - i * 0.08)
        weighted_sum += item.sentiment * weight
        total_weight += weight

    return round(weighted_sum / total_weight, 3) if total_weight > 0 else 0.0
