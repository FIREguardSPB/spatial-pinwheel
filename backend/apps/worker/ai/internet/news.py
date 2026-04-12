"""
P4-02: NewsCollector — сбор публичных финансовых и макро/геополитических новостей.

Источники:
- RSS/Atom: российские, западные, азиатские и отраслевые ленты
- HTML pages: Reuters Business / Markets / Energy / World

Результаты кешируются в Redis с TTL=15 минут.
"""
from __future__ import annotations

import logging
import re
import time
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

import httpx

from core.utils.http_client import make_async_client

from apps.worker.ai.sector_profiles import sector_keywords_for_ticker
from apps.worker.ai.types import NewsItem

logger = logging.getLogger(__name__)
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ru,en-US;q=0.9,en;q=0.8",
}

_RSS_FEEDS = [
    ("RBC Markets", "https://rssexport.rbc.ru/rbcnews/news/30/full.rss"),
    ("Investing RU", "https://ru.investing.com/rss/news.rss"),
    ("Коммерсант", "https://www.kommersant.ru/RSS/news.xml"),
    ("Ведомости", "https://www.vedomosti.ru/rss/news"),
    ("OilPrice", "https://oilprice.com/rss/main"),
    ("Financial Times", "https://www.ft.com/rss/world/markets"),
    ("Wall Street Journal", "https://feeds.a.dj.com/rss/RSSMarketsMain.xml"),
    ("Nikkei Asia", "https://asia.nikkei.com/rss/feed/nar"),
    ("SCMP", "https://www.scmp.com/rss/91/feed"),
]

_REUTERS_PAGES = [
    ("Reuters Business", "https://www.reuters.com/business/"),
    ("Reuters Markets", "https://www.reuters.com/markets/"),
    ("Reuters Energy", "https://www.reuters.com/business/energy/"),
    ("Reuters World", "https://www.reuters.com/world/"),
]

_TICKER_KEYWORDS: dict[str, list[str]] = {
    "SBER": ["сбербанк", "сбер", "sber"],
    "GAZP": ["газпром", "gazprom", "gas export", "газ"],
    "LKOH": ["лукойл", "lukoil"],
    "YNDX": ["яндекс", "yandex"],
    "MOEX": ["мосбиржа", "moex", "московская биржа"],
    "ROSN": ["роснефть", "rosneft"],
    "NVTK": ["новатэк", "novatek", "lng"],
    "VTBR": ["втб", "vtb"],
    "PHOR": ["фосагро", "phosagro", "fertilizer", "удобрени"],
    "HYDR": ["русгидро", "rushydro", "гидро"],
    "TATN": ["татнефть", "tatneft"],
    "SIBN": ["газпром нефть", "gazprom neft"],
    "SNGS": ["сургутнефтегаз", "surgutneftegas"],
    "CBOM": ["московский кредитный банк", "cbom", "мкб"],
    "SFIN": ["sfi", "эсэфай"],
    "VKCO": ["vk", "vk company", "вконтакте", "вк"],
    "RTKM": ["ростелеком", "rostelecom"],
    "MTSS": ["мтс", "mts"],
    "MGNT": ["магнит", "magnit"],
    "OZON": ["ozon", "озон"],
    "FIXP": ["fix price", "фикс прайс"],
    "AFLT": ["аэрофлот", "aeroflot"],
    "GMKN": ["норникель", "nornickel", "gmkn", "гмк"],
    "ALRS": ["алроса", "alrosa"],
    "PLZL": ["полюс", "polyus", "plzl"],
    "POLY": ["polymetal", "poly"],
    "FEES": ["фск еэс", "fees", "россети"],
    "PIKK": ["пик", "pikk", "гк пик"],
    "SMLT": ["самолет", "samolet", "smlt"],
    "AGRO": ["русагро", "rusagro", "agro"],
    "SGZH": ["сегежа", "segezha", "sgzh"],
}

_GLOBAL_MARKET_KEYWORDS = [
    "brent", "нефть", "oil", "opec", "sanction", "санкц", "war", "войн",
    "conflict", "конфликт", "hormuz", "ormuz", "strait", "tariff", "пошлин",
    "inflation", "инфляц", "rate", "ставк", "цб", "fed", "central bank",
    "export", "импорт", "supply", "постав", "shipping", "логист",
    "iran", "иран", "middle east", "ближний восток", "ukraine", "украин",
    "russia", "росси", "moscow exchange", "moex",
]

_NAMESPACE_STRIPPER = re.compile(r"\{.*?\}")

_FAILURE_LOG_STATE: dict[str, tuple[int, float]] = {}


def _log_feed_failure(kind: str, source_name: str, detail: str) -> None:
    key = f"{kind}:{source_name}"
    count, last_ts = _FAILURE_LOG_STATE.get(key, (0, 0.0))
    now = time.monotonic()
    count += 1
    _FAILURE_LOG_STATE[key] = (count, now)
    if count <= 2 or now - last_ts >= 300.0:
        logger.warning("%s [%s]: %s (failures=%d)", kind, source_name, detail, count)


def _mark_feed_success(kind: str, source_name: str) -> None:
    _FAILURE_LOG_STATE.pop(f"{kind}:{source_name}", None)


def _extract_ticker_name(instrument_id: str) -> str:
    return instrument_id.split(":")[-1].upper()


def _keywords_for(ticker: str) -> list[str]:
    base = list(_TICKER_KEYWORDS.get(ticker, [ticker.lower()]))
    for kw in sector_keywords_for_ticker(ticker):
        if kw not in base:
            base.append(kw)
    return base


def _clean_html_text(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"&[a-zA-Z#0-9]+;", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _normalize_title(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _title_matches(title: str, keywords: list[str]) -> bool:
    title_lower = title.lower()
    return any(kw in title_lower for kw in keywords) or any(kw in title_lower for kw in _GLOBAL_MARKET_KEYWORDS)


def _safe_iso_datetime(value: str) -> str:
    if not value:
        return ""
    try:
        return parsedate_to_datetime(value).isoformat()
    except Exception:
        return value.strip()


def _strip_namespaces(xml: str) -> str:
    return _NAMESPACE_STRIPPER.sub("", xml)


def _parse_xml_feed(payload: str, source: str, keywords: list[str]) -> list[NewsItem]:
    items: list[NewsItem] = []
    try:
        root = ET.fromstring(_strip_namespaces(payload))
    except ET.ParseError:
        return items

    candidates = root.findall(".//item") or root.findall(".//entry")
    for entry in candidates:
        title = _clean_html_text(entry.findtext("title", default=""))
        if not title or not _title_matches(title, keywords):
            continue

        link_text = entry.findtext("link", default="")
        if not link_text:
            link_el = entry.find("link")
            if link_el is not None:
                link_text = link_el.attrib.get("href", "") or (link_el.text or "")
        published_raw = (
            entry.findtext("pubDate", default="")
            or entry.findtext("published", default="")
            or entry.findtext("updated", default="")
        )

        items.append(
            NewsItem(
                title=title,
                source=source,
                url=link_text.strip(),
                published_at=_safe_iso_datetime(published_raw),
                sentiment=0.0,
            )
        )
        if len(items) >= 14:
            break
    return items


def _parse_reuters(html: str, source: str, keywords: list[str]) -> list[NewsItem]:
    items: list[NewsItem] = []
    seen: set[str] = set()
    for href, raw_title in re.findall(r'href="(/[^"#?]+)"[^>]*>(.*?)</a>', html, re.DOTALL | re.IGNORECASE):
        title = _clean_html_text(raw_title)
        if len(title) < 25 or not href.startswith("/"):
            continue
        norm_title = _normalize_title(title)
        if norm_title in seen or not _title_matches(title, keywords):
            continue
        seen.add(norm_title)
        items.append(
            NewsItem(
                title=title,
                source=source,
                url=f"https://www.reuters.com{href}",
                published_at="",
                sentiment=0.0,
            )
        )
        if len(items) >= 8:
            break
    return items


class NewsCollector:
    async def fetch(self, ticker: str) -> list[NewsItem]:
        keywords = _keywords_for(_extract_ticker_name(ticker))
        all_items: list[NewsItem] = []
        seen_titles: set[str] = set()

        async with make_async_client(timeout=10.0, headers=_HEADERS, follow_redirects=True) as client:
            for source_name, url in _RSS_FEEDS:
                try:
                    resp = await client.get(url)
                    if resp.status_code != 200:
                        _log_feed_failure("Feed fetch failed", source_name, f"http {resp.status_code}")
                        continue
                    for item in _parse_xml_feed(resp.text, source_name, keywords):
                        norm_title = _normalize_title(item.title)
                        if norm_title in seen_titles:
                            continue
                        seen_titles.add(norm_title)
                        all_items.append(item)
                    _mark_feed_success("Feed fetch failed", source_name)
                except Exception as e:
                    _log_feed_failure("Feed fetch failed", source_name, str(e))

            for source_name, url in _REUTERS_PAGES:
                try:
                    resp = await client.get(url)
                    if resp.status_code != 200:
                        _log_feed_failure("Reuters page fetch failed", source_name, f"http {resp.status_code}")
                        continue
                    for item in _parse_reuters(resp.text, source_name, keywords):
                        norm_title = _normalize_title(item.title)
                        if norm_title in seen_titles:
                            continue
                        seen_titles.add(norm_title)
                        all_items.append(item)
                    _mark_feed_success("Reuters page fetch failed", source_name)
                except Exception as e:
                    _log_feed_failure("Reuters page fetch failed", source_name, str(e))

        all_items.sort(key=lambda n: n.published_at or "", reverse=True)
        return all_items[:24]
