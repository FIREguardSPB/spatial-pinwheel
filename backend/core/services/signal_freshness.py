from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.services.timeframe_engine import timeframe_ms, normalize_timeframe


@dataclass
class SignalFreshnessResult:
    enabled: bool
    age_bars: float | None
    age_sec: int | None
    grace_bars: float
    max_bars: float
    penalty_per_bar: int
    penalty_points: int
    adjusted_score: int
    blocked: bool
    applied: bool
    reason: str

    def to_meta(self) -> dict[str, Any]:
        return {
            'enabled': self.enabled,
            'age_bars': None if self.age_bars is None else round(float(self.age_bars), 3),
            'age_sec': self.age_sec,
            'grace_bars': round(float(self.grace_bars), 3),
            'max_bars': round(float(self.max_bars), 3),
            'penalty_per_bar': int(self.penalty_per_bar),
            'penalty_points': int(self.penalty_points),
            'adjusted_score': int(self.adjusted_score),
            'blocked': bool(self.blocked),
            'applied': bool(self.applied),
            'reason': self.reason,
        }


def compute_signal_age(
    *,
    analysis_ts: int | None,
    execution_ts: int | None,
    execution_timeframe: str | None,
) -> tuple[int | None, float | None]:
    if not analysis_ts or not execution_ts or execution_ts <= analysis_ts:
        return 0, 0.0
    age_sec = max(0, int((int(execution_ts) - int(analysis_ts)) / 1000))
    tf_ms = max(60_000, timeframe_ms(normalize_timeframe(execution_timeframe, '1m')))
    age_bars = age_sec * 1000 / tf_ms
    return age_sec, age_bars


def apply_signal_freshness(
    *,
    decision: str,
    score: int,
    threshold: int,
    analysis_ts: int | None,
    execution_ts: int | None,
    execution_timeframe: str | None,
    settings: Any,
) -> tuple[str, int, SignalFreshnessResult]:
    enabled = bool(getattr(settings, 'signal_freshness_enabled', True))
    grace_bars = float(getattr(settings, 'signal_freshness_grace_bars', 1.0) or 1.0)
    max_bars = float(getattr(settings, 'signal_freshness_max_bars', 3.0) or 3.0)
    penalty_per_bar = int(getattr(settings, 'signal_freshness_penalty_per_bar', 6) or 6)
    age_sec, age_bars = compute_signal_age(
        analysis_ts=analysis_ts,
        execution_ts=execution_ts,
        execution_timeframe=execution_timeframe,
    )
    if not enabled:
        result = SignalFreshnessResult(enabled=False, age_bars=age_bars, age_sec=age_sec, grace_bars=grace_bars, max_bars=max_bars, penalty_per_bar=penalty_per_bar, penalty_points=0, adjusted_score=int(score), blocked=False, applied=False, reason='signal freshness disabled')
        return decision, int(score), result
    if age_bars is None:
        result = SignalFreshnessResult(enabled=True, age_bars=None, age_sec=age_sec, grace_bars=grace_bars, max_bars=max_bars, penalty_per_bar=penalty_per_bar, penalty_points=0, adjusted_score=int(score), blocked=False, applied=False, reason='no signal age available')
        return decision, int(score), result

    excess_bars = max(0.0, float(age_bars) - grace_bars)
    penalty_points = int(round(excess_bars * penalty_per_bar)) if excess_bars > 0 else 0
    adjusted_score = max(0, int(score) - penalty_points)
    blocked = bool(age_bars > max_bars and decision == 'TAKE')
    final_decision = decision
    if blocked:
        final_decision = 'SKIP'
        reason = f'stale signal blocked: age={age_bars:.2f} bars > max={max_bars:.2f}'
    elif decision == 'TAKE' and adjusted_score < int(threshold):
        final_decision = 'SKIP'
        reason = f'signal freshness penalty demoted TAKE: age={age_bars:.2f} bars penalty={penalty_points}'
    elif penalty_points > 0:
        reason = f'signal freshness penalty applied: age={age_bars:.2f} bars penalty={penalty_points}'
    else:
        reason = 'signal is fresh'

    result = SignalFreshnessResult(
        enabled=True,
        age_bars=age_bars,
        age_sec=age_sec,
        grace_bars=grace_bars,
        max_bars=max_bars,
        penalty_per_bar=penalty_per_bar,
        penalty_points=penalty_points,
        adjusted_score=adjusted_score,
        blocked=blocked,
        applied=penalty_points > 0 or blocked,
        reason=reason,
    )
    return final_decision, adjusted_score, result
