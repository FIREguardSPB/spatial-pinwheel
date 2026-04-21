# Implementation Plan: Sprint 8 - Higher-TF Approval Conversion

## Goal

Improve conversion from strong higher-timeframe candidates toward approval/execution readiness by fixing the main actionability blocker before auto-approval would even matter.

## Baseline

- fresh higher-TF candidates often end as `REJECT` with:
  - `score = 0`
  - `economic_filter_valid = False`
  - hard blockers preserved
- current higher-TF `pending_review -> approved` conversion is near zero, but the dominant issue is upstream: many candidates do not survive economic/actionability gating at all

## Scope

- focus on higher-TF actionability blockers in economics / decision scoring
- keep hard discipline intact for clearly invalid trades
- avoid broad approval automation changes

## Files In Scope

- `backend/core/risk/economic.py`
- `backend/apps/worker/decision_engine/engine.py`
- `backend/tests/` targeted regression coverage

## Success Criteria

- strong higher-TF-led setups are less likely to die with `score=0` only because of overly rigid economic gating
- clearly invalid or uneconomic trades still block
- fresh live higher-TF signals more often reach `pending_review` or better with meaningful actionability metadata
