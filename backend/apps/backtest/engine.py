"""
P5-07: BacktestEngine — симуляция торговой стратегии на исторических данных.

Алгоритм:
  1. Итерация по свечам (walk-forward, без lookahead).
  2. На каждой свече: strategy.analyze() → signal?
  3. Если сигнал → DecisionEngine.evaluate() → TAKE?
  4. Открыть виртуальную позицию.
  5. На каждой последующей свече: проверить SL/TP/время.
  6. Собрать статистику: equity curve, drawdown, метрики.

Метрики результата:
  total_return_pct  — суммарный доход (%)
  max_drawdown_pct  — максимальная просадка (%)
  sharpe_ratio      — коэффициент Шарпа (annualized, ~252 trading days)
  win_rate          — процент прибыльных сделок
  profit_factor     — sum(wins) / sum(losses)
  total_trades      — количество сделок
  avg_trade_pct     — средний P&L сделки (%)
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from core.strategy.base import BaseStrategy


@dataclass
class BacktestTrade:
    instrument_id: str
    side: str
    entry_price: float
    sl: float
    tp: float
    size: float
    entry_bar: int          # index в candles
    close_price: float = 0.0
    close_bar: int = 0
    close_reason: str = ""  # "TP" | "SL" | "END"
    pnl: float = 0.0
    pnl_pct: float = 0.0


@dataclass
class BacktestResult:
    instrument_id: str
    strategy_name: str
    from_ts: int
    to_ts: int
    initial_balance: float
    final_balance: float
    total_return_pct: float
    max_drawdown_pct: float
    sharpe_ratio: Optional[float]
    win_rate: float
    profit_factor: Optional[float]
    total_trades: int
    avg_trade_pct: float
    equity_curve: list[dict]    # [{ts, equity}]
    trades: list[dict]          # lightweight trade list
    settings_used: dict[str, Any] = field(default_factory=dict)


class BacktestEngine:
    """
    Walk-forward backtester. No lookahead bias:
    analyze() sees only candles[0..i], decision uses the close of bar i.
    """

    def __init__(
        self,
        strategy: BaseStrategy,
        settings=None,
        initial_balance: float = 100_000.0,
        risk_pct: float = 1.0,          # % of balance risked per trade
        commission_pct: float = 0.03,   # 0.03% per side
        max_open: int = 1,              # max concurrent positions per instrument
        use_decision_engine: bool = True,
    ):
        self.strategy = strategy
        self.settings = settings
        self.initial_balance = initial_balance
        self.risk_pct = risk_pct
        self.commission_pct = commission_pct / 100
        self.max_open = max_open
        self.use_de = use_decision_engine and settings is not None

    def run(self, instrument_id: str, candles: list[dict]) -> BacktestResult:
        """
        Run backtest over the full candle list.
        candles must be sorted oldest → newest.
        """
        lookback = self.strategy.lookback
        if len(candles) < lookback + 10:
            raise ValueError(
                f"Not enough candles: {len(candles)} < {lookback + 10}"
            )

        balance = self.initial_balance
        open_trade: Optional[BacktestTrade] = None
        closed_trades: list[BacktestTrade] = []
        equity_curve: list[dict] = []
        peak_equity = balance

        # Walk-forward
        for i in range(lookback, len(candles)):
            bar = candles[i]
            high  = float(bar["high"])
            low   = float(bar["low"])
            close = float(bar["close"])
            ts    = int(bar.get("time", i))

            # ── Check open position ───────────────────────────────────────────
            if open_trade is not None:
                t = open_trade
                if t.side == "BUY":
                    if low <= t.sl:
                        t.close_price = t.sl
                        t.close_reason = "SL"
                    elif high >= t.tp:
                        t.close_price = t.tp
                        t.close_reason = "TP"
                else:  # SELL
                    if high >= t.sl:
                        t.close_price = t.sl
                        t.close_reason = "SL"
                    elif low <= t.tp:
                        t.close_price = t.tp
                        t.close_reason = "TP"

                if t.close_reason:
                    t.close_bar = i
                    raw_pnl = (
                        (t.close_price - t.entry_price) * t.size
                        if t.side == "BUY"
                        else (t.entry_price - t.close_price) * t.size
                    )
                    comm = t.entry_price * t.size * self.commission_pct * 2
                    t.pnl = raw_pnl - comm
                    t.pnl_pct = (t.pnl / balance) * 100
                    balance += t.pnl
                    closed_trades.append(t)
                    open_trade = None

            # ── Equity snapshot every bar ─────────────────────────────────────
            unrealized = 0.0
            if open_trade is not None:
                t = open_trade
                unrealized = (
                    (close - t.entry_price) * t.size
                    if t.side == "BUY"
                    else (t.entry_price - close) * t.size
                )
            equity = balance + unrealized
            peak_equity = max(peak_equity, equity)
            equity_curve.append({"ts": ts * 1000 if ts < 10_000_000_000 else ts, "equity": round(equity, 2)})

            # ── Try to open new trade ─────────────────────────────────────────
            if open_trade is None:
                history = candles[max(0, i - 300): i + 1]
                sig = self.strategy.analyze(instrument_id, history)
                if sig:
                    if self.use_de:
                        sig = self._run_de(sig, history)
                    if sig:
                        # Size by risk
                        entry  = float(sig["entry"])
                        sl     = float(sig["sl"])
                        sl_dist = abs(entry - sl)
                        if sl_dist > 1e-9:
                            risk_amount = balance * (self.risk_pct / 100)
                            size = risk_amount / sl_dist
                        else:
                            size = 1.0

                        open_trade = BacktestTrade(
                            instrument_id=instrument_id,
                            side=sig["side"],
                            entry_price=entry,
                            sl=sl,
                            tp=float(sig["tp"]),
                            size=size,
                            entry_bar=i,
                        )

        # ── Close any remaining open trade at last bar ─────────────────────────
        if open_trade is not None:
            last = candles[-1]
            open_trade.close_price = float(last["close"])
            open_trade.close_reason = "END"
            open_trade.close_bar = len(candles) - 1
            raw_pnl = (
                (open_trade.close_price - open_trade.entry_price) * open_trade.size
                if open_trade.side == "BUY"
                else (open_trade.entry_price - open_trade.close_price) * open_trade.size
            )
            comm = open_trade.entry_price * open_trade.size * self.commission_pct * 2
            open_trade.pnl = raw_pnl - comm
            open_trade.pnl_pct = (open_trade.pnl / balance) * 100
            balance += open_trade.pnl
            closed_trades.append(open_trade)

        return self._build_result(
            instrument_id=instrument_id,
            candles=candles,
            balance=balance,
            closed_trades=closed_trades,
            equity_curve=equity_curve,
        )

    def _run_de(self, sig: dict, candles: list[dict]) -> Optional[dict]:
        """Run DecisionEngine on signal. Return sig if TAKE, None otherwise."""
        try:
            from apps.worker.decision_engine.engine import DecisionEngine
            from apps.worker.decision_engine.types import MarketSnapshot, Decision
            from decimal import Decimal

            class _Sig:
                def __init__(self, s):
                    self.side   = s["side"]
                    self.entry  = Decimal(str(s["entry"]))
                    self.sl     = Decimal(str(s["sl"]))
                    self.tp     = Decimal(str(s["tp"]))
                    self.size   = Decimal(str(s.get("size", 1)))
                    self.r      = Decimal(str(s.get("r", 1.5)))

            snap = MarketSnapshot(
                candles=candles,
                last_price=Decimal(str(candles[-1]["close"])),
            )
            de = DecisionEngine(self.settings)
            result = de.evaluate(_Sig(sig), snap)
            return sig if result.decision == Decision.TAKE else None
        except Exception:
            return sig   # DE unavailable — pass through

    def _build_result(
        self,
        instrument_id: str,
        candles: list[dict],
        balance: float,
        closed_trades: list[BacktestTrade],
        equity_curve: list[dict],
    ) -> BacktestResult:
        n = len(closed_trades)
        wins   = [t for t in closed_trades if t.pnl > 0]
        losses = [t for t in closed_trades if t.pnl <= 0]

        win_rate = round(len(wins) / n * 100, 1) if n > 0 else 0.0

        sum_wins   = sum(t.pnl for t in wins)
        sum_losses = abs(sum(t.pnl for t in losses))
        profit_factor = round(sum_wins / sum_losses, 2) if sum_losses > 1e-9 else None

        avg_trade_pct = round(sum(t.pnl_pct for t in closed_trades) / n, 3) if n > 0 else 0.0

        total_return_pct = round((balance - self.initial_balance) / self.initial_balance * 100, 2)

        # Max drawdown from equity curve
        peak  = self.initial_balance
        max_dd = 0.0
        for e in equity_curve:
            eq = e["equity"]
            peak = max(peak, eq)
            dd = (peak - eq) / peak * 100 if peak > 0 else 0.0
            max_dd = max(max_dd, dd)

        # Sharpe ratio (annualized, assume 252 bars/year if daily, else scale)
        sharpe = None
        if len(equity_curve) >= 10:
            eq_vals = [e["equity"] for e in equity_curve]
            bar_returns = [
                (eq_vals[i] - eq_vals[i - 1]) / eq_vals[i - 1]
                for i in range(1, len(eq_vals))
                if eq_vals[i - 1] > 0
            ]
            if bar_returns:
                mean_r = sum(bar_returns) / len(bar_returns)
                std_r = math.sqrt(sum((r - mean_r) ** 2 for r in bar_returns) / len(bar_returns))
                if std_r > 1e-12:
                    ann_factor = math.sqrt(252)
                    sharpe = round(mean_r / std_r * ann_factor, 3)

        trades_light = [
            {
                "side":         t.side,
                "entry":        round(t.entry_price, 4),
                "close":        round(t.close_price, 4),
                "pnl":          round(t.pnl, 2),
                "pnl_pct":      round(t.pnl_pct, 3),
                "close_reason": t.close_reason,
                "bars_held":    t.close_bar - t.entry_bar,
            }
            for t in closed_trades
        ]

        from_ts = int(candles[0].get("time", 0))  * 1000 if candles else 0
        to_ts   = int(candles[-1].get("time", 0)) * 1000 if candles else 0

        return BacktestResult(
            instrument_id   = instrument_id,
            strategy_name   = self.strategy.name,
            from_ts         = from_ts,
            to_ts           = to_ts,
            initial_balance = self.initial_balance,
            final_balance   = round(balance, 2),
            total_return_pct= total_return_pct,
            max_drawdown_pct= round(max_dd, 2),
            sharpe_ratio    = sharpe,
            win_rate        = win_rate,
            profit_factor   = profit_factor,
            total_trades    = n,
            avg_trade_pct   = avg_trade_pct,
            equity_curve    = equity_curve,
            trades          = trades_light,
        )
