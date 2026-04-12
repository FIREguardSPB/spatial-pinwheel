"""
P5-07: Backtest API — запуск бэктеста через API.

POST /api/v1/backtest   — запустить бэктест (синхронно, candles передаются в теле)
GET  /api/v1/backtest/strategies — список доступных стратегий
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from apps.backtest.engine import BacktestEngine
from core.strategy.selector import StrategySelector
from apps.api.deps import verify_token
from core.storage.session import get_db
from core.storage.repos import candles as candle_repo
from core.storage.repos import settings as settings_repo

logger = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(verify_token)])

_selector = StrategySelector()


class CandleIn(BaseModel):
    time: int
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


class BacktestRequest(BaseModel):
    instrument_id: str = "TQBR:SBER"
    strategy: str = "breakout"
    candles: list[CandleIn] | None = None
    initial_balance: float = 100_000.0
    risk_pct: float = Field(1.0, ge=0.1, le=10.0)
    commission_pct: float = Field(0.03, ge=0.0, le=1.0)
    use_decision_engine: bool = False   # requires DB Settings; false for pure strategy test
    timeframe: str = Field("1m")
    history_limit: int = Field(500, ge=100, le=5000)
    source: str = Field("cache")
    mode: str = Field("single")
    folds: int = Field(4, ge=2, le=8)
    strategies: list[str] | None = None


class BacktestResponse(BaseModel):
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
    equity_curve: list[dict[str, Any]]
    trades: list[dict[str, Any]]
    walk_forward: dict[str, Any] | None = None


@router.post("", response_model=BacktestResponse)
async def run_backtest(req: BacktestRequest, db: Session = Depends(get_db)):
    """
    Run a walk-forward backtest on supplied candles.

    Candles must be sorted oldest → newest.
    Returns equity curve, per-trade log, and aggregate metrics.
    """
    strategy = _selector.get(req.strategy)

    if req.candles:
        candle_dicts = [c.model_dump() for c in req.candles]
    else:
        candle_dicts = candle_repo.list_candles(db, req.instrument_id, req.timeframe, limit=req.history_limit)

    if len(candle_dicts) < strategy.lookback + 10:
        raise HTTPException(
            status_code=422,
            detail=f"Need at least {strategy.lookback + 10} candles for strategy '{req.strategy}' (got {len(candle_dicts)})"
        )

    runtime_settings = settings_repo.get_settings(db) if req.use_decision_engine else None
    engine = BacktestEngine(
        strategy=strategy,
        settings=runtime_settings,
        initial_balance=req.initial_balance,
        risk_pct=req.risk_pct,
        commission_pct=req.commission_pct,
        use_decision_engine=req.use_decision_engine,
    )

    try:
        result = engine.run(req.instrument_id, candle_dicts)
        walk_forward = None
        if req.mode == 'walk_forward':
            strategies = [
                _selector.get(name)
                for name in (req.strategies or StrategySelector.available())
            ]
            walk_forward = engine.run_walk_forward(req.instrument_id, candle_dicts, strategies=strategies, folds=req.folds)
            result.walk_forward = walk_forward
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.exception("Backtest error: %s", e)
        raise HTTPException(status_code=500, detail="Backtest failed")

    return BacktestResponse(
        instrument_id    = result.instrument_id,
        strategy_name    = result.strategy_name,
        from_ts          = result.from_ts,
        to_ts            = result.to_ts,
        initial_balance  = result.initial_balance,
        final_balance    = result.final_balance,
        total_return_pct = result.total_return_pct,
        max_drawdown_pct = result.max_drawdown_pct,
        sharpe_ratio     = result.sharpe_ratio,
        win_rate         = result.win_rate,
        profit_factor    = result.profit_factor,
        total_trades     = result.total_trades,
        avg_trade_pct    = result.avg_trade_pct,
        equity_curve     = result.equity_curve,
        trades           = result.trades,
        walk_forward     = result.walk_forward,
    )


@router.get("/strategies")
async def list_strategies():
    """Return all available strategy names."""
    return {"strategies": StrategySelector.available()}
