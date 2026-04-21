"""
Worker — separated market polling and analysis loops.

FIX32 goals:
- decouple REST polling from signal analysis so worker never stalls in polling
- reduce T-Bank API load with tiered polling + runtime watchlist refresh
- add detailed worker stage logging and runtime status reporting
- keep watchlist changes effective without worker restart
"""
from __future__ import annotations

import asyncio
import atexit
import fcntl
import logging
import os
import signal
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from urllib.parse import urlparse

import orjson

from core.config import get_token, settings as config
from core.events.bus import bus
from core.logging import configure_logging
from core.metrics import record_tick, update_open_positions
from core.services.recalibration import run_symbol_recalibration_batch
from core.services.symbol_adaptive import ensure_symbol_profiles, build_symbol_plan
from core.services.trading_schedule import refresh_trading_schedule
from core.ml.runtime import maybe_run_scheduled_training
from core.services.instrument_catalog import sync_sandbox_instruments
from core.sentiment.collector import SentimentCollector
from core.services.worker_status import publish_worker_status
from core.storage.models import AccountSnapshot, Position, Signal
from core.storage.repos import candles as candle_repo
from core.storage.repos import signals as signal_repo
from core.storage.repos import settings as settings_repo
from core.storage.session import SessionLocal
from core.strategy.selector import StrategySelector
from core.execution.monitor import PositionMonitor
from core.execution.controls import prefers_paper_execution
from core.execution.paper import PaperExecutionEngine
from core.execution.tbank import TBankExecutionEngine
from core.utils.session import should_close_before_session_end
from core.utils.time import start_of_day_ms

from apps.worker.aggregator import CandleAggregator
from apps.worker.ai.internet.collector import InternetCollector
from apps.worker.market import MarketGenerator
from apps.worker.processor import SignalProcessor
from apps.worker.publisher import MarketPublisher

logger = logging.getLogger(__name__)

_DEFAULT_TICKERS = [
    "TQBR:SBER",
    "TQBR:GAZP",
    "TQBR:LKOH",
    "TQBR:YNDX",
    "TQBR:ROSN",
    "TQBR:NVTK",
    "TQBR:VTBR",
    "TQBR:MOEX",
    "TQBR:GMKN",
    "TQBR:TATN",
]
_HIGH_PRIORITY_TICKERS = {"TQBR:SBER", "TQBR:GAZP", "TQBR:LKOH", "TQBR:YNDX", "TQBR:VTBR", "TQBR:MOEX"}
_shutdown = asyncio.Event()
_WORKER_LOCK_FD = None


def _acquire_single_instance_lock() -> None:
    global _WORKER_LOCK_FD
    lock_path = os.getenv('WORKER_LOCK_PATH', '/tmp/spatial-pinwheel-worker.lock')
    fd = open(lock_path, 'w')
    try:
        fcntl.flock(fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise RuntimeError(f'Worker already running: lock busy at {lock_path}')
    fd.seek(0)
    fd.truncate()
    fd.write(str(os.getpid()))
    fd.flush()
    _WORKER_LOCK_FD = fd


def _release_single_instance_lock() -> None:
    global _WORKER_LOCK_FD
    if _WORKER_LOCK_FD is None:
        return
    try:
        _WORKER_LOCK_FD.close()
    finally:
        _WORKER_LOCK_FD = None


def _now_ms() -> int:
    return int(time.time() * 1000)


def _flatten_timing_metrics(payload: Any, prefix: str = '') -> dict[str, int]:
    if not isinstance(payload, dict):
        return {}
    flat: dict[str, int] = {}
    for key, value in payload.items():
        name = f'{prefix}.{key}' if prefix else str(key)
        if isinstance(value, bool):
            continue
        if isinstance(value, dict):
            flat.update(_flatten_timing_metrics(value, name))
            continue
        if isinstance(value, (int, float)):
            flat[name] = int(value)
    return flat


def _sanitize_proxy_env() -> None:
    for key in ("all_proxy", "ALL_PROXY", "http_proxy", "HTTP_PROXY", "https_proxy", "HTTPS_PROXY"):
        raw = os.getenv(key)
        if not raw:
            continue
        scheme = urlparse(raw).scheme.lower()
        if scheme == "socks":
            logger.warning("Ignoring unsupported proxy env %s=%s", key, raw)
            os.environ.pop(key, None)


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


async def _save_snapshot(balance: float, open_pos: int, day_pnl: float) -> None:
    async with get_db() as db:
        db.add(AccountSnapshot(
            ts=_now_ms(),
            balance=balance,
            equity=balance + day_pnl,
            open_positions=open_pos,
            day_pnl=day_pnl,
        ))
        db.commit()


def _prime_aggregator(aggregator: CandleAggregator, ticker: str, candles: list[dict]) -> None:
    for candle in candles:
        aggregator.on_tick({
            "instrument_id": ticker,
            "time": candle["time"],
            "open": candle["open"],
            "high": candle["high"],
            "low": candle["low"],
            "close": candle["close"],
            "volume": candle.get("volume", 0),
        })


async def _persist_last_completed_candle(ticker: str, aggregator: CandleAggregator, tf_str: str) -> None:
    history = aggregator.get_history(ticker)
    if len(history) < 2:
        return
    completed = history[-2]
    async with get_db() as db:
        candle_repo.upsert_candles(db, instrument_id=ticker, timeframe=tf_str, candles=[completed], source="worker")


async def _load_cached_history(aggregator: CandleAggregator, tickers: list[str], tf_str: str) -> set[str]:
    primed: set[str] = set()
    history_limit = 600 if tf_str == '1m' else 200
    async with get_db() as db:
        for ticker in tickers:
            cached = candle_repo.list_candles(db, ticker, tf_str, limit=history_limit)
            if not cached:
                continue
            _prime_aggregator(aggregator, ticker, cached)
            primed.add(ticker)
            logger.info("History cache bootstrap for %s: %d candles loaded", ticker, min(len(cached), history_limit))
    return primed


async def _bootstrap_history(adapter, aggregator: CandleAggregator, tickers: list[str], tf_str: str, *, skip_tickers: set[str] | None = None) -> None:
    from datetime import timedelta

    now_dt = datetime.now(timezone.utc)
    history_limit = 600 if tf_str == '1m' else 200
    lookback_by_tf = {
        "1m": timedelta(hours=24),
        "5m": timedelta(days=2),
        "15m": timedelta(days=5),
    }
    from_dt = now_dt - lookback_by_tf.get(tf_str, timedelta(hours=8))
    skip_tickers = skip_tickers or set()

    for ticker in tickers:
        if _shutdown.is_set() or ticker in skip_tickers:
            continue
        try:
            candles = await adapter.get_candles(ticker, from_dt, now_dt, interval_str=tf_str)
        except Exception as exc:
            logger.warning("History bootstrap failed for %s: %s", ticker, exc)
            continue
        if candles:
            _prime_aggregator(aggregator, ticker, candles[-history_limit:])
            with SessionLocal() as cache_db:
                candle_repo.upsert_candles(cache_db, instrument_id=ticker, timeframe=tf_str, candles=candles, source="broker")
            logger.info("History bootstrap for %s: %d candles loaded", ticker, min(len(candles), history_limit))


async def _load_watchlist() -> list[str]:
    from core.storage.models import Watchlist
    from apps.broker.tbank.adapter import normalize_instrument_id

    with SessionLocal() as db:
        active = db.query(Watchlist.instrument_id).filter(Watchlist.is_active == True).all()  # noqa: E712
        tickers = [normalize_instrument_id(row[0]) for row in active] if active else list(_DEFAULT_TICKERS)
    tickers = [t for t in tickers if t]
    return tickers or list(_DEFAULT_TICKERS)


@dataclass
class WorkerRuntimeState:
    tickers: list[str]
    phase: str = "startup"
    message: str = "Worker booting"
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    status: dict[str, Any] = field(default_factory=dict)
    last_signal_check: dict[str, float] = field(default_factory=dict)
    last_poll_ts: dict[str, float] = field(default_factory=dict)
    last_seen_candle: dict[str, tuple] = field(default_factory=dict)
    last_analyzed_candle: dict[str, tuple] = field(default_factory=dict)
    unresolved_instruments: set[str] = field(default_factory=set)
    status_dirty: bool = True

    async def snapshot(self) -> dict[str, Any]:
        async with self.lock:
            return {
                **self.status,
                "phase": self.phase,
                "message": self.message,
                "tickers": list(self.tickers),
                "current_instrument_count": len(self.tickers),
                "unresolved_instruments": sorted(self.unresolved_instruments),
                "updated_ts": _now_ms(),
            }

    async def publish(self) -> None:
        payload = await self.snapshot()
        await publish_worker_status(payload)
        async with self.lock:
            self.status_dirty = False

    async def set_phase(self, phase: str, message: str | None = None, **extra: Any) -> None:
        async with self.lock:
            self.phase = phase
            if message is not None:
                self.message = message
            self.status.update(extra)
            self.status_dirty = True

    async def mark_error(self, where: str, exc: Exception | str) -> None:
        async with self.lock:
            self.status["last_error"] = {
                "where": where,
                "message": str(exc),
                "ts": _now_ms(),
            }
            self.status_dirty = True

    async def get_tickers(self) -> list[str]:
        async with self.lock:
            return list(self.tickers)

    async def replace_tickers(self, tickers: list[str]) -> tuple[list[str], list[str]]:
        tickers = list(dict.fromkeys(tickers))
        async with self.lock:
            prev = set(self.tickers)
            nxt = set(tickers)
            added = sorted(nxt - prev)
            removed = sorted(prev - nxt)
            self.tickers = tickers
            for ticker in tickers:
                self.last_signal_check.setdefault(ticker, 0.0)
                self.last_poll_ts.setdefault(ticker, 0.0)
            for ticker in removed:
                self.last_signal_check.pop(ticker, None)
                self.last_poll_ts.pop(ticker, None)
                self.last_seen_candle.pop(ticker, None)
                self.last_analyzed_candle.pop(ticker, None)
                self.unresolved_instruments.discard(ticker)
            self.status["watchlist_last_reload_ts"] = _now_ms()
            self.status["watchlist_added"] = added
            self.status["watchlist_removed"] = removed
            self.status_dirty = True
            return added, removed

    async def should_poll(self, ticker: str, *, now: float, min_interval_sec: float) -> bool:
        async with self.lock:
            last = self.last_poll_ts.get(ticker, 0.0)
            if now - last < min_interval_sec:
                return False
            self.last_poll_ts[ticker] = now
            return True

    async def remember_candle(self, ticker: str, candle: dict) -> bool:
        key = (
            candle["time"],
            str(candle["open"]),
            str(candle["high"]),
            str(candle["low"]),
            str(candle["close"]),
            int(candle.get("volume", 0)),
        )
        async with self.lock:
            changed = self.last_seen_candle.get(ticker) != key
            self.last_seen_candle[ticker] = key
            return changed

    async def note_unresolved(self, ticker: str) -> None:
        async with self.lock:
            self.unresolved_instruments.add(ticker)
            self.status_dirty = True

    async def note_resolved(self, ticker: str) -> None:
        async with self.lock:
            if ticker in self.unresolved_instruments:
                self.unresolved_instruments.discard(ticker)
                self.status_dirty = True

    async def should_analyze(self, ticker: str, *, now: float, signal_interval_sec: float) -> bool:
        async with self.lock:
            latest_candle = self.last_seen_candle.get(ticker)
            if latest_candle is None:
                return False

            last_analyzed_candle = self.last_analyzed_candle.get(ticker)
            if last_analyzed_candle == latest_candle:
                return False

            last = self.last_signal_check.get(ticker, 0.0)
            if now - last < signal_interval_sec:
                return False

            self.last_signal_check[ticker] = now
            self.last_analyzed_candle[ticker] = latest_candle
            return True


def _handle_signal(sig_name: str) -> None:
    logger.warning("Received %s — initiating graceful shutdown...", sig_name)
    _shutdown.set()


async def _refresh_watchlist_loop(state: WorkerRuntimeState, adapter, aggregator: CandleAggregator, tf_str: str) -> None:
    refresh_sec = max(5.0, float(os.getenv("WORKER_WATCHLIST_REFRESH_SEC", "10") or "10"))
    bootstrap_limit = max(1, int(os.getenv("WORKER_BOOTSTRAP_LIMIT", "10") or "10"))
    while not _shutdown.is_set():
        try:
            tickers = await _load_watchlist()
            with SessionLocal() as db:
                runtime_settings = settings_repo.get_settings(db)
            bootstrap_limit = max(1, int(getattr(runtime_settings, "worker_bootstrap_limit", bootstrap_limit) or bootstrap_limit))
            added, removed = await state.replace_tickers(tickers)
            if added or removed:
                logger.info("Watchlist refreshed: total=%d added=%s removed=%s", len(tickers), added, removed)
                await state.set_phase(
                    state.phase,
                    f"Watchlist updated: {len(tickers)} instrument(s)",
                    watchlist=tickers,
                )
            if adapter and added:
                await _load_cached_history(aggregator, added, tf_str)
                await _bootstrap_history(adapter, aggregator, added[:bootstrap_limit], tf_str)
            if added:
                with SessionLocal() as db:
                    ensure_result = ensure_symbol_profiles(
                        db,
                        added,
                        auto_train=True,
                        lookback_days=180,
                        timeframe=tf_str,
                        train_limit=min(len(added), bootstrap_limit),
                        source='watchlist_refresh',
                    )
                await state.set_phase(
                    state.phase,
                    state.message,
                    symbol_profiles_last_ensure_ts=_now_ms(),
                    symbol_profiles_last_ensure=ensure_result,
                )
            if added or removed:
                await state.publish()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("Watchlist refresh failed: %s", exc, exc_info=True)
            await state.mark_error("watchlist_refresh", exc)
            await state.publish()
        await asyncio.sleep(refresh_sec)


async def _apply_tick(aggregator: CandleAggregator, publisher: MarketPublisher, ticker: str, candle: dict, tf_str: str) -> None:
    tick = {
        "instrument_id": ticker,
        "time": candle["time"],
        "open": candle["open"],
        "high": candle["high"],
        "low": candle["low"],
        "close": candle["close"],
        "volume": candle.get("volume", 0),
    }
    aggregated, bar_closed = aggregator.on_tick(tick)
    await publisher.publish_candle(aggregated)
    if bar_closed:
        await _persist_last_completed_candle(ticker, aggregator, tf_str)



async def _run_recalibration_loop(state: WorkerRuntimeState) -> None:
    while not _shutdown.is_set():
        try:
            with SessionLocal() as db:
                result = run_symbol_recalibration_batch(db, force=False, source='worker_schedule')
            if result.get('started'):
                await state.set_phase(
                    state.phase,
                    state.message,
                    recalibration={
                        'last_run_ts': _now_ms(),
                        'completed': int((result.get('summary') or {}).get('completed') or 0),
                        'errors': int((result.get('summary') or {}).get('errors') or 0),
                        'instrument_ids': (result.get('summary') or {}).get('instrument_ids') or [],
                    },
                )
                await state.publish()
                logger.info('Scheduled recalibration finished: %s', result.get('summary'))
        except Exception as exc:
            logger.error('Scheduled recalibration loop failed: %s', exc, exc_info=True)
            await state.mark_error('worker-recalibration', exc)
            await state.publish()
        await asyncio.sleep(60.0)



async def _run_ml_training_loop(state: WorkerRuntimeState) -> None:
    while not _shutdown.is_set():
        try:
            with SessionLocal() as db:
                runtime_settings = settings_repo.get_settings(db)
                result = maybe_run_scheduled_training(db, runtime_settings, source='worker_schedule')
            if result.get('started'):
                await state.set_phase(
                    state.phase,
                    state.message,
                    ml_training={
                        'last_run_ts': _now_ms(),
                        'results': result.get('results') or [],
                    },
                )
                await state.publish()
                logger.info('Scheduled ML training finished: %s', result.get('results'))
        except Exception as exc:
            logger.error('Scheduled ML training loop failed: %s', exc, exc_info=True)
            await state.mark_error('worker-ml-training', exc)
            await state.publish()
        await asyncio.sleep(300.0)


async def _run_instrument_auto_sync_loop(state: WorkerRuntimeState, adapter_factory) -> None:
    last_run_ts = 0
    while not _shutdown.is_set():
        try:
            with SessionLocal() as db:
                runtime_settings = settings_repo.get_settings(db)
                enabled = bool(getattr(runtime_settings, 'instrument_auto_sync_enabled', False))
                interval_hours = max(1, int(getattr(runtime_settings, 'instrument_auto_sync_interval_hours', 24) or 24))
                now_ms = _now_ms()
                due = last_run_ts <= 0 or (now_ms - last_run_ts) >= interval_hours * 3600 * 1000
                if enabled and due:
                    result = await sync_sandbox_instruments(
                        db,
                        adapter_factory=adapter_factory,
                        limit=200,
                        auto_train=True,
                    )
                    last_run_ts = now_ms
                    await state.set_phase(
                        state.phase,
                        state.message,
                        instrument_auto_sync={
                            'last_run_ts': now_ms,
                            'enabled': enabled,
                            'interval_hours': interval_hours,
                            'added': int(result.get('added') or 0),
                            'existing': int(result.get('existing') or 0),
                            'errors': result.get('errors') or [],
                        },
                    )
                    await state.publish()
                    logger.info('Instrument auto-sync finished: %s', result)
                elif not enabled:
                    await state.set_phase(
                        state.phase,
                        state.message,
                        instrument_auto_sync={
                            'last_run_ts': last_run_ts or None,
                            'enabled': False,
                            'interval_hours': interval_hours,
                        },
                    )
        except Exception as exc:
            logger.error('Instrument auto-sync loop failed: %s', exc, exc_info=True)
            await state.mark_error('worker-instrument-auto-sync', exc)
            await state.publish()
        await asyncio.sleep(300.0)


async def _run_sentiment_collection_loop(state: WorkerRuntimeState) -> None:
    last_run_ts = 0
    while not _shutdown.is_set():
        try:
            with SessionLocal() as db:
                runtime_settings = settings_repo.get_settings(db)
                enabled = bool(getattr(runtime_settings, 'sentiment_collection_enabled', False))
                interval_minutes = max(5, int(getattr(runtime_settings, 'sentiment_poll_interval_minutes', 60) or 60))
                now_ms = _now_ms()
                due = last_run_ts <= 0 or (now_ms - last_run_ts) >= interval_minutes * 60 * 1000
                if enabled and due:
                    collector = SentimentCollector(db)
                    result = await collector.collect_once(runtime_settings, force=False)
                    last_run_ts = now_ms
                    await state.set_phase(
                        state.phase,
                        state.message,
                        sentiment_collection={
                            'last_run_ts': now_ms,
                            'enabled': enabled,
                            'interval_minutes': interval_minutes,
                            'inserted': int(result.get('inserted') or 0),
                            'duplicates': int(result.get('skipped_duplicates') or 0),
                            'errors': result.get('error_messages') or [],
                        },
                    )
                    await state.publish()
                    logger.info('Sentiment collection finished: %s', result)
                elif not enabled:
                    await state.set_phase(
                        state.phase,
                        state.message,
                        sentiment_collection={
                            'last_run_ts': last_run_ts or None,
                            'enabled': False,
                            'interval_minutes': interval_minutes,
                        },
                    )
        except Exception as exc:
            logger.error('Sentiment collection loop failed: %s', exc, exc_info=True)
            await state.mark_error('worker-sentiment-collection', exc)
            await state.publish()
        await asyncio.sleep(300.0)


async def _run_status_heartbeat_loop(state: WorkerRuntimeState) -> None:
    while not _shutdown.is_set():
        try:
            await state.publish()
        except Exception as exc:
            logger.warning('Worker status heartbeat publish failed: %s', exc, exc_info=True)
        await asyncio.sleep(60.0)


async def _run_symbol_profile_bootstrap_task(state: WorkerRuntimeState, tickers: list[str], *, train_limit: int, timeframe: str, source: str) -> None:
    try:
        with SessionLocal() as db:
            ensure_result = ensure_symbol_profiles(
                db,
                tickers,
                auto_train=True,
                lookback_days=180,
                timeframe=timeframe,
                train_limit=train_limit,
                source=source,
            )
        await state.set_phase(state.phase, state.message, symbol_profiles_bootstrap=ensure_result)
        await state.publish()
    except Exception as exc:
        logger.error('Symbol profile bootstrap task failed: %s', exc, exc_info=True)
        await state.mark_error('symbol_profile_bootstrap', exc)
        await state.publish()


def _is_optional_worker_task(task_name: str) -> bool:
    return task_name in {'worker-symbol-profile-bootstrap'}


async def _run_tbank_polling_loop(adapter, aggregator: CandleAggregator, publisher: MarketPublisher, state: WorkerRuntimeState, tf_str: str) -> None:
    high_priority_interval = max(3.0, float(os.getenv("WORKER_CORE_POLL_SEC", "5") or "5"))
    low_priority_interval = max(high_priority_interval, float(os.getenv("WORKER_TAIL_POLL_SEC", "15") or "15"))
    await state.set_phase("polling", "Market polling loop started")
    await state.publish()

    while not _shutdown.is_set():
        tickers = await state.get_tickers()
        cycle_started = _now_ms()
        processed = 0
        changed = 0
        errors = 0
        unresolved: list[str] = []
        await state.set_phase("polling", f"Polling {len(tickers)} instrument(s)", last_poll_iteration_started_ts=cycle_started)
        logger.info("Polling iteration started: instruments=%d", len(tickers))
        now_loop = asyncio.get_running_loop().time()
        now_dt = datetime.now(timezone.utc)
        from_dt = now_dt.replace(second=0, microsecond=0) - timedelta(minutes=3)

        for ticker in tickers:
            if _shutdown.is_set():
                break
            min_interval = high_priority_interval if ticker in _HIGH_PRIORITY_TICKERS else low_priority_interval
            if not await state.should_poll(ticker, now=now_loop, min_interval_sec=min_interval):
                continue
            processed += 1
            try:
                candles = await adapter.get_candles(ticker, from_dt, now_dt, interval_str=tf_str)
            except Exception as exc:
                errors += 1
                text = str(exc)
                if "not found" in text.lower():
                    unresolved.append(ticker)
                    await state.note_unresolved(ticker)
                logger.warning("Polling failed for %s: %s", ticker, exc)
                continue

            if not candles:
                continue
            await state.note_resolved(ticker)
            candle = candles[-1]
            is_changed = await state.remember_candle(ticker, candle)
            if is_changed:
                changed += 1
            record_tick(ticker)
            await _apply_tick(aggregator, publisher, ticker, candle, tf_str)
            logger.debug("Polling candle %s t=%s changed=%s", ticker, candle.get("time"), is_changed)

        finished_ts = _now_ms()
        await state.set_phase(
            "idle",
            f"Polling cycle done: processed={processed}, changed={changed}",
            last_poll_iteration_finished_ts=finished_ts,
            last_poll_stats={
                "processed": processed,
                "changed": changed,
                "errors": errors,
                "duration_ms": finished_ts - cycle_started,
                "unresolved_instruments": unresolved,
            },
            tbank_stats=adapter.get_runtime_stats() if hasattr(adapter, "get_runtime_stats") else None,
        )
        await state.publish()
        logger.info(
            "Polling iteration finished: processed=%d changed=%d errors=%d duration_ms=%d",
            processed,
            changed,
            errors,
            finished_ts - cycle_started,
        )
        await asyncio.sleep(1.0)


async def _run_mock_polling_loop(aggregator: CandleAggregator, publisher: MarketPublisher, state: WorkerRuntimeState, tf_str: str) -> None:
    market = MarketGenerator(tickers=await state.get_tickers())
    await state.set_phase("polling", "Mock market polling loop started")
    await state.publish()
    while not _shutdown.is_set():
        tickers = await state.get_tickers()
        market.tickers = tickers
        generated = market.generate_tick()
        for ticker, candle in generated.items():
            record_tick(ticker)
            await state.remember_candle(ticker, candle)
            await _apply_tick(aggregator, publisher, ticker, candle, tf_str)
        await state.set_phase("idle", f"Mock cycle done: processed={len(generated)}", last_poll_stats={"processed": len(generated), "changed": len(generated), "errors": 0})
        await state.publish()
        await asyncio.sleep(1.0)


async def _run_analysis_loop(
    *,
    selector: StrategySelector,
    processor: SignalProcessor,
    aggregator: CandleAggregator,
    monitors: dict[str, PositionMonitor],
    state: WorkerRuntimeState,
    runtime_tbank_token: str | None,
    runtime_tbank_account: str | None,
) -> None:
    signal_interval = max(3.0, float(os.getenv("WORKER_SIGNAL_INTERVAL_SEC", "5") or "5"))
    snapshot_interval = max(30.0, float(os.getenv("WORKER_SNAPSHOT_INTERVAL_SEC", "300") or "300"))
    schedule_refresh_interval = max(60.0, float(os.getenv("WORKER_SCHEDULE_REFRESH_SEC", "900") or "900"))
    last_snapshot_ts = 0.0
    last_schedule_refresh_ts = 0.0

    while not _shutdown.is_set():
        cycle_started = _now_ms()
        tickers = await state.get_tickers()
        processed = 0
        takes = 0
        skipped = 0
        timing_samples = 0
        timing_totals: dict[str, int] = {}
        slowest_analysis: dict[str, Any] | None = None
        last_analysis_result: dict[str, Any] | None = None
        await state.set_phase("analysis", f"Analysis cycle started for {len(tickers)} instrument(s)", last_analysis_started_ts=cycle_started)
        logger.info("Cycle started: instruments=%d", len(tickers))

        now_loop = asyncio.get_running_loop().time()
        for ticker in tickers:
            if _shutdown.is_set():
                break
            if not await state.should_analyze(ticker, now=now_loop, signal_interval_sec=signal_interval):
                continue
            history = aggregator.get_history(ticker)
            logger.info("Instrument processing: %s history_len=%d", ticker, len(history))

            async with get_db() as db:
                settings = settings_repo.get_settings(db)
                if settings and not bool(getattr(settings, "bot_enabled", False)):
                    logger.info("Analysis paused because bot is disabled")
                    await state.set_phase("idle", "Bot disabled — analysis paused")
                    await state.publish()
                    await asyncio.sleep(2.0)
                    break

                adaptive_plan = build_symbol_plan(db, ticker, history, settings) if history else None
                if adaptive_plan:
                    logger.info("Adaptive plan: %s regime=%s strategy=%s threshold=%s hold=%s reentry=%ss risk_x=%.2f", ticker, adaptive_plan.regime, adaptive_plan.strategy_name, adaptive_plan.decision_threshold, adaptive_plan.hold_bars, adaptive_plan.reentry_cooldown_sec, adaptive_plan.risk_multiplier)
                new_strategy_name = adaptive_plan.strategy_name if adaptive_plan else (getattr(settings, "strategy_name", "breakout,mean_reversion") if settings else "breakout,mean_reversion")
                new_strategy = selector.get(new_strategy_name)
                if len(history) < new_strategy.lookback:
                    skipped += 1
                    logger.debug("Instrument skipped: %s history too short (%d < %d)", ticker, len(history), new_strategy.lookback)
                    continue
                processed += 1
                async with state.lock:
                    state.status["last_processed_instrument"] = ticker
                    state.status["last_processed_ts"] = _now_ms()
                if processor.strategy.name != new_strategy.name:
                    logger.info("Strategy hot-swapped: %s → %s", processor.strategy.name, new_strategy.name)
                    processor.strategy = new_strategy

                current_price = history[-1]["close"]
                time_stop = int(getattr(settings, "time_stop_bars", 0) or 0)
                close_before = int(getattr(settings, "close_before_session_end_minutes", 0) or 0)
                session_mode = getattr(settings, "trading_session", None) or getattr(settings, "session_type", None) or "all"

                if ticker not in monitors:
                    monitors[ticker] = PositionMonitor(db)
                else:
                    monitors[ticker].db = db
                await monitors[ticker].on_tick(ticker, current_price, time_stop, history=history)
                if should_close_before_session_end(close_before, session_type=session_mode):
                    await monitors[ticker].close_for_session_end(ticker, current_price)

                if now_loop - last_schedule_refresh_ts > schedule_refresh_interval and config.BROKER_PROVIDER == "tbank" and runtime_tbank_token:
                    last_schedule_refresh_ts = now_loop
                    if settings and bool(getattr(settings, "use_broker_trading_schedule", True)):
                        await refresh_trading_schedule(exchange=(getattr(settings, "trading_schedule_exchange", None) or None), force=False)

                result = await processor.process(ticker, history, db, adaptive_plan=(adaptive_plan.to_meta() if adaptive_plan else None))
                telemetry = dict(result.get('telemetry') or {}) if isinstance(result, dict) else {}
                flat_timings = _flatten_timing_metrics(telemetry)
                if flat_timings:
                    timing_samples += 1
                    for metric, value in flat_timings.items():
                        timing_totals[metric] = timing_totals.get(metric, 0) + int(value)
                result_total_ms = int(flat_timings.get('total_ms') or 0)
                result_summary = {
                    'ticker': ticker,
                    'outcome': result.get('outcome') if isinstance(result, dict) else None,
                    'created_signal': bool(result.get('created_signal')) if isinstance(result, dict) else False,
                    'final_decision': result.get('final_decision') if isinstance(result, dict) else None,
                    'status': result.get('status') if isinstance(result, dict) else None,
                    'signal_id': result.get('signal_id') if isinstance(result, dict) else None,
                    'timings_ms': telemetry,
                }
                last_analysis_result = result_summary
                if result_total_ms and (slowest_analysis is None or result_total_ms > int((_flatten_timing_metrics(slowest_analysis.get('timings_ms') or {}).get('total_ms') or 0))):
                    slowest_analysis = result_summary

                if result.get('created_signal'):
                    logger.info(
                        "DE analysis completed: %s final=%s status=%s total_ms=%s",
                        ticker,
                        result.get('final_decision'),
                        result.get('status'),
                        telemetry.get('total_ms'),
                    )
                    logger.info("%s: stage timings %s", ticker, telemetry)
                    if result.get('final_decision') == "TAKE":
                        takes += 1
                        await state.set_phase(
                            "analysis",
                            f"TAKE generated for {ticker}",
                            last_take_signal_ts=_now_ms(),
                            last_take_instrument=ticker,
                            last_take_signal_id=result.get('signal_id'),
                            last_signal_profile=result_summary,
                        )
                elif result.get('outcome') not in {"no_signal", None}:
                    logger.info("%s: analysis outcome=%s timings=%s", ticker, result.get('outcome'), telemetry)
                else:
                    logger.debug("No actionable signal for %s in this cycle", ticker)

                if db.new or db.dirty or db.deleted:
                    db.commit()

        if now_loop - last_snapshot_ts > snapshot_interval:
            last_snapshot_ts = now_loop
            async with get_db() as db:
                open_pos = db.query(Position).filter(Position.qty > 0).count()
                snap_settings = settings_repo.get_settings(db)
                if snap_settings and getattr(snap_settings, "trade_mode", "review") == "auto_live" and config.BROKER_PROVIDER == "tbank":
                    try:
                        portfolio = await TBankExecutionEngine(db, token=runtime_tbank_token, account_id=runtime_tbank_account, sandbox=config.TBANK_SANDBOX).get_portfolio()
                        snap_balance = float(portfolio.get("total_amount_currencies", 0) or 0)
                    except Exception:
                        logger.warning("Snapshot portfolio fetch failed", exc_info=True)
                        snap_balance = float(getattr(snap_settings, "account_balance", 100_000) or 100_000)
                else:
                    snap_balance = float(getattr(snap_settings, "account_balance", 100_000) or 100_000)
                if snap_settings and getattr(snap_settings, 'trade_mode', 'review') == 'auto_paper':
                    max_positions = int(getattr(snap_settings, 'max_concurrent_positions', 4) or 4)
                    approved_signal = signal_repo.get_oldest_approved_signal(db)
                    if approved_signal is not None:
                        await PaperExecutionEngine(db).execute_approved_signal(approved_signal.id)
                        open_pos = db.query(Position).filter(Position.qty > 0).count()
                    if open_pos < max_positions:
                        top_pending = signal_repo.get_top_pending_review_candidate(db, ttl_sec=int(getattr(snap_settings, 'pending_review_ttl_sec', 900) or 900))
                        if top_pending is not None:
                            top_pending.status = 'approved'
                            db.commit()
                            await PaperExecutionEngine(db).execute_approved_signal(top_pending.id)
                            open_pos += 1
                from sqlalchemy import func
                sod = start_of_day_ms()
                realized_today = float(db.query(func.sum(Position.realized_pnl)).filter(Position.updated_ts >= sod).scalar() or 0.0)
                unrealized = float(db.query(func.sum(Position.unrealized_pnl)).filter(Position.qty > 0).scalar() or 0.0)
                day_pnl = realized_today + unrealized
            update_open_positions(open_pos)
            await _save_snapshot(snap_balance, open_pos, day_pnl)

        cycle_finished = _now_ms()
        avg_timings = {metric: round(total / max(1, timing_samples), 2) for metric, total in timing_totals.items()} if timing_totals else {}
        last_analysis_stats = {
            "processed": processed,
            "takes": takes,
            "skipped": skipped,
            "duration_ms": cycle_finished - cycle_started,
        }
        if timing_samples > 0:
            last_analysis_stats.update({
                "timing_samples": timing_samples,
                "timing_totals_ms": timing_totals,
                "timing_avg_ms": avg_timings,
                "slowest_analysis": slowest_analysis,
                "last_analysis_result": last_analysis_result,
            })
        else:
            async with state.lock:
                previous_stats = dict((state.status or {}).get('last_analysis_stats') or {})
            for key in ('timing_samples', 'timing_totals_ms', 'timing_avg_ms', 'slowest_analysis', 'last_analysis_result'):
                if key in previous_stats:
                    last_analysis_stats[key] = previous_stats[key]
        await state.set_phase(
            "idle",
            f"Analysis cycle done: processed={processed}, takes={takes}, skipped={skipped}",
            last_analysis_finished_ts=cycle_finished,
            last_cycle_completed_ts=cycle_finished,
            last_analysis_stats=last_analysis_stats,
        )
        await state.publish()
        logger.info(
            "Cycle finished: processed=%d takes=%d skipped=%d duration_ms=%d timing_samples=%d avg_total_ms=%s",
            processed,
            takes,
            skipped,
            cycle_finished - cycle_started,
            timing_samples,
            avg_timings.get('total_ms') if avg_timings else None,
        )
        await asyncio.sleep(1.0)


async def run_worker() -> None:
    configure_logging(
        level=os.getenv("LOG_LEVEL", "INFO"),
        json_format=(config.APP_ENV == "production"),
        log_dir=(config.LOG_DIR or os.getenv("LOG_DIR") or None),
    )
    try:
        _acquire_single_instance_lock()
        atexit.register(_release_single_instance_lock)
    except RuntimeError as exc:
        logger.error("%s", exc)
        return
    logger.info("Worker starting (env=%s tf=%s broker=%s)", config.APP_ENV, os.getenv("TF", "1m"), config.BROKER_PROVIDER)
    _sanitize_proxy_env()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda s=sig: _handle_signal(s.name))

    tf_str = os.getenv("TF", "1m")
    frame_sec = {"1m": 60, "5m": 300, "15m": 900}.get(tf_str, 60)
    history_size = max(200, int(os.getenv("WORKER_HISTORY_SIZE", "600") or "600")) if tf_str == '1m' else max(200, int(os.getenv("WORKER_HISTORY_SIZE", "200") or "200"))
    tickers = await _load_watchlist()
    logger.info("Watchlist loaded: %d instrument(s): %s", len(tickers), tickers)
    logger.info("Worker history retention configured: tf=%s history_size=%d", tf_str, history_size)

    selector = StrategySelector()
    with SessionLocal() as init_db:
        settings = settings_repo.get_settings(init_db)
        strategy_name = getattr(settings, "strategy_name", "breakout,mean_reversion") if settings else "breakout,mean_reversion"
        if settings:
            logger.info(
                "Active settings loaded: id=%s updated_ts=%s active=%s threshold=%s reentry=%s risk_per_trade_pct=%s min_sl_distance_pct=%s min_profit_after_costs_multiplier=%s trade_mode=%s",
                getattr(settings, "id", None),
                getattr(settings, "updated_ts", None),
                bool(getattr(settings, "is_active", False)),
                getattr(settings, "decision_threshold", None),
                getattr(settings, "signal_reentry_cooldown_sec", None),
                getattr(settings, "risk_per_trade_pct", None),
                getattr(settings, "min_sl_distance_pct", None),
                getattr(settings, "min_profit_after_costs_multiplier", None),
                getattr(settings, "trade_mode", None),
            )

    strategy = selector.get(strategy_name)
    aggregator = CandleAggregator(frame_sec=frame_sec, history_size=history_size)
    publisher = MarketPublisher(tf_str=tf_str)
    internet = InternetCollector(redis_client=bus.redis, news_ttl=config.NEWS_CACHE_TTL_SEC, macro_ttl=config.MACRO_CACHE_TTL_SEC)
    processor = SignalProcessor(strategy=strategy, internet_collector=internet, aggregator=aggregator)
    monitors: dict[str, PositionMonitor] = {}
    state = WorkerRuntimeState(
        tickers=list(tickers),
        status={"started_ts": _now_ms(), "watchlist": list(tickers), "bootstrap_limit": int(getattr(settings, "worker_bootstrap_limit", 0) or os.getenv("WORKER_BOOTSTRAP_LIMIT", "10") or "10")},
        last_signal_check={t: 0.0 for t in tickers},
        last_poll_ts={t: 0.0 for t in tickers},
    )
    await state.set_phase("bootstrap", f"Worker bootstrapping {len(tickers)} instrument(s)")
    await state.publish()
    status_task = asyncio.create_task(_run_status_heartbeat_loop(state), name="worker-status-heartbeat")

    runtime_tbank_token = get_token("TBANK_TOKEN") or config.TBANK_TOKEN
    runtime_tbank_account = get_token("TBANK_ACCOUNT_ID") or config.TBANK_ACCOUNT_ID
    adapter = None
    polling_task = None
    profile_bootstrap_task = None

    def instrument_adapter_factory():
        if config.BROKER_PROVIDER != 'tbank' or not runtime_tbank_token:
            return None
        from apps.broker.tbank import TBankGrpcAdapter
        return TBankGrpcAdapter(token=runtime_tbank_token, account_id=runtime_tbank_account, sandbox=config.TBANK_SANDBOX)

    if config.BROKER_PROVIDER == "tbank" and runtime_tbank_token:
        from apps.broker.tbank import TBankGrpcAdapter

        adapter = TBankGrpcAdapter(
            token=runtime_tbank_token,
            account_id=runtime_tbank_account,
            sandbox=config.TBANK_SANDBOX,
        )
        if settings and bool(getattr(settings, "use_broker_trading_schedule", True)):
            await refresh_trading_schedule(exchange=(getattr(settings, "trading_schedule_exchange", None) or None), force=True)
        await _load_cached_history(aggregator, tickers, tf_str)
        bootstrap_limit = max(1, int(getattr(settings, "worker_bootstrap_limit", 0) or os.getenv("WORKER_BOOTSTRAP_LIMIT", "10") or "10"))
        await _bootstrap_history(adapter, aggregator, tickers[:bootstrap_limit], tf_str)
        await state.set_phase('bootstrap', f"History primed for {bootstrap_limit} instrument(s)")
        await state.publish()
        polling_task = asyncio.create_task(_run_tbank_polling_loop(adapter, aggregator, publisher, state, tf_str), name="worker-polling")
        profile_bootstrap_task = asyncio.create_task(
            _run_symbol_profile_bootstrap_task(state, tickers, train_limit=bootstrap_limit, timeframe=tf_str, source='worker_startup'),
            name='worker-symbol-profile-bootstrap',
        )
    else:
        primed = await _load_cached_history(aggregator, tickers, tf_str)
        logger.info("Mock mode history bootstrap: primed=%d", len(primed))
        train_limit = max(1, min(len(tickers), int(getattr(settings, "worker_bootstrap_limit", 0) or os.getenv("WORKER_BOOTSTRAP_LIMIT", "10") or "10")))
        await state.set_phase('bootstrap', f"History primed for {len(primed)} instrument(s)")
        await state.publish()
        polling_task = asyncio.create_task(_run_mock_polling_loop(aggregator, publisher, state, tf_str), name="worker-mock-polling")
        profile_bootstrap_task = asyncio.create_task(
            _run_symbol_profile_bootstrap_task(state, tickers, train_limit=train_limit, timeframe=tf_str, source='worker_startup_mock'),
            name='worker-symbol-profile-bootstrap',
        )

    watchlist_task = asyncio.create_task(_refresh_watchlist_loop(state, adapter, aggregator, tf_str), name="worker-watchlist")
    recalibration_task = asyncio.create_task(_run_recalibration_loop(state), name="worker-recalibration")
    ml_training_task = asyncio.create_task(_run_ml_training_loop(state), name="worker-ml-training")
    instrument_sync_task = asyncio.create_task(_run_instrument_auto_sync_loop(state, instrument_adapter_factory), name="worker-instrument-auto-sync")
    analysis_task = asyncio.create_task(
        _run_analysis_loop(
            selector=selector,
            processor=processor,
            aggregator=aggregator,
            monitors=monitors,
            state=state,
            runtime_tbank_token=runtime_tbank_token,
            runtime_tbank_account=runtime_tbank_account,
        ),
        name="worker-analysis",
    )

    cmd_pubsub = bus.redis.pubsub()
    await cmd_pubsub.subscribe("cmd:execute_signal")
    command_task = asyncio.create_task(_command_listener(cmd_pubsub, runtime_tbank_token, runtime_tbank_account), name="worker-command-listener")

    logger.info("Worker running. Instruments: %s", tickers)
    await state.set_phase("running", f"Worker running with {len(tickers)} instrument(s)")
    await state.publish()

    tasks = [polling_task, analysis_task, watchlist_task, recalibration_task, ml_training_task, instrument_sync_task, status_task, command_task]
    if profile_bootstrap_task is not None:
        tasks.append(profile_bootstrap_task)
    try:
        while not _shutdown.is_set():
            await asyncio.sleep(1.0)
            for task in list(tasks):
                if not task.done():
                    continue
                tasks.remove(task)
                exc = task.exception()
                if exc is not None:
                    logger.error("Worker task %s failed: %s", task.get_name(), exc, exc_info=True)
                    await state.mark_error(task.get_name(), exc)
                    await state.publish()
                    raise exc
                if _is_optional_worker_task(task.get_name()):
                    logger.info("Worker optional task %s finished normally", task.get_name())
                    continue
                raise RuntimeError(f"Worker task {task.get_name()} stopped unexpectedly")
    except Exception as exc:
        logger.error("Worker loop error: %s", exc, exc_info=True)
    finally:
        _shutdown.set()
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        try:
            await cmd_pubsub.unsubscribe("cmd:execute_signal")
            await cmd_pubsub.aclose()
        except Exception:
            pass
        if adapter is not None:
            try:
                await adapter.close()
            except Exception:
                pass
        await state.set_phase("stopped", "Worker stopped")
        await state.publish()
        await _shutdown_cleanup(monitors)


async def _shutdown_cleanup(monitors: dict[str, PositionMonitor]) -> None:
    async with get_db() as db:
        open_pos = db.query(Position).filter(Position.qty > 0).all()
        if open_pos:
            instruments = [p.instrument_id for p in open_pos]
            logger.warning("Worker shutdown: %d open position(s) remain: %s — NOT auto-closed", len(open_pos), instruments)
        else:
            logger.info("Worker shutdown gracefully. No open positions.")
    try:
        await bus.redis.aclose()
    except Exception:
        pass


async def _command_listener(pubsub, runtime_tbank_token: str | None, runtime_tbank_account: str | None) -> None:
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
                        settings = settings_repo.get_settings(db)
                        if not settings or not bool(getattr(settings, "bot_enabled", False)):
                            logger.warning("Execution skipped because bot is disabled")
                        else:
                            trade_mode = getattr(settings, "trade_mode", "review") or "review"
                            if trade_mode == "auto_live" and not prefers_paper_execution(settings):
                                await TBankExecutionEngine(db, token=runtime_tbank_token, account_id=runtime_tbank_account, sandbox=config.TBANK_SANDBOX).execute_approved_signal(sig_id)
                            else:
                                await PaperExecutionEngine(db).execute_approved_signal(sig_id)
            await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.error("Command listener error: %s", exc, exc_info=True)
            await asyncio.sleep(1.0)


if __name__ == "__main__":
    asyncio.run(run_worker())
