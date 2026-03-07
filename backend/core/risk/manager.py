"""
P2-02: RiskManager — полная реализация.
P2-04: calculate_position_size() — расчёт размера через risk_per_trade_pct × balance
"""
import logging
import time
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from core.storage.models import Position, Settings, Trade
from core.risk.correlation import check_correlation

logger = logging.getLogger(__name__)


def _start_of_day_ms() -> int:
    now = datetime.now(timezone.utc)
    sod = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return int(sod.timestamp() * 1000)


class RiskManager:
    def __init__(self, db: Session):
        self.db = db
        self._reload_settings()

    def _reload_settings(self) -> None:
        """P2-05: Перечитывать настройки из БД перед каждой проверкой."""
        self.settings = self.db.query(Settings).first()

    def check_new_signal(self, signal, candles_map: dict | None = None) -> tuple[bool, str]:
        """Returns (True, 'OK') or (False, 'Reason')."""
        self._reload_settings()
        if not self.settings:
            return True, "No settings — allowing by default"
        s = self.settings

        # 1. Max Concurrent Positions
        active_count = self.db.query(Position).filter(Position.qty > 0).count()
        if active_count >= s.max_concurrent_positions:
            return False, f"Max positions reached ({active_count}/{s.max_concurrent_positions})"

        # 2. Daily Loss Limit
        today_pnl = self._get_today_realized_pnl()
        balance = self._get_paper_balance()
        limit = balance * (float(s.daily_loss_limit_pct) / 100.0)
        if today_pnl < 0 and abs(today_pnl) >= limit:
            return False, (
                f"Daily loss limit hit: {today_pnl:.2f} >= -{limit:.2f} "
                f"({s.daily_loss_limit_pct}% of {balance:.2f})"
            )

        # 3. Max Trades Per Day
        if s.max_trades_per_day and s.max_trades_per_day > 0:
            today_count = self._get_today_trades_count()
            if today_count >= s.max_trades_per_day:
                return False, f"Max trades per day reached ({today_count}/{s.max_trades_per_day})"

        # 4. Cooldown after loss streak
        if s.cooldown_losses and s.cooldown_losses > 0 and s.cooldown_minutes and s.cooldown_minutes > 0:
            in_cooldown, msg = self._check_cooldown(int(s.cooldown_losses), int(s.cooldown_minutes))
            if in_cooldown:
                return False, msg

        # ── 5. Correlation filter (P5-06) ────────────────────────────────────────
        corr_threshold = float(getattr(s, 'correlation_threshold', 0.8) or 0.8)
        max_corr = int(getattr(s, 'max_correlated_positions', 2) or 2)
        if candles_map is not None:
            instrument_id = signal.get('instrument_id') if isinstance(signal, dict) else getattr(signal, 'instrument_id', None)
            if instrument_id:
                corr_ok, corr_msg = check_correlation(
                    self.db, instrument_id, candles_map,
                    threshold=corr_threshold, max_correlated=max_corr,
                )
                if not corr_ok:
                    return False, corr_msg

        return True, "OK"

    def calculate_position_size(self, entry: float, sl: float, balance: float | None = None, lot_size: int = 1) -> int:
        """
        P2-04: size = (balance × risk_pct%) / |entry - sl|
        Округляет до целых лотов.
        """
        self._reload_settings()
        if balance is None:
            balance = self._get_paper_balance()
        if not self.settings:
            return max(1, lot_size)

        risk_pct = float(self.settings.risk_per_trade_pct) / 100.0
        risk_amount = balance * risk_pct
        sl_distance = abs(entry - sl)
        if sl_distance < 1e-9:
            logger.warning("SL distance ~zero, returning minimum lot size")
            return lot_size

        raw = risk_amount / sl_distance
        lots = max(1, int(raw // lot_size) * lot_size)
        logger.debug("size: balance=%.0f risk=%.2f%% rub=%.2f sl_dist=%.4f → %d lots",
                     balance, risk_pct*100, risk_amount, sl_distance, lots)
        return lots

    def normalize_qty(self, qty: float, lot_size: int = 1) -> int:
        if lot_size <= 0:
            lot_size = 1
        return max(1, int(float(qty) // lot_size) * lot_size)

    # ── helpers ───────────────────────────────────────────────────────────────

    def _get_today_realized_pnl(self) -> float:
        sod = _start_of_day_ms()
        result = (self.db.query(func.sum(Position.realized_pnl))
                  .filter(Position.updated_ts >= sod).scalar())
        return float(result or 0.0)

    def _get_today_trades_count(self) -> int:
        sod = _start_of_day_ms()
        return self.db.query(Trade).filter(Trade.ts >= sod).count()

    def _check_cooldown(self, loss_streak: int, cooldown_minutes: int) -> tuple[bool, str]:
        recent = (self.db.query(Position)
                  .filter(Position.qty == 0, Position.realized_pnl < 0)
                  .order_by(Position.updated_ts.desc())
                  .limit(loss_streak).all())
        if len(recent) < loss_streak:
            return False, ""
        latest_ts = max(float(p.updated_ts) for p in recent)
        elapsed = (time.time() * 1000 - latest_ts) / 60_000
        if elapsed < cooldown_minutes:
            remaining = cooldown_minutes - elapsed
            return True, f"Cooldown: {loss_streak} losses in a row, {remaining:.0f}min remaining"
        return False, ""

    def _get_paper_balance(self) -> float:
        """Read paper balance from Settings (already loaded by _reload_settings), fallback to 100_000."""
        if self.settings and self.settings.account_balance:
            return float(self.settings.account_balance)
        return 100_000.0
