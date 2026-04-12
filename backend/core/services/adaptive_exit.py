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
        max_partials = int(getattr(self.settings, 'adaptive_exit_max_partial_closes', 2) or 2)

        if event_action == 'de_risk' and bars_held >= max(2, int(base_hold_bars * 0.35)) and pnl_pct > -0.15:
            notes.append('event regime requests de-risk')
            return AdaptiveExitDecision(force_reason='EVENT_DE_RISK', notes=notes)

        if bars_held >= max(3, int(base_hold_bars * 0.6)) and progress_to_tp < 0.12 and momentum < -0.0012:
            notes.append('stale trade with adverse micro-momentum')
            return AdaptiveExitDecision(force_reason='ADAPTIVE_TIME_STOP', notes=notes)

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
            if extra > 0:
                notes.append('strong continuation extends hold window')
                return AdaptiveExitDecision(extend_hold_bars=base_hold_bars + extra, notes=notes)

        return AdaptiveExitDecision(notes=['no adaptive action'])
