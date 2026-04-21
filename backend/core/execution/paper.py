"""Paper execution engine with cost-aware fills and optional capital reallocation."""
from __future__ import annotations

import logging
import time
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from core.events.bus import bus
from core.execution.controls import ExecutionControlBlocked, assert_new_entries_allowed
from core.execution.fill_quality import build_fill_quality
from core.execution.idempotent_submit import signal_client_order_id
from core.execution.order_lifecycle import OrderLifecycleManager, map_broker_execution_status
from core.risk.manager import RiskManager
from core.services.capital_allocator import CapitalAllocator
from core.services.excursion_tracker import update_position_excursion
from core.storage.models import Order, Position, Signal, Trade, AccountSnapshot
from core.storage.repos import settings as settings_repo
from core.storage.decision_log_utils import append_decision_log_best_effort
from core.utils.ids import new_prefixed_id

logger = logging.getLogger(__name__)


def _adverse_fill_price(price: float, side: str, slippage_bps: float) -> float:
    slip = float(slippage_bps or 0.0) / 10000.0
    if side == 'BUY':
        return price * (1.0 + slip)
    return price * (1.0 - slip)


def _fee_rub(price: float, qty: float, fees_bps: float) -> float:
    return price * qty * (float(fees_bps or 0.0) / 10000.0)


class PaperExecutionEngine:
    def __init__(self, db: Session):
        self.db = db
        self.risk = RiskManager(db)

    @staticmethod
    def _signal_meta(signal: Signal | None) -> dict[str, Any]:
        return dict(signal.meta or {}) if signal else {}

    @staticmethod
    def _execution_quality_seed(signal: Signal | None, fill_quality: dict[str, Any]) -> dict[str, Any]:
        meta = dict(signal.meta or {}) if signal else {}
        return {
            'thesis_timeframe': meta.get('thesis_timeframe'),
            'review_readiness': dict(meta.get('review_readiness') or {}),
            'conviction_profile': dict(meta.get('conviction_profile') or {}),
            'high_conviction_promotion': dict(meta.get('high_conviction_promotion') or {}),
            'fill_quality_status': fill_quality.get('status'),
        }

    @staticmethod
    def _signal_strategy(signal: Signal | None) -> str | None:
        meta = dict(signal.meta or {}) if signal else {}
        multi = meta.get('multi_strategy') if isinstance(meta, dict) else {}
        return str((multi or {}).get('selected') or meta.get('strategy') or meta.get('strategy_name') or '') or None

    @staticmethod
    def _signal_trace_id(signal: Signal | None) -> str | None:
        meta = dict(signal.meta or {}) if signal else {}
        return meta.get('trace_id') if isinstance(meta, dict) else None

    def _estimate_position_mark_price(self, position: Position) -> float:
        mark = float(getattr(position, 'last_mark_price', 0) or 0)
        if mark > 0:
            return mark
        avg = float(position.avg_price or 0)
        qty = float(position.qty or 0)
        if qty <= 0 or avg <= 0:
            return avg
        unreal = float(position.unrealized_pnl or 0)
        sign = 1.0 if position.side == 'BUY' else -1.0
        derived = avg + unreal / max(1e-9, sign * qty)
        return derived if derived > 0 else avg

    def _position_remaining_potential(self, position: Position) -> float:
        avg = float(position.avg_price or 0)
        qty = float(position.qty or 0)
        if qty <= 0 or avg <= 0:
            return 0.0
        target = float(position.tp or avg)
        sign = 1 if position.side == 'BUY' else -1
        gross = sign * qty * (target - avg)
        return gross - float(position.total_fees_est or 0)

    def _eligible_partial_close_candidate(self, signal: Signal, settings) -> tuple[Position | None, float, dict[str, Any] | None]:
        allocator = CapitalAllocator(self.db, settings)
        candidate = allocator.choose_candidate(signal)
        if candidate is not None:
            pos = self.db.query(Position).filter(Position.instrument_id == candidate.instrument_id, Position.qty > 0).first()
            if pos is not None:
                return pos, float(candidate.qty_ratio), candidate.to_meta()

        threshold = int(getattr(settings, 'partial_close_threshold', 80) or 80)
        min_age = int(getattr(settings, 'min_position_age_for_partial_close', 180) or 180)
        score = int((((signal.meta or {}).get('decision') or {}).get('score') or 0))
        if score < threshold:
            return None, 0.0, None
        now_ms = int(time.time() * 1000)
        candidates: list[tuple[float, Position]] = []
        for pos in self.db.query(Position).filter(Position.qty > 0).all():
            age_sec = max(0, int((now_ms - int(pos.opened_ts or now_ms)) / 1000))
            if age_sec < min_age:
                continue
            potential = self._position_remaining_potential(pos)
            candidates.append((potential, pos))
        if not candidates:
            return None, 0.0, None
        candidates.sort(key=lambda item: (item[0], int(item[1].opened_ts or 0)))
        return candidates[0][1], float(getattr(settings, 'partial_close_ratio', 0.5) or 0.5), {'fallback': True}

    def _partial_close_position(self, position: Position, ratio: float, reason: str, trace_id: str | None = None) -> dict[str, Any] | None:
        settings = settings_repo.get_settings(self.db)
        fees_bps = float(getattr(settings, 'fees_bps', 3) or 3)
        qty_open = float(position.qty or 0)
        if qty_open <= 1:
            return None
        close_qty = max(1, int(qty_open * max(0.05, min(ratio, 0.95))))
        if close_qty >= qty_open:
            close_qty = max(1, int(qty_open) - 1)
        if close_qty <= 0:
            return None
        current_price = float(self._estimate_position_mark_price(position) or float(position.avg_price or 0))
        close_side = 'SELL' if position.side == 'BUY' else 'BUY'
        sign = 1 if position.side == 'BUY' else -1
        gross_realized = sign * close_qty * (current_price - float(position.avg_price or 0))
        exit_fee = _fee_rub(current_price, close_qty, fees_bps)
        net_realized = gross_realized - exit_fee
        now_ms = int(time.time() * 1000)
        lifecycle = OrderLifecycleManager(self.db)
        order = lifecycle.create_order(
            order_id=new_prefixed_id('ord_realloc'),
            instrument_id=position.instrument_id,
            side=close_side,
            order_type='MARKET',
            price=Decimal(str(current_price)),
            qty=Decimal(str(close_qty)),
            related_signal_id=position.opened_signal_id,
            ai_influenced=False,
            ai_mode_used='reallocation',
            strategy=getattr(position, 'strategy', None),
            trace_id=trace_id or getattr(position, 'trace_id', None),
            ts_ms=now_ms,
            reason='partial_close_created',
        ).order
        lifecycle.transition(order, 'submitted', reason='paper_submit', created_at=now_ms + 1)
        lifecycle.transition(order, 'acknowledged', reason='paper_ack', created_at=now_ms + 2)
        lifecycle.transition(order, 'filled', reason='partial_fill_close', filled_qty=Decimal(str(close_qty)), created_at=now_ms + 3)
        trade = Trade(
            trade_id=new_prefixed_id('trd_realloc'),
            instrument_id=position.instrument_id,
            ts=now_ms,
            side=close_side,
            price=Decimal(str(current_price)),
            qty=Decimal(str(close_qty)),
            order_id=order.order_id,
            signal_id=position.opened_signal_id,
            strategy=getattr(position, 'strategy', None),
            trace_id=trace_id or getattr(position, 'trace_id', None),
        )
        self.db.add(order)
        self.db.add(trade)
        remaining_qty = max(0.0, qty_open - close_qty)
        position.qty = Decimal(str(remaining_qty))
        position.realized_pnl = Decimal(str(float(position.realized_pnl or 0) + net_realized))
        position.exit_fee_est = Decimal(str(round(float(position.exit_fee_est or 0) + exit_fee, 6)))
        position.total_fees_est = Decimal(str(round(float(position.total_fees_est or 0) + exit_fee, 6)))
        position.partial_closes_count = int(getattr(position, 'partial_closes_count', 0) or 0) + 1
        position.last_partial_close_ts = now_ms
        position.last_mark_price = Decimal(str(round(current_price, 6)))
        position.last_mark_ts = now_ms
        if remaining_qty <= 0:
            position.closed_order_id = order.order_id
        excursion_meta = update_position_excursion(self.db, position, float(current_price), ts_ms=now_ms, phase='partial_close')
        self.db.commit()
        append_decision_log_best_effort(
            log_type='position_partial_close',
            message=f'Partial close {position.instrument_id}: qty={close_qty}/{qty_open} [{reason}]',
            payload={
                'trace_id': trace_id or getattr(position, 'trace_id', None),
                'instrument_id': position.instrument_id,
                'signal_id': position.opened_signal_id,
                'order_id': order.order_id,
                'trade_id': trade.trade_id,
                'qty_closed': close_qty,
                'qty_remaining': remaining_qty,
                'reason': reason,
                'close_price': current_price,
                'net_pnl': round(net_realized, 4),
                'estimated_mark_price': current_price,
                'partial_closes_count': int(getattr(position, 'partial_closes_count', 0) or 0),
                'excursion': excursion_meta,
            },
            ts_ms=now_ms,
        )
        return {'order_id': order.order_id, 'trade_id': trade.trade_id, 'qty_closed': close_qty, 'qty_remaining': remaining_qty}

    async def execute_approved_signal(self, signal_id: str) -> None:
        signal = self.db.query(Signal).filter(Signal.id == signal_id).first()
        if not signal or signal.status != 'approved':
            logger.warning('execute_approved_signal: signal %s not found or not approved', signal_id)
            return

        settings = settings_repo.get_settings(self.db)
        trace_id = self._signal_trace_id(signal)
        try:
            assert_new_entries_allowed(settings, execution_target='paper')
        except ExecutionControlBlocked as exc:
            signal.status = 'pending_review'
            self.db.commit()
            append_decision_log_best_effort(
                log_type='execution_control_block',
                message=f'Paper entry blocked for {signal.instrument_id}: {exc}',
                payload={
                    'signal_id': signal.id,
                    'instrument_id': signal.instrument_id,
                    'trace_id': trace_id,
                    'code': exc.code,
                    'controls': exc.snapshot,
                    'execution_target': 'paper',
                },
            )
            await bus.publish('signal_updated', {'id': signal_id, 'status': 'pending_review', 'reason': str(exc)})
            return
        risk_ok, risk_reason = self.risk.check_new_signal(signal)
        if not risk_ok:
            candidate, ratio, alloc_meta = self._eligible_partial_close_candidate(signal, settings)
            if candidate is not None:
                realloc = self._partial_close_position(candidate, ratio, f'reallocation_for_{signal.instrument_id}', trace_id=trace_id)
                if realloc:
                    logger.info('Reallocated capital via partial close before executing %s: %s', signal.instrument_id, realloc)
                    append_decision_log_best_effort(
                        log_type='capital_reallocation',
                        message=f'Capital reallocation for {signal.instrument_id}',
                        payload={'signal_id': signal.id, 'trace_id': trace_id, 'candidate': alloc_meta, 'result': realloc},
                    )
                    risk_ok, risk_reason = self.risk.check_new_signal(signal)

        if not risk_ok:
            logger.warning('Paper execution blocked by risk: %s', risk_reason)
            meta = dict(signal.meta or {}) if isinstance(signal.meta, dict) else {}
            meta['execution_stage_block'] = {
                'code': 'execution_risk_block',
                'reason': risk_reason,
                'stage': 'paper_execution',
                'risk_detail': self.risk.last_check_details,
            }
            signal.meta = meta
            signal.status = 'rejected'
            self.db.commit()
            append_decision_log_best_effort(
                log_type='execution_risk_block',
                message=f'Paper execution blocked for {signal.instrument_id}: {risk_reason}',
                payload={'signal_id': signal.id, 'trace_id': trace_id, 'risk_reason': risk_reason, 'risk_detail': self.risk.last_check_details},
            )
            await bus.publish('signal_updated', {'id': signal_id, 'status': 'rejected', 'reason': risk_reason})
            return

        qty = self.risk.normalize_qty(float(signal.size), lot_size=1)
        fees_bps = float(getattr(settings, 'fees_bps', 3) or 3)
        slippage_bps = float(getattr(settings, 'slippage_bps', 5) or 5)
        fill_price = _adverse_fill_price(float(signal.entry), signal.side, slippage_bps)
        entry_fee = _fee_rub(fill_price, qty, fees_bps)
        now_ms = int(time.time() * 1000)
        strategy_name = self._signal_strategy(signal)
        fill_quality = build_fill_quality(
            requested_price=float(signal.entry),
            actual_price=float(fill_price),
            side=signal.side,
            qty=qty,
            expected_slippage_bps=slippage_bps,
            end_to_end_ms=3,
        )

        lifecycle = OrderLifecycleManager(self.db)
        create_result = lifecycle.create_order(
            order_id=new_prefixed_id('ord'),
            client_order_id=signal_client_order_id(signal.id, purpose='paper_open'),
            instrument_id=signal.instrument_id,
            side=signal.side,
            order_type='MARKET',
            price=Decimal(str(fill_price)),
            qty=qty,
            related_signal_id=signal.id,
            ai_influenced=bool(signal.ai_influenced),
            ai_mode_used=signal.ai_mode_used or 'off',
            strategy=strategy_name,
            trace_id=trace_id,
            ts_ms=now_ms,
            reason='paper_order_created',
        )
        order = create_result.order
        if not create_result.created:
            logger.info('Duplicate paper submit suppressed for signal %s client_order_id=%s', signal.id, getattr(order, 'client_order_id', None))
            return
        lifecycle.transition(order, 'submitted', reason='paper_submit', created_at=now_ms + 1)
        lifecycle.transition(order, 'acknowledged', reason='paper_ack', created_at=now_ms + 2)
        lifecycle.transition(order, 'filled', reason='paper_fill', filled_qty=qty, created_at=now_ms + 3)

        trade = Trade(
            trade_id=new_prefixed_id('trd'),
            instrument_id=signal.instrument_id,
            ts=now_ms,
            side=signal.side,
            price=Decimal(str(fill_price)),
            qty=qty,
            order_id=order.order_id,
            signal_id=signal.id,
            strategy=strategy_name,
            trace_id=trace_id,
        )
        self.db.add(trade)

        position = self.db.query(Position).filter(Position.instrument_id == signal.instrument_id).first()
        if not position:
            position = Position(
                instrument_id=signal.instrument_id,
                side=signal.side,
                qty=qty,
                opened_qty=qty,
                avg_price=Decimal(str(fill_price)),
                sl=signal.sl,
                tp=signal.tp,
                unrealized_pnl=Decimal('0'),
                realized_pnl=Decimal('0'),
                opened_signal_id=signal.id,
                strategy=strategy_name,
                trace_id=trace_id,
                opened_order_id=order.order_id,
                entry_fee_est=Decimal(str(round(entry_fee, 6))),
                exit_fee_est=Decimal('0'),
                total_fees_est=Decimal(str(round(entry_fee, 6))),
                partial_closes_count=0,
                last_partial_close_ts=None,
                last_mark_price=Decimal(str(round(fill_price, 6))),
                last_mark_ts=now_ms,
                mfe_total_pnl=Decimal('0'),
                mae_total_pnl=Decimal('0'),
                mfe_pct=Decimal('0'),
                mae_pct=Decimal('0'),
                best_price_seen=Decimal(str(round(fill_price, 6))),
                worst_price_seen=Decimal(str(round(fill_price, 6))),
                excursion_samples=0,
                excursion_updated_ts=now_ms,
                opened_ts=now_ms,
            )
            self.db.add(position)
        else:
            if position.side == signal.side and float(position.qty) > 0:
                total_qty = float(position.qty) + qty
                total_cost = float(position.qty) * float(position.avg_price) + qty * fill_price
                position.avg_price = Decimal(str(round(total_cost / total_qty, 6)))
                position.qty = Decimal(str(total_qty))
                position.opened_qty = Decimal(str(total_qty))
                position.sl = signal.sl
                position.tp = signal.tp
                position.opened_signal_id = signal.id
                position.opened_order_id = order.order_id
                position.strategy = strategy_name or getattr(position, 'strategy', None)
                position.trace_id = trace_id or getattr(position, 'trace_id', None)
                position.entry_fee_est = Decimal(str(round(float(position.entry_fee_est or 0) + entry_fee, 6)))
                position.total_fees_est = Decimal(str(round(float(position.total_fees_est or 0) + entry_fee, 6)))
                position.last_mark_price = Decimal(str(round(fill_price, 6)))
                position.last_mark_ts = now_ms
            elif float(position.qty) == 0:
                position.side = signal.side
                position.qty = Decimal(str(qty))
                position.opened_qty = Decimal(str(qty))
                position.avg_price = Decimal(str(fill_price))
                position.sl = signal.sl
                position.tp = signal.tp
                position.unrealized_pnl = Decimal('0')
                position.opened_signal_id = signal.id
                position.strategy = strategy_name
                position.trace_id = trace_id
                position.opened_order_id = order.order_id
                position.closed_order_id = None
                position.entry_fee_est = Decimal(str(round(entry_fee, 6)))
                position.exit_fee_est = Decimal('0')
                position.total_fees_est = Decimal(str(round(entry_fee, 6)))
                position.partial_closes_count = 0
                position.last_partial_close_ts = None
                position.last_mark_price = Decimal(str(round(fill_price, 6)))
                position.last_mark_ts = now_ms
                position.mfe_total_pnl = Decimal('0')
                position.mae_total_pnl = Decimal('0')
                position.mfe_pct = Decimal('0')
                position.mae_pct = Decimal('0')
                position.best_price_seen = Decimal(str(round(fill_price, 6)))
                position.worst_price_seen = Decimal(str(round(fill_price, 6)))
                position.excursion_samples = 0
                position.excursion_updated_ts = now_ms
                position.opened_ts = now_ms

        update_position_excursion(self.db, position, float(fill_price), ts_ms=now_ms, phase='entry_fill')
        signal.status = 'executed'
        signal_meta = dict(signal.meta or {})
        signal_meta['fill_quality'] = fill_quality
        signal_meta['execution_quality_seed'] = self._execution_quality_seed(signal, fill_quality)
        signal.meta = signal_meta
        self.db.commit()

        strategy_meta = dict(signal.meta or {})
        append_decision_log_best_effort(
            log_type='trade_filled',
            message=f'Filled {qty} @ {fill_price:.4f} [{signal.side}] {signal.instrument_id}',
            payload={
                'trade_id': trade.trade_id,
                'order_id': order.order_id,
                'signal_id': signal.id,
                'trace_id': trace_id,
                'instrument_id': signal.instrument_id,
                'qty': qty,
                'price': fill_price,
                'requested_entry': float(signal.entry),
                'entry_fee_est': round(entry_fee, 6),
                'fees_bps': fees_bps,
                'slippage_bps': slippage_bps,
                'sl': float(signal.sl),
                'tp': float(signal.tp),
                'ai_influenced': bool(signal.ai_influenced),
                'ai_mode_used': signal.ai_mode_used,
                'strategy_name': strategy_name,
                'decision_merge': strategy_meta.get('decision_merge'),
                'fill_quality': fill_quality,
                'execution_quality_seed': strategy_meta.get('execution_quality_seed'),
            },
        )
        append_decision_log_best_effort(
            log_type='fill_quality',
            message=f'Fill quality for {signal.instrument_id}: {fill_quality["status"]}',
            payload={
                'signal_id': signal.id,
                'trace_id': trace_id,
                'instrument_id': signal.instrument_id,
                'order_id': order.order_id,
                'fill_quality': fill_quality,
            },
        )
        if fill_quality['status'] == 'anomaly':
            append_decision_log_best_effort(
                log_type='execution_fill_anomaly',
                message=f'Fill slippage anomaly for {signal.instrument_id}',
                payload={
                    'signal_id': signal.id,
                    'trace_id': trace_id,
                    'instrument_id': signal.instrument_id,
                    'order_id': order.order_id,
                    'fill_quality': fill_quality,
                },
            )

        logger.info(
            'Executed: %s %d @ %.4f sl=%.4f tp=%.4f entry_fee=%.2f strategy=%s',
            signal.instrument_id, qty, fill_price, float(signal.sl), float(signal.tp), entry_fee, strategy_name,
        )

        try:
            balance = float(getattr(settings, 'account_balance', 100_000) or 100_000)
            open_pnl = sum(
                float(p.unrealized_pnl or 0)
                for p in self.db.query(Position).filter(Position.qty > 0).all()
            )
            self.db.add(AccountSnapshot(
                ts=int(time.time() * 1000),
                balance=Decimal(str(round(balance, 4))),
                equity=Decimal(str(round(balance + open_pnl, 4))),
                day_pnl=Decimal(str(round(open_pnl, 4))),
            ))
            self.db.commit()
        except Exception as snap_err:
            logger.debug('AccountSnapshot save failed: %s', snap_err)

        await bus.publish('orders_updated', {'order_id': order.order_id})
        await bus.publish('trade_filled', {'trade_id': trade.trade_id})
        await bus.publish('positions_updated', {'instrument_id': position.instrument_id})
        await bus.publish('signal_updated', {'id': signal.id, 'status': 'executed'})
