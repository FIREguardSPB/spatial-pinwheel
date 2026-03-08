"""
Live execution engine for T-Bank Invest API.

This module performs real broker operations:
- validates account and instrument availability,
- sends market orders,
- waits for terminal order state,
- writes broker-backed orders/trades/positions to the local DB,
- syncs portfolio snapshots after each execution.
"""
from __future__ import annotations

import logging
import time
import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from apps.broker.tbank.adapter import (
    TBankApiError,
    TBankGrpcAdapter,
    TBankOrderRejected,
    money_to_decimal,
)
from core.config import settings as config
from core.events.bus import bus
from core.risk.manager import RiskManager
from core.storage.models import AccountSnapshot, DecisionLog, Order, Position, Signal, Trade

logger = logging.getLogger(__name__)


class TBankExecutionEngine:
    def __init__(self, db: Session, token: str, account_id: str, sandbox: bool = False):
        self.db = db
        self.token = token
        self.account_id = account_id
        self.sandbox = sandbox
        self.risk = RiskManager(db)
        self.adapter = TBankGrpcAdapter(token=token, account_id=account_id, sandbox=sandbox)

    async def execute_approved_signal(self, signal_id: str) -> None:
        signal = self.db.query(Signal).filter(Signal.id == signal_id).first()
        if not signal or signal.status != "approved":
            logger.warning("live execute_approved_signal: signal %s not found or not approved", signal_id)
            return

        risk_ok, risk_reason = self.risk.check_new_signal(signal)
        if not risk_ok:
            signal.status = "rejected"
            self.db.commit()
            await bus.publish("signal_updated", {"id": signal_id, "status": "rejected", "reason": risk_reason})
            raise TBankApiError(f"Signal blocked by risk manager: {risk_reason}")

        details = await self.adapter.ensure_instrument_tradable(signal.instrument_id, signal.side)
        if signal.side == "SELL" and not details.get("short_enabled"):
            existing = self.db.query(Position).filter(
                Position.instrument_id == signal.instrument_id,
                Position.qty > 0,
            ).first()
            if not existing:
                raise TBankApiError(
                    f"Instrument {signal.instrument_id} does not allow short selling and there is no open long position to close"
                )

        lots = self.adapter.normalize_signal_qty_to_lots(Decimal(str(signal.size)), details.get("lot", 1))
        client_order_id = str(uuid.uuid4())
        broker_response = await self.adapter.post_market_order(
            instrument_id=details["uid"],
            quantity_lots=lots,
            direction=signal.side,
            order_id=client_order_id,
            account_id=self.account_id,
        )
        broker_order_id = broker_response.get("orderId") or client_order_id
        order_state = await self.adapter.wait_for_terminal_order_state(
            order_id=broker_order_id,
            timeout_sec=config.TBANK_ORDER_TIMEOUT_SEC,
            poll_interval_sec=config.TBANK_ORDER_POLL_INTERVAL_SEC,
            account_id=self.account_id,
        )

        await self._persist_executed_signal(signal=signal, details=details, requested_lots=lots, state=order_state)
        await self._sync_account_snapshot()

    async def close_position(self, instrument_id: str, close_price: float, reason: str = "EXIT") -> None:
        position = (
            self.db.query(Position)
            .filter(Position.instrument_id == instrument_id, Position.qty > 0)
            .first()
        )
        if not position:
            logger.info("close_position skipped: no open local position for %s", instrument_id)
            return

        details = await self.adapter.ensure_instrument_tradable(
            instrument_id,
            "SELL" if position.side == "BUY" else "BUY",
        )
        qty_units = Decimal(str(position.qty))
        lots = self.adapter.normalize_signal_qty_to_lots(qty_units, details.get("lot", 1))
        close_side = "SELL" if position.side == "BUY" else "BUY"
        client_order_id = str(uuid.uuid4())
        broker_response = await self.adapter.post_market_order(
            instrument_id=details["uid"],
            quantity_lots=lots,
            direction=close_side,
            order_id=client_order_id,
            account_id=self.account_id,
        )
        broker_order_id = broker_response.get("orderId") or client_order_id
        order_state = await self.adapter.wait_for_terminal_order_state(
            order_id=broker_order_id,
            timeout_sec=config.TBANK_ORDER_TIMEOUT_SEC,
            poll_interval_sec=config.TBANK_ORDER_POLL_INTERVAL_SEC,
            account_id=self.account_id,
        )

        status = order_state.get("executionReportStatus")
        if status == "EXECUTION_REPORT_STATUS_REJECTED":
            raise TBankOrderRejected(order_state.get("message") or f"Close order {client_order_id} rejected")
        if status != "EXECUTION_REPORT_STATUS_FILL":
            raise TBankApiError(f"Close order {client_order_id} finished with unexpected status {status}")

        executed_price = money_to_decimal(order_state.get("executedOrderPrice"))
        if executed_price <= 0:
            executed_price = Decimal(str(close_price))
        sign = 1 if position.side == "BUY" else -1
        realized = sign * float(position.qty) * (float(executed_price) - float(position.avg_price))

        trade = Trade(
            trade_id=f"trd_{uuid.uuid4().hex[:8]}",
            instrument_id=instrument_id,
            broker_id=details.get("uid"),
            ts=int(time.time() * 1000),
            side=close_side,
            price=executed_price,
            qty=Decimal(str(position.qty)),
            order_id=broker_order_id,
        )
        self.db.add(trade)

        order = Order(
            order_id=broker_order_id,
            instrument_id=instrument_id,
            broker_id=details.get("uid"),
            ts=int(time.time() * 1000),
            side=close_side,
            type="MARKET",
            price=executed_price,
            qty=Decimal(str(position.qty)),
            filled_qty=Decimal(str(position.qty)),
            status="FILLED",
            related_signal_id=None,
        )
        self.db.merge(order)

        position.realized_pnl = Decimal(str(float(position.realized_pnl or 0) + round(realized, 4)))
        position.unrealized_pnl = Decimal("0")
        position.qty = Decimal("0")
        position.updated_ts = int(time.time() * 1000)

        self.db.add(DecisionLog(
            id=f"log_{uuid.uuid4().hex[:8]}",
            ts=int(time.time() * 1000),
            type="position_closed",
            message=f"Live close {instrument_id} @ {float(executed_price):.4f} [{reason}] pnl={realized:.2f}",
            payload={
                "instrument_id": instrument_id,
                "reason": reason,
                "close_price": float(executed_price),
                "realized_pnl": round(realized, 4),
                "broker_order_id": broker_order_id,
            },
        ))
        self.db.commit()

        await self._sync_account_snapshot()
        await bus.publish("positions_updated", {"instrument_id": instrument_id})
        await bus.publish("trade_filled", {"trade_id": trade.trade_id, "reason": reason, "pnl": round(realized, 4)})

    async def get_portfolio(self) -> dict:
        portfolio = await self.adapter.get_portfolio(self.account_id)
        return {
            "total_amount_portfolio": float(money_to_decimal(portfolio.get("totalAmountPortfolio"))),
            "total_amount_currencies": float(money_to_decimal(portfolio.get("totalAmountCurrencies"))),
            "total_amount_shares": float(money_to_decimal(portfolio.get("totalAmountShares"))),
            "expected_yield": float(money_to_decimal(portfolio.get("expectedYield"))),
        }

    async def _persist_executed_signal(
        self,
        *,
        signal: Signal,
        details: dict,
        requested_lots: int,
        state: dict,
    ) -> None:
        status = state.get("executionReportStatus")
        message = state.get("message") or ""
        if status == "EXECUTION_REPORT_STATUS_REJECTED":
            signal.status = "rejected"
            self.db.commit()
            await bus.publish("signal_updated", {"id": signal.id, "status": "rejected", "reason": message})
            raise TBankOrderRejected(message or f"Order {state.get('orderId')} rejected")
        if status != "EXECUTION_REPORT_STATUS_FILL":
            raise TBankApiError(
                f"Broker order {state.get('orderId')} completed with unexpected status {status}"
            )

        lots_executed = int(state.get("lotsExecuted") or requested_lots)
        qty_units = Decimal(lots_executed * int(details.get("lot", 1)))
        executed_price = money_to_decimal(state.get("executedOrderPrice"))
        avg_price = money_to_decimal(state.get("averagePositionPrice"))
        if executed_price <= 0:
            executed_price = avg_price if avg_price > 0 else Decimal(str(signal.entry))

        order_id = state.get("orderId")
        order = Order(
            order_id=order_id,
            instrument_id=signal.instrument_id,
            broker_id=details.get("uid"),
            ts=int(time.time() * 1000),
            side=signal.side,
            type="MARKET",
            price=executed_price,
            qty=qty_units,
            filled_qty=qty_units,
            status="FILLED",
            related_signal_id=signal.id,
        )
        self.db.merge(order)

        trades = state.get("stages") or []
        if trades:
            for stage in trades:
                trade_qty_units = Decimal(str(int(stage.get("quantity") or lots_executed) * int(details.get("lot", 1))))
                trade_price = money_to_decimal(stage.get("price")) or executed_price
                trade = Trade(
                    trade_id=stage.get("tradeId") or f"trd_{uuid.uuid4().hex[:8]}",
                    instrument_id=signal.instrument_id,
                    broker_id=details.get("uid"),
                    ts=int(time.time() * 1000),
                    side=signal.side,
                    price=trade_price,
                    qty=trade_qty_units,
                    order_id=order_id,
                )
                self.db.merge(trade)
        else:
            trade = Trade(
                trade_id=f"trd_{uuid.uuid4().hex[:8]}",
                instrument_id=signal.instrument_id,
                broker_id=details.get("uid"),
                ts=int(time.time() * 1000),
                side=signal.side,
                price=executed_price,
                qty=qty_units,
                order_id=order_id,
            )
            self.db.add(trade)

        position = self.db.query(Position).filter(Position.instrument_id == signal.instrument_id).first()
        if not position:
            position = Position(
                instrument_id=signal.instrument_id,
                broker_id=details.get("uid"),
                side=signal.side,
                qty=qty_units,
                avg_price=executed_price,
                sl=signal.sl,
                tp=signal.tp,
                unrealized_pnl=Decimal("0"),
                realized_pnl=Decimal("0"),
                opened_ts=int(time.time() * 1000),
            )
            self.db.add(position)
        elif Decimal(str(position.qty or 0)) <= 0:
            position.side = signal.side
            position.broker_id = details.get("uid")
            position.qty = qty_units
            position.avg_price = executed_price
            position.sl = signal.sl
            position.tp = signal.tp
            position.unrealized_pnl = Decimal("0")
            if not position.opened_ts:
                position.opened_ts = int(time.time() * 1000)
        elif position.side == signal.side:
            total_qty = Decimal(str(position.qty)) + qty_units
            total_cost = Decimal(str(position.qty)) * Decimal(str(position.avg_price)) + qty_units * executed_price
            position.avg_price = total_cost / total_qty
            position.qty = total_qty
            position.broker_id = details.get("uid")
            position.sl = signal.sl
            position.tp = signal.tp
            position.unrealized_pnl = Decimal("0")
        else:
            current_qty = Decimal(str(position.qty))
            current_avg = Decimal(str(position.avg_price))
            sign = Decimal("1") if position.side == "BUY" else Decimal("-1")
            closing_qty = min(current_qty, qty_units)
            realized_delta = sign * closing_qty * (executed_price - current_avg)
            position.realized_pnl = Decimal(str(position.realized_pnl or 0)) + realized_delta

            remaining_qty = current_qty - qty_units
            position.broker_id = details.get("uid")
            position.unrealized_pnl = Decimal("0")

            if remaining_qty > 0:
                position.qty = remaining_qty
            elif remaining_qty == 0:
                position.qty = Decimal("0")
                position.avg_price = executed_price
                position.sl = signal.sl
                position.tp = signal.tp
            else:
                position.side = signal.side
                position.qty = abs(remaining_qty)
                position.avg_price = executed_price
                position.sl = signal.sl
                position.tp = signal.tp
                if not position.opened_ts:
                    position.opened_ts = int(time.time() * 1000)

        signal.status = "executed"
        self.db.add(DecisionLog(
            id=f"log_{uuid.uuid4().hex[:8]}",
            ts=int(time.time() * 1000),
            type="trade_filled",
            message=f"Live fill {qty_units} @ {float(executed_price):.4f} [{signal.side}] {signal.instrument_id}",
            payload={
                "broker_order_id": order_id,
                "qty": float(qty_units),
                "price": float(executed_price),
                "lots_executed": lots_executed,
            },
        ))
        self.db.commit()

        await bus.publish("orders_updated", {"order_id": order_id})
        await bus.publish("positions_updated", {"instrument_id": signal.instrument_id})
        await bus.publish("signal_updated", {"id": signal.id, "status": "executed"})
        await bus.publish("trade_filled", {"order_id": order_id, "qty": float(qty_units), "price": float(executed_price)})

    async def _sync_account_snapshot(self) -> None:
        portfolio = await self.adapter.get_portfolio(self.account_id)
        total_portfolio = money_to_decimal(portfolio.get("totalAmountPortfolio"))
        total_cash = money_to_decimal(portfolio.get("totalAmountCurrencies"))
        positions = portfolio.get("positions", []) or []
        open_positions = 0
        open_pnl = Decimal("0")
        for item in positions:
            quantity = money_to_decimal(item.get("quantity"))
            if quantity > 0:
                open_positions += 1
            open_pnl += money_to_decimal(item.get("expectedYield"))

        snapshot = AccountSnapshot(
            ts=int(time.time() * 1000),
            balance=total_cash,
            equity=total_portfolio,
            open_positions=open_positions,
            day_pnl=open_pnl,
        )
        self.db.add(snapshot)
        self.db.commit()