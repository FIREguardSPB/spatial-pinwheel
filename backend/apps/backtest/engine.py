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
    walk_forward: dict[str, Any] | None = None


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

    def _validation_score(self, result: BacktestResult) -> float:
        trade_quality = min(2.5, float(result.total_trades or 0) / 6.0)
        return (
            float(result.total_return_pct or 0.0) * 0.32
            + float(result.win_rate or 0.0) * 0.28
            + float(result.profit_factor or 0.0) * 22.0
            - float(result.max_drawdown_pct or 0.0) * 0.20
            + trade_quality
        )

    def run_walk_forward(self, instrument_id: str, candles: list[dict], *, strategies: list[BaseStrategy], folds: int = 4) -> dict[str, Any]:
        if len(candles) < 320:
            raise ValueError('Need at least 320 candles for walk-forward validation')
        if not strategies:
            raise ValueError('Need at least one strategy for walk-forward validation')

        test_len = max(80, min(240, len(candles) // (folds + 2)))
        min_train = max(200, test_len * 2)
        results: list[dict[str, Any]] = []
        train_leaderboard: dict[str, list[float]] = {s.name: [] for s in strategies}
        oos_leaderboard: dict[str, list[float]] = {s.name: [] for s in strategies}
        selected_counter: dict[str, int] = {s.name: 0 for s in strategies}

        for fold_idx in range(folds):
            train_end = min_train + fold_idx * test_len
            test_start = train_end
            test_end = min(len(candles), test_start + test_len)
            if test_end - test_start < 60:
                break
            train_slice = candles[:train_end]
            test_slice = candles[test_start:test_end]
            train_scores: list[dict[str, Any]] = []
            selected_strategy: BaseStrategy | None = None
            selected_train_score = float('-inf')

            for strategy in strategies:
                if len(train_slice) < strategy.lookback + 10 or len(test_slice) < strategy.lookback + 10:
                    continue
                train_engine = BacktestEngine(
                    strategy=strategy,
                    settings=self.settings,
                    initial_balance=self.initial_balance,
                    risk_pct=self.risk_pct,
                    commission_pct=self.commission_pct * 100,
                    max_open=self.max_open,
                    use_decision_engine=self.use_de,
                )
                train_res = train_engine.run(instrument_id, train_slice)
                train_score = self._validation_score(train_res)
                train_leaderboard[strategy.name].append(train_score)
                candidate = {
                    'strategy': strategy.name,
                    'train_score': round(train_score, 4),
                    'train_total_return_pct': train_res.total_return_pct,
                    'train_win_rate': train_res.win_rate,
                    'train_profit_factor': train_res.profit_factor,
                    'train_max_drawdown_pct': train_res.max_drawdown_pct,
                    'train_total_trades': train_res.total_trades,
                }
                train_scores.append(candidate)
                if train_score > selected_train_score:
                    selected_train_score = train_score
                    selected_strategy = strategy

            if not train_scores or selected_strategy is None:
                continue

            train_scores.sort(key=lambda item: item['train_score'], reverse=True)
            selected_counter[selected_strategy.name] = selected_counter.get(selected_strategy.name, 0) + 1
            test_engine = BacktestEngine(
                strategy=selected_strategy,
                settings=self.settings,
                initial_balance=self.initial_balance,
                risk_pct=self.risk_pct,
                commission_pct=self.commission_pct * 100,
                max_open=self.max_open,
                use_decision_engine=self.use_de,
            )
            oos_res = test_engine.run(instrument_id, test_slice)
            oos_score = self._validation_score(oos_res)
            oos_leaderboard[selected_strategy.name].append(oos_score)
            results.append({
                'fold': fold_idx + 1,
                'train_from_ts': int(train_slice[0].get('time', 0)),
                'train_to_ts': int(train_slice[-1].get('time', 0)),
                'test_from_ts': int(test_slice[0].get('time', 0)),
                'test_to_ts': int(test_slice[-1].get('time', 0)),
                'selected_strategy': selected_strategy.name,
                'train_scores': train_scores,
                'out_of_sample': {
                    'strategy': selected_strategy.name,
                    'validation_score': round(oos_score, 4),
                    'total_return_pct': oos_res.total_return_pct,
                    'win_rate': oos_res.win_rate,
                    'profit_factor': oos_res.profit_factor,
                    'max_drawdown_pct': oos_res.max_drawdown_pct,
                    'total_trades': oos_res.total_trades,
                    'avg_trade_pct': oos_res.avg_trade_pct,
                },
            })

        aggregate = []
        for strategy in strategies:
            name = strategy.name
            train_values = train_leaderboard.get(name, [])
            oos_values = oos_leaderboard.get(name, [])
            selected = selected_counter.get(name, 0)
            if not train_values and not oos_values and selected == 0:
                continue
            avg_train = sum(train_values) / len(train_values) if train_values else 0.0
            std_train = math.sqrt(sum((v - avg_train) ** 2 for v in train_values) / len(train_values)) if len(train_values) > 1 else 0.0
            avg_oos = sum(oos_values) / len(oos_values) if oos_values else 0.0
            std_oos = math.sqrt(sum((v - avg_oos) ** 2 for v in oos_values) / len(oos_values)) if len(oos_values) > 1 else 0.0
            aggregate.append({
                'strategy': name,
                'avg_train_score': round(avg_train, 4),
                'train_std_score': round(std_train, 4),
                'avg_oos_score': round(avg_oos, 4),
                'oos_std_score': round(std_oos, 4),
                'robust_oos_score': round(avg_oos - std_oos * 0.8, 4),
                'folds_selected': int(selected),
                'train_folds': len(train_values),
                'oos_folds': len(oos_values),
            })
        aggregate.sort(key=lambda item: (item['robust_oos_score'], item['avg_oos_score'], item['folds_selected']), reverse=True)
        return {
            'mode': 'walk_forward',
            'folds': results,
            'strategy_rankings': aggregate,
            'best_strategy': aggregate[0]['strategy'] if aggregate else None,
            'fold_count': len(results),
            'test_window_bars': test_len,
            'selection_mode': 'expanding_train_pick_best_then_oos',
        }

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
            walk_forward    = None,
        )
