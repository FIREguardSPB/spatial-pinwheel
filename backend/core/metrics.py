"""
P3-06: Prometheus metrics for the trading bot.

Exposes /metrics endpoint (internal only — nginx blocks from public).

Custom metrics:
  signals_total          — counter by decision (TAKE/SKIP/REJECT) and instrument
  trades_total           — counter by side (BUY/SELL)
  pnl_gauge              — current day realized PnL
  open_positions_gauge   — number of open positions
  signal_score_histogram — distribution of decision engine scores
  request_latency        — HTTP request duration (from prometheus-fastapi-instrumentator)
"""

try:
    from prometheus_client import Counter, Gauge, Histogram, CollectorRegistry, REGISTRY
    _HAS_PROMETHEUS = True
except ImportError:
    _HAS_PROMETHEUS = False


def _make_metrics():
    if not _HAS_PROMETHEUS:
        return None

    class _Metrics:
        signals_total = Counter(
            "trading_signals_total",
            "Total signals generated, labelled by decision and instrument",
            ["decision", "instrument", "side"],
        )
        trades_total = Counter(
            "trading_trades_total",
            "Total trades executed",
            ["side", "instrument"],
        )
        pnl_gauge = Gauge(
            "trading_day_pnl_rub",
            "Realized PnL for today in rubles",
        )
        open_positions_gauge = Gauge(
            "trading_open_positions",
            "Number of currently open positions",
        )
        risk_blocked_total = Counter(
            "trading_risk_blocked_total",
            "Signals blocked by RiskManager",
            ["reason"],
        )
        signal_score_histogram = Histogram(
            "trading_signal_score",
            "Decision engine score distribution",
            buckets=[10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
        )
        worker_ticks_total = Counter(
            "trading_worker_ticks_total",
            "Total market ticks processed by worker",
            ["instrument"],
        )

    return _Metrics()


# Singleton — import this in worker and API
metrics = _make_metrics()


def record_signal(decision: str, instrument: str, side: str, score: int) -> None:
    """Called after DecisionEngine.evaluate()."""
    if not metrics:
        return
    metrics.signals_total.labels(
        decision=decision, instrument=instrument, side=side
    ).inc()
    metrics.signal_score_histogram.observe(score)


def record_trade(side: str, instrument: str) -> None:
    """Called after PaperExecutionEngine fills an order."""
    if not metrics:
        return
    metrics.trades_total.labels(side=side, instrument=instrument).inc()


def record_risk_block(reason_prefix: str) -> None:
    """Called when RiskManager blocks a signal."""
    if not metrics:
        return
    # Bucket reason into a short label (first 30 chars, no spaces)
    label = reason_prefix[:30].replace(" ", "_").lower()
    metrics.risk_blocked_total.labels(reason=label).inc()


def update_pnl(day_pnl: float) -> None:
    if metrics:
        metrics.pnl_gauge.set(day_pnl)


def update_open_positions(count: int) -> None:
    if metrics:
        metrics.open_positions_gauge.set(count)


def record_tick(instrument: str) -> None:
    if metrics:
        metrics.worker_ticks_total.labels(instrument=instrument).inc()


def setup_metrics_endpoint(app) -> None:
    """
    Add /metrics endpoint to FastAPI app.
    Protected by nginx — should not be publicly accessible.
    """
    if not _HAS_PROMETHEUS:
        import logging
        logging.getLogger(__name__).warning(
            "prometheus_client not installed — /metrics endpoint not available. "
            "Add prometheus-client to pyproject.toml dependencies."
        )
        return

    from prometheus_client import make_asgi_app
    from starlette.routing import Mount

    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)
