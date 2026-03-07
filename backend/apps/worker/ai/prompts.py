"""
P4-04: Unified prompt templates for all AI providers.

A single template ensures consistency across Claude, Ollama, OpenAI.
"""
from __future__ import annotations

from apps.worker.ai.types import AIContext


SYSTEM_PROMPT = """Ты — опытный трейдер на Московской бирже (MOEX) с 15-летним стажем.
Ты специализируешься на акциях первого эшелона: Сбербанк, Газпром, Лукойл, ВТБ и др.
Ты знаешь особенности российского рынка: влияние санкций, нефтяных цен, ключевой ставки ЦБ.
Твоя задача — оценить торговый сигнал и дать чёткую рекомендацию.

Правила ответа:
- Отвечай ТОЛЬКО в указанном XML-формате, без лишнего текста до или после.
- <decision> содержит ТОЛЬКО одно из: TAKE, SKIP, REJECT
- <confidence> содержит ТОЛЬКО целое число 0-100
- <reasoning> — краткое обоснование на русском, 2-4 предложения
- <key_factors> — 2-5 ключевых факторов, каждый на новой строке через тег <factor>
"""


def build_user_prompt(ctx: AIContext) -> str:
    """Build the analysis request prompt from AIContext."""
    
    # Candle summary — safe formatting for None values
    cs = ctx.candles_summary
    def _fmt(val, fmt_spec=".4f", fallback="N/A"):
        if val is None or val == "?":
            return fallback
        try:
            return f"{val:{fmt_spec}}"
        except (TypeError, ValueError):
            return fallback

    candle_info = (
        f"Последние свечи: цена {_fmt(cs.get('last_close'))}, "
        f"ATR={_fmt(cs.get('atr14'))}, "
        f"EMA50={_fmt(cs.get('ema50'))}, "
        f"RSI14={_fmt(cs.get('rsi14'), '.1f')}, "
        f"MACD hist={_fmt(cs.get('macd_hist'))}"
    ) if cs else "Данные по свечам недоступны"

    # Internet context
    internet_info = ""
    if ctx.internet:
        inet = ctx.internet
        if inet.news:
            top_news = "\n".join(
                f"  • [{n.source}] {n.title} (sentiment={n.sentiment:+.2f})"
                for n in inet.news[:5]
            )
            internet_info += f"\nАктуальные новости по инструменту:\n{top_news}"
        if inet.macro.cbr_key_rate is not None:
            internet_info += (
                f"\nМакро: ЦБ ставка={inet.macro.cbr_key_rate}%, "
                f"USD/RUB={inet.macro.usd_rub}, "
                f"Brent=${inet.macro.brent_usd}"
            )
        internet_info += f"\nОбщий sentiment={inet.sentiment_score:+.2f}, geopolitical_risk={inet.geopolitical_risk:.2f}"

    # DE reasons summary
    reasons_str = ""
    if ctx.de_reasons:
        reasons_str = "\nПричины DE:\n" + "\n".join(
            f"  [{r.get('severity','?').upper()}] {r.get('code','?')}: {r.get('msg','')}"
            for r in ctx.de_reasons[:8]
        )

    prompt = f"""Оцени следующий торговый сигнал.

=== СИГНАЛ ===
Инструмент:  {ctx.instrument_id}
Направление: {ctx.side}
Вход:        {ctx.entry:.4f}
Стоп-лосс:  {ctx.sl:.4f}
Тейк-профит: {ctx.tp:.4f}
R/R:         {ctx.r:.2f}

=== ТЕХНИЧЕСКИЙ АНАЛИЗ ===
{candle_info}
Decision Engine score: {ctx.de_score}/100 → {ctx.de_decision}{reasons_str}

=== РЫНОЧНЫЙ КОНТЕКСТ ==={internet_info if internet_info else " (данные не загружены)"}

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
    """
    Parse XML-structured LLM response.
    Returns dict with: decision, confidence, reasoning, key_factors.
    Tolerant of malformed XML — extracts by simple tag search.
    """
    import re
    from apps.worker.ai.types import AIDecision

    def extract(tag: str) -> str:
        m = re.search(rf"<{tag}>(.*?)</{tag}>", raw, re.DOTALL | re.IGNORECASE)
        return m.group(1).strip() if m else ""

    raw_decision = extract("decision").upper()
    try:
        decision = AIDecision(raw_decision)
    except ValueError:
        # If not parseable, default to SKIP
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
