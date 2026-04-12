"""RiskManager — application-level trade guards, sizing and capital reallocation."""
from __future__ import annotations

import importlib
import logging
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from core.risk.correlation import check_correlation
try:
    _storage_models = importlib.import_module("core.storage.models")
except Exception:  # pragma: no cover
    _storage_models = None


class _MissingModel:
    qty = 0
    ts = 0
    updated_ts = 0
    instrument_id = None
    side = None
    status = None
    type = None


DecisionLog = getattr(_storage_models, "DecisionLog", _MissingModel) if _storage_models is not None else _MissingModel
Position = getattr(_storage_models, "Position", _MissingModel) if _storage_models is not None else _MissingModel
Signal = getattr(_storage_models, "Signal", _MissingModel) if _storage_models is not None else _MissingModel
from core.storage.repos import settings as settings_repo

logger = logging.getLogger(__name__)
_MSK = ZoneInfo("Europe/Moscow")


def _coerce_number(value: Any, default: float = 0.0, *, as_int: bool = False):
    if isinstance(value, bool):
        return int(value) if as_int else float(value)
    if isinstance(value, (int, float)):
        return int(value) if as_int else float(value)
    try:
        text = str(value).strip()
        if not text or text.startswith('<MagicMock'):
            raise ValueError
        return int(float(text)) if as_int else float(text)
    except Exception:
        return int(default) if as_int else float(default)


def _setting_int(obj: Any, name: str, default: int) -> int:
    return int(_coerce_number(getattr(obj, name, default), default, as_int=True))


def _setting_float(obj: Any, name: str, default: float) -> float:
    return float(_coerce_number(getattr(obj, name, default), default, as_int=False))


def _safe_get_symbol_profile(instrument_id: str | None, *, db: Session):
    if not instrument_id:
        return None
    try:
        from core.services.symbol_adaptive import get_symbol_profile
        return get_symbol_profile(instrument_id, db=db)
    except Exception:
        logger.debug("symbol profile unavailable for %s", instrument_id, exc_info=True)
        return None


def _start_of_day_ms() -> int:
    now_utc = datetime.now(timezone.utc)
    now_msk = now_utc.astimezone(_MSK)
    sod_msk = now_msk.replace(hour=0, minute=0, second=0, microsecond=0)
    return int(sod_msk.astimezone(timezone.utc).timestamp() * 1000)


class RiskManager:
    def __init__(self, db: Session):
        self.db = db
        self.settings = None
        self.last_check_details: dict[str, Any] = {}
        self.last_size_details: dict[str, Any] = {}
        self._reload_settings()

    def _reload_settings(self) -> None:
        self.settings = settings_repo.get_settings(self.db)

    def _risk_window_start_ms(self) -> int:
        sod = _start_of_day_ms()
        reset_ts = (
            self.db.query(func.max(DecisionLog.ts))
            .filter(DecisionLog.type == "risk_daily_reset")
            .scalar()
        )
        return max(int(sod), int(reset_ts or 0))

    def _extract_signal_score(self, signal: Any) -> int:
        if isinstance(signal, dict):
            meta = signal.get("meta") or {}
            decision = meta.get("decision") if isinstance(meta, dict) else {}
            decision = decision if isinstance(decision, dict) else {}
            return int(decision.get("score") or decision.get("score_pct") or signal.get("de_score") or 0)
        meta = getattr(signal, "meta", None) or {}
        decision = meta.get("decision") if isinstance(meta, dict) else {}
        decision = decision if isinstance(decision, dict) else {}
        return int(decision.get("score") or decision.get("score_pct") or getattr(signal, "de_score", 0) or 0)

    def _signal_instrument_id(self, signal: Any) -> str | None:
        if isinstance(signal, dict):
            return signal.get('instrument_id') or signal.get('ticker')
        return getattr(signal, 'instrument_id', None) or getattr(signal, 'ticker', None)

    def _fallback_adaptive_plan(self, instrument_id: str | None) -> dict[str, Any]:
        if not instrument_id:
            return {}
        profile = _safe_get_symbol_profile(instrument_id, db=self.db)
        if not profile:
            return {}
        base_threshold = _setting_int(self.settings, 'decision_threshold', 70)
        threshold_offset = int(profile.get('decision_threshold_offset') or 0)
        preferred = str(profile.get('preferred_strategies') or getattr(self.settings, 'strategy_name', 'breakout') or 'breakout')
        strategy_name = next((item.strip() for item in preferred.split(',') if item.strip()), 'breakout')
        hold_bars = int(profile.get('last_hold_bars') or profile.get('hold_bars_base') or getattr(self.settings, 'time_stop_bars', 12) or 12)
        return {
            'strategy_name': strategy_name,
            'regime': str(profile.get('last_regime') or 'balanced'),
            'decision_threshold': max(15, min(95, base_threshold + threshold_offset)),
            'hold_bars': max(1, hold_bars),
            'reentry_cooldown_sec': int(profile.get('reentry_cooldown_sec') or _setting_int(self.settings, 'signal_reentry_cooldown_sec', 300)),
            'risk_multiplier': float(profile.get('risk_multiplier') or 1.0),
            'source': 'profile_fallback',
        }

    def _extract_adaptive_plan(self, signal: Any) -> dict[str, Any]:
        instrument_id = self._signal_instrument_id(signal)
        if isinstance(signal, dict):
            if isinstance(signal.get('adaptive_plan'), dict):
                return dict(signal.get('adaptive_plan') or {})
            meta = signal.get('meta') or {}
        else:
            top_level = getattr(signal, 'adaptive_plan', None)
            if isinstance(top_level, dict):
                return dict(top_level or {})
            meta = getattr(signal, 'meta', None) or {}
        if isinstance(meta, dict):
            plan = meta.get('adaptive_plan') or {}
            if isinstance(plan, dict) and plan:
                return dict(plan)
        return self._fallback_adaptive_plan(instrument_id)

    def _effective_max_positions(self, signal_score: int) -> int:
        base = _setting_int(self.settings, 'max_concurrent_positions', 4)
        strong_threshold = _setting_int(self.settings, 'strong_signal_score_threshold', 80)
        strong_bonus = _setting_int(self.settings, 'strong_signal_position_bonus', 2)
        if signal_score >= strong_threshold:
            return max(base, base + max(0, strong_bonus))
        return base

    def check_new_signal(self, signal, candles_map: dict | None = None) -> tuple[bool, str]:
        self._reload_settings()
        self.last_check_details = {}
        if not self.settings:
            self.last_check_details = {"allowed": True, "reason": "no_settings", "limits": {}}
            return True, "No settings — allowing by default"

        s = self.settings
        instrument_id = self._signal_instrument_id(signal)
        side = signal.get('side') if isinstance(signal, dict) else getattr(signal, 'side', None)
        signal_score = self._extract_signal_score(signal)
        adaptive_plan = self._extract_adaptive_plan(signal)
        effective_max_positions = self._effective_max_positions(signal_score)

        try:
            active_count = self.db.query(Position).filter(Position.qty > 0).count()
        except Exception:
            try:
                active_count = self.db.query(Position).count()
            except Exception:
                active_count = 0
        active_count = _coerce_number(active_count, 0, as_int=True)
        profile = _safe_get_symbol_profile(instrument_id, db=self.db) if instrument_id else None
        if profile and not bool(profile.get('enabled', True)):
            self.last_check_details.update({"allowed": False, "blocked_by": "symbol_profile_disabled"})
            return False, f"Symbol profile disabled for {instrument_id}"

        self.last_check_details = {
            "allowed": True,
            "instrument_id": instrument_id,
            "side": side,
            "signal_score": signal_score,
            "limits": {
                "max_concurrent_positions": _setting_int(s, 'max_concurrent_positions', 0),
                "effective_max_concurrent_positions": effective_max_positions,
                "daily_loss_limit_pct": _setting_float(s, 'daily_loss_limit_pct', 0),
                "max_trades_per_day": _setting_int(s, 'max_trades_per_day', 0),
                "cooldown_losses": _setting_int(s, 'cooldown_losses', 0),
                "cooldown_minutes": _setting_int(s, 'cooldown_minutes', 0),
                "signal_reentry_cooldown_sec": _setting_int(s, 'signal_reentry_cooldown_sec', 0),
            },
            "current": {"active_positions": active_count},
            "risk_window_start_ms": self._risk_window_start_ms(),
        }
        if active_count >= effective_max_positions:
            self.last_check_details.update({
                "allowed": False,
                "blocked_by": "max_concurrent_positions",
                "current": {**self.last_check_details["current"], "active_positions": active_count},
                "threshold": effective_max_positions,
            })
            return False, f"Max positions reached ({active_count}/{effective_max_positions})"

        today_pnl = self._get_today_realized_pnl()
        balance = self._get_paper_balance()
        limit = balance * (_setting_float(s, 'daily_loss_limit_pct', 0.0) / 100.0)
        self.last_check_details["current"].update({"today_realized_pnl": today_pnl, "balance": balance, "daily_loss_limit_rub": limit})
        if today_pnl < 0 and abs(today_pnl) >= limit:
            self.last_check_details.update({"allowed": False, "blocked_by": "daily_loss_limit", "threshold": -limit})
            return False, (
                f"Daily loss limit hit: {today_pnl:.2f} >= -{limit:.2f} "
                f"({s.daily_loss_limit_pct}% of {balance:.2f})"
            )

        max_trades_per_day = _setting_int(s, 'max_trades_per_day', 0)
        if max_trades_per_day > 0:
            today_count = self._get_today_trades_count()
            self.last_check_details["current"]["today_trades_count"] = today_count
            if today_count >= max_trades_per_day:
                self.last_check_details.update({"allowed": False, "blocked_by": "max_trades_per_day", "threshold": int(max_trades_per_day)})
                return False, f"Max trades per day reached ({today_count}/{max_trades_per_day})"

        cooldown_losses = _setting_int(s, 'cooldown_losses', 0)
        cooldown_minutes = _setting_int(s, 'cooldown_minutes', 0)
        if cooldown_losses > 0 and cooldown_minutes > 0:
            in_cooldown, msg, detail = self._check_loss_streak_cooldown(cooldown_losses, cooldown_minutes)
            if in_cooldown:
                self.last_check_details.update({"allowed": False, "blocked_by": "loss_streak_cooldown", **detail})
                return False, msg

        reentry_cooldown = int((adaptive_plan.get('reentry_cooldown_sec') if adaptive_plan else None) or _setting_int(s, 'signal_reentry_cooldown_sec', 300) or 0)
        if instrument_id and side and reentry_cooldown > 0:
            blocked, msg = self._check_signal_reentry_cooldown(instrument_id, side, reentry_cooldown)
            if blocked:
                self.last_check_details.update({"allowed": False, "blocked_by": "signal_reentry_cooldown", "threshold": reentry_cooldown})
                return False, msg

        corr_threshold = _setting_float(s, 'correlation_threshold', 0.8)
        max_corr = _setting_int(s, 'max_correlated_positions', 2)
        if candles_map is not None and instrument_id:
            corr_ok, corr_msg = check_correlation(
                self.db, instrument_id, candles_map,
                threshold=corr_threshold, max_correlated=max_corr,
            )
            if not corr_ok:
                self.last_check_details.update({"allowed": False, "blocked_by": "correlation_limit", "threshold": corr_threshold})
                return False, corr_msg

        return True, "OK"

    def _recent_closed_positions(self, limit: int = 8) -> list[Position]:
        query = self.db.query(Position)
        try:
            query = query.filter(Position.qty == 0, Position.updated_ts >= self._risk_window_start_ms())
            query = query.order_by(Position.updated_ts.desc())
        except Exception:
            logger.debug("recent closed positions fallback path", exc_info=True)
        return query.limit(limit).all()

    def _current_portfolio_pressure(self, balance: float) -> dict[str, float]:
        open_exposure = self._get_current_open_exposure()
        exposure_pct = (open_exposure / max(balance, 1e-9)) * 100.0 if balance > 0 else 0.0
        cap_pct = float(getattr(self.settings, 'max_total_exposure_pct_balance', 35.0) or 35.0)
        cap_ratio = exposure_pct / max(cap_pct, 1e-9) if cap_pct > 0 else 0.0
        return {
            'open_exposure': round(open_exposure, 4),
            'exposure_pct_balance': round(exposure_pct, 4),
            'exposure_cap_pct': round(cap_pct, 4),
            'exposure_cap_ratio': round(cap_ratio, 4),
        }

    def _portfolio_risk_multiplier(self, balance: float) -> tuple[float, dict[str, Any]]:
        if not self.settings or not bool(getattr(self.settings, 'pm_risk_throttle_enabled', True)):
            return 1.0, {
                'enabled': False,
                'portfolio_risk_multiplier': 1.0,
                'reasons': [],
            }

        today_pnl = self._get_today_realized_pnl()
        drawdown_pct = max(0.0, (-today_pnl / max(balance, 1e-9)) * 100.0) if today_pnl < 0 else 0.0
        recent = self._recent_closed_positions(limit=max(8, _setting_int(self.settings, 'pm_loss_streak_hard_limit', 4) + 2))
        loss_streak = 0
        for pos in recent:
            if float(pos.realized_pnl or 0.0) < 0:
                loss_streak += 1
            else:
                break
        soft_dd = _setting_float(self.settings, 'pm_drawdown_soft_limit_pct', 1.5)
        hard_dd = max(soft_dd + 0.01, _setting_float(self.settings, 'pm_drawdown_hard_limit_pct', 3.0))
        soft_ls = _setting_int(self.settings, 'pm_loss_streak_soft_limit', 2)
        hard_ls = max(soft_ls + 1, _setting_int(self.settings, 'pm_loss_streak_hard_limit', 4))
        min_mult = _setting_float(self.settings, 'pm_min_risk_multiplier', 0.35)

        dd_mult = 1.0
        ls_mult = 1.0
        reasons: list[str] = []
        if drawdown_pct >= soft_dd:
            dd_progress = min(1.0, max(0.0, (drawdown_pct - soft_dd) / max(0.01, hard_dd - soft_dd)))
            dd_mult = 1.0 - (1.0 - min_mult) * dd_progress
            reasons.append(f'drawdown={drawdown_pct:.2f}%')
        if loss_streak >= soft_ls:
            ls_progress = min(1.0, max(0.0, (loss_streak - soft_ls) / max(1, hard_ls - soft_ls)))
            ls_mult = 1.0 - (1.0 - min_mult) * ls_progress
            reasons.append(f'loss_streak={loss_streak}')

        pressure = self._current_portfolio_pressure(balance)
        pressure_mult = 1.0
        if pressure['exposure_cap_ratio'] >= 0.85:
            overflow = min(1.0, max(0.0, pressure['exposure_cap_ratio'] - 0.85) / 0.35)
            pressure_mult = max(min_mult, 1.0 - 0.30 * overflow)
            reasons.append(f'exposure={pressure["exposure_pct_balance"]:.2f}%')

        multiplier = max(min_mult, min(dd_mult, ls_mult, pressure_mult))
        return multiplier, {
            'enabled': True,
            'portfolio_risk_multiplier': round(multiplier, 4),
            'drawdown_pct': round(drawdown_pct, 4),
            'loss_streak': int(loss_streak),
            'soft_drawdown_pct': round(soft_dd, 4),
            'hard_drawdown_pct': round(hard_dd, 4),
            'soft_loss_streak': int(soft_ls),
            'hard_loss_streak': int(hard_ls),
            'min_risk_multiplier': round(min_mult, 4),
            'pressure': pressure,
            'reasons': reasons,
        }

    def calculate_position_size(self, entry: float, sl: float, balance: float | None = None, lot_size: int = 1, risk_multiplier: float = 1.0) -> int:
        self._reload_settings()
        self.last_size_details = {}
        if balance is None:
            balance = self._get_paper_balance()
        if not self.settings:
            self.last_size_details = {'allowed': True, 'portfolio_risk_multiplier': 1.0, 'effective_risk_multiplier': float(max(0.1, risk_multiplier or 1.0))}
            return max(1, lot_size)

        portfolio_mult, portfolio_detail = self._portfolio_risk_multiplier(balance)
        base_signal_mult = float(max(0.1, risk_multiplier or 1.0))
        effective_signal_mult = max(0.1, base_signal_mult * portfolio_mult)
        risk_pct = (_setting_float(self.settings, 'risk_per_trade_pct', 1.0) / 100.0) * effective_signal_mult
        risk_amount = balance * risk_pct
        sl_distance = abs(entry - sl)
        if sl_distance < 1e-9:
            logger.warning("SL distance ~zero, returning 0 lots")
            self.last_size_details = {**portfolio_detail, 'allowed': False, 'reason': 'zero_sl_distance', 'effective_risk_multiplier': effective_signal_mult}
            return 0

        raw_units = risk_amount / sl_distance
        per_position_cap_notional = balance * (_setting_float(self.settings, 'max_position_notional_pct_balance', 100.0) / 100.0)
        total_exposure_cap = balance * (_setting_float(self.settings, 'max_total_exposure_pct_balance', 100.0) / 100.0)
        current_open_exposure = self._get_current_open_exposure()
        remaining_total_notional = max(0.0, total_exposure_cap - current_open_exposure)

        per_position_cap_qty = (per_position_cap_notional / entry) if entry > 0 else 0.0
        remaining_cap_qty = (remaining_total_notional / entry) if entry > 0 else 0.0
        capped_units = min(raw_units, per_position_cap_qty, remaining_cap_qty)
        lots = int(capped_units // max(1, lot_size)) * max(1, lot_size)
        lots = max(0, lots)
        self.last_size_details = {
            **portfolio_detail,
            'allowed': lots > 0,
            'base_signal_risk_multiplier': round(base_signal_mult, 4),
            'effective_risk_multiplier': round(effective_signal_mult, 4),
            'risk_pct': round(risk_pct * 100.0, 4),
            'risk_amount_rub': round(risk_amount, 4),
            'sl_distance': round(sl_distance, 8),
            'raw_units': round(raw_units, 4),
            'per_position_cap_qty': round(per_position_cap_qty, 4),
            'remaining_cap_qty': round(remaining_cap_qty, 4),
            'current_open_exposure': round(current_open_exposure, 4),
            'lots': int(lots),
        }
        logger.debug(
            "size: balance=%.2f risk_pct=%.4f risk_amount=%.2f sl_dist=%.6f raw=%.2f per_pos_cap_qty=%.2f remaining_cap_qty=%.2f portfolio_mult=%.3f -> %d",
            balance, risk_pct, risk_amount, sl_distance, raw_units, per_position_cap_qty, remaining_cap_qty, portfolio_mult, lots,
        )
        return lots

    def normalize_qty(self, qty: float, lot_size: int = 1) -> int:
        if lot_size <= 0:
            lot_size = 1
        return max(1, int(float(qty) // lot_size) * lot_size)

    def _get_today_realized_pnl(self) -> float:
        cutoff = self._risk_window_start_ms()
        try:
            result = (self.db.query(func.sum(Position.realized_pnl))
                      .filter(Position.updated_ts >= cutoff).scalar())
        except Exception:
            logger.debug("today realized pnl fallback path", exc_info=True)
            result = self.db.query(func.sum(Position.realized_pnl)).scalar()
        return float(result or 0.0)

    def _get_today_trades_count(self) -> int:
        cutoff = self._risk_window_start_ms()
        try:
            return (
                self.db.query(DecisionLog)
                .filter(DecisionLog.type == 'trade_filled', DecisionLog.ts >= cutoff)
                .count()
            )
        except Exception:
            logger.debug("today trades count fallback path", exc_info=True)
            return self.db.query(DecisionLog).count()

    def _check_loss_streak_cooldown(self, loss_streak: int, cooldown_minutes: int) -> tuple[bool, str, dict[str, Any]]:
        cutoff = self._risk_window_start_ms()
        query = self.db.query(Position)
        try:
            query = (query
                     .filter(Position.qty == 0, Position.realized_pnl < 0, Position.updated_ts >= cutoff)
                     .order_by(Position.updated_ts.desc()))
        except Exception:
            logger.debug("loss streak cooldown fallback path", exc_info=True)
        recent = query.limit(loss_streak).all()
        if len(recent) < loss_streak:
            return False, "", {"loss_count": len(recent), "threshold": loss_streak}
        latest_ts = max(float(p.updated_ts) for p in recent)
        elapsed = (time.time() * 1000 - latest_ts) / 60_000
        if elapsed < cooldown_minutes:
            remaining = max(0.0, cooldown_minutes - elapsed)
            return True, f"Cooldown: {loss_streak} losses in a row, {remaining:.0f}min remaining", {
                "loss_count": loss_streak,
                "threshold": loss_streak,
                "cooldown_remaining_min": remaining,
                "cooldown_minutes": cooldown_minutes,
            }
        return False, "", {"loss_count": loss_streak, "cooldown_minutes": cooldown_minutes, "cooldown_remaining_min": 0}

    def _check_signal_reentry_cooldown(self, instrument_id: str, side: str, cooldown_sec: int) -> tuple[bool, str]:
        cutoff = int(time.time() * 1000) - cooldown_sec * 1000
        try:
            recent = (
                self.db.query(Signal.created_ts)
                .filter(
                    Signal.instrument_id == instrument_id,
                    Signal.side == side,
                    Signal.status == 'executed',
                    Signal.created_ts >= cutoff,
                )
                .order_by(Signal.created_ts.desc())
                .first()
            )
        except Exception:
            logger.debug("signal reentry cooldown fallback path", exc_info=True)
            recent = self.db.query(Signal).first()
        if recent:
            return True, f"Recent executed {side} trade for {instrument_id} within cooldown ({cooldown_sec}s)"
        return False, ""

    def _get_current_open_exposure(self) -> float:
        query = self.db.query(Position)
        try:
            open_positions = query.filter(Position.qty > 0).all()
        except Exception:
            logger.debug("current exposure fallback path", exc_info=True)
            open_positions = query.all()
        return sum(float(getattr(p, 'qty', 0) or 0) * float(getattr(p, 'avg_price', 0) or 0) for p in open_positions)

    def _get_paper_balance(self) -> float:
        if self.settings and self.settings.account_balance:
            return float(self.settings.account_balance)
        return 100_000.0
