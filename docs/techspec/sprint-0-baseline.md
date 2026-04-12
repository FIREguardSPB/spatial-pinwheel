# Sprint 0 — Observation / Baseline / Control Pack

## Date
2026-04-06

## Objective
Run a baseline observation week on the **current trading configuration** without changing decision semantics. Collect ground truth on signal flow, guardrail behavior, execution anomalies, latency and missed alpha.

## In Scope
- baseline freeze;
- guardrail attribution;
- missed alpha reporting;
- latency / execution baseline;
- regression anchors;
- daily short reports + weekly deep review pack.

## Out of Scope
- decision threshold changes;
- risk policy loosening;
- full loop concurrency redesign;
- AI authority changes;
- strategy behavior changes.

## Product Principles
- reliability > delivery speed;
- determinism > convenience;
- recoverability > "авось".

## Start Conditions
- current production-like paper configuration is the baseline;
- only telemetry/reporting/docs and emergency stabilization fixes are allowed;
- hotfixes must be documented as stabilization changes, not trading logic upgrades.

## Deliverables
- baseline snapshot;
- guardrail attribution report;
- missed-alpha report;
- latency / execution baseline report;
- golden regression cases;
- daily short report template;
- weekly deep review template.

## Acceptance
Sprint 0 is accepted only if we can answer:
1. where execution is fragile,
2. which guardrails save capital,
3. which guardrails suppress alpha,
4. what baseline behavior must not be broken in Sprint 1.
