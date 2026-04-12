FIX69 — UoW execution path, freeze analytics, frontend/backend stability pass

Closed plan block:
- Part 12 — trading-quality runtime stabilization + frontend/backend integration hardening

Implemented:
- signal execution unit-of-work with persisted execution_uow / execution_error.unit_of_work metadata
- richer auto freeze/degrade analytics: execution_error_streak, rejection_streak, recent_execution_errors
- static MOEX schedule fallback with real MSK session windows instead of unknown/blank snapshot
- softer frontend handling for degraded backend GET paths; reduced false-disconnect noise
- dashboard/manual-order trade mode now falls back to /state mode when /settings is late/unavailable
- query placeholderData/retry for dashboard/signals/schedule/candles/orders/positions metrics
- schedule panel now explains static fallback instead of surfacing it as a hard failure
- compacted ugly signal table blocks in geometry/AI columns

Validation performed:
- python3 -m compileall -q backend
- PYTHONPATH=backend python3 -m unittest backend.tests.test_timeframe_resample backend.tests.test_degrade_policy backend.tests.test_trading_schedule_static -v
- npx tsc --noEmit
