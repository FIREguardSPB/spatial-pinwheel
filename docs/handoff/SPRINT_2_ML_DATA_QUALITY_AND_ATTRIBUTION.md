# Sprint 2 — ML data quality and attribution hardening

## Why this sprint exists
Sprint 1 stabilized read-side/runtime enough to make the system operable again.
The next weak point is not flashy architecture, but **data quality and attribution discipline**.

Right now:
- `trade_outcome` is active and usable,
- `take_fill` is active but heavily class-imbalanced,
- we still need cleaner attribution between signal intent, execution outcome, guardrail effects, and ML overlay behavior.

## Sprint objective
Turn the current ML/attribution layer from “technically active” into “operationally trustworthy”.

## Scope
### A. `take_fill` dataset hardening
1. Audit how `take_fill` negatives are produced.
2. Ensure rejected/non-filled TAKE candidates are captured consistently.
3. Remove accidental duplication or label leakage.
4. Produce dataset diagnostics by:
   - label balance,
   - strategy,
   - regime,
   - instrument,
   - session/hour.

### B. Attribution layer
1. Add a report or endpoint that clearly separates:
   - signal generated,
   - TAKE decided,
   - TAKE vetoed by ML,
   - TAKE blocked by deterministic guardrails,
   - TAKE not filled/executed,
   - trade closed profit/loss.
2. Make it possible to answer, for a recent window, which layer killed or saved what.

### C. ML runtime observability
1. Expose in UI/API, in a compact form:
   - which model was used,
   - probabilities,
   - whether overlay boosted/cut/vetoed,
   - reason code,
   - model freshness / last train ts.
2. Ensure this is lightweight and does not bloat `ui/signals` payload again.

### D. Regression safety
1. Add tests for dataset building from immutable close logs.
2. Add tests for rare-class fallback behavior.
3. Add tests that read-model responses remain compact when ML overlay fields are present.

## Out of scope
- strategy rewrites,
- changing risk philosophy,
- broad concurrency redesign,
- “improving profitability” by arbitrary threshold tuning.

## Deliverables
1. Clean diagnostic note/report with findings on `take_fill` imbalance.
2. Code changes for dataset/attribution/runtime observability.
3. Tests covering new behavior.
4. Short runbook note explaining where to inspect ML overlay decisions.

## Acceptance criteria
Sprint is accepted only if all of the following are true:
- `take_fill` negatives are traceable and explainable,
- attribution can show where trades/signals were blocked or altered,
- ML overlay visibility is available without making UI endpoints heavy again,
- test coverage exists for the new dataset/runtime behavior,
- no regression in API/UI responsiveness.

## Practical notes
- Prefer immutable event sources over mutable state rows.
- Do not stuff giant nested ML payloads into hot UI endpoints.
- If you need more detail, add dedicated diagnostic endpoints or reports.
- Any performance fix must be measured, not asserted.
