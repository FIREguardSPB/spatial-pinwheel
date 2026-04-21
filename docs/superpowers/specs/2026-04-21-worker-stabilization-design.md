# Worker Stabilization Design

## Context

Current evidence shows the trading worker is the immediate blocker, not the signal list UI and not the higher-timeframe logic by itself.

Observed facts:

- worker process repeatedly reaches extreme memory usage (`RSS ~12 GB`)
- worker enters kernel `D` state with `mem_cgroup_handle_over_high`
- worker heartbeat disappears from Redis/API
- today the system produced `0` signals and almost no decision logs
- market-data paths may still partially move, but the analysis/decision loop becomes effectively dead

This means the system currently fails before we can fairly evaluate live trading behavior.

## Decision

We will stabilize the existing Python worker first.

We will **not** do a full worker rewrite in Rust at this stage.

## Why Not Rust Now

Rust may eventually be useful for narrow hot paths, but a full rewrite is the wrong move right now because:

- we already have a concrete runtime failure in the current worker and have not yet proven the root cause
- a rewrite would copy unclear behavior into a new implementation and expand risk dramatically
- the project strategy is still surgical evolution, not rewrite
- the current blocker is operational reliability, not just raw CPU speed

## Recommended Path

### Phase 1: Root-cause stabilization

Goal: make the worker run reliably long enough to produce live analysis and signals again.

Work items:

- identify where memory is retained or grows unbounded
- determine whether the main driver is candle history retention, per-instrument state, AI/context accumulation, background loops, or blocking I/O under memory pressure
- restore stable heartbeat publication while analysis is active
- ensure operator-visible status reflects true loop health

### Phase 2: Runtime guards

Goal: prevent silent death and make failures obvious and bounded.

Work items:

- add worker memory watermark telemetry
- add loop-progress telemetry (`last_analysis_started_ts`, `last_analysis_finished_ts`, per-cycle counters, heartbeat freshness)
- add fail-safe degradation when worker becomes unhealthy instead of hanging indefinitely
- surface unhealthy-worker state clearly to dashboard/runtime views

### Phase 3: Post-stabilization performance decisions

Only after the worker is stable:

- profile hot paths under realistic load
- decide whether any narrow subsystem should be rewritten or offloaded
- consider Rust only for isolated compute-heavy or memory-sensitive modules, not the full worker by default

## Scope

In scope:

- worker memory blow-up investigation
- heartbeat loss investigation
- stable analysis loop restoration
- operator/runtime visibility for worker health

Out of scope for this stage:

- full Rust rewrite of the worker
- full architecture replacement
- redesign of all execution and signal pipelines

## Success Criteria

The worker stabilization stage is successful when:

- worker no longer grows into multi-GB runaway RSS during normal operation
- worker heartbeat remains fresh while the process is alive
- analysis loop produces normal decision logs again
- signals can be created today, not only historical ones from yesterday
- dashboard reflects true worker health without ambiguity

## Follow-up

Once the worker is stable again, return to the main product goal:

- validate whether `5m/15m` higher-timeframe thesis now appears in live `timeframe_competition`
- continue evolving the trader away from `1m execution_fallback`
