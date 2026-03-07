"""
P4-02: MacroCollector — ключевые макроэкономические данные.

Источники (публичные API без ключей):
  - ЦБ РФ: https://www.cbr.ru/scripts/XML_daily.asp  (курсы валют + ставка)
  - CBR key rate: https://www.cbr.ru/hd_base/KeyRate/ (HTML парсинг fallback)
  - Brent: через Yahoo Finance RSS (публичный, без auth)

Все данные кешируются в Redis с TTL=1 час.
"""
from __future__ import annotations

import logging
import re

import httpx

from apps.worker.ai.types import MacroData

logger = logging.getLogger(__name__)


async def _fetch_cbr_rates() -> dict[str, float]:
    """Fetch USD/RUB from CBR daily XML feed."""
    url = "https://www.cbr.ru/scripts/XML_daily.asp"
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            xml = resp.text

        # Extract USD rate
        m = re.search(r'<CharCode>USD</CharCode>.*?<Value>([\d,]+)</Value>', xml, re.DOTALL)
        usd_rub = float(m.group(1).replace(",", ".")) if m else None
        return {"usd_rub": usd_rub}
    except Exception as e:
        logger.warning("CBR rates fetch failed: %s", e)
        return {}


async def _fetch_cbr_key_rate() -> float | None:
    """
    Fetch CBR key rate from their statistics API.
    Returns rate as float (e.g. 16.0) or None on failure.
    """
    # CBR provides key rate history via this endpoint
    url = "https://www.cbr.ru/hd_base/KeyRate/?UniDbQuery.Posted=True&UniDbQuery.From=01.01.2024&UniDbQuery.To=31.12.2025"
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
        # Parse last rate from HTML table (last row)
        rates = re.findall(r"(\d{2}\.\d{2}\.\d{4})</td>\s*<td[^>]*>([\d,]+)</td>", resp.text)
        if rates:
            last_rate = float(rates[-1][1].replace(",", "."))
            return last_rate
    except Exception as e:
        logger.warning("CBR key rate fetch failed: %s", e)
    return None


async def _fetch_brent() -> float | None:
    """Fetch Brent crude price via Yahoo Finance RSS (public, no auth)."""
    url = "https://finance.yahoo.com/rss/headline?s=BZ=F"
    try:
        async with httpx.AsyncClient(timeout=8.0, headers={"User-Agent": "TradingBot/1.0"}) as client:
            resp = await client.get(url)
            resp.raise_for_status()
        # Extract price from title like "Brent Crude Oil Jul 24 (BZ=F) - 87.34"
        m = re.search(r"\(BZ=F\)[^-]*-\s*([\d.]+)", resp.text)
        return float(m.group(1)) if m else None
    except Exception as e:
        logger.debug("Brent fetch failed: %s", e)
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
