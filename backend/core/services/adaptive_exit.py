from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class AdaptiveExitDecision:
    force_reason: str | None = None
    extend_hold_bars: int | None = None
    tighten_sl: float | None = None
    partial_close_ratio: float | None = None
    notes: list[str] | None = None

    def to_meta(self) -> dict[str, Any]:
        payload = asdict(self)
        payload['notes'] = list(self.notes or [])
        return payload


class AdaptiveExitManager:
    def __init__(self, settings: Any):
        self.settings = settings

    @staticmethod
    def _break_even_price(*, entry: float, side: str, qty: float, total_fees_est: float) -> float:
        if entry <= 0 or qty <= 0:
            return entry
        fee_per_unit = max(0.0, float(total_fees_est or 0.0)) / max(1e-9, float(qty))
        if side == 'BUY':
            return entry + fee_per_unit
        return entry - fee_per_unit

    @staticmethod
    def _trailing_stop_price(*, entry: float, best_price_seen: float, side: str, lock_ratio: float, break_even_px: float) -> float:
        lock_ratio = max(0.05, min(0.95, float(lock_ratio or 0.0)))
        if side == 'BUY':
            trailed = entry + max(0.0, best_price_seen - entry) * lock_ratio
            return max(break_even_px, trailed)
        trailed = entry - max(0.0, entry - best_price_seen) * lock_ratio
        return min(break_even_px, trailed)

    @staticmethod
    def _momentum(history: list[dict[str, Any]], side: str, bars: int = 4) -> float:
        closes = [float(c.get('close') or 0.0) for c in history[-(bars + 1):] if c.get('close') is not None]
        if len(closes) < 2 or closes[0] <= 0:
            return 0.0
        move = (closes[-1] - closes[0]) / closes[0]
        return move if side == 'BUY' else -move

    def evaluate(
        self,
        *,
        position_side: str,
        current_price: float,
        avg_price: float,
        sl: float | None,
        tp: float | None,
        bars_held: int,
        base_hold_bars: int,
        history: list[dict[str, Any]],
        adaptive_plan: dict[str, Any] | None = None,
        event_regime: dict[str, Any] | None = None,
        partial_closes_count: int = 0,
        partial_close_cooldown_active: bool = False,
        mfe_capture_ratio: float | None = None,
        mfe_pct: float | None = None,
        mae_pct: float | None = None,
        position_qty: float | None = None,
        total_fees_est: float | None = None,
        best_price_seen: float | None = None,
        conviction_profile: dict[str, Any] | None = None,
    ) -> AdaptiveExitDecision:
        if not bool(getattr(self.settings, 'adaptive_exit_enabled', True)):
            return AdaptiveExitDecision(notes=['adaptive exit disabled'])
        notes: list[str] = []
        entry = float(avg_price or 0.0)
        if entry <= 0:
            return AdaptiveExitDecision(notes=['invalid avg price'])
        tp_val = float(tp) if tp is not None else None
        sl_val = float(sl) if sl is not None else None
        sign = 1.0 if position_side == 'BUY' else -1.0
        pnl_pct = sign * (current_price - entry) / entry * 100.0
        momentum = self._momentum(history, position_side)
        progress_to_tp = 0.0
        if tp_val is not None and abs(tp_val - entry) > 1e-9:
            progress_to_tp = max(0.0, min(2.0, sign * (current_price - entry) / (tp_val - entry)))
        regime = str((adaptive_plan or {}).get('regime') or 'balanced')
        event_action = str((event_regime or {}).get('action') or 'observe')
        extend_cap = int(getattr(self.settings, 'adaptive_exit_extend_bars_limit', 8) or 8)
        tighten_sl_pct = float(getattr(self.settings, 'adaptive_exit_tighten_sl_pct', 0.35) or 0.35) / 100.0
        break_even_enabled = bool(getattr(self.settings, 'adaptive_exit_break_even_enabled', True))
        break_even_progress_pct = float(getattr(self.settings, 'adaptive_exit_break_even_progress_pct', 0.35) or 0.35)
        trailing_enabled = bool(getattr(self.settings, 'adaptive_exit_trailing_enabled', True))
        trailing_activation_progress_pct = float(getattr(self.settings, 'adaptive_exit_trailing_activation_progress_pct', 0.55) or 0.55)
        trailing_lock_ratio = float(getattr(self.settings, 'adaptive_exit_trailing_lock_ratio', 0.45) or 0.45)
        thesis_decay_enabled = bool(getattr(self.settings, 'adaptive_exit_thesis_decay_enabled', True))
        thesis_decay_progress_pct = float(getattr(self.settings, 'adaptive_exit_thesis_decay_progress_pct', 0.2) or 0.2)
        max_partials = int(getattr(self.settings, 'adaptive_exit_max_partial_closes', 2) or 2)
        conviction = dict(conviction_profile or {})
        tier = str(conviction.get('tier') or 'C')
        higher_tf_trend = str(conviction.get('higher_timeframe_trend') or adaptive_plan.get('higher_timeframe_trend') or 'flat')
        if tier == 'A+':
            break_even_progress_pct = min(0.55, break_even_progress_pct + 0.10)
            trailing_activation_progress_pct = max(0.40, trailing_activation_progress_pct - 0.10)
            trailing_lock_ratio = min(0.60, trailing_lock_ratio + 0.08)
            thesis_decay_progress_pct = max(0.12, thesis_decay_progress_pct - 0.04)
        elif tier == 'A':
            break_even_progress_pct = min(0.50, break_even_progress_pct + 0.05)
            trailing_activation_progress_pct = max(0.45, trailing_activation_progress_pct - 0.05)
            trailing_lock_ratio = min(0.55, trailing_lock_ratio + 0.05)
        elif tier == 'B':
            break_even_progress_pct = max(0.20, break_even_progress_pct - 0.03)
            thesis_decay_progress_pct = min(0.28, thesis_decay_progress_pct + 0.03)
        elif tier == 'C':
            break_even_progress_pct = max(0.18, break_even_progress_pct - 0.06)
            thesis_decay_progress_pct = min(0.32, thesis_decay_progress_pct + 0.05)
        if higher_tf_trend in {'up', 'down'}:
            same_direction = (higher_tf_trend == 'up' and position_side == 'BUY') or (higher_tf_trend == 'down' and position_side == 'SELL')
            if same_direction:
                trailing_activation_progress_pct = max(0.35, trailing_activation_progress_pct - 0.05)
                thesis_decay_progress_pct = max(0.10, thesis_decay_progress_pct - 0.03)
            else:
                break_even_progress_pct = max(0.18, break_even_progress_pct - 0.04)
                thesis_decay_progress_pct = min(0.34, thesis_decay_progress_pct + 0.04)
        break_even_px = self._break_even_price(
            entry=entry,
            side=position_side,
            qty=float(position_qty or 0.0),
            total_fees_est=float(total_fees_est or 0.0),
        )

        if pnl_pct > 0.20 and 0.20 <= progress_to_tp <= 0.32 and momentum > -0.0002 and bars_held >= max(3, int(base_hold_bars * 0.35)):
            extra = 1 if regime in {'trend', 'expansion_trend'} else 0
            if extra > 0:
                notes.append('healthy winner preserves hold while thesis remains intact')
                return AdaptiveExitDecision(extend_hold_bars=base_hold_bars + min(extend_cap, extra), tighten_sl=break_even_px, notes=notes)

        if event_action == 'de_risk' and bars_held >= max(2, int(base_hold_bars * 0.35)) and pnl_pct > -0.15:
            notes.append('event regime requests de-risk')
            return AdaptiveExitDecision(force_reason='EVENT_DE_RISK', notes=notes)

        if thesis_decay_enabled and bars_held >= max(3, int(base_hold_bars * 0.35)):
            thesis_lagging = progress_to_tp < max(0.05, thesis_decay_progress_pct)
            weak_momentum = momentum < -0.0008
            gave_back_probe = bool(best_price_seen and ((position_side == 'BUY' and float(best_price_seen) > entry and current_price <= break_even_px) or (position_side == 'SELL' and float(best_price_seen) < entry and current_price >= break_even_px)))
            if thesis_lagging and (weak_momentum or gave_back_probe):
                notes.append('trade thesis decayed before reaching expected path')
                return AdaptiveExitDecision(force_reason='THESIS_DECAY', notes=notes)

        if bars_held >= max(3, int(base_hold_bars * 0.6)) and progress_to_tp < 0.12 and momentum < -0.0012:
            notes.append('stale trade with adverse micro-momentum')
            return AdaptiveExitDecision(force_reason='ADAPTIVE_TIME_STOP', notes=notes)

        if trailing_enabled and sl_val is not None and best_price_seen is not None and progress_to_tp >= max(0.2, trailing_activation_progress_pct):
            trail_px = self._trailing_stop_price(
                entry=entry,
                best_price_seen=float(best_price_seen),
                side=position_side,
                lock_ratio=trailing_lock_ratio,
                break_even_px=break_even_px,
            )
            if position_side == 'BUY' and trail_px > sl_val and trail_px < current_price and momentum > -0.0006:
                notes.append('trail winner stop to retain continuation gains')
                return AdaptiveExitDecision(tighten_sl=trail_px, notes=notes)
            if position_side == 'SELL' and trail_px < sl_val and trail_px > current_price and momentum > -0.0006:
                notes.append('trail winner stop to retain continuation gains')
                return AdaptiveExitDecision(tighten_sl=trail_px, notes=notes)

        if break_even_enabled and sl_val is not None and progress_to_tp >= max(0.1, break_even_progress_pct):
            if position_side == 'BUY' and break_even_px > sl_val and break_even_px < current_price and momentum > -0.0003:
                notes.append('move stop to break-even after sufficient progress')
                return AdaptiveExitDecision(tighten_sl=break_even_px, notes=notes)
            if position_side == 'SELL' and break_even_px < sl_val and break_even_px > current_price and momentum > -0.0003:
                notes.append('move stop to break-even after sufficient progress')
                return AdaptiveExitDecision(tighten_sl=break_even_px, notes=notes)

        capture_ratio = float(mfe_capture_ratio or 0.0) if mfe_capture_ratio is not None else 0.0
        if capture_ratio > 0 and pnl_pct > 0.08 and bars_held >= max(2, int(base_hold_bars * 0.35)):
            if capture_ratio < 0.28 and momentum < 0.0002:
                notes.append('mfe giveback detected, locking gains aggressively')
                return AdaptiveExitDecision(force_reason='MFE_GIVEBACK_EXIT', notes=notes)
            if capture_ratio < 0.42 and progress_to_tp >= 0.45:
                if partial_close_cooldown_active:
                    notes.append('capture partial skipped: cooldown active')
                elif partial_closes_count >= max_partials:
                    notes.append('capture partial skipped: max partial closes reached')
                else:
                    notes.append('mfe giveback detected, partial de-risk')
                    return AdaptiveExitDecision(partial_close_ratio=0.30 if partial_closes_count == 0 else 0.18, notes=notes)

        if progress_to_tp >= 0.75 and momentum < 0.0004:
            if partial_close_cooldown_active:
                notes.append('partial close skipped: cooldown active')
            elif partial_closes_count >= max_partials:
                notes.append('partial close skipped: max partial closes reached')
            else:
                notes.append('profit mostly realized, momentum fading')
                ratio = 0.35 if partial_closes_count == 0 else 0.20
                return AdaptiveExitDecision(partial_close_ratio=ratio, notes=notes)

        if pnl_pct > 0.18 and sl_val is not None:
            protect_px = entry * (1.0 + (tighten_sl_pct if position_side == 'BUY' else -tighten_sl_pct))
            if position_side == 'BUY' and protect_px > sl_val and protect_px < current_price:
                notes.append('tighten stop above entry')
                return AdaptiveExitDecision(tighten_sl=protect_px, notes=notes)
            if position_side == 'SELL' and protect_px < sl_val and protect_px > current_price:
                notes.append('tighten stop below entry')
                return AdaptiveExitDecision(tighten_sl=protect_px, notes=notes)

        if bars_held >= max(1, base_hold_bars - 1) and progress_to_tp >= 0.55 and momentum > 0.0015:
            extra = 2 if regime in {'trend', 'expansion_trend'} else 1
            extra = min(extend_cap, extra + max(0, int((progress_to_tp - 0.55) * 6)))
            if tier == 'A+':
                extra = min(extend_cap, extra + 1)
            elif tier == 'C':
                extra = max(0, extra - 1)
            if extra > 0:
                notes.append('strong continuation extends hold window')
                return AdaptiveExitDecision(extend_hold_bars=base_hold_bars + extra, notes=notes)

        return AdaptiveExitDecision(notes=['no adaptive action'])
