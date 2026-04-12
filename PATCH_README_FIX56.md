# FIX56 — Adaptive geometry optimizer

What changed:
- Added `core/services/geometry_optimizer.py`
- `SignalProcessor` now runs an initial geometry optimization pass before risk sizing
- If DE rejects/skips mainly due to economics, a rescue geometry pass re-shapes SL/TP/hold and re-runs DE once
- AI prompt now includes geometry optimizer context
- Signals API exposes geometry optimizer state
- Signals UI shows adaptive geometry badges and original vs optimized SL/TP

Scope:
- widen micro-stops to economically sane minimums
- extend TP to target RR floor
- extend hold bars when geometry expands
- add higher-timeframe hint on rescue path

Notes:
- This does not yet switch the real execution timeframe source; it surfaces an HTF hint and adapts geometry within the existing 1m-driven pipeline.
- Global risk contour still remains the final safety boundary.
