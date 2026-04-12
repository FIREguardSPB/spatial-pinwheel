from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_contextual_sentiment_detects_war_as_negative():
    from apps.worker.ai.internet.sentiment import score_text

    score = score_text("Ukraine and Russia at War as oil supply fears mount")
    assert score < -0.4


def test_contextual_sentiment_detects_sanctions_easing_as_positive():
    from apps.worker.ai.internet.sentiment import score_text

    score = score_text("US may ease sanctions on Russian oil exports")
    assert score > 0.1


def test_prompt_focuses_on_dynamic_context_for_oil_company():
    from apps.worker.ai.prompts import build_user_prompt
    from apps.worker.ai.types import AIContext, InternetContext, MacroData, NewsItem

    internet = InternetContext(
        ticker="ROSN",
        news=[
            NewsItem(
                title="Iran tells world to get ready for oil at $200 a barrel",
                source="Reuters Energy",
                url="https://example.com/1",
                published_at="2026-03-15T10:00:00+00:00",
                sentiment=-0.65,
            ),
            NewsItem(
                title="Drone attack raises risks for Black Sea energy logistics",
                source="Reuters World",
                url="https://example.com/2",
                published_at="2026-03-15T09:00:00+00:00",
                sentiment=-0.75,
            ),
        ],
        sentiment_score=-0.52,
        macro=MacroData(brent_usd=111.4, usd_rub=79.068),
        geopolitical_risk=1.0,
        topics=["война/конфликт", "нефть/логистика", "санкции"],
        topic_counts={"война/конфликт": 16, "нефть/логистика": 8, "санкции": 3, "ставки/инфляция": 0},
        narrative_summary=[],
    )

    ctx = AIContext(
        signal_id="sig_rosn",
        instrument_id="TQBR:ROSN",
        side="BUY",
        entry=540.0,
        sl=535.0,
        tp=550.0,
        size=1200,
        r=2.0,
        de_score=62,
        de_decision="SKIP",
        de_reasons=[],
        de_metrics={"vol_ratio": 1.8, "vwap": 538.0, "net_rr": 1.35, "gross_rr": 1.56, "costs_fee_bps": 3, "costs_slippage_bps": 5},
        candles_summary={"last_close": 540.0, "ema50": 534.0, "atr14": 4.2, "rsi14": 58.4, "macd_hist": 0.12},
        internet=internet,
    )

    prompt = build_user_prompt(ctx)

    assert "ТЕХНИЧЕСКИЙ КОНТЕКСТ" in prompt
    assert "Brent: $111.40" in prompt
    assert "Свежие корпоративные/секторные новости (24ч)" in prompt
    assert "не используй статичную ставку" not in prompt
    assert "Контекст для ROSN" in prompt
    assert "ЭКОНОМИКА СДЕЛКИ" in prompt
    assert "Round-trip cost" in prompt


def test_prompt_omits_static_rate_and_geo_for_tech_without_fresh_catalyst():
    from apps.worker.ai.prompts import build_user_prompt
    from apps.worker.ai.types import AIContext, InternetContext, MacroData, NewsItem

    internet = InternetContext(
        ticker="YNDX",
        news=[
            NewsItem(
                title="Yandex launches updated subscription bundle for city services",
                source="Reuters Markets",
                url="https://example.com/tech1",
                published_at="2026-03-15T10:00:00+00:00",
                sentiment=0.18,
            ),
        ],
        sentiment_score=0.12,
        macro=MacroData(cbr_key_rate=16.0, usd_rub=96.4, brent_usd=111.4),
        geopolitical_risk=0.72,
        topics=["война/конфликт", "ставки/инфляция"],
        topic_counts={"война/конфликт": 7, "нефть/логистика": 3, "санкции": 2, "ставки/инфляция": 4},
        narrative_summary=[],
    )

    ctx = AIContext(
        signal_id="sig_yndx",
        instrument_id="TQBR:YNDX",
        side="BUY",
        entry=4200.0,
        sl=4140.0,
        tp=4320.0,
        size=10,
        r=2.0,
        de_score=66,
        de_decision="TAKE",
        de_reasons=[],
        de_metrics={"vol_ratio": 1.4, "vwap": 4194.0, "net_rr": 1.62, "gross_rr": 1.8, "costs_fee_bps": 3, "costs_slippage_bps": 5},
        candles_summary={"last_close": 4200.0, "ema50": 4155.0, "atr14": 55.0, "rsi14": 57.4, "macd_hist": 0.22},
        internet=internet,
    )

    prompt = build_user_prompt(ctx)

    assert "Сектор: технологии и интернет" in prompt
    assert "ставка 16.00%" not in prompt
    assert "война/конфликт=7" not in prompt
    assert "нет значимого свежего макро/гео-триггера" in prompt.lower()
    assert "не используй статичную ставку" in prompt


def test_sector_company_context_for_real_estate_ignores_static_rate_without_event():
    from apps.worker.ai.sector_profiles import build_sector_company_context
    from apps.worker.ai.types import InternetContext, MacroData, NewsItem

    inet = InternetContext(
        ticker="SMLT",
        news=[
            NewsItem(
                title="SMLT opens new residential phase in Moscow",
                source="RBC",
                url="https://example.com/smlt",
                published_at="2026-03-15T11:00:00+00:00",
                sentiment=0.08,
            )
        ],
        macro=MacroData(cbr_key_rate=16.0, usd_rub=92.5),
        geopolitical_risk=0.5,
        topic_counts={"война/конфликт": 0, "нефть/логистика": 0, "санкции": 0, "ставки/инфляция": 1},
    )

    lines = build_sector_company_context("SMLT", inet, horizon="scalp")
    joined = " ".join(lines)

    assert "16.00%" not in joined
    assert "свежем rate-headline" in joined


def test_sector_company_context_includes_rate_when_fresh_rate_event_exists():
    from apps.worker.ai.sector_profiles import build_sector_company_context
    from apps.worker.ai.types import InternetContext, MacroData, NewsItem

    inet = InternetContext(
        ticker="SMLT",
        news=[
            NewsItem(
                title="ЦБ дал сигнал на длительное сохранение высокой ставки после заседания",
                source="Интерфакс",
                url="https://example.com/cbr",
                published_at="2026-03-15T11:00:00+00:00",
                sentiment=-0.22,
            )
        ],
        macro=MacroData(cbr_key_rate=16.0, usd_rub=92.5),
        geopolitical_risk=0.5,
        topic_counts={"война/конфликт": 0, "нефть/логистика": 0, "санкции": 0, "ставки/инфляция": 1},
    )

    lines = build_sector_company_context("SMLT", inet, horizon="scalp")
    joined = " ".join(lines)

    assert "16.00%" in joined
    assert "свежий rate-катализатор" in joined


def test_sector_keywords_cover_retail_names():
    from apps.worker.ai.internet.news import _keywords_for

    keywords = _keywords_for("OZON")
    assert "маркетплейс" in keywords
    assert "ритейл" in keywords
    assert "consumer" in keywords
