"""
P4-02: InternetCollector — оркестратор сбора интернет-данных.

Параллельно собирает новости + макро, кеширует результат в Redis.

Cache keys:
  internet:news:{ticker}   TTL = NEWS_CACHE_TTL_SEC (default 900s = 15min)
  internet:macro           TTL = MACRO_CACHE_TTL_SEC (default 3600s = 1h)
"""
from __future__ import annotations

import asyncio
import json
import logging

from apps.worker.ai.internet.macro import MacroCollector
from apps.worker.ai.internet.news import NewsCollector
from apps.worker.ai.internet.sentiment import analyze as sentiment_analyze, aggregate_sentiment
from apps.worker.ai.types import InternetContext, MacroData, NewsItem

logger = logging.getLogger(__name__)


def _news_to_dict(n: NewsItem) -> dict:
    return {"title": n.title, "source": n.source, "url": n.url,
            "published_at": n.published_at, "sentiment": n.sentiment}


def _dict_to_news(d: dict) -> NewsItem:
    return NewsItem(**d)


def _macro_to_dict(m: MacroData) -> dict:
    return {"cbr_key_rate": m.cbr_key_rate, "fed_funds_rate": m.fed_funds_rate,
            "usd_rub": m.usd_rub, "brent_usd": m.brent_usd,
            "geopolitical_risk": m.geopolitical_risk, "data_ts": m.data_ts}


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
        """
        Fetch internet context for ticker.
        Uses Redis cache when available.
        Gracefully degrades: returns empty context on any failure.
        """
        try:
            news, macro = await asyncio.gather(
                self._get_news(ticker),
                self._get_macro(),
                return_exceptions=False,
            )
        except Exception as e:
            logger.warning("InternetCollector error for %s: %s", ticker, e)
            return InternetContext(ticker=ticker)

        # Sentiment scoring
        scored_news = sentiment_analyze(news)
        sentiment = aggregate_sentiment(scored_news)

        return InternetContext(
            ticker=ticker,
            news=scored_news,
            sentiment_score=sentiment,
            macro=macro,
            geopolitical_risk=self._estimate_geopolitical_risk(scored_news),
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
    def _estimate_geopolitical_risk(news: list[NewsItem]) -> float:
        """Rough geopolitical risk: ratio of strongly negative articles."""
        if not news:
            return 0.0
        very_negative = sum(1 for n in news if n.sentiment < -0.3)
        return round(min(1.0, very_negative / max(len(news), 1)), 2)
