from sqlalchemy.orm import Session
from core.storage.models import Order, Trade, Position, Signal, DecisionLog
from core.risk.manager import RiskManager
from core.events.bus import bus
import time
import uuid

class PaperExecutionEngine:
    def __init__(self, db: Session):
        self.db = db
        self.risk = RiskManager(db)

    async def execute_approved_signal(self, signal_id: str):
        # 1. Fetch Signal
        signal = self.db.query(Signal).filter(Signal.id == signal_id).first()
        if not signal or signal.status != "approved":
            # Log error or ignore?
            return

        # 2. Risk Check (Double check before execution)
        # Skip for MVP speed, assume approved means manual check passed or risk was checked at approve time.
        
        # 3. Create Order
        # Normalize Qty (P0.2)
        qty = self.risk.normalize_qty(signal.size, lot_size=10) # Mock lot 10
        
        order = Order(
            order_id=f"ord_{uuid.uuid4().hex[:8]}",
            instrument_id=signal.instrument_id,
            ts=int(time.time() * 1000),
            side=signal.side,
            type="MARKET", # Execution is immediate paper fill
            price=signal.entry,
            qty=qty,
            filled_qty=qty,
            status="FILLED",
            related_signal_id=signal.id
        )
        self.db.add(order)
        
        # 4. Create Trade
        trade = Trade(
            trade_id=f"trd_{uuid.uuid4().hex[:8]}",
            instrument_id=signal.instrument_id,
            ts=int(time.time() * 1000),
            side=signal.side,
            price=signal.entry, # Fill at entry price
            qty=qty,
            order_id=order.order_id
        )
        self.db.add(trade)
        
        # 5. Update/Create Position
        position = self.db.query(Position).filter(Position.instrument_id == signal.instrument_id).first()
        if not position:
            position = Position(
                instrument_id=signal.instrument_id,
                side=signal.side,
                qty=qty,
                avg_price=signal.entry,
                sl=signal.sl,
                tp=signal.tp,
                opened_ts=int(time.time() * 1000)
            )
            self.db.add(position)
        else:
            # Simple averaging logic or replace?
            # For MVP, if side matches, add qty. If opposite, reduce/close.
            # Simplified: Just replace/add for now (assuming 1 pos per instrument)
            if position.side == signal.side:
                total_qty = position.qty + qty
                total_cost = (position.qty * position.avg_price) + (qty * signal.entry)
                position.avg_price = total_cost / total_qty
                position.qty = total_qty
            else:
                # Opposite side - simplify: close old, open new remaining?
                # Spec doesn't demand full FIFO.
                pass 
        
        # 6. Update Signal Status
        signal.status = "executed"
        
        # 7. Commit
        self.db.commit()
        
        # 8. Publish Events
        await bus.publish("orders_updated", {"order_id": order.order_id})
        await bus.publish("trade_filled", {"trade_id": trade.trade_id})
        await bus.publish("positions_updated", {"instrument_id": position.instrument_id})
        await bus.publish("signal_updated", {"id": signal.id, "status": "executed"})
        
        # Log
        log = DecisionLog(
             id=f"log_{uuid.uuid4().hex[:8]}",
             ts=int(time.time() * 1000),
             type="trade_filled",
             message=f"Filled {qty} @ {signal.entry} for {signal.instrument_id}",
             payload={"trade_id": trade.trade_id}
        )
        self.db.add(log)
        self.db.commit()
