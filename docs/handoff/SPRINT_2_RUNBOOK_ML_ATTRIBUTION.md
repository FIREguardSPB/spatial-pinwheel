# Sprint 2 runbook — ML dataset, attribution, and compact observability

## What to inspect now

### 1. Dataset diagnostics
Use:
- `GET /api/v1/ml/dataset?lookback_days=120&sample_limit=20`

What changed:
- `take_fill` now reports `fill_outcomes` and `label_sources`.
- `take_fill.stats.diagnostics` now includes breakdowns by:
  - strategy,
  - regime,
  - instrument,
  - session hour,
  - fill outcome.
- `trade_outcome.stats.diagnostics` now includes the same main slices plus label source.
- `trade_outcome` also reports `duplicate_close_logs_skipped`.

### 2. Attribution report
Use:
- `GET /api/v1/ml/attribution?days=30&limit=50`

Main counters:
- `signal_generated`
- `take_candidate`
- `take_decided`
- `take_vetoed_by_ml`
- `take_blocked_by_guardrail`
- `take_not_filled`
- `trade_filled`
- `trade_closed_profit`
- `trade_closed_loss`

This endpoint is intended for recent forensic windows and should answer which layer killed or altered a trade path.

### 3. Runtime model freshness
Use:
- `GET /api/v1/ml/status`
- `GET /api/v1/ui/runtime`

What changed:
- active/recent model rows now include `freshness_minutes` and `freshness_hours`.
- UI can show last train timestamp without loading heavy model payloads.

### 4. Hot read-model for signals
Use:
- `GET /api/v1/ui/signals`

Compact `meta.ml_overlay` now carries only lightweight fields needed in the hot path:
- probabilities,
- action,
- reason,
- target/fill model ids.

`ai_decision.reasoning` and `ai_decision.key_factors` are intentionally excluded from compact mode to keep payloads tight.

## Current code-level finding on `take_fill`
Before Sprint 2 hardening, `take_fill` negatives were derived mostly from the *absence* of execution / closed position. That made the class imbalance visible, but not very explainable.

After the hardening pass, negatives are bucketed explicitly where possible:
- `execution_risk_block`
- `signal_risk_block`
- `execution_error`
- `rejected`
- `approved_not_executed`
- `pending_not_executed`
- `expired_without_fill`
- fallback `not_filled`

This does **not** guarantee perfect historical attribution for older data if earlier logs were missing or inconsistent. In that case the fallback buckets still appear, which is expected and should be treated as an observability gap rather than hidden.
