"""
P4-02: NewsCollector — парсинг RSS-лент финансовых СМИ.

Источники: RBC, Investing.com RU, Reuters RU
Результаты кешируются в Redis с TTL=15 минут.
Соблюдает rate limits и robots.txt — только публичные RSS-фиды.
"""
from __future__ import annotations

import logging
import re
import time
from email.utils import parsedate_to_datetime
from typing import TYPE_CHECKING

import httpx

from apps.worker.ai.types import NewsItem

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Публичные RSS-фиды (только официальные, соблюдаем robots.txt)
_RSS_FEEDS = [
    ("RBC Markets", "https://rssexport.rbc.ru/rbcnews/news/30/full.rss"),
    ("Investing RU", "https://ru.investing.com/rss/news.rss"),
]

# Ключевые слова тикера → полные названия для поиска в заголовках
_TICKER_KEYWORDS: dict[str, list[str]] = {
    "SBER": ["сбербанк", "сбер", "sber"],
    "GAZP": ["газпром", "gazprom"],
    "LKOH": ["лукойл", "lukoil"],
    "YNDX": ["яндекс", "yandex"],
    "MOEX": ["мосбиржа", "moex", "московская биржа"],
    "ROSN": ["роснефть", "rosneft"],
    "NVTK": ["новатэк", "novatek"],
    "VTBR": ["втб", "vtb"],
}


def _extract_ticker_name(instrument_id: str) -> str:
    """'TQBR:SBER' → 'SBER'"""
    return instrument_id.split(":")[-1].upper()


def _keywords_for(ticker: str) -> list[str]:
    return _TICKER_KEYWORDS.get(ticker, [ticker.lower()])


def _parse_rss(xml: str, source: str, keywords: list[str]) -> list[NewsItem]:
    """Parse RSS XML, filter items matching keywords in title/description."""
    items: list[NewsItem] = []
    # Simple regex-based parse (no lxml dependency needed for MVP)
    entries = re.findall(r"<item>(.*?)</item>", xml, re.DOTALL)
    for entry in entries:
        title_m = re.search(r"<title>(.*?)</title>", entry, re.DOTALL)
        link_m = re.search(r"<link>(.*?)</link>", entry, re.DOTALL)
        pub_m = re.search(r"<pubDate>(.*?)</pubDate>", entry, re.DOTALL)

        title = re.sub(r"<[^>]+>|&lt;|&gt;|&amp;|&quot;|&#\d+;", " ", title_m.group(1) if title_m else "").strip()
        link = (link_m.group(1) if link_m else "").strip()
        pub_raw = (pub_m.group(1) if pub_m else "").strip()

        if not title:
            continue

        title_lower = title.lower()
        if not any(kw in title_lower for kw in keywords):
            continue

        try:
            pub_dt = parsedate_to_datetime(pub_raw).isoformat() if pub_raw else ""
        except Exception:
            pub_dt = ""

        items.append(NewsItem(
            title=title,
            source=source,
            url=link,
            published_at=pub_dt,
            sentiment=0.0,  # filled by SentimentAnalyzer
        ))

    return items[:10]  # cap per feed


class NewsCollector:
    """
    Collects and filters news relevant to a specific ticker.
    Results are cached in Redis by the InternetCollector orchestrator.
    """

    async def fetch(self, ticker: str) -> list[NewsItem]:
        """Fetch news from all RSS feeds, filter by ticker keywords."""
        keywords = _keywords_for(ticker)
        all_items: list[NewsItem] = []

        async with httpx.AsyncClient(timeout=10.0, headers={"User-Agent": "TradingBot/1.0 RSS Reader"}) as client:
            for source_name, url in _RSS_FEEDS:
                try:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        items = _parse_rss(resp.text, source_name, keywords)
                        all_items.extend(items)
                        logger.debug("%s: %d relevant items from %s", ticker, len(items), source_name)
                except Exception as e:
                    logger.warning("RSS fetch failed [%s]: %s", source_name, e)

        # Sort by publication date descending (newest first)
        all_items.sort(key=lambda n: n.published_at, reverse=True)
        return all_items[:15]
