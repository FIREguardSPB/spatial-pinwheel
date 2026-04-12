# AUDIT FIX84

## Input evidence used

- worker log from deployed environment
- HAR traces showing `/api/v1/ui/settings` and `/api/v1/ui/dashboard` hanging/aborting
- screenshots showing contradictory runtime card states (`loaded` + `не загрузилось`)
- latest code base from the current project archive

## Root-cause summary

### 1. Frontend was not the only problem
The frontend was clearly surfacing failures, but the critical bottleneck sat inside backend coordinator endpoints.

### 2. Heavy sync work was executed inside async FastAPI handlers
`/ui/settings` and `/ui/dashboard` were declared as `async def`, but internally executed multiple synchronous DB/CPU-heavy builders inline. Under load, this creates head-of-line blocking for other requests.

### 3. Settings bootstrap included expensive runtime sections
The settings page bootstrap still pulled expensive runtime blocks such as:
- policy runtime
- ML runtime
- pipeline counters

This made `ui/settings` much heavier than a page bootstrap should be.

### 4. Runtime overview endpoint was overloaded
`/settings/runtime-overview` was being used for per-instrument details, but also built unrelated global runtime diagnostics. That made even the paper/instrument tab much slower than necessary.

### 5. Token resolution was inefficient on read-paths
Multiple runtime helpers used `get_token()` inside UI read-paths, which opens additional DB sessions internally and is inappropriate for hot coordinator endpoints.

### 6. Runtime transport semantics were misleading
The application could run in `auto_paper`, while status still reflected `BROKER_PROVIDER=tbank` too directly. This produced a confusing mismatch between effective runtime mode and configured broker backend.

### 7. UI state semantics were contradictory
The settings cards could render “loaded” while showing “не загрузилось”, because the badge state and the text state used different logic.

## Corrective strategy implemented

### A. Make coordinator endpoints truly lightweight
Done by:
- moving sync work into threadpool execution
- replacing heavy runtime sections with lighter summaries
- removing unnecessary instrument coupling from page bootstrap queries

### B. Separate page bootstrap from deep instrument diagnostics
Done by:
- keeping `ui/settings` fast
- loading `runtime-overview` only in the `Бумаги` tab
- stripping global heavy diagnostics from the default `runtime-overview` response

### C. Fix transport/mode semantics
Done by:
- resolving effective runtime provider from mode + runtime token availability
- validating `auto_live` against actual runtime token availability

### D. Fix frontend state truthfulness
Done by:
- normalizing runtime card states
- ignoring cancelled requests as hard API failures
- removing parent-level unnecessary overview fetches

## Remaining risk

The worker log still shows that the trading loop itself finds some candidate signals and then blocks them with freeze policy. That is a separate trading-policy issue from the coordinator/UI stability issue.

So FIX84 targets:
- API responsiveness
- frontend stability
- truthful runtime/status semantics

It does **not** claim to solve all trading-quality issues in one step.
