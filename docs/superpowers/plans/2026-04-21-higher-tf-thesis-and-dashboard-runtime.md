# Implementation Plan: Higher-TF Thesis And Dashboard Runtime

## Scope

This plan covers two tightly related tracks that should be implemented together:

1. Strengthen higher-timeframe thesis formation so `5m/15m` can win on their own merit more often instead of losing to `1m` execution fallback.
2. Improve dashboard runtime clarity so bot start, worker heartbeat, and degraded runtime states are visible without confusing the operator.

## Files In Scope

- `backend/core/services/timeframe_engine.py`
  - Expand higher-TF thesis detection beyond the current narrow breakout continuation pattern.
- `backend/tests/test_timeframe_thesis_selection.py`
  - Add tests for new higher-TF thesis scenarios and selection outcomes.
- `src/features/dashboard/DashboardPage.tsx`
  - Improve operator-facing start/heartbeat/degraded-runtime messaging.
- `src/__tests__/DashboardPage.test.tsx`
  - Add regression coverage for start pending state and worker heartbeat rendering.

## Implementation Tasks

### 1. Expand higher-TF thesis scenarios with TDD

- Add failing tests for at least these cases:
  - `5m/15m` trend continuation without a fresh breakout print on the last bar
  - pullback-hold continuation in an established higher-TF trend
  - reclaim / failed-breakdown recovery on higher TF
- Keep the implementation inside `build_higher_tf_continuation_thesis(...)` unless a tiny helper is clearly needed.
- Preserve existing behavior for the already-tested breakout continuation path.

### 2. Verify selection metadata still tells the truth

- Ensure existing selection tests still pass.
- If new thesis scenarios cause `5m/15m` to win more often, verify `timeframe_selection_reason`, `thesis_timeframe`, and `timeframe_competition` stay coherent.

### 3. Improve dashboard runtime UX with TDD

- Add failing frontend tests for:
  - start button pending/starting feedback while `useStartBot()` is in flight
  - explicit worker heartbeat visibility when worker status is missing/offline/degraded
  - retaining already-loaded dashboard content while showing degraded runtime hints
- Keep the change minimal and local to `DashboardPage.tsx` unless a tiny presentational helper is justified.

### 4. Verification

- Run targeted backend tests:
  - `backend/tests/test_timeframe_thesis_selection.py`
- Run targeted frontend tests:
  - `src/__tests__/DashboardPage.test.tsx`
- Verify in DevTools that:
  - dashboard shows clearer worker heartbeat/start status
  - loaded content is not replaced by a blank fatal error during transient issues

## Notes

- Do not redesign the whole timeframe engine.
- Do not rebuild dashboard data fetching.
- Prefer minimal additions that increase higher-TF expressiveness and operator clarity.
