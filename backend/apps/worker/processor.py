"""
P4-08: SignalProcessor — strategy + DE + AI + save + execution pipeline.

P4-01: AIMode controls how AI merges with DE decision
P4-02: InternetCollector provides news/macro context (parallel with DE)
P4-07: Every AI call is logged to ai_decisions table
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid

from sqlalchemy.orm import Session

from apps.worker.decision_engine.engine import DecisionEngine
from apps.worker.decision_engine.types import Decision, MarketSnapshot
from core.events.bus import bus
from core.execution.paper import PaperExecutionEngine
from core.metrics import record_signal, record_risk_block
from core.risk.manager import RiskManager
from core.storage.models import DecisionLog, Settings
from core.storage.repos import signals as signal_repo
from core.storage.repos.ai_repo import save_ai_decision
from core.strategy.base import BaseStrategy

logger = logging.getLogger(__name__)


def _build_candles_summary(candles: list[dict]) -> dict:
    """Extract key indicators from candle history for AI context."""
    if not candles:
        return {}
    closes = [float(c["close"]) for c in candles]
    highs  = [float(c["high"])  for c in candles]
    lows   = [float(c["low"])   for c in candles]

    # Simple EMA50
    ema50 = None
    if len(closes) >= 50:
        k = 2 / 51
        ema50 = closes[-50]
        for p in closes[-49:]:
            ema50 = p * k + ema50 * (1 - k)

    # ATR14
    atr14 = None
    if len(candles) >= 15:
        trs = []
        for i in range(1, min(15, len(candles))):
            h, l, pc = highs[-i], lows[-i], closes[-i-1]
            trs.append(max(h - l, abs(h - pc), abs(l - pc)))
        atr14 = sum(trs) / len(trs)

    # RSI14
    rsi14 = None
    if len(closes) >= 15:
        deltas = [closes[i] - closes[i-1] for i in range(-14, 0)]
        gains = [max(0, d) for d in deltas]
        losses = [max(0, -d) for d in deltas]
        avg_gain = sum(gains) / 14
        avg_loss = sum(losses) / 14
        if avg_loss > 0:
            rs = avg_gain / avg_loss
            rsi14 = round(100 - 100 / (1 + rs), 1)

    return {
        "last_close": closes[-1] if closes else 0,
        "ema50": round(ema50, 4) if ema50 else None,
        "atr14": round(atr14, 4) if atr14 else None,
        "rsi14": rsi14,
        "macd_hist": None,  # would need full MACD calc
    }


class SignalProcessor:
    def __init__(self, strategy: BaseStrategy, internet_collector=None, aggregator=None):
        self.strategy = strategy
        self._internet = internet_collector  # P4-02: optional InternetCollector
        self._aggregator = aggregator        # P5-06: for correlation candles_map

    async def process(self, ticker: str, candle_history: list[dict], db: Session) -> bool:
        if len(candle_history) < self.strategy.lookback:
            logger.debug("%s: history too short (%d < %d)", ticker, len(candle_history), self.strategy.lookback)
            return False

        # 1. Strategy signal
        sig_data = self.strategy.analyze(ticker, candle_history)
        if not sig_data:
            logger.debug("Strategy analyzed %s: signal=none history_len=%d", ticker, len(candle_history))
            return False

        logger.info("Strategy analyzed %s: signal=found side=%s entry=%.4f history_len=%d",
                     ticker, sig_data["side"], sig_data["entry"], len(candle_history))

        # 2. Risk check (with correlation candles_map if aggregator available)
        risk = RiskManager(db)
        candles_map = None
        if self._aggregator is not None:
            candles_map = {
                t: self._aggregator.get_history(t)
                for t in self._aggregator._history.keys()
            }
            # Ensure current ticker is in map
            if ticker not in candles_map:
                candles_map[ticker] = candle_history
        risk_ok, risk_reason = risk.check_new_signal(sig_data, candles_map=candles_map)
        if not risk_ok:
            logger.info("%s: blocked by risk — %s", ticker, risk_reason)
            record_risk_block(risk_reason)
            return False

        # 3. Position sizing
        sig_data["size"] = float(risk.calculate_position_size(
            entry=sig_data["entry"], sl=sig_data["sl"], lot_size=1,
        ))

        # 4. Check for existing pending signal
        if signal_repo.count_pending_signals(db, ticker) > 0:
            logger.debug("%s: already has pending signal", ticker)
            return False

        # 5. Persist signal
        try:
            signal_orm = signal_repo.create_signal(db, sig_data)
        except Exception as e:
            logger.error("%s: failed to create signal — %s", ticker, e, exc_info=True)
            return False

        # 6. Load settings
        settings = db.query(Settings).first()
        if not settings:
            logger.warning("%s: no settings row — skipping DE/AI", ticker)
            return True

        # 7. P4-08: Run DE and internet collection in parallel
        snapshot = MarketSnapshot(candles=candle_history, last_price=candle_history[-1]["close"])
        de = DecisionEngine(settings)

        if self._internet:
            evaluation, internet_ctx = await asyncio.gather(
                asyncio.to_thread(de.evaluate, signal_orm, snapshot),
                self._internet.get_context(ticker),
                return_exceptions=False,
            )
        else:
            evaluation = de.evaluate(signal_orm, snapshot)
            internet_ctx = None

        # 8. P4-08: AI analysis
        from apps.worker.ai.types import AIMode
        ai_mode_str = getattr(settings, "ai_mode", "off") or "off"
        try:
            ai_mode = AIMode(ai_mode_str)
        except ValueError:
            ai_mode = AIMode.OFF

        ai_result = None
        final_decision = evaluation.decision.value

        if ai_mode != AIMode.OFF:
            from apps.worker.ai.types import AIContext
            from apps.worker.ai.router import AIProviderRouter

            de_reasons = [r.model_dump() for r in evaluation.reasons]
            ai_ctx = AIContext(
                signal_id=signal_orm.id,
                instrument_id=ticker,
                side=sig_data["side"],
                entry=sig_data["entry"],
                sl=sig_data["sl"],
                tp=sig_data["tp"],
                r=sig_data["r"],
                de_score=evaluation.score,
                de_decision=evaluation.decision.value,
                de_reasons=de_reasons,
                de_metrics=dict(evaluation.metrics),
                candles_summary=_build_candles_summary(candle_history),
                internet=internet_ctx,
            )

            router = AIProviderRouter()
            ai_result = await router.analyze(ai_ctx, ai_mode)

            # Merge decisions per ai_mode
            ai_min_conf = int(getattr(settings, "ai_min_confidence", 70) or 70)
            final_decision, merge_reason = router.merge_decisions(
                de_decision=evaluation.decision.value,
                de_score=evaluation.score,
                ai_result=ai_result,
                ai_mode=ai_mode,
                ai_min_confidence=ai_min_conf,
            )
            logger.info("%s: merge=%s [%s]", ticker, final_decision, merge_reason)

            # P4-07: Log AI decision
            try:
                save_ai_decision(
                    db=db,
                    signal_id=signal_orm.id,
                    instrument_id=ticker,
                    ai_result=ai_result,
                    final_decision=final_decision,
                    de_score=evaluation.score,
                )
            except Exception as e:
                logger.warning("Failed to save AI decision log: %s", e)

        # 9. Save decision metadata
        meta = dict(signal_orm.meta or {})
        meta["decision"] = evaluation.model_dump(mode="json")
        if ai_result:
            meta["ai_decision"] = {
                "provider": ai_result.provider,
                "decision": ai_result.decision.value,
                "confidence": ai_result.confidence,
                "reasoning": ai_result.reasoning,
                "key_factors": ai_result.key_factors,
            }
        meta["final_decision"] = final_decision
        signal_orm.meta = meta
        db.commit()

        # 10. Decision log
        db.add(DecisionLog(
            id=f"log_{uuid.uuid4().hex[:8]}",
            ts=int(time.time() * 1000),
            type="decision_engine",
            message=f"{final_decision} {ticker} de_score={evaluation.score}",
            payload={"de": evaluation.model_dump(mode="json"), "ai_mode": ai_mode_str},
        ))
        db.commit()

        # 11. Metrics
        record_signal(
            decision=final_decision,
            instrument=ticker,
            side=sig_data["side"],
            score=evaluation.score,
        )

        # 12. SSE
        await bus.publish("signal_updated", {
            "id": signal_orm.id, "status": signal_orm.status, "meta": meta,
        })
        logger.info("%s: final=%s (DE=%s score=%d)", ticker, final_decision, evaluation.decision.value, evaluation.score)

        # 12b. Telegram notification (P6-04/P2-01)
        try:
            from core.notifications.telegram import TelegramNotifier as _Tg
            _tg = _Tg.from_settings(settings)
            if _tg:
                _sig_info = {
                    "id": signal_orm.id,
                    "instrument_id": ticker,
                    "side": sig_data["side"],
                    "entry": float(sig_data.get("entry", 0)),
                    "sl": float(sig_data.get("sl", 0)),
                    "tp": float(sig_data.get("tp", 0)),
                    "r": float(sig_data.get("r", 0)),
                    "score": evaluation.score,
                    "decision": final_decision,
                }
                import asyncio as _aio
                _aio.create_task(_tg.send_signal_created(_sig_info))
        except Exception:
            pass  # Telegram must never block trading

        # 13. Auto-execution based on final_decision
        trade_mode = settings.trade_mode or "review"
        if final_decision == "TAKE":
            if trade_mode == "auto_paper":
                signal_repo.update_signal_status(db, signal_orm.id, "approved")
                await PaperExecutionEngine(db).execute_approved_signal(signal_orm.id)
            elif trade_mode == "auto_live":
                from core.config import settings as cfg
                if cfg.TBANK_TOKEN:
                    from core.execution.tbank import TBankExecutionEngine
                    engine = TBankExecutionEngine(db, cfg.TBANK_TOKEN, cfg.TBANK_ACCOUNT_ID, cfg.TBANK_SANDBOX)
                    signal_repo.update_signal_status(db, signal_orm.id, "approved")
                    await engine.execute_approved_signal(signal_orm.id)

        return True
