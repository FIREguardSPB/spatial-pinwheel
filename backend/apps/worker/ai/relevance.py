from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable

from apps.worker.ai.types import InternetContext, NewsItem

_RATE_NOUNS = (
    "ставк", "rate", "central bank", "центробанк", "цб", "fed", "boe", "ecb", "fomc",
)
_RATE_CHANGE_VERBS = (
    "повыс", "сниз", "поднял", "опуст", "cut", "hike", "raise", "lower", "hold", "pivot",
    "meeting", "заседан", "решени", "guidance", "signal", "смягчен", "ужесточ", "сохран", "retention",
)
_GEO_SHOCK_PATTERNS = (
    "attack", "strike", "drone", "missile", "атака", "удар", "обстрел", "взрыв", "threat",
    "угроз", "hormuz", "pipeline", "ceasefire", "truce", "escalat", "санкц", "embargo",
    "эмбарго", "blockade", "shipping", "логист", "tariff", "пошлин",
)
_FX_PATTERNS = (
    "usd/rub", "доллар", "рубл", "валют", "currency", "fx", "devaluation", "девальвац",
)
_SECTOR_GEO_SENSITIVE = {
    "oil_gas", "transport", "metals_mining", "fertilizers_agro", "forestry_packaging", "banks_finance",
}
_SECTOR_FX_SENSITIVE = {
    "oil_gas", "technology", "telecom", "transport", "retail_ecommerce", "metals_mining",
    "fertilizers_agro", "forestry_packaging",
}


def parse_news_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    raw = value.strip()
    if not raw:
        return None
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def iter_recent_news(news: Iterable[NewsItem], *, hours: int = 24, now: datetime | None = None) -> list[NewsItem]:
    anchor = now or datetime.now(timezone.utc)
    cutoff = anchor - timedelta(hours=hours)
    items: list[tuple[datetime, NewsItem]] = []
    for item in news:
        dt = parse_news_datetime(item.published_at)
        if dt is None:
            continue
        if dt >= cutoff:
            items.append((dt, item))
    items.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in items]


def _title_has_any(item: NewsItem, patterns: Iterable[str]) -> bool:
    title = (item.title or "").lower()
    return any(pattern in title for pattern in patterns)


def has_dynamic_rate_event(inet: InternetContext, *, hours: int = 120) -> bool:
    for item in iter_recent_news(inet.news, hours=hours):
        title = (item.title or "").lower()
        if any(noun in title for noun in _RATE_NOUNS) and any(verb in title for verb in _RATE_CHANGE_VERBS):
            return True
    return False


def has_dynamic_geopolitical_event(inet: InternetContext, *, hours: int = 120) -> bool:
    for item in iter_recent_news(inet.news, hours=hours):
        if _title_has_any(item, _GEO_SHOCK_PATTERNS):
            return True
    return False


def has_dynamic_fx_event(inet: InternetContext, *, hours: int = 120) -> bool:
    for item in iter_recent_news(inet.news, hours=hours):
        if _title_has_any(item, _FX_PATTERNS):
            return True
    return False


def select_recent_company_news(inet: InternetContext, *, hours: int = 24, limit: int = 3) -> list[NewsItem]:
    recent = iter_recent_news(inet.news, hours=hours)
    ranked = sorted(recent, key=lambda item: (abs(item.sentiment), len(item.title or "")), reverse=True)
    return ranked[:limit]


def should_include_rate_context(sector_code: str, inet: InternetContext, *, horizon: str = "scalp") -> bool:
    if horizon != "scalp":
        return True
    return has_dynamic_rate_event(inet)


def should_include_geopolitical_context(sector_code: str, inet: InternetContext, *, horizon: str = "scalp") -> bool:
    if horizon != "scalp":
        return True
    if sector_code not in _SECTOR_GEO_SENSITIVE:
        return False
    return has_dynamic_geopolitical_event(inet)


def should_include_fx_context(sector_code: str, inet: InternetContext, *, horizon: str = "scalp") -> bool:
    if horizon != "scalp":
        return True
    if sector_code not in _SECTOR_FX_SENSITIVE:
        return False
    return has_dynamic_fx_event(inet)


def is_dynamic_macro_signal_present(sector_code: str, inet: InternetContext, *, horizon: str = "scalp") -> bool:
    return any(
        (
            should_include_rate_context(sector_code, inet, horizon=horizon),
            should_include_geopolitical_context(sector_code, inet, horizon=horizon),
            should_include_fx_context(sector_code, inet, horizon=horizon),
        )
    )
