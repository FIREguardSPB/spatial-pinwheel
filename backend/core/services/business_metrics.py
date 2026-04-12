from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from core.storage.models import AccountSnapshot, DecisionLog, Position, Signal, Trade


def _ts_days_ago(days: int) -> int:
    return int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp() * 1000)


def _strategy_from_signal(signal: Signal | None) -> str:
    if not signal or not isinstance(signal.meta, dict):
        return "unknown"
    meta = signal.meta or {}
    multi = meta.get("multi_strategy") if isinstance(meta, dict) else {}
    return str((multi or {}).get("selected") or meta.get("strategy") or meta.get("strategy_name") or "unknown")


def _max_drawdown_pct(values: list[float]) -> float:
    if not values:
        return 0.0
    peak = values[0]
    max_dd = 0.0
    for value in values:
        peak = max(peak, value)
        if peak > 0:
            max_dd = max(max_dd, (peak - value) / peak * 100.0)
    return round(max_dd, 2)


def _position_mark_value(position: Position) -> float:
    qty = float(position.qty or 0)
    if qty <= 0:
        return 0.0
    mark = float(getattr(position, 'last_mark_price', 0) or 0)
    if mark <= 0:
        avg = float(position.avg_price or 0)
        unreal = float(position.unrealized_pnl or 0)
        sign = 1.0 if str(getattr(position, 'side', 'BUY') or 'BUY').upper() == 'BUY' else -1.0
        if avg > 0:
            mark = avg + (unreal / max(1e-9, sign * qty))
        else:
            mark = avg
    return qty * max(0.0, mark)


def build_metrics(db: Session, days: int = 7) -> dict[str, Any]:
    cutoff = _ts_days_ago(days)
    positions = (
        db.query(Position)
        .filter(Position.qty == 0, Position.realized_pnl.isnot(None), Position.updated_ts >= cutoff)
        .order_by(Position.updated_ts.asc())
        .all()
    )
    open_positions = db.query(Position).filter(Position.qty > 0).all()
    signals = db.query(Signal).filter(Signal.created_ts >= cutoff).all()
    trades = db.query(Trade).filter(Trade.ts >= cutoff).all()
    logs = db.query(DecisionLog).filter(DecisionLog.ts >= cutoff).all()
    signal_by_id = {s.id: s for s in signals}

    pnls = [float(p.realized_pnl or 0) for p in positions]
    wins = [x for x in pnls if x > 0]
    losses = [x for x in pnls if x < 0]
    total_pnl = round(sum(pnls), 2)

    day_cutoff = _ts_days_ago(1)
    daily_pnl = round(sum(float(p.realized_pnl or 0) for p in positions if int(p.updated_ts or 0) >= day_cutoff), 2)
    signals_count = len(signals)
    takes_count = 0
    for s in signals:
        meta = s.meta or {}
        final_decision = meta.get("final_decision") or ((meta.get("decision") or {}).get("decision") if isinstance(meta, dict) else None)
        if final_decision == "TAKE":
            takes_count += 1
    trades_count = len(positions)
    executed_signal_ids = {str(t.signal_id) for t in trades if getattr(t, 'signal_id', None)}

    durations = [max(0, int((int(p.updated_ts or 0) - int(p.opened_ts or 0)) / 1000)) for p in positions if p.opened_ts and p.updated_ts]

    strategy_breakdown: dict[str, dict[str, Any]] = defaultdict(lambda: {"trades": 0, "pnl": 0.0, "wins": 0})
    instrument_breakdown: dict[str, dict[str, Any]] = defaultdict(lambda: {"trades": 0, "pnl": 0.0, "wins": 0})
    pnl_curve: list[dict[str, Any]] = []
    cumulative = 0.0

    for pos in positions:
        signal = signal_by_id.get(getattr(pos, "opened_signal_id", None))
        strategy = getattr(pos, "strategy", None) or _strategy_from_signal(signal)
        instrument = pos.instrument_id
        pnl = float(pos.realized_pnl or 0)
        cumulative += pnl
        strategy_breakdown[strategy]["trades"] += 1
        strategy_breakdown[strategy]["pnl"] += pnl
        strategy_breakdown[strategy]["wins"] += 1 if pnl > 0 else 0
        instrument_breakdown[instrument]["trades"] += 1
        instrument_breakdown[instrument]["pnl"] += pnl
        instrument_breakdown[instrument]["wins"] += 1 if pnl > 0 else 0
        pnl_curve.append({
            "ts": int(pos.updated_ts or pos.opened_ts or 0),
            "pnl": round(pnl, 2),
            "cumulative_pnl": round(cumulative, 2),
            "instrument_id": instrument,
            "strategy": strategy,
        })

    snapshots = (
        db.query(AccountSnapshot)
        .filter(AccountSnapshot.ts >= cutoff)
        .order_by(AccountSnapshot.ts.asc())
        .all()
    )
    equity_curve = [
        {
            "ts": int(s.ts),
            "balance": float(s.balance or 0),
            "equity": float(s.equity or 0),
            "day_pnl": float(s.day_pnl or 0),
        }
        for s in snapshots
    ]
    dd_source = [row['equity'] for row in equity_curve] or [100000.0 + row['cumulative_pnl'] for row in pnl_curve]

    strategy_rows = []
    for strategy, info in strategy_breakdown.items():
        trades_n = info["trades"] or 0
        strategy_rows.append({
            "strategy": strategy,
            "trades": trades_n,
            "pnl": round(info["pnl"], 2),
            "win_rate": round((info["wins"] / trades_n) * 100.0, 2) if trades_n else 0.0,
        })
    strategy_rows.sort(key=lambda row: (-row["trades"], row["strategy"]))

    instrument_rows = []
    for instrument, info in instrument_breakdown.items():
        trades_n = info["trades"] or 0
        instrument_rows.append({
            "instrument_id": instrument,
            "trades": trades_n,
            "pnl": round(info["pnl"], 2),
            "win_rate": round((info["wins"] / trades_n) * 100.0, 2) if trades_n else 0.0,
        })
    instrument_rows.sort(key=lambda row: (-row["trades"], row["instrument_id"]))

    close_reasons = Counter()
    adaptive_partials = 0
    capital_reallocations = 0
    freshness_penalties = 0
    stale_signal_blocks = 0
    reallocation_ratios: list[float] = []
    optimizer_multipliers: list[float] = []
    optimizer_adjustments = 0
    recalibration_runs = 0
    recalibration_symbols = 0
    last_recalibration_ts = 0
    throttle_hits = 0
    throttle_multipliers: list[float] = []
    for log in logs:
        if log.type == 'position_closed':
            payload = dict(log.payload or {})
            close_reasons[str(payload.get('reason') or 'unknown')] += 1
        elif log.type == 'adaptive_exit_partial':
            adaptive_partials += 1
        elif log.type == 'capital_reallocation':
            capital_reallocations += 1
            payload = dict(log.payload or {})
            candidate = dict(payload.get('candidate') or {})
            if candidate.get('qty_ratio') is not None:
                reallocation_ratios.append(float(candidate.get('qty_ratio') or 0.0))
        elif log.type == 'portfolio_optimizer_overlay':
            payload = dict(log.payload or {})
            optimizer = dict(payload.get('optimizer') or {})
            mult = optimizer.get('optimizer_risk_multiplier')
            if mult is not None:
                optimizer_multipliers.append(float(mult or 0.0))
                if abs(float(mult or 0.0) - 1.0) >= 0.01:
                    optimizer_adjustments += 1
        elif log.type == 'signal_freshness':
            freshness_penalties += 1
            payload = dict(log.payload or {})
            if bool((payload.get('freshness') or {}).get('blocked')):
                stale_signal_blocks += 1
        elif log.type == 'symbol_recalibration_batch':
            recalibration_runs += 1
            last_recalibration_ts = max(last_recalibration_ts, int(log.ts or 0))
            payload = dict(log.payload or {})
            recalibration_symbols += int(payload.get('completed') or 0)
        elif log.type == 'pm_risk_throttle':
            throttle_hits += 1
            payload = dict(log.payload or {})
            risk_sizing = dict(payload.get('risk_sizing') or {})
            mult = risk_sizing.get('portfolio_risk_multiplier')
            if mult is not None:
                throttle_multipliers.append(float(mult or 0.0))
    execution_errors = db.query(Signal).filter(Signal.created_ts >= cutoff, Signal.status == 'execution_error').count()

    open_values = [_position_mark_value(pos) for pos in open_positions]
    total_open_value = sum(open_values)
    portfolio_concentration_pct = round((max(open_values) / total_open_value) * 100.0, 2) if total_open_value > 0 else 0.0

    mfe_pcts = [float(getattr(p, 'mfe_pct', 0) or 0) for p in positions if getattr(p, 'mfe_pct', None) is not None]
    mae_pcts = [float(getattr(p, 'mae_pct', 0) or 0) for p in positions if getattr(p, 'mae_pct', None) is not None]
    mfe_capture = [
        (float(p.realized_pnl or 0) / float(getattr(p, 'mfe_total_pnl', 0) or 0))
        for p in positions
        if float(getattr(p, 'mfe_total_pnl', 0) or 0) > 1e-9
    ]
    profit_factor = round(sum(wins) / abs(sum(losses)), 4) if losses else None
    best_trade = round(max(wins), 2) if wins else 0.0
    worst_trade = round(min(losses), 2) if losses else 0.0
    expectancy = round(total_pnl / trades_count, 2) if trades_count else 0.0
    for s in signals:
        meta = dict(s.meta or {}) if isinstance(s.meta, dict) else {}
        rs = dict(meta.get('risk_sizing') or {})
        mult = rs.get('portfolio_risk_multiplier')
        if mult is not None and float(mult or 0.0) < 0.999:
            throttle_multipliers.append(float(mult or 0.0))
    avg_realloc_ratio = round(sum(reallocation_ratios) / len(reallocation_ratios), 4) if reallocation_ratios else 0.0
    avg_portfolio_risk_multiplier = round(sum(throttle_multipliers) / len(throttle_multipliers), 4) if throttle_multipliers else 1.0
    return {
        "period_days": days,
        "total_pnl": total_pnl,
        "daily_pnl": daily_pnl,
        "win_rate": round((len(wins) / trades_count) * 100.0, 2) if trades_count else 0.0,
        "profit_factor": profit_factor,
        "signals_count": signals_count,
        "takes_count": takes_count,
        "trades_count": trades_count,
        "raw_fills_count": len(trades),
        "conversion_rate": round((len(executed_signal_ids) / signals_count) * 100.0, 2) if signals_count else 0.0,
        "avg_holding_time_sec": round(sum(durations) / len(durations), 2) if durations else 0.0,
        "avg_profit_per_trade": round(sum(wins) / len(wins), 2) if wins else 0.0,
        "avg_loss_per_trade": round(sum(losses) / len(losses), 2) if losses else 0.0,
        "expectancy_per_trade": expectancy,
        "max_drawdown_pct": _max_drawdown_pct(dd_source),
        "wins_count": len(wins),
        "losses_count": len(losses),
        "best_trade": best_trade,
        "worst_trade": worst_trade,
        "execution_error_count": execution_errors,
        "adaptive_partial_closes_count": adaptive_partials,
        "capital_reallocations_count": capital_reallocations,
        "avg_reallocation_ratio": avg_realloc_ratio,
        "freshness_penalties_count": freshness_penalties,
        "stale_signal_blocks_count": stale_signal_blocks,
        "portfolio_concentration_pct": portfolio_concentration_pct,
        "avg_mfe_pct": round(sum(mfe_pcts) / len(mfe_pcts), 4) if mfe_pcts else 0.0,
        "avg_mae_pct": round(sum(mae_pcts) / len(mae_pcts), 4) if mae_pcts else 0.0,
        "avg_realized_to_mfe_capture_ratio": round(sum(mfe_capture) / len(mfe_capture), 4) if mfe_capture else 0.0,
        "portfolio_optimizer_adjustments_count": optimizer_adjustments,
        "avg_optimizer_risk_multiplier": round(sum(optimizer_multipliers) / len(optimizer_multipliers), 4) if optimizer_multipliers else 1.0,
        "recalibration_runs_count": recalibration_runs,
        "recalibration_symbols_trained": recalibration_symbols,
        "last_recalibration_ts": last_recalibration_ts or None,
        "avg_portfolio_risk_multiplier": avg_portfolio_risk_multiplier,
        "throttle_hits_count": throttle_hits,
        "exit_reason_breakdown": dict(close_reasons),
        "strategy_breakdown": strategy_rows,
        "instrument_breakdown": instrument_rows[:25],
        "pnl_curve": pnl_curve,
        "equity_curve": equity_curve,
    }
