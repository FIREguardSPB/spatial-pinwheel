"""Position monitor with cost-aware close simulation."""
from __future__ import annotations

import asyncio
import importlib
import logging
import time
from decimal import Decimal

from sqlalchemy.orm import Session

from core.config import get_token, settings as config
from core.events.bus import bus
from core.execution.idempotent_submit import close_position_client_order_id
from core.execution.order_lifecycle import OrderLifecycleManager, map_broker_execution_status
from core.services.adaptive_exit import AdaptiveExitManager
from core.services.exit_diagnostics import build_exit_diagnostics
from core.services.excursion_tracker import update_position_excursion
try:
    _storage_models = importlib.import_module("core.storage.models")
except Exception:  # pragma: no cover - lightweight tests may stub storage.models partially
    _storage_models = None


class _MissingModel:
    id = None
    instrument_id = None
    ts = 0
    qty = 0
    avg_price = 0
    side = None
    status = None

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


Order = getattr(_storage_models, "Order", _MissingModel) if _storage_models is not None else _MissingModel
Position = getattr(_storage_models, "Position", _MissingModel) if _storage_models is not None else _MissingModel
Signal = getattr(_storage_models, "Signal", _MissingModel) if _storage_models is not None else _MissingModel
Trade = getattr(_storage_models, "Trade", _MissingModel) if _storage_models is not None else _MissingModel
try:
    from core.storage.repos import settings as settings_repo
except Exception:  # pragma: no cover
    class _SettingsRepo:
        @staticmethod
        def get_settings(_db):
            class _Defaults:
                fees_bps = 3
                adaptive_exit_partial_cooldown_sec = 180
                adaptive_exit_max_partial_closes = 2
                time_stop_bars = 12
                adaptive_exit_enabled = False
                partial_close_ratio = 0.25
                partial_close_threshold = 0.7
                min_position_age_for_partial_close = 1
                strong_signal_score_threshold = 70
            return _Defaults()
    settings_repo = _SettingsRepo()
def _safe_train_symbol_profile(db, instrument_id: str) -> None:
    try:
        from core.services.symbol_adaptive import train_symbol_profile
        train_symbol_profile(db, instrument_id, lookback_days=90, timeframe='1m', source='online_recalibration')
    except Exception:
        logger.debug('symbol profile retrain skipped for %s', instrument_id, exc_info=True)

from core.storage.decision_log_utils import append_decision_log_best_effort
from core.utils.ids import new_prefixed_id

logger = logging.getLogger(__name__)


def _fee_rub(price: float, qty: float, fees_bps: float) -> float:
    return price * qty * (float(fees_bps or 0.0) / 10000.0)


def _adverse_close_fill(current_price: float, position_side: str, slippage_bps: float) -> float:
    slip = float(slippage_bps or 0.0) / 10000.0
    if position_side == 'BUY':
        return current_price * (1.0 - slip)
    return current_price * (1.0 + slip)


class PositionMonitor:
    def __init__(self, db: Session):
        self.db = db
        self._bar_counters: dict[str, int] = {}
        self._dynamic_hold_overrides: dict[str, int] = {}

    def _signal_feedback_context(self, signal_id: str | None) -> dict:
        if not signal_id:
            return {}
        try:
            signal = self.db.query(Signal).filter(Signal.id == signal_id).first()
        except Exception:
            return {}
        meta = dict((signal.meta or {}) if signal else {})
        return {
            'conviction_profile': dict(meta.get('conviction_profile') or {}),
            'high_conviction_promotion': dict(meta.get('high_conviction_promotion') or {}),
            'review_readiness': dict(meta.get('review_readiness') or {}),
            'execution_quality_seed': dict(meta.get('execution_quality_seed') or {}),
        }

    def _effective_time_stop_bars(self, position: Position, default_bars: int) -> int:
        signal_id = getattr(position, 'opened_signal_id', None)
        if not signal_id:
            return int(self._dynamic_hold_overrides.get(position.instrument_id) or default_bars or 0)
        signal = self.db.query(Signal).filter(Signal.id == signal_id).first()
        meta = dict((signal.meta or {}) if signal else {})
        adaptive_plan = dict(meta.get('adaptive_plan') or {}) if isinstance(meta, dict) else {}
        base = int(adaptive_plan.get('hold_bars') or default_bars or 0)
        return int(self._dynamic_hold_overrides.get(position.instrument_id) or base)

    def _partial_close_controls(self, position: Position) -> tuple[int, int, bool]:
        settings = settings_repo.get_settings(self.db)
        cooldown_sec = int(getattr(settings, 'adaptive_exit_partial_cooldown_sec', 180) or 180)
        max_partials = int(getattr(settings, 'adaptive_exit_max_partial_closes', 2) or 2)
        count = int(getattr(position, 'partial_closes_count', 0) or 0)
        last_ts = int(getattr(position, 'last_partial_close_ts', 0) or 0)
        cooldown_active = bool(last_ts and cooldown_sec > 0 and (time.time() * 1000 - last_ts) < cooldown_sec * 1000)
        return count, max_partials, cooldown_active

    def _partial_close_position(self, position: Position, ratio: float, current_price: float, reason: str, *, bars_held: int | None = None, hold_limit_bars: int | None = None) -> None:
        qty_open = float(position.qty or 0)
        if qty_open <= 1:
            return
        close_qty = max(1, int(qty_open * max(0.05, min(ratio, 0.95))))
        if close_qty >= qty_open:
            close_qty = max(1, int(qty_open) - 1)
        if close_qty <= 0:
            return
        settings = settings_repo.get_settings(self.db)
        fees_bps = float(getattr(settings, 'fees_bps', 3) or 3)
        close_side = 'SELL' if position.side == 'BUY' else 'BUY'
        sign = 1 if position.side == 'BUY' else -1
        gross_realized = sign * close_qty * (current_price - float(position.avg_price or 0))
        exit_fee = _fee_rub(current_price, close_qty, fees_bps)
        net_realized = gross_realized - exit_fee
        now_ms = int(time.time() * 1000)
        lifecycle = OrderLifecycleManager(self.db)
        order = lifecycle.create_order(
            order_id=new_prefixed_id('ord_exitpart'),
            instrument_id=position.instrument_id,
            side=close_side,
            order_type='MARKET',
            price=Decimal(str(current_price)),
            qty=Decimal(str(close_qty)),
            related_signal_id=position.opened_signal_id,
            ai_influenced=False,
            ai_mode_used='adaptive_exit',
            strategy=getattr(position, 'strategy', None),
            trace_id=getattr(position, 'trace_id', None),
            ts_ms=now_ms,
            reason='adaptive_partial_close_created',
        ).order
        lifecycle.transition(order, 'submitted', reason='paper_submit', created_at=now_ms + 1)
        lifecycle.transition(order, 'acknowledged', reason='paper_ack', created_at=now_ms + 2)
        lifecycle.transition(order, 'filled', reason='adaptive_partial_close_fill', filled_qty=Decimal(str(close_qty)), created_at=now_ms + 3)
        trade = Trade(
            trade_id=new_prefixed_id('trd_exitpart'),
            instrument_id=position.instrument_id,
            ts=now_ms,
            side=close_side,
            price=Decimal(str(current_price)),
            qty=Decimal(str(close_qty)),
            order_id=order.order_id,
            signal_id=position.opened_signal_id,
            strategy=getattr(position, 'strategy', None),
            trace_id=getattr(position, 'trace_id', None),
        )
        self.db.add(order)
        self.db.add(trade)
        position.qty = Decimal(str(max(0.0, qty_open - close_qty)))
        position.realized_pnl = Decimal(str(float(position.realized_pnl or 0) + net_realized))
        position.exit_fee_est = Decimal(str(round(float(position.exit_fee_est or 0) + exit_fee, 6)))
        position.total_fees_est = Decimal(str(round(float(position.total_fees_est or 0) + exit_fee, 6)))
        position.partial_closes_count = int(getattr(position, 'partial_closes_count', 0) or 0) + 1
        position.last_partial_close_ts = now_ms
        position.last_mark_price = Decimal(str(round(float(current_price), 6)))
        position.last_mark_ts = now_ms
        excursion_meta = update_position_excursion(self.db, position, float(current_price), ts_ms=now_ms, bar_index=bars_held, phase='partial_close')
        exit_diagnostics = build_exit_diagnostics(
            position=position,
            requested_close_price=float(current_price),
            close_price=float(current_price),
            reason=reason,
            bars_held=bars_held,
            hold_limit_bars=hold_limit_bars,
            gross_realized=gross_realized,
            net_realized=net_realized,
            entry_fee=0.0,
            exit_fee=exit_fee,
            closed_qty=close_qty,
            now_ms=now_ms,
        )
        self.db.commit()
        append_decision_log_best_effort(
            log_type='adaptive_exit_partial',
            message=f'Adaptive partial close for {position.instrument_id}',
            payload={
                'instrument_id': position.instrument_id,
                'qty_closed': close_qty,
                'qty_remaining': max(0.0, qty_open - close_qty),
                'reason': reason,
                'close_price': current_price,
                'partial_closes_count': int(getattr(position, 'partial_closes_count', 0) or 0),
                'trace_id': getattr(position, 'trace_id', None),
                'signal_id': position.opened_signal_id,
                'exit_diagnostics': exit_diagnostics,
                'excursion': excursion_meta,
            },
            ts_ms=now_ms,
        )

    async def on_tick(self, instrument_id: str, current_price: float, time_stop_bars: int = 0, history: list[dict] | None = None) -> None:
        position = (
            self.db.query(Position)
            .filter(Position.instrument_id == instrument_id, Position.qty > 0)
            .first()
        )
        if not position:
            self._bar_counters.pop(instrument_id, None)
            return

        sign = 1 if position.side == 'BUY' else -1
        pnl = sign * float(position.qty) * (current_price - float(position.avg_price))
        position.unrealized_pnl = round(pnl, 4)
        position.last_mark_price = Decimal(str(round(float(current_price), 6)))
        position.last_mark_ts = int(time.time() * 1000)

        self._bar_counters[instrument_id] = self._bar_counters.get(instrument_id, 0) + 1
        update_position_excursion(self.db, position, float(current_price), ts_ms=int(position.last_mark_ts or 0), bar_index=self._bar_counters[instrument_id], phase='tick')
        bars_held = self._bar_counters[instrument_id]
        close_reason = None

        if position.sl is not None:
            sl = float(position.sl)
            if position.side == 'BUY' and current_price <= sl:
                close_reason = 'SL'
            elif position.side == 'SELL' and current_price >= sl:
                close_reason = 'SL'

        if close_reason is None and position.tp is not None:
            tp = float(position.tp)
            if position.side == 'BUY' and current_price >= tp:
                close_reason = 'TP'
            elif position.side == 'SELL' and current_price <= tp:
                close_reason = 'TP'

        signal = self.db.query(Signal).filter(Signal.id == getattr(position, 'opened_signal_id', None)).first() if getattr(position, 'opened_signal_id', None) else None
        signal_meta = dict((signal.meta or {}) if signal else {})
        adaptive_plan = dict(signal_meta.get('adaptive_plan') or {}) if isinstance(signal_meta, dict) else {}
        event_regime = dict(signal_meta.get('event_regime') or {}) if isinstance(signal_meta, dict) else {}
        effective_time_stop = self._effective_time_stop_bars(position, time_stop_bars)
        partial_count, _max_partials, cooldown_active = self._partial_close_controls(position)
        exit_manager = AdaptiveExitManager(settings_repo.get_settings(self.db))
        current_unreal = float(position.unrealized_pnl or 0)
        mfe_total = float(getattr(position, 'mfe_total_pnl', 0) or 0)
        mfe_capture_ratio = (current_unreal / mfe_total) if mfe_total > 1e-9 and current_unreal > 0 else None
        exit_decision = exit_manager.evaluate(
            position_side=position.side,
            current_price=float(current_price),
            avg_price=float(position.avg_price or 0),
            sl=float(position.sl) if position.sl is not None else None,
            tp=float(position.tp) if position.tp is not None else None,
            bars_held=bars_held,
            base_hold_bars=effective_time_stop,
            history=history or [],
            adaptive_plan=adaptive_plan,
            event_regime=event_regime,
            partial_closes_count=partial_count,
            partial_close_cooldown_active=cooldown_active,
            mfe_capture_ratio=mfe_capture_ratio,
            mfe_pct=float(getattr(position, 'mfe_pct', 0) or 0),
            mae_pct=float(getattr(position, 'mae_pct', 0) or 0),
            position_qty=float(position.qty or 0),
            total_fees_est=float(getattr(position, 'total_fees_est', 0) or 0),
            best_price_seen=float(getattr(position, 'best_price_seen', 0) or 0),
        )
        if exit_decision.extend_hold_bars is not None and exit_decision.extend_hold_bars > effective_time_stop:
            self._dynamic_hold_overrides[instrument_id] = int(exit_decision.extend_hold_bars)
            effective_time_stop = int(exit_decision.extend_hold_bars)
        if exit_decision.tighten_sl is not None:
            position.sl = Decimal(str(round(float(exit_decision.tighten_sl), 6)))
        if exit_decision.partial_close_ratio is not None:
            self._partial_close_position(position, float(exit_decision.partial_close_ratio), float(current_price), 'ADAPTIVE_PARTIAL', bars_held=bars_held, hold_limit_bars=effective_time_stop)
            position = (
                self.db.query(Position)
                .filter(Position.instrument_id == instrument_id, Position.qty > 0)
                .first()
            )
            if not position:
                self._bar_counters.pop(instrument_id, None)
                self._dynamic_hold_overrides.pop(instrument_id, None)
                return
        if close_reason is None and exit_decision.force_reason:
            close_reason = exit_decision.force_reason
        if close_reason is None and effective_time_stop > 0 and bars_held >= effective_time_stop:
            close_reason = f'TIME_STOP ({bars_held}/{effective_time_stop} bars)'

        if close_reason:
            await self._close_position(position, current_price, close_reason, bars_held=bars_held, hold_limit_bars=effective_time_stop)
        else:
            self.db.commit()

    async def close_for_session_end(self, instrument_id: str, current_price: float) -> None:
        position = (
            self.db.query(Position)
            .filter(Position.instrument_id == instrument_id, Position.qty > 0)
            .first()
        )
        if position:
            await self._close_position(position, current_price, 'SESSION_END', bars_held=self._bar_counters.get(instrument_id, 0), hold_limit_bars=self._effective_time_stop_bars(position, 0))

    async def _close_position(self, position: Position, current_price: float, reason: str, *, bars_held: int | None = None, hold_limit_bars: int | None = None) -> None:
        if config.BROKER_PROVIDER == 'tbank':
            try:
                live_settings = settings_repo.get_settings(self.db)
                if live_settings and getattr(live_settings, 'trade_mode', 'review') == 'auto_live':
                    from core.execution.tbank import TBankExecutionEngine
                    await TBankExecutionEngine(
                        self.db,
                        token=get_token('TBANK_TOKEN') or config.TBANK_TOKEN,
                        account_id=get_token('TBANK_ACCOUNT_ID') or config.TBANK_ACCOUNT_ID,
                        sandbox=config.TBANK_SANDBOX,
                    ).close_position(position.instrument_id, current_price, reason=reason)
                    return
            except Exception as exc:
                logger.error('Live close failed for %s: %s', position.instrument_id, exc)
                raise

        settings = settings_repo.get_settings(self.db)
        fees_bps = float(getattr(settings, 'fees_bps', 3) or 3)
        slippage_bps = float(getattr(settings, 'slippage_bps', 5) or 5)
        close_price = _adverse_close_fill(float(current_price), position.side, slippage_bps)

        sign = 1 if position.side == 'BUY' else -1
        gross_realized = sign * float(position.qty) * (close_price - float(position.avg_price))
        entry_fee = float(position.entry_fee_est or 0)
        exit_fee = _fee_rub(close_price, float(position.qty), fees_bps)
        net_realized = gross_realized - entry_fee - exit_fee
        position.realized_pnl = float(position.realized_pnl or 0) + round(net_realized, 4)
        position.unrealized_pnl = 0.0
        position.exit_fee_est = Decimal(str(round(exit_fee, 6)))
        position.total_fees_est = Decimal(str(round(float(position.total_fees_est or 0) + exit_fee, 6)))

        closed_qty = position.qty
        instrument_id = position.instrument_id
        close_side = 'SELL' if position.side == 'BUY' else 'BUY'
        now_ms = int(time.time() * 1000)
        trace_id = getattr(position, 'trace_id', None)
        strategy_name = getattr(position, 'strategy', None)
        lifecycle = OrderLifecycleManager(self.db)
        create_result = lifecycle.create_order(
            order_id=new_prefixed_id('ord_close'),
            client_order_id=close_position_client_order_id(
                instrument_id=instrument_id,
                opened_order_id=getattr(position, 'opened_order_id', None),
                opened_signal_id=getattr(position, 'opened_signal_id', None),
                opened_ts=getattr(position, 'opened_ts', None),
                side=close_side,
                purpose='paper_close',
            ),
            instrument_id=instrument_id,
            side=close_side,
            order_type='MARKET',
            price=Decimal(str(close_price)),
            qty=closed_qty,
            related_signal_id=None,
            ai_influenced=False,
            ai_mode_used='monitor',
            strategy=strategy_name,
            trace_id=trace_id,
            ts_ms=now_ms,
            reason='monitor_close_created',
        )
        close_order = create_result.order
        if not create_result.created:
            logger.info('Duplicate monitor close submit suppressed for %s client_order_id=%s', instrument_id, getattr(close_order, 'client_order_id', None))
            return
        lifecycle.transition(close_order, 'submitted', reason='paper_submit', created_at=now_ms + 1)
        lifecycle.transition(close_order, 'acknowledged', reason='paper_ack', created_at=now_ms + 2)
        lifecycle.transition(close_order, 'filled', reason=reason.lower(), filled_qty=closed_qty, created_at=now_ms + 3)
        trade = Trade(
            trade_id=new_prefixed_id('trd'),
            instrument_id=instrument_id,
            ts=now_ms,
            side=close_side,
            price=Decimal(str(close_price)),
            qty=closed_qty,
            order_id=close_order.order_id,
            signal_id=position.opened_signal_id,
            strategy=strategy_name,
            trace_id=trace_id,
        )
        self.db.add(trade)
        position.closed_order_id = close_order.order_id
        position.qty = Decimal('0')
        excursion_meta = update_position_excursion(self.db, position, float(close_price), ts_ms=now_ms, bar_index=bars_held, phase='final_close')

        try:
            from core.notifications.telegram import TelegramNotifier as _Tg
            notifier = _Tg.from_settings(self.db)
            if notifier:
                trade_info = {
                    'instrument_id': instrument_id,
                    'side': close_side,
                    'price': close_price,
                    'qty': int(closed_qty),
                    'realized_pnl': round(net_realized, 2),
                    'reason': reason,
                }
                if reason == 'SL':
                    asyncio.create_task(notifier.send_sl_hit(trade_info))
                elif reason == 'TP':
                    asyncio.create_task(notifier.send_tp_hit(trade_info))
                else:
                    asyncio.create_task(notifier.send_trade_executed(trade_info))
        except Exception:
            pass

        exit_diagnostics = build_exit_diagnostics(
            position=position,
            requested_close_price=float(current_price),
            close_price=float(close_price),
            reason=reason,
            bars_held=bars_held,
            hold_limit_bars=hold_limit_bars,
            gross_realized=gross_realized,
            net_realized=net_realized,
            entry_fee=entry_fee,
            exit_fee=exit_fee,
            closed_qty=float(closed_qty),
            now_ms=now_ms,
        )
        self.db.commit()
        feedback_ctx = self._signal_feedback_context(position.opened_signal_id)
        append_decision_log_best_effort(
            log_type='position_closed',
            message=f'Closed {instrument_id} @ {close_price:.4f} [{reason}] gross={gross_realized:.2f} net={net_realized:.2f}',
            payload={
                'trace_id': trace_id,
                'instrument_id': instrument_id,
                'signal_id': position.opened_signal_id,
                'strategy_name': strategy_name,
                'opened_order_id': position.opened_order_id,
                'closed_order_id': close_order.order_id,
                'reason': reason,
                'requested_close_price': float(current_price),
                'close_price': close_price,
                'qty': int(closed_qty),
                'opened_qty': float(position.opened_qty or closed_qty or 0),
                'opened_ts': int(position.opened_ts or 0),
                'closed_ts': now_ms,
                'gross_pnl': round(gross_realized, 4),
                'entry_fee_est': round(entry_fee, 6),
                'exit_fee_est': round(exit_fee, 6),
                'fees_est': round(entry_fee + exit_fee, 6),
                'net_pnl': round(net_realized, 4),
                'fees_bps': fees_bps,
                'slippage_bps': slippage_bps,
                'exit_diagnostics': exit_diagnostics,
                'excursion': excursion_meta,
                'conviction_profile': feedback_ctx.get('conviction_profile'),
                'high_conviction_promotion': feedback_ctx.get('high_conviction_promotion'),
                'review_readiness': feedback_ctx.get('review_readiness'),
                'execution_quality_seed': feedback_ctx.get('execution_quality_seed'),
            },
            ts_ms=now_ms,
        )

        try:
            outcome = 'profit' if net_realized > 0 else ('stopped' if 'TIME_STOP' in reason or 'SESSION_END' in reason else 'loss')
            from core.storage.repos.ai_repo import update_outcome
            if position.opened_signal_id:
                update_outcome(self.db, position.opened_signal_id, outcome)
        except Exception as exc:
            logger.debug('AI outcome update failed: %s', exc)

        try:
            _safe_train_symbol_profile(self.db, instrument_id)
        except Exception as exc:
            logger.debug('Online symbol recalibration failed for %s: %s', instrument_id, exc)

        self._bar_counters.pop(instrument_id, None)
        self._dynamic_hold_overrides.pop(instrument_id, None)
        logger.info('Position closed: %s reason=%s price=%.4f gross=%.2f net=%.2f', instrument_id, reason, close_price, gross_realized, net_realized)
        await bus.publish('positions_updated', {'instrument_id': instrument_id})
        await bus.publish('trade_filled', {'trade_id': trade.trade_id, 'reason': reason, 'pnl': round(net_realized, 4)})
