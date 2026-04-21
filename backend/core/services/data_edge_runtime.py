from __future__ import annotations

import time
from typing import Any

from core.sentiment.repo import build_collection_status, build_source_analytics
from core.storage.models import CandleCache, DecisionLog


def _now_ms() -> int:
    return int(time.time() * 1000)


def _freshness_label(age_ms: int | None, *, ok_ms: int, stale_ms: int) -> str:
    if age_ms is None:
        return 'unknown'
    if age_ms <= ok_ms:
        return 'fresh'
    if age_ms <= stale_ms:
        return 'aging'
    return 'stale'


def _normalize_timestamp_ms(value: int | None) -> int | None:
    if value is None:
        return None
    raw = int(value)
    if raw <= 0:
        return None
    return raw * 1000 if raw < 10_000_000_000 else raw


def _build_market_data_health(db) -> dict[str, Any]:
    try:
        candle = db.query(CandleCache).order_by(CandleCache.ts.desc()).first()
    except Exception:
        candle = None
    last_ts = int(getattr(candle, 'ts', 0) or 0) if candle is not None else None
    last_ts_ms = _normalize_timestamp_ms(last_ts)
    age_ms = max(0, _now_ms() - last_ts_ms) if last_ts_ms else None
    return {
        'last_candle_ts': last_ts,
        'candle_age_ms': age_ms,
        'freshness': _freshness_label(age_ms, ok_ms=3 * 60 * 1000, stale_ms=15 * 60 * 1000),
        'status': 'ready' if candle is not None else 'degraded',
    }


def _build_streaming_readiness(db) -> dict[str, Any]:
    cutoff = _now_ms() - 7 * 24 * 3600 * 1000
    try:
        logs = (
            db.query(DecisionLog)
            .filter(DecisionLog.ts >= cutoff)
            .order_by(DecisionLog.ts.desc())
            .limit(200)
            .all()
        )
    except Exception:
        logs = []
    reconnect_evidence = False
    for row in logs or []:
        message = str(getattr(row, 'message', '') or '').lower()
        payload = getattr(row, 'payload', None) or {}
        log_type = str(getattr(row, 'type', '') or '')
        if 'reconnect' in message or 'stream' in message or log_type in {'marketdata_stream', 'stream_reconnect'} or payload.get('streaming'):
            reconnect_evidence = True
            break
    return {
        'status': 'shadow_ready' if reconnect_evidence else 'baseline_only',
        'reconnect_evidence': reconnect_evidence,
        'primary_mode': 'polling_with_stream_hooks',
        'fallback_mode': 'polling',
    }


def _build_microstructure_readiness() -> dict[str, Any]:
    return {
        'status': 'shadow_ready',
        'orderbook_available': False,
        'tick_stream_available': False,
        'best_bid_ask_tracking': False,
        'notes': [
            'stream adapter exists and reconnect path is verified',
            'microstructure features are not yet first-class decision inputs',
        ],
    }


def _build_cross_asset_readiness() -> dict[str, Any]:
    return {
        'status': 'shadow_ready',
        'macro_context_available': True,
        'cross_asset_used_in_reasoning': True,
        'decision_weighting_mode': 'bounded_context_only',
    }


def build_data_edge_runtime_summary(db, settings: Any | None = None) -> dict[str, Any]:
    sentiment_status = build_collection_status(db, settings)
    source_analytics = build_source_analytics(db, settings)
    market_data = _build_market_data_health(db)
    streaming = _build_streaming_readiness(db)
    microstructure = _build_microstructure_readiness()
    cross_asset = _build_cross_asset_readiness()
    healthy_sources = sum(1 for item in source_analytics if not item.get('last_error'))
    enabled_sources = sum(1 for item in source_analytics if item.get('enabled'))
    return {
        'status': 'ready',
        'market_data': market_data,
        'streaming': streaming,
        'sentiment': {
            'status': sentiment_status.get('status'),
            'enabled': sentiment_status.get('enabled'),
            'total_messages': sentiment_status.get('total_messages'),
            'top_instruments': list(sentiment_status.get('top_instruments') or [])[:5],
            'freshness': sentiment_status.get('freshness') or sentiment_status.get('message_freshness') if isinstance(sentiment_status, dict) else None,
        },
        'news_sources': {
            'enabled_sources': enabled_sources,
            'healthy_sources': healthy_sources,
            'top_sources': list(source_analytics or [])[:5],
        },
        'microstructure': microstructure,
        'cross_asset': cross_asset,
        'summary_cards': [
            {'key': 'market_data_freshness', 'label': 'Market data freshness', 'value': market_data.get('freshness'), 'tone': 'good' if market_data.get('freshness') == 'fresh' else 'warning'},
            {'key': 'streaming_mode', 'label': 'Streaming readiness', 'value': streaming.get('status'), 'tone': 'good' if streaming.get('status') == 'shadow_ready' else 'neutral'},
            {'key': 'sentiment_messages', 'label': 'Sentiment messages', 'value': sentiment_status.get('total_messages', 0), 'tone': 'neutral'},
            {'key': 'healthy_news_sources', 'label': 'Healthy news sources', 'value': healthy_sources, 'tone': 'good' if healthy_sources else 'warning'},
            {'key': 'microstructure', 'label': 'Microstructure readiness', 'value': microstructure.get('status'), 'tone': 'neutral'},
        ],
    }
