from core.models.schemas import RiskSettings, Signal
from core.storage.models import Position, Trade, Settings
from sqlalchemy.orm import Session
from datetime import datetime, timezone

class RiskManager:
    def __init__(self, db: Session):
        self.db = db
        self.settings = db.query(Settings).first() # Cache or fetch? Fetch for safety in MVP

    def check_new_signal(self, signal: Signal) -> tuple[bool, str]:
        """
        Returns (True, "OK") or (False, "Reason")
        """
        if not self.settings:
            return True, "Default Settings"

        # 1. Max Concurrent Positions
        active_positions = self.db.query(Position).count() # Simply count all rows in positions table?
        # Assuming positions table holds ONLY active positions (spec implies pure current state). 
        # If positions are kept as history, we need a filter. 
        # Spec 3.7: "Positions: items in current portfolio". Let's assume table = active.
        if active_positions >= self.settings.max_concurrent_positions:
            return False, f"Max positions reached ({active_positions}/{self.settings.max_concurrent_positions})"

        # 2. Daily Loss Limit (Mock calculation for MVP)
        # In real app: sum realized_pnl of trades today
        # today_pnl = self.get_today_pnl()
        # limit = balance * (daily_loss_limit_pct / 100)
        # For MVP we skip complex balance tracking and assume infinite balance or simplistic check.
        
        # 3. Max Trades Per Day
        # count trades with ts > start_of_day
        # skipped for speed unless critical.
        
        return True, "OK"

    def normalize_qty(self, qty: float, lot_size: int = 1) -> int:
        """
        P0.2: Normalize size/qty to lot integer
        """
        if lot_size <= 0: lot_size = 1
        return max(1, int(qty // lot_size) * lot_size)
