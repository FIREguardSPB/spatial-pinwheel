"""
Worker — торговый цикл.

P3-03: Рефакторинг монолита run_worker() → CandleAggregator + SignalProcessor + MarketPublisher
P3-08: Graceful shutdown через SIGTERM/SIGINT
P2-01: PositionMonitor на каждом тике
P2-06: DB context manager
P2-07: Session end close
P2-08: AccountSnapshot
P1-01: Полная история из aggregator.get_history()
"""
import asyncio
import logging
import orjson
import os
import signal
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from decimal import Decimal

from core.config import settings as config
from core.events.bus import bus
from core.logging import configure_logging
from core.metrics import record_tick, update_open_positions, update_pnl
from core.storage.models import AccountSnapshot, Position, Settings
from core.storage.session import SessionLocal
from core.strategy.selector import StrategySelector
from core.execution.paper import PaperExecutionEngine
from core.execution.monitor import PositionMonitor
from core.utils.session import should_close_before_session_end

from apps.worker.ai.internet.collector import InternetCollector
from apps.worker.aggregator import CandleAggregator
from apps.worker.processor import SignalProcessor
from apps.worker.publisher import MarketPublisher
from apps.worker.market import MarketGenerator

logger = logging.getLogger(__name__)


# ── P2-06: DB context manager ─────────────────────────────────────────────────
@asynccontextmanager
async def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ── P2-08: AccountSnapshot ────────────────────────────────────────────────────
async def _save_snapshot(balance: float, open_pos: int, day_pnl: float) -> None:
    async with get_db() as db:
        db.add(AccountSnapshot(
            ts=int(time.time() * 1000),
            balance=balance,
            equity=balance + day_pnl,
            open_positions=open_pos,
            day_pnl=day_pnl,
        ))
        db.commit()


# ── P3-08: Graceful shutdown flag ─────────────────────────────────────────────
_shutdown = asyncio.Event()

def _handle_signal(sig_name: str) -> None:
    logger.warning("Received %s — initiating graceful shutdown...", sig_name)
    _shutdown.set()


async def run_worker() -> None:
    configure_logging(
        level=os.getenv("LOG_LEVEL", "INFO"),
        json_format=(config.APP_ENV == "production"),
    )
    logger.info("Worker starting (env=%s tf=%s broker=%s)",
                config.APP_ENV, os.getenv("TF", "1m"), config.BROKER_PROVIDER)

    # P3-08: register POSIX signal handlers
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda s=sig: _handle_signal(s.name))

    tf_str = os.getenv("TF", "1m")
    frame_sec = {"1m": 60, "5m": 300, "15m": 900}.get(tf_str, 60)

    # P6-09: load active instruments from watchlist table
    _default_tickers = ["TQBR:SBER", "TQBR:GAZP", "TQBR:LKOH"]
    with SessionLocal() as _wl_db:
        from core.storage.models import Watchlist
        _active = _wl_db.query(Watchlist.instrument_id).filter(Watchlist.is_active == True).all()  # noqa: E712
        tickers = [row[0] for row in _active] if _active else _default_tickers
    if not tickers:
        tickers = _default_tickers
    logger.info("Watchlist loaded: %d instrument(s): %s", len(tickers), tickers)

    # ── Components ─────────────────────────────────────────────────────────────
    # P5-05: Read strategy from Settings (hot-swappable)
    selector = StrategySelector()
    with SessionLocal() as _init_db:
        _s = _init_db.query(Settings).first()
        _strategy_name = getattr(_s, 'strategy_name', 'breakout') if _s else 'breakout'
    strategy = selector.get(_strategy_name)
    aggregator = CandleAggregator(frame_sec=frame_sec)
    publisher = MarketPublisher(tf_str=tf_str)
    # P4-02/08: InternetCollector with Redis caching
    internet = InternetCollector(
        redis_client=bus.redis,
        news_ttl=config.NEWS_CACHE_TTL_SEC,
        macro_ttl=config.MACRO_CACHE_TTL_SEC,
    )
    processor = SignalProcessor(strategy=strategy, internet_collector=internet, aggregator=aggregator)
    monitors: dict[str, PositionMonitor] = {}

    # ── Market stream ──────────────────────────────────────────────────────────
    if config.BROKER_PROVIDER == "tbank" and config.TBANK_TOKEN:
        from apps.broker.tbank import TBankGrpcAdapter
        adapter = TBankGrpcAdapter(
            token=config.TBANK_TOKEN,
            account_id=config.TBANK_ACCOUNT_ID,
            sandbox=config.TBANK_SANDBOX,
        )
        market_stream = adapter.stream_marketdata(tickers)
    else:
        market = MarketGenerator(tickers=tickers)

        async def mock_stream():
            while not _shutdown.is_set():
                for t, c in market.generate_tick().items():
                    yield {
                        "instrument_id": t, "broker_id": None,
                        "time": c["time"],
                        "open": Decimal(str(c["open"])), "high": Decimal(str(c["high"])),
                        "low": Decimal(str(c["low"])), "close": Decimal(str(c["close"])),
                        "volume": c["volume"], "is_complete": False,
                    }
                await asyncio.sleep(1.0)

        market_stream = mock_stream()

    cmd_pubsub = bus.redis.pubsub()
    await cmd_pubsub.subscribe("cmd:execute_signal")
    command_task = asyncio.create_task(_command_listener(cmd_pubsub))

    last_signal_check: dict[str, float] = {t: 0.0 for t in tickers}
    last_snapshot_ts = 0.0
    signal_interval = 60.0
    snapshot_interval = 300.0

    logger.info("Worker running. Instruments: %s", tickers)

    try:
        async for tick in market_stream:
            if _shutdown.is_set():
                break

            ticker = tick["instrument_id"]
            record_tick(ticker)

            # ── Candle aggregation ─────────────────────────────────────────────
            candle, _ = aggregator.on_tick(tick)
            await publisher.publish_candle(candle)

            current_price = candle.close
            now = asyncio.get_running_loop().time()

            # ── P2-01: Position Monitor ────────────────────────────────────────
            async with get_db() as db:
                s = db.query(Settings).first()
                time_stop = int(s.time_stop_bars) if s and s.time_stop_bars else 0
                close_before = int(s.close_before_session_end_minutes) if s and s.close_before_session_end_minutes else 0

                if ticker not in monitors:
                    monitors[ticker] = PositionMonitor(db)
                else:
                    monitors[ticker].db = db

                await monitors[ticker].on_tick(ticker, current_price, time_stop)

                # P2-07: Session end
                if should_close_before_session_end(close_before):
                    await monitors[ticker].close_for_session_end(ticker, current_price)

            # ── P2-08: Snapshot ────────────────────────────────────────────────
            if now - last_snapshot_ts > snapshot_interval:
                last_snapshot_ts = now
                async with get_db() as db:
                    open_pos = db.query(Position).filter(Position.qty > 0).count()
                    # Read real balance from Settings
                    _snap_settings = db.query(Settings).first()
                    _snap_balance = float(getattr(_snap_settings, 'account_balance', 100_000) or 100_000)
                    # Calculate day PnL: sum of realized_pnl updated today + unrealized
                    from sqlalchemy import func
                    _sod = int(datetime.now(timezone.utc).replace(
                        hour=0, minute=0, second=0, microsecond=0
                    ).timestamp() * 1000)
                    _realized_today = float(
                        db.query(func.sum(Position.realized_pnl))
                        .filter(Position.updated_ts >= _sod).scalar() or 0.0
                    )
                    _unrealized = float(
                        db.query(func.sum(Position.unrealized_pnl))
                        .filter(Position.qty > 0).scalar() or 0.0
                    )
                    _day_pnl = _realized_today + _unrealized
                update_open_positions(open_pos)
                await _save_snapshot(_snap_balance, open_pos, _day_pnl)

            # ── Signal cycle ───────────────────────────────────────────────────
            if now - last_signal_check.get(ticker, 0) < signal_interval:
                continue
            last_signal_check[ticker] = now

            async with get_db() as db:
                # P5-05: Hot-swap strategy if changed in Settings
                _cur_settings = db.query(Settings).first()
                _new_strategy_name = getattr(_cur_settings, 'strategy_name', 'breakout') if _cur_settings else 'breakout'
                _new_strategy = selector.get(_new_strategy_name)
                if processor.strategy.name != _new_strategy.name:
                    logger.info("Strategy hot-swapped: %s → %s", processor.strategy.name, _new_strategy.name)
                    processor.strategy = _new_strategy

                history = aggregator.get_history(ticker)
                await processor.process(ticker, history, db)

    except Exception as e:
        logger.error("Worker loop error: %s", e, exc_info=True)
    finally:
        command_task.cancel()
        await _shutdown_cleanup(monitors)


async def _shutdown_cleanup(monitors: dict) -> None:
    """P3-08: Log open positions and close resources."""
    async with get_db() as db:
        open_pos = db.query(Position).filter(Position.qty > 0).all()
        count = len(open_pos)
        if count:
            instruments = [p.instrument_id for p in open_pos]
            logger.warning(
                "Worker shutdown: %d open position(s) remain: %s — NOT auto-closed",
                count, instruments,
            )
        else:
            logger.info("Worker shutdown gracefully. No open positions.")

    try:
        await bus.redis.aclose()
    except Exception:
        pass


async def _command_listener(pubsub) -> None:
    logger.info("Command listener ready")
    while not _shutdown.is_set():
        try:
            msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if msg:
                data = orjson.loads(msg["data"])
                sig_id = data.get("signal_id")
                if sig_id:
                    logger.info("Execute command: signal_id=%s", sig_id)
                    async with get_db() as db:
                        await PaperExecutionEngine(db).execute_approved_signal(sig_id)
            await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("Command listener error: %s", e)
            await asyncio.sleep(1.0)


if __name__ == "__main__":
    asyncio.run(run_worker())
