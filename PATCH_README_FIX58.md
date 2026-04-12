# FIX58 — architecture stabilization pass for fix57

## What was changed

### P0 — critical architecture
- Enforced effective strategy policy in `backend/core/services/symbol_adaptive.py`:
  - selected strategy now comes from the effective intersection of global + symbol constraints.
  - cache key now includes more runtime/profile/event inputs.
- Split read/write plan building:
  - `build_symbol_plan_readonly()` for GET/diagnostic routes.
  - `build_symbol_plan_persisting()` / default persistent path for worker/runtime.
- Removed hidden DB writes from diagnostic current-plan reads:
  - `/api/v1/settings/runtime-overview`
  - `/api/v1/symbol-profiles/{instrument_id}`
- Reduced hot-path transaction churn:
  - `_store_regime_snapshot()` now updates/adds and flushes, but does not commit per call.
- Reworked timeframe resampling in `backend/core/services/timeframe_engine.py`:
  - session/day anchored bucketing based on first candle of local trading day.
  - incomplete last HTF bucket is dropped by default.

### P0/P1 — signal lifecycle and API honesty
- Added runtime controls to settings model/schema/repo:
  - `pending_review_ttl_sec`
  - `max_pending_per_symbol`
- Added migration:
  - `20260331_01_signal_pending_controls.py`
- Added stale pending expiry in `core/storage/repos/signals.py`.
- Worker now expires stale pending signals before processing a symbol.
- Worker execution path now marks failed TAKE execution as `execution_error` instead of leaving the signal logically stuck.
- `auto_live` without T-Bank credentials now lands in `execution_error` instead of silently keeping the symbol occupied.
- `/api/v1/state*` no longer silently lies with empty successful responses:
  - returns degraded payload with request/error ids and HTTP 503 on backend failure.
- Global exception handler now returns `error_id` as well as `request_id`.

## What was verified locally
- `python -m compileall -q backend` — OK
- `python -m unittest backend.tests.test_timeframe_resample -v` — OK

## What was NOT fully verified in this container
- Full runtime integration with real DB / Redis / worker / broker credentials was not executed here.
- SQLAlchemy-based integration tests could not be run in this container because `sqlalchemy` is not installed in the test environment.
- Frontend runtime validation in browser was not performed here.
