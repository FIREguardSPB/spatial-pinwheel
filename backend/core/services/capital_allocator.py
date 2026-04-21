from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from typing import Any

from sqlalchemy.orm import Session

from core.storage.models import DecisionLog
from core.storage.models import Position, Signal
from core.services.portfolio_optimizer import build_portfolio_optimizer_overlay


@dataclass
class ReallocationCandidate:
    instrument_id: str
    qty_ratio: float
    current_edge: float
    incoming_edge: float
    score_gap: int
    age_sec: int
    rationale: str
    estimated_mark_price: float | None = None
    free_cash_pct_before: float | None = None
    edge_improvement: float | None = None
    current_notional_pct: float | None = None
    portfolio_pressure: float | None = None
    incoming_corr: float | None = None
    current_risk_contribution_pct: float | None = None
    target_risk_budget_pct: float | None = None
    optimizer_multiplier: float | None = None
    decay_bias: float | None = None
    mfe_capture_gap: float | None = None
    current_unrealized_return_pct: float | None = None
    partial_closes_count: int | None = None
    cooldown_active: bool | None = None
    allocator_score: float | None = None

    def to_meta(self) -> dict[str, Any]:
        payload = asdict(self)
        for key in ('qty_ratio', 'current_edge', 'incoming_edge', 'edge_improvement', 'current_notional_pct', 'portfolio_pressure', 'incoming_corr', 'current_risk_contribution_pct', 'target_risk_budget_pct', 'optimizer_multiplier', 'decay_bias', 'mfe_capture_gap', 'current_unrealized_return_pct', 'allocator_score'):
            if payload.get(key) is not None:
                payload[key] = round(float(payload[key]), 4)
        if self.estimated_mark_price is not None:
            payload['estimated_mark_price'] = round(float(self.estimated_mark_price), 6)
        if self.free_cash_pct_before is not None:
            payload['free_cash_pct_before'] = round(float(self.free_cash_pct_before), 4)
        return payload


class CapitalAllocator:
    """Ranks open positions vs incoming signal and proposes partial/full reallocation."""

    def __init__(self, db: Session, settings: Any):
        self.db = db
        self.settings = settings

    @staticmethod
    def _signal_confidence_multiplier(signal: Signal | None) -> float:
        meta = dict((signal.meta or {}) if signal else {})
        review = dict(meta.get('review_readiness') or {}) if isinstance(meta, dict) else {}
        return float(review.get('confidence_multiplier') or 1.0)

    def _rotation_memory_bias(self, incoming_signal: Signal | None, *, lookback_sec: int = 7200) -> float:
        instrument_id = str(getattr(incoming_signal, 'instrument_id', None) or '')
        if not instrument_id:
            return 0.0
        cutoff = int(time.time() * 1000) - max(1, int(lookback_sec)) * 1000
        rows = (
            self.db.query(DecisionLog)
            .filter(DecisionLog.ts >= cutoff, DecisionLog.type == 'capital_reallocation')
            .all()
        )
        penalty = 0.0
        for row in rows:
            payload = dict(getattr(row, 'payload', None) or {})
            result = dict(payload.get('result') or {})
            if str(result.get('incoming_instrument') or payload.get('instrument_id') or '') == instrument_id:
                penalty += 0.08
        return min(0.24, penalty)

    @staticmethod
    def _should_hold_current_position(*, current_edge: float, incoming_edge: float, decay_bias: float, pnl_component: float, incoming_confidence_mult: float) -> bool:
        if incoming_confidence_mult >= 1.1:
            return False
        if pnl_component <= 0:
            return False
        if decay_bias >= 0.15:
            return False
        return current_edge >= incoming_edge * 0.9

    @staticmethod
    def _signal_score(signal: Signal | None) -> int:
        meta = dict((signal.meta or {}) if signal else {})
        decision = dict(meta.get('decision') or {})
        base_score = int(meta.get('event_adjusted_score') or decision.get('score') or 0)
        conviction = dict(meta.get('conviction_profile') or {}) if isinstance(meta, dict) else {}
        governor = dict(meta.get('performance_governor') or {}) if isinstance(meta, dict) else {}
        ml_overlay = dict(meta.get('ml_overlay') or {}) if isinstance(meta, dict) else {}
        priority = float(governor.get('execution_priority') or 1.0) * float(ml_overlay.get('execution_priority') or 1.0)
        priority *= float(conviction.get('allocator_priority_bonus') or 1.0)
        return int(round(base_score + max(-15.0, min(20.0, (priority - 1.0) * 25.0))))

    @staticmethod
    def _signal_edge(signal: Signal | None) -> float:
        meta = dict((signal.meta or {}) if signal else {})
        decision = dict(meta.get('decision') or {})
        metrics = dict(decision.get('metrics') or {})
        score = float(meta.get('event_adjusted_score') or decision.get('score') or 0) / 100.0
        net_rr = float(metrics.get('net_rr') or 0.0)
        vol_ratio = float(metrics.get('vol_ratio') or 1.0)
        event_bias = float(((meta.get('event_regime') or {}).get('score_bias')) or 0.0) / 10.0
        freshness = dict(meta.get('signal_freshness') or {}) if isinstance(meta, dict) else {}
        freshness_penalty = float(freshness.get('penalty_applied') or 0.0) / 100.0
        conviction = dict(meta.get('conviction_profile') or {}) if isinstance(meta, dict) else {}
        review = dict(meta.get('review_readiness') or {}) if isinstance(meta, dict) else {}
        governor = dict(meta.get('performance_governor') or {}) if isinstance(meta, dict) else {}
        ml_overlay = dict(meta.get('ml_overlay') or {}) if isinstance(meta, dict) else {}
        alloc_mult = float(governor.get('allocator_priority_multiplier') or 1.0) * float(ml_overlay.get('allocator_priority_multiplier') or 1.0)
        alloc_mult *= float(conviction.get('allocator_priority_bonus') or 1.0)
        alloc_mult *= float(review.get('confidence_multiplier') or 1.0)
        exec_priority = float(governor.get('execution_priority') or 1.0) * float(ml_overlay.get('execution_priority') or 1.0)
        base_edge = score * 0.55 + max(-1.0, min(3.0, net_rr)) * 0.25 + min(2.5, vol_ratio) * 0.12 + event_bias * 0.08 - freshness_penalty
        return base_edge * alloc_mult + max(-0.25, min(0.35, (exec_priority - 1.0) * 0.45))

    @staticmethod
    def _estimate_mark_price(pos: Position) -> float:
        mark = float(getattr(pos, 'last_mark_price', 0) or 0)
        if mark > 0:
            return mark
        qty = float(pos.qty or 0)
        avg = float(pos.avg_price or 0)
        if qty <= 0 or avg <= 0:
            return avg
        unreal = float(pos.unrealized_pnl or 0)
        sign = 1.0 if str(getattr(pos, 'side', 'BUY') or 'BUY').upper() == 'BUY' else -1.0
        derived = avg + (unreal / max(1e-9, sign * qty))
        return derived if derived > 0 else avg

    def _account_balance(self) -> float:
        return float(getattr(self.settings, 'account_balance', 100_000) or 100_000)

    def _open_positions(self) -> list[Position]:
        return self.db.query(Position).filter(Position.qty > 0).all()

    def _position_notional(self, pos: Position) -> float:
        return float(pos.qty or 0) * max(0.0, self._estimate_mark_price(pos))

    def _free_cash_pct(self) -> float:
        balance = self._account_balance()
        if balance <= 0:
            return 0.0
        open_notional = sum(self._position_notional(pos) for pos in self._open_positions())
        free_cash = max(0.0, balance - open_notional)
        return free_cash / balance * 100.0

    def _position_strength(self, pos: Position) -> tuple[float, int, float, float, float, float, bool, int, float]:
        entry_signal = None
        if getattr(pos, 'opened_signal_id', None):
            entry_signal = self.db.query(Signal).filter(Signal.id == pos.opened_signal_id).first()
        edge = self._signal_edge(entry_signal)
        unreal = float(pos.unrealized_pnl or 0.0)
        fees = float(pos.total_fees_est or 0.0)
        qty = float(pos.qty or 0.0)
        mark_price = self._estimate_mark_price(pos)
        gross_notional = qty * max(0.0, mark_price or float(pos.avg_price or 0.0))
        pnl_component = 0.0 if gross_notional <= 0 else unreal / gross_notional * 100.0
        age_sec = max(0, int((time.time() * 1000 - int(pos.opened_ts or time.time() * 1000)) / 1000))
        age_decay = float(getattr(self.settings, 'capital_allocator_age_decay_per_hour', 0.08) or 0.08)
        age_penalty = min(2.0, (age_sec / 3600.0) * age_decay) if age_sec >= 180 else 0.0
        concentration_pct = 0.0
        balance = self._account_balance()
        if balance > 0:
            concentration_pct = gross_notional / balance * 100.0
        min_age = int(getattr(self.settings, 'min_position_age_for_partial_close', 180) or 180)
        partial_count = int(getattr(pos, 'partial_closes_count', 0) or 0)
        cooldown_sec = int(getattr(self.settings, 'adaptive_exit_partial_cooldown_sec', 180) or 180)
        last_partial_close_ts = int(getattr(pos, 'last_partial_close_ts', 0) or 0)
        cooldown_active = bool(last_partial_close_ts and cooldown_sec > 0 and (time.time() * 1000 - last_partial_close_ts) < cooldown_sec * 1000)
        mfe_total = float(getattr(pos, 'mfe_total_pnl', 0) or 0.0)
        capture_gap = 0.0
        if mfe_total > 1e-9:
            capture_gap = max(0.0, 1.0 - max(0.0, unreal) / mfe_total)
        decay_bias = 0.0
        if age_sec >= min_age:
            decay_bias += min(0.35, ((age_sec - min_age) / 3600.0) * 0.08)
        if capture_gap > 0:
            decay_bias += min(0.35, capture_gap * 0.45)
        if pnl_component < 0:
            decay_bias += min(0.25, abs(pnl_component) * 0.04)
        if cooldown_active:
            decay_bias -= 0.20
        strength = edge + pnl_component * 0.25 - fees * 0.01 - age_penalty - decay_bias
        return strength, age_sec, mark_price, concentration_pct, decay_bias, capture_gap, cooldown_active, partial_count, pnl_component

    def choose_candidate(self, incoming_signal: Signal) -> ReallocationCandidate | None:
        if not bool(getattr(self.settings, 'capital_allocator_enabled', True)):
            return None
        free_cash_pct = self._free_cash_pct()
        min_free_cash = float(getattr(self.settings, 'capital_allocator_min_free_cash_pct', 8.0) or 8.0)
        if free_cash_pct >= min_free_cash:
            return None
        incoming_score = self._signal_score(incoming_signal)
        incoming_edge = self._signal_edge(incoming_signal)
        incoming_meta = dict((incoming_signal.meta or {}) if incoming_signal else {})
        incoming_governor = dict(incoming_meta.get('performance_governor') or {}) if isinstance(incoming_meta, dict) else {}
        incoming_ml = dict(incoming_meta.get('ml_overlay') or {}) if isinstance(incoming_meta, dict) else {}
        incoming_exec_priority = float(incoming_governor.get('execution_priority') or 1.0) * float(incoming_ml.get('execution_priority') or 1.0)
        incoming_allocator_mult = float(incoming_governor.get('allocator_priority_multiplier') or 1.0) * float(incoming_ml.get('allocator_priority_multiplier') or 1.0)
        incoming_confidence_mult = self._signal_confidence_multiplier(incoming_signal)
        rotation_memory_penalty = self._rotation_memory_bias(incoming_signal)
        incoming_instrument = str(getattr(incoming_signal, 'instrument_id', None) or '')
        optimizer_overlay = build_portfolio_optimizer_overlay(self.db, self.settings, incoming_signal)
        trim_candidates = list(optimizer_overlay.get('trim_candidates') or []) if isinstance(optimizer_overlay, dict) else []
        min_gap = int(getattr(self.settings, 'capital_allocator_min_score_gap', 12) or 12)
        max_ratio = float(getattr(self.settings, 'capital_allocator_max_reallocation_pct', 0.65) or 0.65)
        min_edge_improvement = float(getattr(self.settings, 'capital_allocator_min_edge_improvement', 0.18) or 0.18)
        min_gap = max(4, int(round(min_gap / max(0.75, incoming_exec_priority))))
        min_edge_improvement = max(0.05, min_edge_improvement / max(0.75, incoming_allocator_mult))
        max_concentration_pct = float(getattr(self.settings, 'capital_allocator_max_position_concentration_pct', 18.0) or 18.0)
        pressure = max(0.0, min_free_cash - free_cash_pct) / max(1.0, min_free_cash)
        pressure += max(0.0, incoming_exec_priority - 1.0) * 0.12
        best: ReallocationCandidate | None = None
        balance = self._account_balance()
        min_age = int(getattr(self.settings, 'min_position_age_for_partial_close', 180) or 180)
        max_partials = int(getattr(self.settings, 'adaptive_exit_max_partial_closes', 2) or 2)
        if trim_candidates:
            top = trim_candidates[0]
            pos = self.db.query(Position).filter(Position.instrument_id == top.get('instrument_id'), Position.qty > 0).first()
            if pos is not None:
                current_edge, age_sec, mark_price, current_notional_pct, decay_bias, capture_gap, cooldown_active, partial_count, pnl_component = self._position_strength(pos)
                if age_sec < min_age or cooldown_active or partial_count >= max_partials:
                    pos = None
            if pos is not None:
                allocator_score = max(0.0, (incoming_edge - current_edge) + pressure * 0.35 + decay_bias - rotation_memory_penalty)
                return ReallocationCandidate(
                    instrument_id=pos.instrument_id,
                    qty_ratio=min(max_ratio, max(0.15, float(top.get('qty_ratio') or 0.2) * min(1.2, max(0.9, incoming_confidence_mult)) * max(0.85, 1.0 - rotation_memory_penalty))),
                    current_edge=current_edge,
                    incoming_edge=incoming_edge,
                    score_gap=max(min_gap, incoming_score - int(round(current_edge * 20))),
                    age_sec=age_sec,
                    rationale=(
                        f"optimizer trim: rc {float(top.get('current_risk_contribution_pct') or 0):.2f}% > budget {float(top.get('target_risk_budget_pct') or 0):.2f}% ; "
                        f"corr={float(top.get('corr_to_incoming') or 0):.2f}; target_weight={float(top.get('target_weight_pct') or 0):.2f}%"
                    ),
                    estimated_mark_price=mark_price,
                    free_cash_pct_before=free_cash_pct,
                    edge_improvement=incoming_edge - current_edge,
                    current_notional_pct=current_notional_pct,
                    portfolio_pressure=pressure,
                    incoming_corr=float(top.get('corr_to_incoming') or 0.0),
                    current_risk_contribution_pct=float(top.get('current_risk_contribution_pct') or 0.0),
                    target_risk_budget_pct=float(top.get('target_risk_budget_pct') or 0.0),
                    optimizer_multiplier=float(optimizer_overlay.get('optimizer_risk_multiplier') or 1.0),
                    decay_bias=decay_bias,
                    mfe_capture_gap=capture_gap,
                    current_unrealized_return_pct=pnl_component,
                    partial_closes_count=partial_count,
                    cooldown_active=cooldown_active,
                    allocator_score=allocator_score,
                )
        for pos in self._open_positions():
            if incoming_instrument and pos.instrument_id == incoming_instrument:
                continue
            current_edge, age_sec, mark_price, current_notional_pct, decay_bias, capture_gap, cooldown_active, partial_count, pnl_component = self._position_strength(pos)
            if age_sec < min_age or cooldown_active or partial_count >= max_partials:
                continue
            score_gap = incoming_score - int(round(current_edge * 20))
            edge_improvement = incoming_edge - current_edge
            allocator_score = edge_improvement + pressure * 0.30 + decay_bias + max(0.0, (current_notional_pct - max_concentration_pct) / max(1.0, max_concentration_pct)) - rotation_memory_penalty
            if score_gap < min_gap and allocator_score < min_edge_improvement:
                continue
            if edge_improvement < min_edge_improvement and current_notional_pct < max_concentration_pct and decay_bias < 0.18:
                continue
            if self._should_hold_current_position(
                current_edge=current_edge,
                incoming_edge=incoming_edge,
                decay_bias=decay_bias,
                pnl_component=pnl_component,
                incoming_confidence_mult=incoming_confidence_mult,
            ):
                continue
            if current_notional_pct < max_concentration_pct * 0.55 and pressure < 0.45 and decay_bias < 0.20:
                # Avoid churn on already modest positions unless portfolio is really tight.
                continue
            ratio = 0.20
            if current_notional_pct > max_concentration_pct:
                ratio += 0.18
            elif current_notional_pct > max_concentration_pct * 0.8:
                ratio += 0.10
            if edge_improvement >= min_edge_improvement + 0.15:
                ratio += 0.10
            if edge_improvement >= min_edge_improvement + 0.35:
                ratio += 0.08
            if score_gap >= min_gap + 12:
                ratio += 0.07
            if pressure >= 0.4:
                ratio += 0.06
            ratio *= min(1.2, max(0.9, incoming_confidence_mult)) * max(0.85, 1.0 - rotation_memory_penalty)
            ratio = min(max_ratio, max(0.15, ratio))
            rationale = (
                f'incoming edge {incoming_edge:.2f} > position edge {current_edge:.2f}; '
                f'improvement={edge_improvement:.2f}; gap={score_gap}; age={age_sec}s; '
                f'free_cash={free_cash_pct:.2f}%; concentration={current_notional_pct:.2f}% of {balance:.0f}; '
                f'decay_bias={decay_bias:.2f}; mfe_gap={capture_gap:.2f}; pnl={pnl_component:.2f}%'
            )
            candidate = ReallocationCandidate(
                instrument_id=pos.instrument_id,
                qty_ratio=ratio,
                current_edge=current_edge,
                incoming_edge=incoming_edge,
                score_gap=score_gap,
                age_sec=age_sec,
                rationale=rationale,
                estimated_mark_price=mark_price,
                free_cash_pct_before=free_cash_pct,
                edge_improvement=edge_improvement,
                current_notional_pct=current_notional_pct,
                portfolio_pressure=pressure,
                decay_bias=decay_bias,
                mfe_capture_gap=capture_gap,
                current_unrealized_return_pct=pnl_component,
                partial_closes_count=partial_count,
                cooldown_active=cooldown_active,
                allocator_score=allocator_score,
            )
            if best is None:
                best = candidate
                continue
            if (candidate.allocator_score or 0.0) > (best.allocator_score or 0.0) + 0.02:
                best = candidate
                continue
            if (candidate.edge_improvement or 0.0) > (best.edge_improvement or 0.0) + 0.01:
                best = candidate
                continue
            if candidate.score_gap > best.score_gap:
                best = candidate
                continue
            if (candidate.current_notional_pct or 0.0) > (best.current_notional_pct or 0.0) and (candidate.current_edge < best.current_edge + 0.05):
                best = candidate
        return best
