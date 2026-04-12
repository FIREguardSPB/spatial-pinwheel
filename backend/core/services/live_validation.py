from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

try:
    from sqlalchemy.orm import Session
except Exception:  # pragma: no cover
    class Session:  # lightweight tests without sqlalchemy
        pass

try:
    from core.services.business_metrics import build_metrics as _build_metrics
except Exception:  # pragma: no cover
    _build_metrics = None

try:
    from core.services.paper_audit import build_paper_audit as _build_paper_audit
except Exception:  # pragma: no cover
    _build_paper_audit = None


def build_metrics(db: Any, *, days: int) -> dict[str, Any]:
    if _build_metrics is None:  # pragma: no cover
        raise RuntimeError('business_metrics unavailable')
    return _build_metrics(db, days=days)


def build_paper_audit(db: Any, *, days: int) -> dict[str, Any]:
    if _build_paper_audit is None:  # pragma: no cover
        raise RuntimeError('paper_audit unavailable')
    return _build_paper_audit(db, days=days)
from core.storage.decision_log_utils import append_decision_log_best_effort
from core.storage.models import DecisionLog, Position, Signal


@dataclass
class ChecklistThreshold:
    minimum: float | int | None = None
    target: float | int | None = None


def _now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def _ts_days_ago(days: int) -> int:
    return int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp() * 1000)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _status(value: str) -> str:
    return value if value in {"pass", "partial", "fail", "insufficient_data"} else "insufficient_data"


def _grade_numeric(*, value: float | None, minimum: float | None = None, target: float | None = None, inverse: bool = False) -> str:
    if value is None:
        return 'insufficient_data'
    try:
        num = float(value)
    except Exception:
        return 'insufficient_data'
    if minimum is None and target is None:
        return 'insufficient_data'
    if not inverse:
        if target is not None and num >= target:
            return 'pass'
        if minimum is not None and num >= minimum:
            return 'partial'
        return 'fail'
    if target is not None and num <= target:
        return 'pass'
    if minimum is not None and num <= minimum:
        return 'partial'
    return 'fail'


def _pf(pnls: list[float]) -> float | None:
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    if not wins and not losses:
        return None
    if not losses:
        return 999.0
    return round(sum(wins) / abs(sum(losses)), 4)


def _week_key(ts_ms: int) -> str:
    dt = datetime.fromtimestamp(int(ts_ms) / 1000.0, tz=timezone.utc)
    iso = dt.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _extract_signal_meta(signal: Signal | None) -> dict[str, Any]:
    if signal is None:
        return {}
    meta = getattr(signal, 'meta', {}) or {}
    return dict(meta) if isinstance(meta, dict) else {}


def _extract_regime(signal: Signal | None) -> str:
    meta = _extract_signal_meta(signal)
    event_regime = meta.get('event_regime') or {}
    adaptive_plan = meta.get('adaptive_plan') or {}
    for candidate in (
        event_regime.get('regime'),
        adaptive_plan.get('regime'),
        meta.get('regime'),
        meta.get('market_regime'),
    ):
        if candidate:
            return str(candidate)
    return 'unknown'


def _extract_strategy(signal: Signal | None, position: Position | None = None) -> str:
    meta = _extract_signal_meta(signal)
    strategy = meta.get('strategy_name') or getattr(signal, 'strategy_name', None) or getattr(position, 'strategy', None)
    return str(strategy or 'unknown')




def _query_recent(db: Session, model: Any, *, ts_field: str, cutoff: int, require_closed: bool = False) -> list[Any]:
    try:
        query = db.query(model)
        if require_closed:
            query = query.filter(getattr(model, 'qty') == 0)
        query = query.filter(getattr(model, ts_field) >= cutoff).order_by(getattr(model, ts_field).asc())
        return query.all()
    except Exception:
        items = list(db.query(model).all())
        result = []
        for item in items:
            ts = int(getattr(item, ts_field, 0) or 0)
            if require_closed and _safe_float(getattr(item, 'qty', 0.0), 0.0) != 0.0:
                continue
            if ts >= cutoff:
                result.append(item)
        return sorted(result, key=lambda item: int(getattr(item, ts_field, 0) or 0))

def _trend_weekly_status(week_rows: list[dict[str, Any]]) -> dict[str, Any]:
    recent = week_rows[-5:]
    if not recent:
        return {
            'status': 'insufficient_data',
            'target_green_weeks': 4,
            'considered_weeks': 0,
            'green_weeks': 0,
            'red_weeks': 0,
        }
    green = sum(1 for row in recent if row['pnl'] > 0)
    red = sum(1 for row in recent if row['pnl'] < 0)
    if len(recent) < 3:
        status = 'insufficient_data'
    elif green >= 4:
        status = 'pass'
    elif green >= 3:
        status = 'partial'
    else:
        status = 'fail'
    return {
        'status': status,
        'target_green_weeks': 4,
        'considered_weeks': len(recent),
        'green_weeks': green,
        'red_weeks': red,
    }


def _summarize_regimes(regime_rows: list[dict[str, Any]], *, min_trades: int = 5) -> dict[str, Any]:
    meaningful = [row for row in regime_rows if int(row.get('trades', 0) or 0) >= min_trades]
    if not meaningful:
        return {
            'status': 'insufficient_data',
            'meaningful_regimes': 0,
            'passing_regimes': 0,
            'min_trades_per_regime': min_trades,
        }
    passing = 0
    for row in meaningful:
        pf = row.get('profit_factor')
        wr = _safe_float(row.get('win_rate'))
        if (pf is not None and _safe_float(pf) >= 1.20) or wr >= 45.0:
            passing += 1
    ratio = passing / max(1, len(meaningful))
    if ratio >= 1.0:
        status = 'pass'
    elif ratio >= 0.6:
        status = 'partial'
    else:
        status = 'fail'
    return {
        'status': status,
        'meaningful_regimes': len(meaningful),
        'passing_regimes': passing,
        'min_trades_per_regime': min_trades,
    }


def build_live_trader_validation(db: Session, *, days: int = 45, weeks: int = 8) -> dict[str, Any]:
    cutoff = _ts_days_ago(days)
    metrics = build_metrics(db, days=days)
    audit = build_paper_audit(db, days=days)

    signals = _query_recent(db, Signal, ts_field='created_ts', cutoff=cutoff)
    signal_by_id = {str(s.id): s for s in signals}
    positions = _query_recent(db, Position, ts_field='updated_ts', cutoff=cutoff, require_closed=True)

    week_buckets: dict[str, dict[str, Any]] = defaultdict(lambda: {'week': '', 'pnl': 0.0, 'trades': 0, 'wins': 0, 'losses': 0, 'pnls': []})
    regime_buckets: dict[str, dict[str, Any]] = defaultdict(lambda: {'regime': '', 'trades': 0, 'wins': 0, 'losses': 0, 'pnl': 0.0, 'pnls': []})
    strategy_buckets: dict[str, dict[str, Any]] = defaultdict(lambda: {'strategy': '', 'trades': 0, 'wins': 0, 'losses': 0, 'pnl': 0.0, 'pnls': []})

    for pos in positions:
        ts = int(getattr(pos, 'updated_ts', 0) or getattr(pos, 'opened_ts', 0) or 0)
        pnl = _safe_float(getattr(pos, 'realized_pnl', 0.0))
        signal = signal_by_id.get(str(getattr(pos, 'opened_signal_id', '') or ''))
        week = _week_key(ts)
        wb = week_buckets[week]
        wb['week'] = week
        wb['pnl'] += pnl
        wb['trades'] += 1
        wb['pnls'].append(pnl)
        if pnl > 0:
            wb['wins'] += 1
        elif pnl < 0:
            wb['losses'] += 1

        regime = _extract_regime(signal)
        rb = regime_buckets[regime]
        rb['regime'] = regime
        rb['trades'] += 1
        rb['pnl'] += pnl
        rb['pnls'].append(pnl)
        if pnl > 0:
            rb['wins'] += 1
        elif pnl < 0:
            rb['losses'] += 1

        strategy = _extract_strategy(signal, pos)
        sb = strategy_buckets[strategy]
        sb['strategy'] = strategy
        sb['trades'] += 1
        sb['pnl'] += pnl
        sb['pnls'].append(pnl)
        if pnl > 0:
            sb['wins'] += 1
        elif pnl < 0:
            sb['losses'] += 1

    week_rows: list[dict[str, Any]] = []
    for week in sorted(week_buckets.keys())[-max(1, weeks):]:
        row = week_buckets[week]
        trades = int(row['trades'])
        week_rows.append({
            'week': week,
            'pnl': round(_safe_float(row['pnl']), 2),
            'trades': trades,
            'wins': int(row['wins']),
            'losses': int(row['losses']),
            'win_rate': round((int(row['wins']) / trades) * 100.0, 2) if trades else 0.0,
            'profit_factor': _pf([_safe_float(p) for p in row['pnls']]),
            'expectancy_per_trade': round(_safe_float(row['pnl']) / trades, 2) if trades else 0.0,
        })

    regime_rows: list[dict[str, Any]] = []
    for regime in sorted(regime_buckets.keys()):
        row = regime_buckets[regime]
        trades = int(row['trades'])
        regime_rows.append({
            'regime': regime,
            'trades': trades,
            'pnl': round(_safe_float(row['pnl']), 2),
            'win_rate': round((int(row['wins']) / trades) * 100.0, 2) if trades else 0.0,
            'profit_factor': _pf([_safe_float(p) for p in row['pnls']]),
            'expectancy_per_trade': round(_safe_float(row['pnl']) / trades, 2) if trades else 0.0,
        })
    regime_rows.sort(key=lambda item: (-int(item['trades']), item['regime']))

    strategy_rows: list[dict[str, Any]] = []
    for strategy in sorted(strategy_buckets.keys()):
        row = strategy_buckets[strategy]
        trades = int(row['trades'])
        strategy_rows.append({
            'strategy': strategy,
            'trades': trades,
            'pnl': round(_safe_float(row['pnl']), 2),
            'win_rate': round((int(row['wins']) / trades) * 100.0, 2) if trades else 0.0,
            'profit_factor': _pf([_safe_float(p) for p in row['pnls']]),
            'expectancy_per_trade': round(_safe_float(row['pnl']) / trades, 2) if trades else 0.0,
        })
    strategy_rows.sort(key=lambda item: (-int(item['trades']), item['strategy']))

    avg_loss = abs(_safe_float(metrics.get('avg_loss_per_trade')))
    expectancy_r = None
    if avg_loss > 1e-9:
        expectancy_r = round(_safe_float(metrics.get('expectancy_per_trade')) / avg_loss, 4)

    weekly_status = _trend_weekly_status(week_rows)
    regime_status = _summarize_regimes(regime_rows, min_trades=5)
    capture_ratio = _safe_float(audit.get('exit_diagnostics', {}).get('avg_mfe_capture_ratio'))
    slippage_bps = _safe_float(audit.get('exit_diagnostics', {}).get('avg_adverse_slippage_bps'))
    execution_errors = int(metrics.get('execution_error_count') or 0)
    concentration = _safe_float(metrics.get('portfolio_concentration_pct'))

    execution_status = 'pass' if capture_ratio >= 0.45 and execution_errors == 0 and slippage_bps <= 12.0 else (
        'partial' if capture_ratio >= 0.30 and execution_errors <= 2 and slippage_bps <= 25.0 else 'fail'
    )
    portfolio_status = 'pass' if concentration <= 30.0 else ('partial' if concentration <= 35.0 else 'fail')
    post_trade_ready = bool(positions) and all(
        key in audit.get('exit_diagnostics', {})
        for key in ('avg_mfe_pct', 'avg_mae_pct', 'avg_mfe_capture_ratio', 'avg_mae_recovery_ratio')
    )
    post_trade_status = 'pass' if post_trade_ready else ('insufficient_data' if not positions else 'partial')

    checklist = [
        {
            'key': 'profit_factor',
            'label': 'Profit Factor',
            'status': _grade_numeric(value=metrics.get('profit_factor'), minimum=1.30, target=1.50),
            'value': metrics.get('profit_factor'),
            'thresholds': {'minimum': 1.30, 'target': 1.50},
            'details': 'Минимум 1.30, комфортно 1.50+.',
        },
        {
            'key': 'expectancy_r',
            'label': 'Expectancy per trade',
            'status': _grade_numeric(value=expectancy_r, minimum=0.0, target=0.15),
            'value': expectancy_r,
            'thresholds': {'minimum': 0.0, 'target': 0.15},
            'details': 'Нормированная expectancy в долях средней убыточной сделки.',
        },
        {
            'key': 'max_drawdown_pct',
            'label': 'Max Drawdown',
            'status': _grade_numeric(value=metrics.get('max_drawdown_pct'), minimum=12.0, target=8.0, inverse=True),
            'value': metrics.get('max_drawdown_pct'),
            'thresholds': {'maximum_partial': 12.0, 'maximum_target': 8.0},
            'details': 'До 8% хорошо, до 12% терпимо.',
        },
        {
            'key': 'regime_hit_rate',
            'label': 'Hit rate by regime',
            'status': regime_status['status'],
            'value': regime_status,
            'thresholds': {'min_trades_per_regime': 5, 'win_rate_target': 45.0, 'profit_factor_min': 1.20},
            'details': 'В каждом значимом режиме нужен WR ≥ 45% или PF ≥ 1.20.',
        },
        {
            'key': 'weekly_stability',
            'label': 'Weekly stability',
            'status': weekly_status['status'],
            'value': weekly_status,
            'thresholds': {'target_green_weeks': 4, 'window_weeks': min(5, len(week_rows))},
            'details': 'Цель — минимум 4 зелёные недели из последних 5.',
        },
        {
            'key': 'execution_quality',
            'label': 'Execution quality',
            'status': execution_status,
            'value': {
                'avg_mfe_capture_ratio': capture_ratio,
                'avg_adverse_slippage_bps': slippage_bps,
                'execution_error_count': execution_errors,
            },
            'thresholds': {'mfe_capture_target': 0.45, 'mfe_capture_partial': 0.30, 'slippage_bps_target': 12.0, 'slippage_bps_partial': 25.0},
            'details': 'Capture должен быть высоким, а execution errors близки к нулю.',
        },
        {
            'key': 'portfolio_discipline',
            'label': 'Portfolio discipline',
            'status': portfolio_status,
            'value': {
                'portfolio_concentration_pct': concentration,
                'optimizer_adjustments_count': int(metrics.get('portfolio_optimizer_adjustments_count') or 0),
                'capital_reallocations_count': int(metrics.get('capital_reallocations_count') or 0),
            },
            'thresholds': {'concentration_target_pct': 30.0, 'concentration_partial_pct': 35.0},
            'details': 'Крупнейшая позиция не должна чрезмерно доминировать open book.',
        },
        {
            'key': 'post_trade_analytics',
            'label': 'Post-trade analytics maturity',
            'status': post_trade_status,
            'value': {
                'avg_mfe_pct': audit.get('exit_diagnostics', {}).get('avg_mfe_pct'),
                'avg_mae_pct': audit.get('exit_diagnostics', {}).get('avg_mae_pct'),
                'avg_mfe_capture_ratio': audit.get('exit_diagnostics', {}).get('avg_mfe_capture_ratio'),
                'avg_mae_recovery_ratio': audit.get('exit_diagnostics', {}).get('avg_mae_recovery_ratio'),
            },
            'thresholds': {'required_fields': ['avg_mfe_pct', 'avg_mae_pct', 'avg_mfe_capture_ratio', 'avg_mae_recovery_ratio']},
            'details': 'MAE/MFE и capture/recovery должны быть доступны на всей жизни позиции.',
        },
    ]

    status_counts = Counter(_status(item['status']) for item in checklist)
    if status_counts['fail'] > 0:
        overall = 'fail'
    elif status_counts['partial'] > 0:
        overall = 'partial'
    elif status_counts['pass'] > 0:
        overall = 'pass'
    else:
        overall = 'insufficient_data'

    recommendations: list[str] = []
    if _status(checklist[0]['status']) == 'fail':
        recommendations.append('Profit Factor ниже рабочего минимума — не переводить стратегию из auto_paper ближе к live без пересмотра входов и выходов.')
    if _status(checklist[1]['status']) == 'fail':
        recommendations.append('Expectancy неположительная — бот в среднем не создаёт положительное ожидание на сделку.')
    if _status(checklist[2]['status']) == 'fail':
        recommendations.append('Drawdown превышает допустимый диапазон — усилить PM throttle или снизить базовый risk_per_trade_pct.')
    if weekly_status['status'] == 'fail':
        recommendations.append('Нестабильность по неделям — нужна дотяжка режима/сессии или более жёсткий portfolio gate.')
    if regime_status['status'] == 'fail':
        recommendations.append('Есть рыночные режимы, в которых бот статистически слаб — стоит резать торговлю в этих режимах или повышать timeframe floor.')
    if execution_status == 'fail':
        recommendations.append('Execution quality слабое — бот недобирает MFE или слишком часто допускает execution errors/slippage.')
    if portfolio_status == 'fail':
        recommendations.append('Портфель слишком концентрирован — optimizer/allocator ещё не удерживают риск-вклад в рабочих пределах.')

    summary = {
        'days': days,
        'weeks': weeks,
        'overall_status': overall,
        'passed_items': status_counts['pass'],
        'partial_items': status_counts['partial'],
        'failed_items': status_counts['fail'],
        'insufficient_data_items': status_counts['insufficient_data'],
        'trades_count': int(metrics.get('trades_count') or 0),
        'signals_count': int(metrics.get('signals_count') or 0),
        'conversion_rate': _safe_float(metrics.get('conversion_rate')),
        'period_total_pnl': _safe_float(metrics.get('total_pnl')),
    }

    return {
        'summary': summary,
        'checklist': checklist,
        'weekly_rows': week_rows,
        'weekly_stability': weekly_status,
        'regime_rows': regime_rows,
        'strategy_rows': strategy_rows[:20],
        'paper_audit': {
            'summary': audit.get('summary', {}),
            'exit_diagnostics': audit.get('exit_diagnostics', {}),
            'recommendations': audit.get('recommendations', []),
        },
        'metrics_snapshot': {
            'profit_factor': metrics.get('profit_factor'),
            'expectancy_per_trade': metrics.get('expectancy_per_trade'),
            'expectancy_r': expectancy_r,
            'max_drawdown_pct': metrics.get('max_drawdown_pct'),
            'win_rate': metrics.get('win_rate'),
            'avg_realized_to_mfe_capture_ratio': metrics.get('avg_realized_to_mfe_capture_ratio'),
            'execution_error_count': execution_errors,
            'portfolio_concentration_pct': concentration,
        },
        'recommendations': recommendations,
    }


def create_live_validation_snapshot(db: Session, *, days: int = 45, weeks: int = 8, source: str = 'manual') -> dict[str, Any]:
    report = build_live_trader_validation(db, days=days, weeks=weeks)
    summary = dict(report.get('summary') or {})
    append_decision_log_best_effort(
        log_type='live_validation_snapshot',
        message=f"Live trader checklist snapshot ({source}) overall={summary.get('overall_status')}",
        payload={
            'source': source,
            'days': days,
            'weeks': weeks,
            'summary': summary,
            'failed_keys': [item.get('key') for item in report.get('checklist', []) if item.get('status') == 'fail'],
            'partial_keys': [item.get('key') for item in report.get('checklist', []) if item.get('status') == 'partial'],
            'recommendations': report.get('recommendations', [])[:10],
        },
        ts_ms=_now_ms(),
    )
    return report


def list_live_validation_snapshots(db: Session, *, limit: int = 20) -> list[dict[str, Any]]:
    rows = (
        db.query(DecisionLog)
        .filter(DecisionLog.type == 'live_validation_snapshot')
        .order_by(DecisionLog.ts.desc())
        .limit(max(1, min(int(limit), 100)))
        .all()
    )
    items: list[dict[str, Any]] = []
    for row in rows:
        payload = dict(row.payload or {})
        summary = dict(payload.get('summary') or {})
        items.append({
            'id': str(getattr(row, 'id', '')),
            'ts': int(getattr(row, 'ts', 0) or 0),
            'source': str(payload.get('source') or 'unknown'),
            'days': int(payload.get('days') or 0),
            'weeks': int(payload.get('weeks') or 0),
            'summary': summary,
            'failed_keys': list(payload.get('failed_keys') or []),
            'partial_keys': list(payload.get('partial_keys') or []),
            'recommendations': list(payload.get('recommendations') or []),
        })
    return items
