from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from apps.worker.ai.types import InternetContext, NewsItem
from core.storage.models import SymbolEventRegime


@dataclass
class EventRegime:
    instrument_id: str
    regime: str = 'calm'
    severity: float = 0.0
    direction: str = 'neutral'
    score_bias: int = 0
    hold_bias: int = 0
    risk_bias: float = 1.0
    action: str = 'observe'
    catalysts: list[str] | None = None
    narrative: str | None = None

    def to_meta(self) -> dict[str, Any]:
        payload = asdict(self)
        payload['severity'] = round(float(self.severity), 4)
        payload['risk_bias'] = round(float(self.risk_bias), 4)
        payload['catalysts'] = list(self.catalysts or [])
        return payload


def _published_age_hours(item: NewsItem) -> float | None:
    try:
        raw = (item.published_at or '').replace('Z', '+00:00')
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - dt.astimezone(timezone.utc)).total_seconds() / 3600.0)
    except Exception:
        return None


def _classify_title(title: str) -> tuple[str, int]:
    low = (title or '').lower()
    if any(word in low for word in ('дивид', 'dividend', 'buyback', 'guidance', 'upgrade', 'контракт', 'рост прибыли', 'strong results', 'рекорд')):
        return 'supportive', 1
    if any(word in low for word in ('санкц', 'downgrade', 'убыт', 'скидка к дивиденду', 'эмбарго', 'fire', 'штраф', 'паден', 'drop', 'guidance cut')):
        return 'adverse', -1
    if any(word in low for word in ('ставк', 'цб', 'fed', 'inflation', 'nonfarm', 'cpi', 'opec', 'brent', 'usd/rub', 'usd rub', 'курс')):
        return 'macro', 0
    return 'neutral', 0


def analyze_event_regime(
    instrument_id: str,
    side: str,
    internet: InternetContext | None,
    symbol_profile: dict[str, Any] | None = None,
    symbol_diagnostics: dict[str, Any] | None = None,
) -> EventRegime:
    profile = dict(symbol_profile or {})
    diagnostics = dict(symbol_diagnostics or {})
    ctx = internet or InternetContext(ticker=instrument_id)
    sensitivity = float(profile.get('news_sensitivity') or 1.0)
    sentiment = float(getattr(ctx, 'sentiment_score', 0.0) or 0.0)
    geo = float(getattr(ctx, 'geopolitical_risk', 0.0) or 0.0)
    volatility_pct = float(diagnostics.get('volatility_pct') or 0.0)
    catalysts: list[str] = []
    supportive_weight = 0.0
    adverse_weight = 0.0
    macro_weight = 0.0

    for item in list(getattr(ctx, 'news', []) or [])[:6]:
        age_h = _published_age_hours(item)
        freshness = 1.0 if age_h is None else max(0.25, 1.15 - min(age_h, 24.0) / 24.0)
        label, direction = _classify_title(item.title)
        weight = freshness * (1.0 + abs(float(item.sentiment or 0.0)))
        if label == 'supportive':
            supportive_weight += weight
            catalysts.append(f'+ {item.title[:90]}')
        elif label == 'adverse':
            adverse_weight += weight
            catalysts.append(f'- {item.title[:90]}')
        elif label == 'macro':
            macro_weight += weight * 0.7
            catalysts.append(f'~ {item.title[:90]}')

    raw_bias = (supportive_weight - adverse_weight) + sentiment * 1.6
    if geo > 0.55:
        raw_bias -= (geo - 0.55) * 3.0
    if macro_weight > 0:
        raw_bias += 0.35 * macro_weight if side == 'BUY' else -0.10 * macro_weight

    severity = min(1.0, (abs(raw_bias) * 0.22 + geo * 0.25) * max(0.65, sensitivity))
    direction = 'supportive' if raw_bias >= 0.25 else 'adverse' if raw_bias <= -0.25 else 'neutral'
    if severity < 0.18 and abs(sentiment) < 0.12 and geo < 0.4:
        regime = 'calm'
    elif direction == 'supportive' and severity >= 0.35:
        regime = 'catalyst_follow_through'
    elif direction == 'adverse' and severity >= 0.35:
        regime = 'risk_off_shock'
    elif volatility_pct >= 1.2 and abs(raw_bias) >= 0.2:
        regime = 'eventful_high_vol'
    else:
        regime = 'watchful'

    score_bias = 0
    hold_bias = 0
    risk_bias = 1.0
    action = 'observe'
    if regime == 'catalyst_follow_through':
        score_bias = 5 if side == 'BUY' else 2
        hold_bias = 2
        risk_bias = 1.05
        action = 'lean_with_catalyst'
    elif regime == 'risk_off_shock':
        score_bias = -10 if side == 'BUY' else -4
        hold_bias = -3
        risk_bias = 0.75
        action = 'de_risk'
    elif regime == 'eventful_high_vol':
        score_bias = 2 if direction == 'supportive' else -3
        hold_bias = 1 if direction == 'supportive' else -2
        risk_bias = 0.90 if direction == 'adverse' else 1.0
        action = 'trade_smaller'
    elif regime == 'watchful':
        score_bias = 1 if direction == 'supportive' else -2 if direction == 'adverse' else 0
        hold_bias = 0
        risk_bias = 0.95 if direction == 'adverse' else 1.0

    narrative = '; '.join(catalysts[:3]) if catalysts else 'no fresh event catalyst'
    return EventRegime(
        instrument_id=instrument_id,
        regime=regime,
        severity=severity,
        direction=direction,
        score_bias=score_bias,
        hold_bias=hold_bias,
        risk_bias=risk_bias,
        action=action,
        catalysts=catalysts[:5],
        narrative=narrative,
    )


def persist_event_regime(db: Session, event: EventRegime) -> None:
    try:
        db.add(SymbolEventRegime(
            instrument_id=event.instrument_id,
            ts=int(time.time() * 1000),
            regime=event.regime,
            severity=float(event.severity),
            direction=event.direction,
            score_bias=int(event.score_bias),
            hold_bias=int(event.hold_bias),
            risk_bias=float(event.risk_bias),
            action=event.action,
            payload=event.to_meta(),
        ))
        db.commit()
    except Exception:
        db.rollback()
        raise
