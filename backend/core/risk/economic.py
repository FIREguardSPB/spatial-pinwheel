from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from apps.worker.decision_engine.types import Reason, ReasonCode, Severity


@dataclass(slots=True)
class EconomicFilterConfig:
    min_sl_distance_pct: float = 0.08
    min_profit_after_costs_multiplier: float = 1.25
    min_trade_value_rub: float = 1000.0
    min_instrument_price_rub: float = 1.0
    min_tick_floor_rub: float = 0.0
    commission_dominance_warn_ratio: float = 0.30
    volatility_sl_floor_multiplier: float = 0.0
    sl_cost_floor_multiplier: float = 0.0


@dataclass(slots=True)
class EconomicFilterResult:
    is_valid: bool
    block_reason: Reason | None = None
    warnings: list[Reason] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)


class EconomicFilter:
    def __init__(self, config: EconomicFilterConfig):
        self.config = config

    def evaluate(
        self,
        *,
        entry: float,
        sl: float,
        tp: float,
        qty: float,
        fees_bps: float,
        slippage_bps: float,
        atr14: float | None = None,
    ) -> EconomicFilterResult:
        if entry <= 0:
            reason = Reason(
                code=ReasonCode.ECONOMIC_INVALID,
                severity=Severity.BLOCK,
                msg="Economic filter: invalid entry price",
            )
            return EconomicFilterResult(False, block_reason=reason, metrics={"economic_filter_valid": False})

        stop_abs = abs(entry - sl)
        target_abs = abs(tp - entry)
        stop_pct = stop_abs / entry * 100.0
        target_pct = target_abs / entry * 100.0
        atr_pct = ((atr14 or 0.0) / entry * 100.0) if atr14 else 0.0
        total_cost_pct = (float(fees_bps or 0.0) + float(slippage_bps or 0.0)) / 10000.0 * 100.0
        round_trip_cost_rub = entry * ((float(fees_bps or 0.0) + float(slippage_bps or 0.0)) / 10000.0) * 2.0
        min_required_profit_pct = max(total_cost_pct * float(self.config.min_profit_after_costs_multiplier), total_cost_pct)
        min_required_profit_rub = round_trip_cost_rub * max(float(self.config.min_profit_after_costs_multiplier), 1.0)
        min_required_sl_pct = max(
            float(self.config.min_sl_distance_pct),
            total_cost_pct * max(float(self.config.sl_cost_floor_multiplier), 0.0),
            atr_pct * max(float(self.config.volatility_sl_floor_multiplier), 0.0) if atr_pct > 0 else 0.0,
        )
        min_required_sl_rub = max(
            max(float(self.config.min_tick_floor_rub), 0.0),
            entry * (float(self.config.min_sl_distance_pct) / 100.0),
        )
        position_value_rub = entry * max(float(qty or 0.0), 0.0)
        commission_dominance_ratio = (round_trip_cost_rub / stop_abs) if stop_abs > 0 else None
        breakeven_move_pct = total_cost_pct
        expected_profit_after_costs_rub = target_abs - round_trip_cost_rub
        flags: list[str] = []
        warnings: list[Reason] = []

        if stop_pct < float(self.config.min_sl_distance_pct) or stop_abs < min_required_sl_rub:
            flags.append("MICRO_LEVELS_WARNING")
        if commission_dominance_ratio is not None and commission_dominance_ratio >= float(self.config.commission_dominance_warn_ratio):
            flags.append("COMMISSION_DOMINANCE_WARNING")
            warnings.append(
                Reason(
                    code=ReasonCode.ECONOMIC_COMMISSION_DOMINANCE,
                    severity=Severity.WARN,
                    msg=(
                        f"Round-trip costs are {commission_dominance_ratio * 100:.1f}% of stop distance"
                    ),
                )
            )
        if entry < float(self.config.min_instrument_price_rub):
            flags.append("LOW_PRICE_WARNING")

        metrics = {
            "entry_price_rub": round(entry, 6),
            "position_qty": round(float(qty or 0.0), 6),
            "position_value_rub": round(position_value_rub, 4),
            "sl_distance_rub": round(stop_abs, 6),
            "sl_distance_pct": round(stop_pct, 4),
            "tp_distance_rub": round(target_abs, 6),
            "tp_distance_pct": round(target_pct, 4),
            "round_trip_cost_rub": round(round_trip_cost_rub, 6),
            "round_trip_cost_pct": round(total_cost_pct, 4),
            "min_required_sl_pct": round(min_required_sl_pct, 4),
            "min_required_sl_rub": round(min_required_sl_rub, 6),
            "min_required_profit_pct": round(min_required_profit_pct, 4),
            "min_required_profit_rub": round(min_required_profit_rub, 6),
            "expected_profit_after_costs_rub": round(expected_profit_after_costs_rub, 6),
            "config_min_sl_distance_pct": round(float(self.config.min_sl_distance_pct), 6),
            "config_min_profit_after_costs_multiplier": round(float(self.config.min_profit_after_costs_multiplier), 6),
            "config_min_trade_value_rub": round(float(self.config.min_trade_value_rub), 6),
            "config_min_instrument_price_rub": round(float(self.config.min_instrument_price_rub), 6),
            "config_min_tick_floor_rub": round(float(self.config.min_tick_floor_rub), 6),
            "config_volatility_sl_floor_multiplier": round(float(self.config.volatility_sl_floor_multiplier), 6),
            "config_sl_cost_floor_multiplier": round(float(self.config.sl_cost_floor_multiplier), 6),
            "breakeven_move_pct": round(breakeven_move_pct, 4),
            "commission_dominance_ratio": round(commission_dominance_ratio, 4) if commission_dominance_ratio is not None else None,
            "economic_warning_flags": flags,
            "economic_filter_valid": True,
        }

        if entry < float(self.config.min_instrument_price_rub):
            reason = Reason(
                code=ReasonCode.ECONOMIC_LOW_PRICE,
                severity=Severity.BLOCK,
                msg=(
                    f"Instrument price {entry:.4f} RUB < min {float(self.config.min_instrument_price_rub):.2f} RUB"
                ),
            )
            metrics["economic_filter_valid"] = False
            return EconomicFilterResult(False, block_reason=reason, warnings=warnings, metrics=metrics)

        if position_value_rub < float(self.config.min_trade_value_rub):
            reason = Reason(
                code=ReasonCode.ECONOMIC_MIN_TRADE_VALUE,
                severity=Severity.BLOCK,
                msg=(
                    f"Position value {position_value_rub:.2f} RUB < min {float(self.config.min_trade_value_rub):.2f} RUB"
                ),
            )
            metrics["economic_filter_valid"] = False
            return EconomicFilterResult(False, block_reason=reason, warnings=warnings, metrics=metrics)

        if stop_pct < min_required_sl_pct or stop_abs < min_required_sl_rub:
            reason = Reason(
                code=ReasonCode.ECONOMIC_MICRO_LEVELS,
                severity=Severity.BLOCK,
                msg=(
                    f"SL distance {stop_pct:.4f}%/{stop_abs:.4f} RUB < required {min_required_sl_pct:.4f}%/{min_required_sl_rub:.4f} RUB"
                ),
            )
            metrics["economic_filter_valid"] = False
            return EconomicFilterResult(False, block_reason=reason, warnings=warnings, metrics=metrics)

        if target_pct < min_required_profit_pct or target_abs < min_required_profit_rub or expected_profit_after_costs_rub <= 0:
            reason = Reason(
                code=ReasonCode.ECONOMIC_PROFIT_TOO_SMALL,
                severity=Severity.BLOCK,
                msg=(
                    f"Expected profit {target_pct:.4f}%/{target_abs:.4f} RUB < required {min_required_profit_pct:.4f}%/{min_required_profit_rub:.4f} RUB"
                ),
            )
            metrics["economic_filter_valid"] = False
            return EconomicFilterResult(False, block_reason=reason, warnings=warnings, metrics=metrics)

        return EconomicFilterResult(True, warnings=warnings, metrics=metrics)
