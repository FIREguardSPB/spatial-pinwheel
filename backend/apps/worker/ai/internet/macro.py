"""
P4-02: MacroCollector — ключевые макроэкономические данные.

Источники (публичные API без ключей):
  - ЦБ РФ: https://www.cbr.ru/scripts/XML_daily.asp  (курсы валют + ставка)
  - CBR key rate: https://www.cbr.ru/hd_base/KeyRate/ (HTML парсинг fallback)
  - Brent: multi-source fallback (Yahoo quote/RSS, Investing, MarketWatch)

Все данные кешируются в Redis с TTL=1 час.
"""
from __future__ import annotations

import logging
import re

import httpx

from core.utils.http_client import make_async_client

from apps.worker.ai.types import MacroData

logger = logging.getLogger(__name__)
_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
}


async def _fetch_cbr_rates() -> dict[str, float]:
    """Fetch USD/RUB from CBR daily XML feed."""
    url = "https://www.cbr.ru/scripts/XML_daily.asp"
    try:
        async with make_async_client(timeout=8.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            xml = resp.text

        m = re.search(r'<CharCode>USD</CharCode>.*?<Value>([\d,]+)</Value>', xml, re.DOTALL)
        usd_rub = float(m.group(1).replace(",", ".")) if m else None
        return {"usd_rub": usd_rub}
    except Exception as e:
        logger.warning("CBR rates fetch failed: %s", e)
        return {}


async def _fetch_cbr_key_rate() -> float | None:
    """Fetch CBR key rate from their statistics page."""
    url = "https://www.cbr.ru/hd_base/KeyRate/?UniDbQuery.Posted=True&UniDbQuery.From=01.01.2024&UniDbQuery.To=31.12.2026"
    try:
        async with make_async_client(timeout=8.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
        rates = re.findall(r"(\d{2}\.\d{2}\.\d{4})</td>\s*<td[^>]*>([\d,]+)</td>", resp.text)
        if rates:
            return float(rates[-1][1].replace(",", "."))
    except Exception as e:
        logger.warning("CBR key rate fetch failed: %s", e)
    return None


def _extract_number(text: str, patterns: list[str]) -> float | None:
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if not match:
            continue
        raw = match.group(1).replace(",", ".").strip()
        try:
            value = float(raw)
        except ValueError:
            continue
        if 20.0 <= value <= 300.0:
            return value
    return None


async def _fetch_brent_yahoo_rss(client: httpx.AsyncClient) -> float | None:
    resp = await client.get("https://finance.yahoo.com/rss/headline?s=BZ=F")
    resp.raise_for_status()
    return _extract_number(resp.text, [r"\(BZ=F\)[^-]*-\s*([\d.]+)"])


async def _fetch_brent_yahoo_quote(client: httpx.AsyncClient) -> float | None:
    resp = await client.get("https://finance.yahoo.com/quote/BZ%3DF/")
    resp.raise_for_status()
    return _extract_number(
        resp.text,
        [
            r'"regularMarketPrice"\s*:\s*\{[^}]*"raw"\s*:\s*([\d.]+)',
            r'"currentPrice"\s*:\s*\{[^}]*"raw"\s*:\s*([\d.]+)',
        ],
    )


async def _fetch_brent_investing(client: httpx.AsyncClient) -> float | None:
    resp = await client.get("https://www.investing.com/commodities/brent-oil")
    resp.raise_for_status()
    return _extract_number(
        resp.text,
        [
            r"current price of Brent Oil futures is\s*([\d.]+)",
            r'"last_last"[^>]*>\s*([\d.]+)\s*<',
            r'"last"\s*:\s*([\d.]+)',
        ],
    )


async def _fetch_brent_marketwatch(client: httpx.AsyncClient) -> float | None:
    resp = await client.get("https://www.marketwatch.com/investing/future/brn00?countrycode=uk")
    resp.raise_for_status()
    return _extract_number(
        resp.text,
        [
            r"Futures Overview\s*;\s*Brent Crude Oil Continuous Contract,\s*\$?([\d.]+)",
            r'"price"\s*:\s*"?([\d.]+)"?',
            r'"last"\s*:\s*\{[^}]*"price"\s*:\s*([\d.]+)',
        ],
    )


async def _fetch_brent() -> float | None:
    """Fetch Brent crude price using a resilient multi-source fallback chain."""
    fetchers = [
        ("yahoo_quote", _fetch_brent_yahoo_quote),
        ("yahoo_rss", _fetch_brent_yahoo_rss),
        ("investing", _fetch_brent_investing),
        ("marketwatch", _fetch_brent_marketwatch),
    ]
    async with make_async_client(timeout=10.0, headers=_BROWSER_HEADERS, follow_redirects=True) as client:
        for source_name, fetcher in fetchers:
            try:
                value = await fetcher(client)
            except Exception as e:
                logger.debug("Brent fetch failed via %s: %s", source_name, e)
                continue
            if value is not None:
                logger.info("Brent price loaded via %s: %.2f", source_name, value)
                return value
    logger.warning("Brent price unavailable from all configured public sources")
    return None


class MacroCollector:
    """Collects macro-economic data for AI context."""

    async def fetch(self) -> MacroData:
        """Collect all macro data. Partial failures return available data."""
        import asyncio
        cbr_rates, cbr_rate, brent = await asyncio.gather(
            _fetch_cbr_rates(),
            _fetch_cbr_key_rate(),
            _fetch_brent(),
            return_exceptions=True,
        )

        usd_rub = cbr_rates.get("usd_rub") if isinstance(cbr_rates, dict) else None
        key_rate = cbr_rate if isinstance(cbr_rate, float) else None
        brent_price = brent if isinstance(brent, float) else None

        import time
        return MacroData(
            cbr_key_rate=key_rate,
            usd_rub=usd_rub,
            brent_usd=brent_price,
            data_ts=int(time.time() * 1000),
        )
