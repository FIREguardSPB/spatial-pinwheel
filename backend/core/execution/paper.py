"""
PaperExecutionEngine — бумажное исполнение ордеров.

P2-02: RiskManager.check_new_signal() перед исполнением
P2-04: Размер позиции уже рассчитан воркером, normalize_qty применяется к лотам
"""
import logging
import time
import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from core.events.bus import bus
from core.risk.manager import RiskManager
from core.storage.models import DecisionLog, Order, Position, Signal, Trade

logger = logging.getLogger(__name__)


class PaperExecutionEngine:
    def __init__(self, db: Session):
        self.db = db
        self.risk = RiskManager(db)

    async def execute_approved_signal(self, signal_id: str) -> None:
        signal = self.db.query(Signal).filter(Signal.id == signal_id).first()
        if not signal or signal.status != "approved":
            logger.warning("execute_approved_signal: signal %s not found or not approved", signal_id)
            return

        # P2-02: двойная проверка риска перед реальным исполнением
        risk_ok, risk_reason = self.risk.check_new_signal(signal)
        if not risk_ok:
            logger.warning("Paper execution blocked by risk: %s", risk_reason)
            signal.status = "rejected"
            self.db.commit()
            await bus.publish("signal_updated", {"id": signal_id, "status": "rejected", "reason": risk_reason})
            return

        # P2-04: normalize qty (сигнал уже содержит рассчитанный size)
        qty = self.risk.normalize_qty(float(signal.size), lot_size=1)

        # Order
        order = Order(
            order_id=f"ord_{uuid.uuid4().hex[:8]}",
            instrument_id=signal.instrument_id,
            ts=int(time.time() * 1000),
            side=signal.side,
            type="MARKET",
            price=signal.entry,
            qty=qty,
            filled_qty=qty,
            status="FILLED",
            related_signal_id=signal.id,
        )
        self.db.add(order)

        # Trade
        trade = Trade(
            trade_id=f"trd_{uuid.uuid4().hex[:8]}",
            instrument_id=signal.instrument_id,
            ts=int(time.time() * 1000),
            side=signal.side,
            price=signal.entry,
            qty=qty,
            order_id=order.order_id,
        )
        self.db.add(trade)

        # Position — обновить или создать
        position = (
            self.db.query(Position)
            .filter(Position.instrument_id == signal.instrument_id)
            .first()
        )
        if not position:
            position = Position(
                instrument_id=signal.instrument_id,
                side=signal.side,
                qty=qty,
                avg_price=signal.entry,
                sl=signal.sl,
                tp=signal.tp,
                unrealized_pnl=Decimal("0"),
                realized_pnl=Decimal("0"),
                opened_ts=int(time.time() * 1000),
            )
            self.db.add(position)
        else:
            if position.side == signal.side and float(position.qty) > 0:
                # Averaging
                total_qty = float(position.qty) + qty
                total_cost = float(position.qty) * float(position.avg_price) + qty * float(signal.entry)
                position.avg_price = Decimal(str(round(total_cost / total_qty, 6)))
                position.qty = Decimal(str(total_qty))
                position.sl = signal.sl
                position.tp = signal.tp
            elif float(position.qty) == 0:
                # Переоткрыть позицию
                position.side = signal.side
                position.qty = Decimal(str(qty))
                position.avg_price = signal.entry
                position.sl = signal.sl
                position.tp = signal.tp
                position.unrealized_pnl = Decimal("0")
                position.opened_ts = int(time.time() * 1000)

        signal.status = "executed"
        self.db.commit()

        # Лог
        self.db.add(DecisionLog(
            id=f"log_{uuid.uuid4().hex[:8]}",
            ts=int(time.time() * 1000),
            type="trade_filled",
            message=f"Filled {qty} @ {float(signal.entry):.4f} [{signal.side}] {signal.instrument_id}",
            payload={"trade_id": trade.trade_id, "qty": qty, "price": float(signal.entry)},
        ))
        self.db.commit()

        logger.info("Executed: %s %d @ %.4f sl=%.4f tp=%.4f",
                    signal.instrument_id, qty, float(signal.entry),
                    float(signal.sl), float(signal.tp))

        # P2-08: AccountSnapshot after every trade (equity curve)
        try:
            from core.storage.models import AccountSnapshot, Settings
            from decimal import Decimal as _D
            s = self.db.query(Settings).first()
            balance = float(getattr(s, 'account_balance', 100_000) or 100_000)
            open_pnl = sum(
                float(p.unrealized_pnl or 0)
                for p in self.db.query(Position).filter(Position.qty > 0).all()
            )
            self.db.add(AccountSnapshot(
                ts=int(time.time() * 1000),
                balance=_D(str(round(balance, 4))),
                equity=_D(str(round(balance + open_pnl, 4))),
                day_pnl=_D(str(round(open_pnl, 4))),  # closest column
            ))
            self.db.commit()
        except Exception as _snap_err:
            logger.debug("AccountSnapshot save failed: %s", _snap_err)

        # SSE
        await bus.publish("orders_updated",   {"order_id": order.order_id})
        await bus.publish("trade_filled",     {"trade_id": trade.trade_id})
        await bus.publish("positions_updated", {"instrument_id": position.instrument_id})
        await bus.publish("signal_updated",   {"id": signal.id, "status": "executed"})
