from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from statistics import mean
from typing import Any
from zoneinfo import ZoneInfo

try:
    from sqlalchemy.orm import Session
except Exception:  # pragma: no cover
    Session = Any  # type: ignore

from apps.backtest.engine import BacktestEngine
from core.storage.models import DecisionLog, Position, Signal, Watchlist
try:
    from core.storage.repos.candles import list_candles as _list_candles
except Exception:  # pragma: no cover
    _list_candles = None
try:
    from core.storage.repos.settings import get_settings as _get_settings
except Exception:  # pragma: no cover
    _get_settings = None
from core.strategy.selector import StrategySelector

MSK = ZoneInfo('Europe/Moscow')


def list_candles(db: Session, instrument_id: str, timeframe: str, limit: int = 500) -> list[dict[str, Any]]:
    if _list_candles is None:  # pragma: no cover
        raise RuntimeError('candle repo unavailable')
    return _list_candles(db, instrument_id, timeframe, limit=limit)


def get_settings(db: Session) -> Any:
    if _get_settings is None:  # pragma: no cover
        raise RuntimeError('settings repo unavailable')
    return _get_settings(db)


def _cutoff_ms(days: int) -> int:
    return int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp() * 1000)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _pf(values: list[float]) -> float | None:
    wins = [value for value in values if value > 0]
    losses = [value for value in values if value < 0]
    if not wins and not losses:
        return None
    if not losses:
        return 999.0
    return round(sum(wins) / abs(sum(losses)), 4)


def _capture_status(*, trades: int, pf: float | None, expectancy: float, win_rate: float) -> str:
    if trades < 3:
        return 'insufficient_data'
    if (pf is not None and pf >= 1.25 and expectancy >= 0.0) or (win_rate >= 50.0 and expectancy > 0.0):
        return 'pass'
    if (pf is not None and pf >= 1.0) or expectancy >= -25.0 or win_rate >= 42.0:
        return 'partial'
    return 'fail'


def _signal_meta(signal: Signal | None) -> dict[str, Any]:
    if signal is None:
        return {}
    meta = getattr(signal, 'meta', {}) or {}
    return dict(meta) if isinstance(meta, dict) else {}


def _extract_strategy(signal: Signal | None, position: Position | None = None) -> str:
    meta = _signal_meta(signal)
    multi = dict(meta.get('multi_strategy') or {}) if isinstance(meta.get('multi_strategy'), dict) else {}
    return str(
        multi.get('selected')
        or meta.get('strategy_name')
        or meta.get('strategy')
        or getattr(position, 'strategy', None)
        or 'unknown'
    )


def _extract_regime(signal: Signal | None) -> str:
    meta = _signal_meta(signal)
    adaptive = dict(meta.get('adaptive_plan') or {}) if isinstance(meta.get('adaptive_plan'), dict) else {}
    event_regime = dict(meta.get('event_regime') or {}) if isinstance(meta.get('event_regime'), dict) else {}
    for value in (
        event_regime.get('regime'),
        adaptive.get('regime'),
        meta.get('regime'),
        meta.get('market_regime'),
        meta.get('last_regime'),
    ):
        if value:
            return str(value)
    return 'unknown'


def _msk_hour_bucket(ts_ms: int) -> str:
    dt = datetime.fromtimestamp(int(ts_ms) / 1000.0, tz=timezone.utc).astimezone(MSK)
    hour = int(dt.hour)
    if 7 <= hour < 10:
        return 'morning'
    if 10 <= hour < 14:
        return 'midday'
    if 14 <= hour < 18:
        return 'afternoon'
    if 18 <= hour < 23:
        return 'evening'
    return 'overnight'


def _bucket_table(rows: dict[str, dict[str, Any]], *, key_name: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for key, row in rows.items():
        pnls = row.get('pnls') or []
        captures = row.get('captures') or []
        trades = int(row.get('trades') or 0)
        win_rate = round((int(row.get('wins') or 0) / trades) * 100.0, 2) if trades else 0.0
        expectancy = round(sum(pnls) / trades, 4) if trades else 0.0
        pf = _pf(pnls)
        avg_capture = round(mean(captures), 4) if captures else None
        item = {
            key_name: key,
            'trades': trades,
            'wins': int(row.get('wins') or 0),
            'losses': int(row.get('losses') or 0),
            'pnl': round(sum(pnls), 4),
            'win_rate': win_rate,
            'profit_factor': pf,
            'expectancy_per_trade': expectancy,
            'avg_mfe_capture_ratio': avg_capture,
            'status': _capture_status(trades=trades, pf=pf, expectancy=expectancy, win_rate=win_rate),
        }
        result.append(item)
    result.sort(key=lambda item: (-int(item.get('trades') or 0), -_safe_float(item.get('pnl'))))
    return result


def _candidate_instruments(db: Session, cutoff: int, *, max_instruments: int) -> list[str]:
    ids: list[str] = []
    try:
        ids.extend([str(row.instrument_id) for row in db.query(Watchlist).filter(Watchlist.is_active == True).order_by(Watchlist.added_ts.asc()).all()])
    except Exception:
        pass
    try:
        ids.extend([str(row.instrument_id) for row in db.query(Position.instrument_id).filter(Position.updated_ts >= cutoff).distinct().all()])
    except Exception:
        pass
    try:
        ids.extend([str(row.instrument_id) for row in db.query(Signal.instrument_id).filter(Signal.created_ts >= cutoff).distinct().all()])
    except Exception:
        pass
    seen: set[str] = set()
    result: list[str] = []
    for value in ids:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
        if len(result) >= max_instruments:
            break
    return result


def _walk_forward_status(*, instruments: int, pass_rate_pct: float, avg_oos_score: float, avg_oos_pf: float) -> str:
    if instruments == 0:
        return 'insufficient_data'
    if pass_rate_pct >= 65.0 and avg_oos_score >= 12.0 and avg_oos_pf >= 1.15:
        return 'pass'
    if pass_rate_pct >= 40.0 and avg_oos_score >= 5.0 and avg_oos_pf >= 0.95:
        return 'partial'
    return 'fail'


def build_performance_layer(
    db: Session,
    *,
    days: int = 45,
    timeframe: str = '1m',
    history_limit: int = 720,
    folds: int = 4,
    max_instruments: int = 8,
) -> dict[str, Any]:
    days = max(7, min(int(days or 45), 180))
    history_limit = max(320, min(int(history_limit or 720), 3000))
    folds = max(2, min(int(folds or 4), 8))
    max_instruments = max(1, min(int(max_instruments or 8), 16))
    cutoff = _cutoff_ms(days)

    settings = get_settings(db)
    signals = (
        db.query(Signal)
        .filter(Signal.created_ts >= cutoff)
        .order_by(Signal.created_ts.asc())
        .all()
    )
    positions = (
        db.query(Position)
        .filter(Position.updated_ts >= cutoff, Position.qty == 0)
        .order_by(Position.updated_ts.asc())
        .all()
    )
    close_logs = (
        db.query(DecisionLog)
        .filter(DecisionLog.ts >= cutoff, DecisionLog.type == 'position_closed')
        .order_by(DecisionLog.ts.asc())
        .all()
    )

    signal_by_id = {str(signal.id): signal for signal in signals}
    close_diag_by_trace: dict[str, dict[str, Any]] = {}
    close_diag_by_signal: dict[str, dict[str, Any]] = {}
    for row in close_logs:
        payload = dict(row.payload or {}) if isinstance(row.payload, dict) else {}
        diag = dict(payload.get('exit_diagnostics') or {}) if isinstance(payload.get('exit_diagnostics'), dict) else {}
        trace_id = str(payload.get('trace_id') or '')
        signal_id = str(payload.get('signal_id') or '')
        if trace_id and trace_id not in close_diag_by_trace:
            close_diag_by_trace[trace_id] = diag
        if signal_id and signal_id not in close_diag_by_signal:
            close_diag_by_signal[signal_id] = diag

    strategy_rows: dict[str, dict[str, Any]] = defaultdict(lambda: {'pnls': [], 'captures': [], 'trades': 0, 'wins': 0, 'losses': 0})
    regime_rows: dict[str, dict[str, Any]] = defaultdict(lambda: {'pnls': [], 'captures': [], 'trades': 0, 'wins': 0, 'losses': 0})
    combo_rows: dict[str, dict[str, Any]] = defaultdict(lambda: {'pnls': [], 'captures': [], 'trades': 0, 'wins': 0, 'losses': 0})
    session_rows: dict[str, dict[str, Any]] = defaultdict(lambda: {'pnls': [], 'captures': [], 'trades': 0, 'wins': 0, 'losses': 0})

    for position in positions:
        pnl = _safe_float(getattr(position, 'realized_pnl', 0.0))
        signal_id = str(getattr(position, 'opened_signal_id', '') or '')
        signal = signal_by_id.get(signal_id)
        strategy = _extract_strategy(signal, position)
        regime = _extract_regime(signal)
        combo = f'{strategy} | {regime}'
        session_bucket = _msk_hour_bucket(int(getattr(position, 'opened_ts', 0) or getattr(position, 'updated_ts', 0) or 0))
        trace_id = str(getattr(position, 'trace_id', '') or '')
        diag = close_diag_by_trace.get(trace_id) or close_diag_by_signal.get(signal_id) or {}
        capture_ratio = diag.get('realized_to_mfe_capture_ratio')
        capture = _safe_float(capture_ratio) if capture_ratio is not None else None
        for bucket_key, bucket in (
            (strategy, strategy_rows[strategy]),
            (regime, regime_rows[regime]),
            (combo, combo_rows[combo]),
            (session_bucket, session_rows[session_bucket]),
        ):
            bucket['trades'] += 1
            bucket['pnls'].append(pnl)
            if capture is not None:
                bucket['captures'].append(capture)
            if pnl > 0:
                bucket['wins'] += 1
            elif pnl < 0:
                bucket['losses'] += 1

    strategy_table = _bucket_table(strategy_rows, key_name='strategy')
    regime_table = _bucket_table(regime_rows, key_name='regime')
    combo_table = _bucket_table(combo_rows, key_name='slice')
    session_table = _bucket_table(session_rows, key_name='session')
    best_combo = max(combo_table, key=lambda item: (_safe_float(item.get('expectancy_per_trade')), _safe_float(item.get('pnl'))), default=None)
    worst_combo = min(combo_table, key=lambda item: (_safe_float(item.get('expectancy_per_trade')), _safe_float(item.get('pnl'))), default=None)

    selector = StrategySelector()
    active_strategy_names = StrategySelector.parse_names(getattr(settings, 'strategy_name', None)) or StrategySelector.available()
    strategy_objs = [selector.get(name) for name in active_strategy_names]
    walk_rows: list[dict[str, Any]] = []
    walk_strategy_rows: dict[str, dict[str, Any]] = defaultdict(lambda: {'oos_scores': [], 'oos_pfs': [], 'selected': 0, 'passes': 0, 'fails': 0, 'instruments': set()})

    candidate_instruments = _candidate_instruments(db, cutoff, max_instruments=max_instruments)
    risk_pct = max(0.1, _safe_float(getattr(settings, 'risk_per_trade_pct', None), 0.5))
    commission_pct = max(0.0, _safe_float(getattr(settings, 'fees_bps', None), 3.0) / 100.0)
    initial_balance = max(10_000.0, _safe_float(getattr(settings, 'account_balance', None), 100_000.0))

    for instrument_id in candidate_instruments:
        candles = list_candles(db, instrument_id, timeframe, limit=history_limit)
        bars = len(candles)
        if bars < 320:
            walk_rows.append({
                'instrument_id': instrument_id,
                'bars': bars,
                'status': 'insufficient_data',
                'reason': 'not_enough_history',
            })
            continue
        try:
            engine = BacktestEngine(
                strategy=strategy_objs[0],
                settings=settings,
                initial_balance=initial_balance,
                risk_pct=risk_pct,
                commission_pct=commission_pct,
                use_decision_engine=True,
            )
            walk = engine.run_walk_forward(instrument_id, candles, strategies=strategy_objs, folds=folds)
            rankings = list(walk.get('strategy_rankings') or [])
            folds_rows = list(walk.get('folds') or [])
            best = rankings[0] if rankings else {}
            oos_scores = [float((row.get('out_of_sample') or {}).get('validation_score') or 0.0) for row in folds_rows]
            oos_pfs = [float((row.get('out_of_sample') or {}).get('profit_factor') or 0.0) for row in folds_rows if (row.get('out_of_sample') or {}).get('profit_factor') is not None]
            oos_returns = [float((row.get('out_of_sample') or {}).get('total_return_pct') or 0.0) for row in folds_rows]
            oos_drawdowns = [float((row.get('out_of_sample') or {}).get('max_drawdown_pct') or 0.0) for row in folds_rows]
            oos_trades = [int((row.get('out_of_sample') or {}).get('total_trades') or 0) for row in folds_rows]
            pass_count = sum(1 for row in folds_rows if float((row.get('out_of_sample') or {}).get('validation_score') or 0.0) >= 8.0)
            selected_strategy = str(best.get('strategy') or walk.get('best_strategy') or 'unknown')
            avg_oos_score = round(mean(oos_scores), 4) if oos_scores else 0.0
            avg_oos_pf = round(mean(oos_pfs), 4) if oos_pfs else 0.0
            avg_oos_return = round(mean(oos_returns), 4) if oos_returns else 0.0
            avg_oos_drawdown = round(mean(oos_drawdowns), 4) if oos_drawdowns else 0.0
            avg_oos_trades = round(mean(oos_trades), 2) if oos_trades else 0.0
            status = 'pass' if pass_count >= max(1, len(folds_rows) - 1) and avg_oos_pf >= 1.1 else ('partial' if pass_count >= max(1, len(folds_rows) // 2) and avg_oos_pf >= 0.9 else 'fail')
            walk_rows.append({
                'instrument_id': instrument_id,
                'bars': bars,
                'status': status,
                'selected_strategy': selected_strategy,
                'avg_oos_score': avg_oos_score,
                'avg_oos_profit_factor': avg_oos_pf,
                'avg_oos_return_pct': avg_oos_return,
                'avg_oos_drawdown_pct': avg_oos_drawdown,
                'avg_oos_trades': avg_oos_trades,
                'fold_count': int(walk.get('fold_count') or len(folds_rows)),
                'pass_folds': pass_count,
                'fail_folds': max(0, len(folds_rows) - pass_count),
                'best_strategy_rankings': rankings[:3],
            })
            stat = walk_strategy_rows[selected_strategy]
            stat['selected'] += 1
            stat['oos_scores'].extend(oos_scores)
            stat['oos_pfs'].extend(oos_pfs)
            stat['instruments'].add(instrument_id)
            if status == 'pass':
                stat['passes'] += 1
            elif status == 'fail':
                stat['fails'] += 1
            for rank in rankings:
                rank_name = str(rank.get('strategy') or 'unknown')
                per = walk_strategy_rows[rank_name]
                per['instruments'].add(instrument_id)
                if rank.get('avg_oos_score') is not None:
                    per['oos_scores'].append(_safe_float(rank.get('avg_oos_score')))
                if rank.get('robust_oos_score') is not None:
                    per['oos_pfs'].append(max(0.0, _safe_float(rank.get('robust_oos_score')) / 10.0))
        except Exception as exc:
            walk_rows.append({
                'instrument_id': instrument_id,
                'bars': bars,
                'status': 'fail',
                'reason': str(exc),
            })

    wf_instrument_rows = sorted(walk_rows, key=lambda row: (0 if row.get('status') == 'pass' else 1 if row.get('status') == 'partial' else 2, -_safe_float(row.get('avg_oos_score'))))
    scored_rows = [row for row in wf_instrument_rows if row.get('status') in {'pass', 'partial', 'fail'} and row.get('avg_oos_score') is not None]
    pass_rate_pct = round((sum(1 for row in scored_rows if row.get('status') == 'pass') / len(scored_rows)) * 100.0, 2) if scored_rows else 0.0
    avg_oos_score = round(mean([_safe_float(row.get('avg_oos_score')) for row in scored_rows]), 4) if scored_rows else 0.0
    avg_oos_pf = round(mean([_safe_float(row.get('avg_oos_profit_factor')) for row in scored_rows]), 4) if scored_rows else 0.0
    walk_status = _walk_forward_status(instruments=len(scored_rows), pass_rate_pct=pass_rate_pct, avg_oos_score=avg_oos_score, avg_oos_pf=avg_oos_pf)

    wf_strategy_rows = []
    for strategy_name, stat in walk_strategy_rows.items():
        instruments_count = len(stat['instruments'])
        avg_score = round(mean(stat['oos_scores']), 4) if stat['oos_scores'] else 0.0
        avg_pf = round(mean(stat['oos_pfs']), 4) if stat['oos_pfs'] else 0.0
        wf_strategy_rows.append({
            'strategy': strategy_name,
            'instruments': instruments_count,
            'selected_count': int(stat['selected']),
            'pass_count': int(stat['passes']),
            'fail_count': int(stat['fails']),
            'avg_oos_score': avg_score,
            'avg_oos_profit_factor_proxy': avg_pf,
        })
    wf_strategy_rows.sort(key=lambda row: (-row['selected_count'], -row['avg_oos_score'], row['strategy']))

    overall_recommendations: list[str] = []
    if worst_combo and worst_combo.get('status') == 'fail':
        overall_recommendations.append(
            f"Худший реальный slice {worst_combo.get('slice')} даёт expectancy {worst_combo.get('expectancy_per_trade')} и PnL {worst_combo.get('pnl')}: его стоит жёстче дросселировать или исключать."
        )
    if best_combo and best_combo.get('status') == 'pass':
        overall_recommendations.append(
            f"Лучший реальный slice {best_combo.get('slice')} стабилен: можно усиливать аллокацию и приоритет входов для этого сочетания стратегия+режим."
        )
    if walk_status == 'fail':
        overall_recommendations.append('Walk-forward слабый: out-of-sample слой пока не доказывает устойчивость, значит нельзя считать систему готовой к live без дальнейшей селекции режимов и стратегий.')
    elif walk_status == 'partial':
        overall_recommendations.append('Walk-forward частично подтверждает edge: нужны жёсткие whitelist/blacklist по инструментам и стратегиям, а не равномерное доверие ко всему watchlist.')
    if regime_table and all(row.get('status') == 'fail' for row in regime_table[: min(3, len(regime_table))]):
        overall_recommendations.append('Regime-sliced аудит слабый почти во всех режимах: проблема уже не в одном инструменте, а в общей устойчивости decision/execution слоя.')

    return {
        'period_days': days,
        'post_trade_attribution': {
            'status': 'pass' if strategy_table and any(row.get('status') == 'pass' for row in strategy_table) else ('partial' if strategy_table else 'insufficient_data'),
            'closed_trades_count': len(positions),
            'strategy_rows': strategy_table[:12],
            'regime_rows': regime_table[:12],
            'strategy_regime_rows': combo_table[:16],
            'session_rows': session_table[:8],
            'best_slice': best_combo,
            'worst_slice': worst_combo,
        },
        'walk_forward': {
            'status': walk_status,
            'timeframe': timeframe,
            'history_limit': history_limit,
            'folds': folds,
            'active_strategies': active_strategy_names,
            'candidate_instruments': candidate_instruments,
            'considered_instruments_count': len(candidate_instruments),
            'scored_instruments_count': len(scored_rows),
            'pass_rate_pct': pass_rate_pct,
            'avg_oos_score': avg_oos_score,
            'avg_oos_profit_factor': avg_oos_pf,
            'instrument_rows': wf_instrument_rows[:12],
            'strategy_rows': wf_strategy_rows[:10],
        },
        'regime_sliced_audit': {
            'status': 'pass' if regime_table and any(row.get('status') == 'pass' for row in regime_table) else ('partial' if regime_table else 'insufficient_data'),
            'regime_rows': regime_table[:12],
            'session_rows': session_table[:8],
            'dominant_draggers': [row for row in combo_table if row.get('status') == 'fail'][:6],
            'dominant_winners': [row for row in combo_table if row.get('status') == 'pass'][:6],
        },
        'recommendations': overall_recommendations,
    }
