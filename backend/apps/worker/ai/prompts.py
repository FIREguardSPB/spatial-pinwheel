from __future__ import annotations

from apps.worker.ai.relevance import (
    is_dynamic_macro_signal_present,
    select_recent_company_news,
    should_include_fx_context,
    should_include_geopolitical_context,
    should_include_rate_context,
)
from apps.worker.ai.sector_profiles import (
    build_sector_causal_context,
    build_sector_company_context,
    get_sector_profile,
    instrument_code,
    sector_driver_summary,
)
from apps.worker.ai.types import AIContext, InternetContext


PROMPT_PROFILE = "intraday_dynamic_v3_research_scalp"


SYSTEM_PROMPT = """Ты — опытный внутридневной трейдер MOEX.
Горизонт анализа: скальпинг и intraday-импульсы 1–30 минут.
Твоя задача — оценить качество ТЕКУЩЕГО технического сигнала и его экономическую целесообразность после издержек.

Критические правила:
- Не используй как самостоятельную причину SKIP/REJECT статичные факторы, которые не меняются в рамках intraday: давно известный уровень ставки, общий фоновый геополитический риск, абстрактные разговоры о санкциях без свежего катализатора.
- Учитывай макро/геополитику ТОЛЬКО если есть свежий динамический catalyst (новость/решение/эскалация за последние часы-дни), релевантный именно для этой бумаги или её сектора.
- В приоритете: объём, momentum, уровни, VWAP, волатильность, стоимость round-trip, Net RR, ликвидность, сила текущего импульса.
- Отдельно оцени экономику сделки: абсолютный размер SL/TP в RUB и %, стоимость позиции, комиссии, breakeven move, доминирование комиссий над SL.
- Hard blocks от risk/decision engine (например negative Net RR, micro-levels, low volume) уважай всегда.
- Если свежего катализатора нет, пиши нейтрально и не превращай AI в вечного пессимиста.

Правила ответа:
- Отвечай ТОЛЬКО в указанном XML-формате, без лишнего текста до или после.
- <decision> содержит ТОЛЬКО одно из: TAKE, SKIP, REJECT
- <confidence> содержит ТОЛЬКО целое число 0-100
- <reasoning> — краткое обоснование на русском, 2-4 предложения
- <key_factors> — 2-5 ключевых факторов, каждый на новой строке через тег <factor>
"""


def _fmt(val, fmt_spec=".4f", fallback="N/A"):
    if val is None or val == "?":
        return fallback
    try:
        return f"{val:{fmt_spec}}"
    except (TypeError, ValueError):
        return fallback


def _count(ctx: InternetContext, key: str) -> int:
    return ctx.topic_counts.get(key, 0) if ctx.topic_counts else 0


def _describe_vwap_position(last_close: float | None, vwap: float | None) -> str:
    if last_close is None or vwap is None:
        return "N/A"
    if abs(last_close - vwap) / max(abs(last_close), 1e-9) <= 0.0015:
        return "около VWAP"
    return "выше VWAP" if last_close > vwap else "ниже VWAP"


def _build_technical_context(ctx: AIContext) -> str:
    cs = ctx.candles_summary or {}
    metrics = ctx.de_metrics or {}

    last_close = cs.get("last_close")
    atr14 = cs.get("atr14") or metrics.get("atr14")
    entry = float(ctx.entry)
    stop_distance_pct = (abs(float(ctx.entry) - float(ctx.sl)) / entry * 100.0) if entry else None
    atr_pct = (float(atr14) / entry * 100.0) if atr14 and entry else None
    total_cost_bps = None
    fee_bps = metrics.get("costs_fee_bps")
    slip_bps = metrics.get("costs_slippage_bps")
    if fee_bps is not None or slip_bps is not None:
        total_cost_bps = float(fee_bps or 0) + float(slip_bps or 0)

    nearest_level = metrics.get("nearest_level")
    level_clearance_ratio = metrics.get("level_clearance_ratio")
    if nearest_level is None:
        levels_status = "релевантный opposing level не найден"
    else:
        levels_status = f"nearest={_fmt(nearest_level, '.4f')}, clearance={_fmt(level_clearance_ratio, '.2f')}x"

    block_reasons = [r for r in ctx.de_reasons if str(r.get("severity", "")).lower() == "block"]
    warnings = [r for r in ctx.de_reasons if str(r.get("severity", "")).lower() == "warn"]

    adaptive = metrics.get('adaptive_plan') or {}
    lines = [
        "=== ТЕХНИЧЕСКИЙ КОНТЕКСТ (ПРИОРИТЕТ ДЛЯ СКАЛЬПИНГА) ===",
        f"Объём: {_fmt(metrics.get('vol_ratio'), '.2f')}x от среднего",
        f"Momentum: RSI14={_fmt(cs.get('rsi14'), '.1f')}, MACD hist={_fmt(cs.get('macd_hist'))}",
        f"VWAP: {_describe_vwap_position(last_close, metrics.get('vwap'))} | VWAP={_fmt(metrics.get('vwap'))}",
        f"Уровни: {levels_status}",
        (
            f"Комиссии/издержки: fee={_fmt(fee_bps, '.1f', '0')}bps + "
            f"slippage={_fmt(slip_bps, '.1f', '0')}bps = {_fmt(total_cost_bps, '.1f', 'N/A')}bps round-trip"
        ),
        f"Net RR: {_fmt(metrics.get('net_rr'), '.2f')} | Gross RR: {_fmt(metrics.get('gross_rr'), '.2f')}",
        f"Волатильность: ATR={_fmt(atr14)} ({_fmt(atr_pct, '.2f')}%) | стоп={_fmt(stop_distance_pct, '.2f')}% | stop/ATR={_fmt(metrics.get('stop_atr_ratio'), '.2f')}",
    ]
    if adaptive:
        lines.append(
            f"Adaptive plan: regime={adaptive.get('regime')} | strategy={adaptive.get('strategy_name')} | hold={adaptive.get('hold_bars')} bars | threshold={adaptive.get('decision_threshold')} | reentry={adaptive.get('reentry_cooldown_sec')}s | risk x{_fmt(adaptive.get('risk_multiplier'), '.2f')}"
        )
    if block_reasons:
        lines.append("Hard blocks DE: " + "; ".join(f"{r.get('code')}: {r.get('msg')}" for r in block_reasons[:4]))
    elif warnings:
        lines.append("Предупреждения DE: " + "; ".join(f"{r.get('code')}: {r.get('msg')}" for r in warnings[:4]))
    return "\n".join(lines)


def _build_economic_context(ctx: AIContext) -> str:
    metrics = ctx.de_metrics or {}
    flags = metrics.get("economic_warning_flags") or []
    position_value = metrics.get("position_value_rub")
    round_trip_cost_rub = metrics.get("round_trip_cost_rub")
    warnings = []
    if "MICRO_LEVELS_WARNING" in flags:
        warnings.append("MICRO_LEVELS_WARNING: SL слишком близко для intraday-шумов")
    if "COMMISSION_DOMINANCE_WARNING" in flags:
        warnings.append("COMMISSION_DOMINANCE_WARNING: комиссия/проскальзывание слишком велики относительно SL")
    if "LOW_PRICE_WARNING" in flags:
        warnings.append("LOW_PRICE_WARNING: бумага слишком дешёвая для комфортного scalp execution")

    lines = [
        "=== ЭКОНОМИКА СДЕЛКИ (ОБЯЗАТЕЛЬНО УЧИТЫВАТЬ) ===",
        f"Цена бумаги: {_fmt(metrics.get('entry_price_rub'), '.4f')} RUB",
        f"Позиция: qty={_fmt(metrics.get('position_qty'), '.0f')} | value={_fmt(position_value, '.2f')} RUB",
        f"SL: {_fmt(metrics.get('sl_distance_rub'), '.4f')} RUB ({_fmt(metrics.get('sl_distance_pct'), '.4f')}%) | min required={_fmt(metrics.get('min_required_sl_rub'), '.4f')} RUB / {_fmt(metrics.get('min_required_sl_pct'), '.4f')}%",
        f"TP: {_fmt(metrics.get('tp_distance_rub'), '.4f')} RUB ({_fmt(metrics.get('tp_distance_pct'), '.4f')}%) | min required={_fmt(metrics.get('min_required_profit_rub'), '.4f')} RUB / {_fmt(metrics.get('min_required_profit_pct'), '.4f')}%",
        f"Round-trip cost: {_fmt(round_trip_cost_rub, '.4f')} RUB ({_fmt(metrics.get('round_trip_cost_pct'), '.4f')}%)",
        f"Breakeven move: {_fmt(metrics.get('breakeven_move_pct'), '.4f')}% | Expected profit after costs: {_fmt(metrics.get('expected_profit_after_costs_rub'), '.4f')} RUB",
    ]
    if metrics.get("commission_dominance_ratio") is not None:
        lines.append(
            f"Commission dominance: {_fmt((metrics.get('commission_dominance_ratio') or 0) * 100.0, '.1f')}% of stop distance"
        )
    if warnings:
        lines.append("Economic warnings: " + "; ".join(warnings))
    return "\n".join(lines)


def _build_dynamic_context(ctx: AIContext) -> str:
    if not ctx.internet:
        return "=== ДИНАМИЧЕСКИЙ КОНТЕКСТ ===\nНет данных из интернета; принимай решение только по технике, экономике сделки и hard-blocks."

    inet = ctx.internet
    ticker = instrument_code(ctx.instrument_id)
    profile = get_sector_profile(ticker)
    recent_news = select_recent_company_news(inet, hours=24, limit=3)
    if not recent_news and inet.news:
        recent_news = select_recent_company_news(inet, hours=24 * 14, limit=3)
    include_rate = should_include_rate_context(profile.code, inet, horizon="scalp")
    include_geo = should_include_geopolitical_context(profile.code, inet, horizon="scalp")
    include_fx = should_include_fx_context(profile.code, inet, horizon="scalp")
    dynamic_macro = is_dynamic_macro_signal_present(profile.code, inet, horizon="scalp")

    lines = [
        "=== ДИНАМИЧЕСКИЙ КОНТЕКСТ (ТОЛЬКО РЕЛЕВАНТНОЕ ДЛЯ 1–30 МИН) ===",
        f"Сектор: {profile.name_ru} | Профильные драйверы: {sector_driver_summary(ticker)}",
    ]

    if recent_news:
        lines.append("Свежие корпоративные/секторные новости (24ч):")
        for item in recent_news:
            lines.append(f"- [{item.source}] {item.title} (sentiment={item.sentiment:+.2f})")
    else:
        lines.append("Свежих корпоративных/секторных headline'ов за 24ч не найдено.")

    if profile.code in {"oil_gas", "transport"} and inet.macro.brent_usd is not None:
        lines.append(f"Brent: ${inet.macro.brent_usd:.2f} — учитывать как динамический секторный драйвер, а не как общий фон.")

    if include_rate and inet.macro.cbr_key_rate is not None:
        lines.append(f"Свежий rate-катализатор: ставка/риторика ЦБ делают уровень {_fmt(inet.macro.cbr_key_rate, '.2f')}% релевантным именно сейчас.")
    if include_geo:
        lines.append(
            f"Свежий geo/logistics catalyst: война/конфликт={_count(inet, 'война/конфликт')}, санкции={_count(inet, 'санкции')}, нефть/логистика={_count(inet, 'нефть/логистика')}"
        )
    if include_fx and inet.macro.usd_rub is not None:
        lines.append(f"Свежий FX-катализатор: USD/RUB={_fmt(inet.macro.usd_rub, '.3f')} релевантен для сектора прямо сейчас.")

    causal_lines = build_sector_causal_context(ticker, inet, horizon="scalp")
    company_lines = build_sector_company_context(ticker, inet, horizon="scalp")
    if causal_lines:
        lines.extend(["Секторная интерпретация:", *[f"- {line}" for line in causal_lines[:3]]])
    if company_lines:
        lines.extend([f"Контекст для {ticker}:", *[f"- {line}" for line in company_lines[:4]]])

    if not dynamic_macro:
        lines.append(
            "Важно: для этого сигнала нет значимого свежего макро/гео-триггера; не используй статичную ставку или общий военный фон как самостоятельный блокер."
        )

    return "\n".join(lines)




def _build_symbol_profile_context(ctx: AIContext) -> str:
    profile = ctx.symbol_profile or {}
    diagnostics = ctx.symbol_diagnostics or {}
    if not profile and not diagnostics:
        return "=== ПРОФИЛЬ БУМАГИ ===\nПрофиль бумаги не обучен; оценивай сигнал по текущей технике, истории и режиму."
    best_hours = profile.get('best_hours_json') or diagnostics.get('best_hours') or []
    blocked_hours = profile.get('blocked_hours_json') or diagnostics.get('blocked_hours') or []
    lines = ["=== ПРОФИЛЬ БУМАГИ ==="]
    if profile:
        lines.append(
            "Предпочтения: strategies={strategies} | hold={hold}-{hold_max} bars | reentry={reentry}s | risk x{risk} | bias={bias}".format(
                strategies=profile.get('preferred_strategies') or 'N/A',
                hold=profile.get('hold_bars_base') or 'N/A',
                hold_max=profile.get('hold_bars_max') or 'N/A',
                reentry=profile.get('reentry_cooldown_sec') or 'N/A',
                risk=_fmt(profile.get('risk_multiplier'), '.2f'),
                bias=profile.get('session_bias') or 'all',
            )
        )
    if diagnostics:
        perf = diagnostics.get('performance') or {}
        lines.append(
            "Характер: regime={regime} | vol={vol}% | trend={trend} | chop={chop} | win_rate={wr} | avg_win_bars={awb}".format(
                regime=diagnostics.get('regime') or 'unknown',
                vol=_fmt(diagnostics.get('volatility_pct'), '.2f'),
                trend=_fmt(diagnostics.get('trend_strength'), '.2f'),
                chop=_fmt(diagnostics.get('chop_ratio'), '.2f'),
                wr=_fmt(perf.get('win_rate'), '.2f'),
                awb=_fmt(perf.get('avg_win_bars'), '.1f'),
            )
        )
    if best_hours:
        lines.append("Лучшие часы: " + ", ".join(str(h) for h in best_hours[:6]))
    if blocked_hours:
        lines.append("Токсичные часы: " + ", ".join(str(h) for h in blocked_hours[:6]))
    return "\n".join(lines)


def _build_event_regime_context(ctx: AIContext) -> str:
    regime = ctx.event_regime or {}
    if not regime:
        return "=== EVENT / NEWS REGIME ===\nСвежий event-regime не определён; опирайся на технику, экономику сделки и свежие новости по умолчанию."
    lines = [
        "=== EVENT / NEWS REGIME ===",
        "regime={regime} | severity={sev} | direction={direction} | action={action}".format(
            regime=regime.get('regime') or 'unknown',
            sev=_fmt(regime.get('severity'), '.2f'),
            direction=regime.get('direction') or 'neutral',
            action=regime.get('action') or 'observe',
        ),
        "bias: score={score:+} | hold={hold:+} | risk x{risk}".format(
            score=int(regime.get('score_bias') or 0),
            hold=int(regime.get('hold_bias') or 0),
            risk=_fmt(regime.get('risk_bias'), '.2f'),
        ),
    ]
    catalysts = regime.get('catalysts') or []
    if catalysts:
        lines.append("Catalysts: " + "; ".join(str(item) for item in catalysts[:4]))
    if regime.get('narrative'):
        lines.append(f"Narrative: {regime.get('narrative')}")
    return "\n".join(lines)



def _build_geometry_context(ctx: AIContext) -> str:
    geo = ctx.geometry or {}
    if not geo:
        return "=== GEOMETRY OPTIMIZER ===\nГеометрия сигнала не корректировалась; оценивай исходный entry/SL/TP как есть."
    lines = ["=== GEOMETRY OPTIMIZER ==="]
    lines.append(
        "source={source} | phase={phase} | action={action} | min_stop={min_stop}% | target_rr={rr}".format(
            source=geo.get('geometry_source') or 'strategy',
            phase=geo.get('phase') or 'initial',
            action=geo.get('action') or 'none',
            min_stop=_fmt(geo.get('min_stop_pct'), '.3f'),
            rr=_fmt(geo.get('target_rr'), '.2f'),
        )
    )
    if geo.get('original_sl') is not None and geo.get('optimized_sl') is not None:
        lines.append(
            "SL/TP: {osl}->{nsl} / {otp}->{ntp}".format(
                osl=_fmt(geo.get('original_sl'), '.4f'),
                nsl=_fmt(geo.get('optimized_sl'), '.4f'),
                otp=_fmt(geo.get('original_tp'), '.4f'),
                ntp=_fmt(geo.get('optimized_tp'), '.4f'),
            )
        )
    if geo.get('suggested_timeframe'):
        lines.append(f"HTF hint: {geo.get('suggested_timeframe')}")
    notes = geo.get('notes') or []
    if notes:
        lines.append("Notes: " + "; ".join(str(item) for item in notes[:3]))
    return "\n".join(lines)

def _build_historical_context(ctx: AIContext) -> str:
    hist = ctx.historical_context or {}
    patterns = hist.get("patterns") or []
    if not patterns:
        return "=== ИСТОРИЧЕСКИЙ КОНТЕКСТ ===\nПохожих исторических паттернов не найдено; оценивай сигнал по текущей технике и экономике."
    lines = ["=== ИСТОРИЧЕСКИЙ КОНТЕКСТ ==="]
    for item in patterns[:4]:
        outcome = f" | outcome={item.get('outcome')}" if item.get('outcome') else ""
        ref = f" | ref={item.get('reference')}" if item.get('reference') else ""
        lines.append(f"- [{item.get('source')}] {item.get('summary')}{outcome}{ref}")
    return "\n".join(lines)

def build_user_prompt(ctx: AIContext) -> str:
    ticker = instrument_code(ctx.instrument_id)
    profile = get_sector_profile(ticker)
    technical_info = _build_technical_context(ctx)
    economic_info = _build_economic_context(ctx)
    dynamic_info = _build_dynamic_context(ctx)
    historical_info = _build_historical_context(ctx)
    symbol_profile_info = _build_symbol_profile_context(ctx)
    event_regime_info = _build_event_regime_context(ctx)
    geometry_info = _build_geometry_context(ctx)
    reasons_str = ""
    if ctx.de_reasons:
        reasons_str = "\nПричины DE:\n" + "\n".join(
            f"  [{r.get('severity','?').upper()}] {r.get('code','?')}: {r.get('msg','')}"
            for r in ctx.de_reasons[:10]
        )

    prompt = f"""Оцени следующий торговый сигнал для внутридневной торговли (скальпинг 1–30 минут).

=== СИГНАЛ ===
Инструмент:  {ctx.instrument_id}
Сектор:      {profile.name_ru}
Направление: {ctx.side}
Вход:        {ctx.entry:.4f}
Стоп-лосс:   {ctx.sl:.4f}
Тейк-профит: {ctx.tp:.4f}
Размер:      {ctx.size:.0f} шт.
R/R:         {ctx.r:.2f}
Decision Engine score: {ctx.de_score}/100 → {ctx.de_decision}{reasons_str}

{technical_info}

{economic_info}

{dynamic_info}

{historical_info}

{symbol_profile_info}

{event_regime_info}

{geometry_info}

=== ПРАВИЛА ИНТЕРПРЕТАЦИИ ===
1. Сначала оцени силу техники: объём, VWAP, momentum, уровни, Net RR, stop/ATR.
2. Затем проверь экономическую целесообразность: абсолютный SL/TP, комиссии, breakeven move, размер позиции и наличие микро-уровней.
3. Только после этого используй свежие динамические катализаторы. Не наказывай сигнал за константный макрофон.
4. Если техника выглядит приемлемо, но экономика сделки плохая (микро-уровни, комиссии доминируют, прибыль после costs слишком мала) — это повод для SKIP/REJECT.
5. Уважай hard-blocks от DE: low volume, non-positive Net RR, economic filter и другие критические причины нельзя игнорировать.
6. Учитывай характер бумаги: если профиль указывает лучшие/токсичные часы и допустимые playbook, это усиливает или ослабляет уверенность, но не отменяет hard-blocks.
7. Если event/news regime помечен как risk_off_shock или action=de_risk — требуй более сильную технику и не переоценивай слабый импульс.
8. Для сектора \"{profile.name_ru}\" учитывай драйверы: {sector_driver_summary(ticker)}.

=== ТВОЁ РЕШЕНИЕ ===
Ответь СТРОГО в XML-формате:

<decision>TAKE|SKIP|REJECT</decision>
<confidence>0-100</confidence>
<reasoning>Краткое обоснование 2-4 предложения</reasoning>
<key_factors>
<factor>Фактор 1</factor>
<factor>Фактор 2</factor>
<factor>Фактор 3</factor>
</key_factors>"""

    return prompt


def parse_xml_response(raw: str, provider: str, context: AIContext) -> dict:
    import re
    from apps.worker.ai.types import AIDecision

    def extract(tag: str) -> str:
        m = re.search(rf"<{tag}>(.*?)</{tag}>", raw, re.DOTALL | re.IGNORECASE)
        return m.group(1).strip() if m else ""

    raw_decision = extract("decision").upper()
    try:
        decision = AIDecision(raw_decision)
    except ValueError:
        decision = AIDecision.SKIP

    raw_conf = extract("confidence")
    try:
        confidence = max(0, min(100, int(raw_conf)))
    except (ValueError, TypeError):
        confidence = 50

    reasoning = extract("reasoning") or "Нет обоснования"
    factors_raw = re.findall(r"<factor>(.*?)</factor>", raw, re.DOTALL | re.IGNORECASE)
    key_factors = [f.strip() for f in factors_raw if f.strip()]

    return {
        "decision": decision,
        "confidence": confidence,
        "reasoning": reasoning,
        "key_factors": key_factors,
    }