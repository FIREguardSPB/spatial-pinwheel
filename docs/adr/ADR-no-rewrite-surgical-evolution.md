# ADR: No Full Rewrite — Surgical Evolution / Strangler Pattern

## Status
Accepted

## Date
2026-04-06

## Context
Spatial Pinwheel has a strong domain core already in production-like paper operation: adaptive symbol planning, multi-strategy selection, event regime, ML overlay, risk/portfolio logic, telemetry and operational controls. A full rewrite would likely destroy verified domain semantics and introduce a large regression surface.

## Decision
We do **not** rewrite the whole project from scratch.

We evolve it via **surgical subsystem redesign** and **strangler pattern**:
- preserve the working decision/risk domain core as the baseline;
- redesign weak subsystems locally (execution, trade management, attribution, streaming ingest, later reasoning layer);
- ship changes behind feature flags, shadow mode or paper validation first;
- maintain regression anchors and baseline comparison packs.

## Consequences
### Positive
- preserves valuable domain behavior;
- reduces regression blast radius;
- allows incremental improvement with measurable outcomes;
- keeps alpha logic and infra refactors separable.

### Negative
- architecture will remain partially hybrid for some time;
- local redesigns require discipline and compatibility shims;
- technical debt is reduced gradually, not instantly.

## Rules
- no big-bang worker rewrite;
- no full concurrency in core analysis loop without redesign;
- no direct uncontrolled AI authority over execution core;
- alpha-affecting changes must go through shadow/paper validation first.
