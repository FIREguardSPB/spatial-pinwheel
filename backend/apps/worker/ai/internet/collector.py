"""
P4-02: InternetCollector — оркестратор сбора интернет-данных.

Параллельно собирает новости + макро, кеширует результат в Redis.
"""
from __future__ import annotations

import asyncio
import json
import logging

from apps.worker.ai.internet.macro import MacroCollector
from apps.worker.ai.relevance import (
    has_dynamic_geopolitical_event,
    has_dynamic_rate_event,
    select_recent_company_news,
    should_include_fx_context,
    should_include_geopolitical_context,
    should_include_rate_context,
)
from apps.worker.ai.sector_profiles import build_sector_narrative_summary, get_sector_profile
from apps.worker.ai.internet.news import NewsCollector
from apps.worker.ai.internet.sentiment import analyze as sentiment_analyze, aggregate_sentiment
from apps.worker.ai.types import InternetContext, MacroData, NewsItem

logger = logging.getLogger(__name__)

_TOPIC_RULES: dict[str, tuple[str, ...]] = {
    "санкции": ("sanction", "санкц", "restriction", "эмбарго", "embargo", "waiver"),
    "война/конфликт": (
        "war", "войн", "conflict", "escalat", "атака", "strike", "iran", "middle east",
        "ближний восток", "ukraine", "украин", "israel", "gaza", "hormuz",
    ),
    "нефть/логистика": (
        "brent", "oil", "нефть", "opec", "hormuz", "shipping", "танкер", "логист",
        "supply", "barrel", "добыч", "экспорт нефти",
    ),
    "ставки/инфляция": ("rate", "ставк", "inflation", "инфляц", "fed", "цб", "central bank"),
    "пошлины/торговля": ("tariff", "пошлин", "export", "import", "экспорт", "импорт", "trade"),
}

_OIL_GAS_TICKERS = {"ROSN", "LKOH", "NVTK", "GAZP", "TATN", "SIBN"}


def _news_to_dict(n: NewsItem) -> dict:
    return {
        "title": n.title,
        "source": n.source,
        "url": n.url,
        "published_at": n.published_at,
        "sentiment": n.sentiment,
    }


def _dict_to_news(d: dict) -> NewsItem:
    return NewsItem(**d)


def _macro_to_dict(m: MacroData) -> dict:
    return {
        "cbr_key_rate": m.cbr_key_rate,
        "fed_funds_rate": m.fed_funds_rate,
        "usd_rub": m.usd_rub,
        "brent_usd": m.brent_usd,
        "geopolitical_risk": m.geopolitical_risk,
        "data_ts": m.data_ts,
    }


def _dict_to_macro(d: dict) -> MacroData:
    return MacroData(**d)


class InternetCollector:
    def __init__(self, redis_client=None, news_ttl: int = 900, macro_ttl: int = 3600):
        self._redis = redis_client
        self._news_ttl = news_ttl
        self._macro_ttl = macro_ttl
        self._news_collector = NewsCollector()
        self._macro_collector = MacroCollector()

    async def get_context(self, ticker: str) -> InternetContext:
        try:
            news, macro = await asyncio.gather(
                self._get_news(ticker),
                self._get_macro(),
                return_exceptions=False,
            )
        except Exception as e:
            logger.warning("InternetCollector error for %s: %s", ticker, e)
            return InternetContext(ticker=ticker)

        scored_news = sentiment_analyze(news)
        sentiment = aggregate_sentiment(scored_news)
        topic_counts = self._count_topics(scored_news)
        topics = [label for label, count in sorted(topic_counts.items(), key=lambda item: item[1], reverse=True) if count > 0][:5]
        geopolitical_risk = self._estimate_geopolitical_risk(scored_news, macro, topic_counts)
        macro.geopolitical_risk = geopolitical_risk
        narrative_summary = self._build_narrative_summary(ticker, scored_news, macro, topic_counts, geopolitical_risk, sentiment)

        return InternetContext(
            ticker=ticker,
            news=scored_news,
            sentiment_score=sentiment,
            macro=macro,
            geopolitical_risk=geopolitical_risk,
            topics=topics,
            topic_counts=topic_counts,
            narrative_summary=narrative_summary,
            from_cache=False,
        )

    async def _get_news(self, ticker: str) -> list[NewsItem]:
        cache_key = f"internet:news:{ticker}"

        if self._redis:
            try:
                cached = await self._redis.get(cache_key)
                if cached:
                    data = json.loads(cached)
                    logger.debug("News cache HIT for %s (%d items)", ticker, len(data))
                    return [_dict_to_news(d) for d in data]
            except Exception as e:
                logger.debug("Redis news cache read error: %s", e)

        news = await self._news_collector.fetch(ticker)

        if self._redis and news:
            try:
                payload = json.dumps([_news_to_dict(n) for n in news])
                await self._redis.setex(cache_key, self._news_ttl, payload)
            except Exception as e:
                logger.debug("Redis news cache write error: %s", e)

        return news

    async def _get_macro(self) -> MacroData:
        cache_key = "internet:macro"

        if self._redis:
            try:
                cached = await self._redis.get(cache_key)
                if cached:
                    logger.debug("Macro cache HIT")
                    return _dict_to_macro(json.loads(cached))
            except Exception as e:
                logger.debug("Redis macro cache read error: %s", e)

        macro = await self._macro_collector.fetch()

        if self._redis:
            try:
                await self._redis.setex(cache_key, self._macro_ttl, json.dumps(_macro_to_dict(macro)))
            except Exception as e:
                logger.debug("Redis macro cache write error: %s", e)

        return macro

    @staticmethod
    def _count_topics(news: list[NewsItem]) -> dict[str, int]:
        counts: dict[str, int] = {label: 0 for label in _TOPIC_RULES}
        for item in news:
            title = item.title.lower()
            for label, patterns in _TOPIC_RULES.items():
                if any(pattern in title for pattern in patterns):
                    counts[label] += 1
        return counts

    @staticmethod
    def _estimate_geopolitical_risk(news: list[NewsItem], macro: MacroData, topic_counts: dict[str, int]) -> float:
        if not news:
            base = 0.0
        else:
            very_negative = sum(1 for n in news if n.sentiment <= -0.45)
            conflict_hits = topic_counts.get("война/конфликт", 0)
            sanctions_hits = topic_counts.get("санкции", 0)
            oil_hits = topic_counts.get("нефть/логистика", 0)
            base = (very_negative * 0.08) + (conflict_hits * 0.05) + (sanctions_hits * 0.04)
            if oil_hits >= 3 and conflict_hits >= 3:
                base += 0.10

        if macro.brent_usd is not None and macro.brent_usd >= 95:
            base += 0.08
        if macro.brent_usd is not None and macro.brent_usd >= 110:
            base += 0.08
        if macro.usd_rub is not None and macro.usd_rub >= 95:
            base += 0.05
        return round(min(1.0, base), 2)

    @staticmethod
    def _build_narrative_summary(
        ticker: str,
        news: list[NewsItem],
        macro: MacroData,
        topic_counts: dict[str, int],
        geopolitical_risk: float,
        sentiment_score: float,
    ) -> list[str]:
        summary: list[str] = []
        ticker_code = ticker.split(":")[-1].upper()
        profile = get_sector_profile(ticker_code)
        inet = InternetContext(
            ticker=ticker,
            news=news,
            sentiment_score=sentiment_score,
            macro=macro,
            geopolitical_risk=geopolitical_risk,
            topic_counts=topic_counts,
        )

        recent_news = select_recent_company_news(inet, hours=24, limit=2)
        if recent_news:
            summary.append("Свежие headline'ы по бумаге/сектору: " + "; ".join(item.title for item in recent_news) + ".")

        if ticker_code in _OIL_GAS_TICKERS and macro.brent_usd is not None:
            if macro.brent_usd >= 100:
                summary.append(f"Для {ticker_code} Brent ${macro.brent_usd:.2f} остаётся поддерживающим intraday-драйвером.")
            elif macro.brent_usd <= 70:
                summary.append(f"Для {ticker_code} Brent ${macro.brent_usd:.2f} создаёт слабый сырьевой фон даже внутри дня.")

        if macro.cbr_key_rate is not None and should_include_rate_context(profile.code, inet, horizon="scalp") and has_dynamic_rate_event(inet):
            summary.append(f"Есть свежий rate-катализатор: ставка/риторика ЦБ делают уровень {macro.cbr_key_rate:.2f}% актуальным именно сейчас.")

        if should_include_geopolitical_context(profile.code, inet, horizon="scalp") and has_dynamic_geopolitical_event(inet):
            summary.append(
                f"Свежий geo/logistics catalyst: война/конфликт={topic_counts.get('война/конфликт', 0)}, санкции={topic_counts.get('санкции', 0)}, нефть/логистика={topic_counts.get('нефть/логистика', 0)}."
            )

        if should_include_fx_context(profile.code, inet, horizon="scalp") and macro.usd_rub is not None:
            summary.append(f"Свежий FX-фон при USD/RUB={macro.usd_rub:.3f} важен для сектора {profile.name_ru}.")

        if not summary:
            summary.append("Нет значимых свежих макро/гео-триггеров для горизонта 1–30 минут; приоритет у техники и ликвидности.")

        summary.extend(build_sector_narrative_summary(ticker, inet, horizon="scalp"))
        return summary[:6]
