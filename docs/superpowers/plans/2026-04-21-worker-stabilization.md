# Implementation Plan: Worker Stabilization

## Scope

This plan stabilizes the existing Python worker so the system can produce live analysis and signals again.

It does not attempt a worker rewrite.

## Files In Scope

- `backend/apps/worker/main.py`
  - Primary runtime loop, heartbeat publishing, polling, analysis scheduling, and worker lifecycle.
- `backend/core/services/worker_status.py`
  - Worker heartbeat semantics and read/write expectations.
- `backend/tests/` new or updated tests
  - Regression coverage for worker health/heartbeat behavior and the identified failure mode.

## Implementation Tasks

### 1. Root-cause investigation before code changes

- Inspect worker memory-sensitive structures in `main.py`:
  - ticker/watchlist state
  - aggregator history retention
  - per-instrument caches (`last_seen_candle`, `last_analyzed_candle`, unresolved sets, telemetry accumulators)
  - background loops that may keep large objects alive
- Determine whether the primary issue is:
  - unbounded in-memory retention
  - excessive per-symbol history duplication
  - blocking behavior under memory pressure
  - heartbeat not being published independently enough from the analysis loop

### 2. Add failing tests for the identified behavior

- Add narrow regression tests for whichever issue is proven by investigation.
- Likely useful targets:
  - heartbeat snapshot advances independently of long-running work
  - worker status becomes degraded/stale in a controlled way instead of silently disappearing
  - large per-cycle state is trimmed/reset after each loop

### 3. Implement minimal stabilization fix

- Prefer the smallest safe change that directly addresses the proven root cause.
- Candidate categories:
  - bound memory retained by in-memory worker structures
  - decouple heartbeat freshness from heavy analysis path
  - add explicit progress timestamps and stale-loop detection
  - prevent large transient telemetry from accumulating across cycles

### 4. Verification

- Run targeted backend tests for the new regression cases.
- Restart worker and verify:
  - heartbeat key remains present in Redis/API
  - `updated_ts` advances over time
  - worker leaves bootstrap/idle appropriately
  - today’s decision logs start appearing again under normal operation

## Success Criteria

- worker no longer drops into silent offline state during normal runtime
- worker heartbeat remains fresh
- analysis loop progress is visible
- system starts producing current-day decision activity again
