FIX45 — backlog stabilization pass for FIX44

What was fixed
- RiskManager no longer depends blindly on signal.meta.adaptive_plan.
  - Added safe extraction from top-level signal/adaptive_plan.
  - Added DB-backed fallback from symbol_profiles when adaptive_plan is missing.
  - Added explicit block when a symbol profile is disabled.
- SignalProcessor now rebuilds adaptive_plan on its own if the caller did not pass one.
- Added compatibility module backend/core/ml/time_stop.py so legacy imports do not crash the worker.
- Alembic migration conflict fixed.
  - Economic filter runtime-controls migration now has unique revision id 20260321_01b.
  - Candle-cache migration now depends on 20260321_01b.
- Symbol profiles are now auto-seeded / optionally auto-trained.
  - New helper ensure_symbol_profiles(...)
  - Worker startup now ensures profiles for the current watchlist.
  - Watchlist refresh now ensures/trains profiles for newly added instruments.
  - Watchlist API add/reactivate now seeds symbol profiles immediately.
  - New API endpoint: POST /api/v1/symbol-profiles/ensure
- Event regime is now injected into adaptive symbol planning, not only into final decision merge.
- News feed failure logging is throttled to avoid log spam on repeatedly failing sources.

Operational notes
- This archive still excludes node_modules/dist/build/__pycache__/pyc files on purpose.
- After update, restart backend and worker.
- If the database was already stamped manually around the conflicting 20260321 revisions, align Alembic state before future upgrades.
