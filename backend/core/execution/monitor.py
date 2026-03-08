"""
P2-01: PositionMonitor — автоматическое закрытие позиций по SL / TP / Time Stop.

Вызывается из Worker на каждом тике:
    await monitor.on_tick(ticker, current_price, current_bar_index)

При срабатывании SL/TP:
  - Position.qty = 0, realized_pnl обновлён
  - Создаётся закрывающий Trade
  - Публикуется SSE-событие positions_updated
  - Лог в decision_log
"""

import logging
import time
import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from core.events.bus import bus
from core.storage.models import DecisionLog, Position, Trade
from core.config import get_token, settings as config

logger = logging.getLogger(__name__)


class PositionMonitor:
    def __init__(self, db: Session):
        self.db = db
        # bar_counter[instrument_id] = количество баров с момента открытия позиции
        self._bar_counters: dict[str, int] = {}

    async def on_tick(
        self,
        instrument_id: str,
        current_price: float,
        time_stop_bars: int = 0,
    ) -> None:
        """
        Проверяет все открытые позиции по инструменту.
        current_price — последняя цена (close текущей свечи).
        time_stop_bars — закрыть позицию если она открыта дольше N баров (0 = выключено).
        """
        position = (
            self.db.query(Position)
            .filter(Position.instrument_id == instrument_id, Position.qty > 0)
            .first()
        )
        if not position:
            self._bar_counters.pop(instrument_id, None)
            return

        # Обновить unrealized_pnl
        sign = 1 if position.side == "BUY" else -1
        pnl = sign * float(position.qty) * (current_price - float(position.avg_price))
        position.unrealized_pnl = round(pnl, 4)

        # Счётчик баров с момента открытия
        self._bar_counters[instrument_id] = self._bar_counters.get(instrument_id, 0) + 1
        bars_held = self._bar_counters[instrument_id]

        close_reason = None

        # ── SL Check ──────────────────────────────────────────────────────────
        if position.sl is not None:
            sl = float(position.sl)
            if position.side == "BUY" and current_price <= sl:
                close_reason = "SL"
            elif position.side == "SELL" and current_price >= sl:
                close_reason = "SL"

        # ── TP Check ──────────────────────────────────────────────────────────
        if close_reason is None and position.tp is not None:
            tp = float(position.tp)
            if position.side == "BUY" and current_price >= tp:
                close_reason = "TP"
            elif position.side == "SELL" and current_price <= tp:
                close_reason = "TP"

        # ── Time Stop ─────────────────────────────────────────────────────────
        if close_reason is None and time_stop_bars > 0 and bars_held >= time_stop_bars:
            close_reason = f"TIME_STOP ({bars_held} bars)"

        if close_reason:
            await self._close_position(position, current_price, close_reason)
        else:
            self.db.commit()

    async def close_for_session_end(self, instrument_id: str, current_price: float) -> None:
        """P2-07: Принудительное закрытие перед концом торговой сессии."""
        position = (
            self.db.query(Position)
            .filter(Position.instrument_id == instrument_id, Position.qty > 0)
            .first()
        )
        if position:
            await self._close_position(position, current_price, "SESSION_END")

    async def _close_position(
        self, position: Position, close_price: float, reason: str
    ) -> None:
        """Закрывает позицию: обновляет PnL, создаёт Trade, очищает qty."""
        if config.BROKER_PROVIDER == "tbank":
            try:
                from core.storage.models import Settings as LiveSettings
                live_settings = self.db.query(LiveSettings).first()
                if live_settings and getattr(live_settings, "trade_mode", "review") == "auto_live":
                    from core.execution.tbank import TBankExecutionEngine
                    await TBankExecutionEngine(self.db, token=get_token("TBANK_TOKEN") or config.TBANK_TOKEN, account_id=get_token("TBANK_ACCOUNT_ID") or config.TBANK_ACCOUNT_ID, sandbox=config.TBANK_SANDBOX).close_position(position.instrument_id, close_price, reason=reason)
                    return
            except Exception as exc:
                logger.error("Live close failed for %s: %s", position.instrument_id, exc)
                raise

        sign = 1 if position.side == "BUY" else -1
        realized = sign * float(position.qty) * (close_price - float(position.avg_price))
        position.realized_pnl = float(position.realized_pnl or 0) + round(realized, 4)
        position.unrealized_pnl = 0.0

        closed_qty = position.qty
        instrument_id = position.instrument_id

        # Закрывающий Trade
        close_side = "SELL" if position.side == "BUY" else "BUY"
        trade = Trade(
            trade_id=f"trd_{uuid.uuid4().hex[:8]}",
            instrument_id=instrument_id,
            ts=int(time.time() * 1000),
            side=close_side,
            price=Decimal(str(close_price)),
            qty=closed_qty,
            order_id=f"ord_close_{uuid.uuid4().hex[:8]}",
        )
        self.db.add(trade)

        # Закрыть позицию (qty = 0)
        position.qty = Decimal("0")

        # P6-04: Telegram notification on SL/TP/TimeStop
        try:
            from core.notifications.telegram import TelegramNotifier as _Tg
            _notifier = _Tg.from_settings(self.db)
            if _notifier:
                _trade_info = {
                    "instrument_id": instrument_id,
                    "side": close_side,
                    "price": close_price,
                    "qty": int(closed_qty),
                    "realized_pnl": round(realized, 2),
                    "reason": reason,
                }
                import asyncio as _aio
                if reason == "SL":
                    _aio.create_task(_notifier.send_sl_hit(_trade_info))
                elif reason == "TP":
                    _aio.create_task(_notifier.send_tp_hit(_trade_info))
                else:
                    _aio.create_task(_notifier.send_trade_executed(_trade_info))
        except Exception:
            pass  # Telegram errors must not disrupt trading

        # Лог
        log = DecisionLog(
            id=f"log_{uuid.uuid4().hex[:8]}",
            ts=int(time.time() * 1000),
            type="position_closed",
            message=f"Closed {instrument_id} @ {close_price:.4f} [{reason}] pnl={realized:.2f}",
            payload={
                "instrument_id": instrument_id,
                "reason": reason,
                "close_price": close_price,
                "realized_pnl": round(realized, 4),
            },
        )
        self.db.add(log)
        self.db.commit()

        # P4-07: Update AI decision outcome after position close
        try:
            outcome = "profit" if realized > 0 else ("stopped" if "TIME_STOP" in reason or "SESSION_END" in reason else "loss")
            from core.storage.repos.ai_repo import update_outcome
            # Find signals for this instrument closed recently
            from core.storage.models import Signal
            recent_signals = (
                self.db.query(Signal)
                .filter(Signal.instrument_id == instrument_id, Signal.status == "executed")
                .order_by(Signal.updated_ts.desc())
                .limit(1)
                .all()
            )
            for sig in recent_signals:
                update_outcome(self.db, sig.id, outcome)
        except Exception as e:
            logging.getLogger(__name__).debug("AI outcome update failed: %s", e)

        # Сбросить счётчик баров
        self._bar_counters.pop(instrument_id, None)

        logger.info(
            "Position closed: %s reason=%s price=%.4f pnl=%.2f",
            instrument_id, reason, close_price, realized,
        )

        # SSE-события
        await bus.publish("positions_updated", {"instrument_id": instrument_id})
        await bus.publish(
            "trade_filled",
            {"trade_id": trade.trade_id, "reason": reason, "pnl": round(realized, 4)},
        )
