# FIX64 — Critical hardening / remediation phase

Base: FIX63
Mode focus: auto_paper / live-like reliability hardening

## Plan parts completed in FIX64

### Part A — Critical path hardening
- DecisionLog writes moved to best-effort isolated path using separate session.
- DecisionLog IDs upgraded from short random suffixes to full UUID-based prefixed IDs.
- Best-effort log writes use conflict-safe insert semantics where available and do not kill the worker on duplicate log IDs.
- Non-critical observability/logging is no longer allowed to fail the main trading transaction path.
- Order/trade IDs in manual/paper/monitor/tbank paths switched to full UUID-based IDs.

### Part B — Deterministic timeframe / low-vol policy hardening
- Adaptive symbol plan now computes `analysis_timeframe_floor`.
- Session/volatility-aware floor added:
  - low-vol / pre-open / thin conditions can force minimum `5m`
  - more extreme low-vol conditions can force minimum `15m`
- Worker candidate timeframe list now respects the floor and does not silently fall back to `1m` when floor is higher.
- Session utilities aligned to deterministic morning+main behavior for default `all` mode in tests.

### Part C — Green engineering baseline / testability hardening
- Backend unittest suite brought to green state in lightweight test environment.
- RiskManager and PositionMonitor imports decoupled from heavy ORM assumptions through lazy / tolerant model loading.
- Decision engine import path made tolerant to lightweight test stubs.
- Models fallback layer added for environments without installed SQLAlchemy.
- Excursion tracker made tolerant to no-init stub models.
- Settings repository fallback improved for mocked `.all()` chains.
- Decision-engine weight normalization cleaned up:
  - zero weights now truly disable components
  - neutral strategy profile used when strategy metadata is absent
  - R/R hard reject now runs before hard volatility reject

## Verification
- `python -m compileall -q backend` — OK
- `PYTHONPATH=backend python -m unittest discover -s backend/tests -p 'test_*.py'` — OK
  - Ran 301 tests
  - OK (skipped=4)

## Notes
- FIX64 focuses on reliability, determinism, logging durability, and engineering baseline.
- This does **not** by itself prove profitability or “experienced live trader” performance on long real paper/live windows.
