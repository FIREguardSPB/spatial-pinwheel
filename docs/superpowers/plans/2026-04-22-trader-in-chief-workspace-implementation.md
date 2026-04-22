# Trader-in-Chief Workspace Implementation Plan

## Goal

Implement the first production slice of the `Trader-in-Chief` workspace.

Priority order:

1. AI-first machine-readable workspace for the main trader agent
2. lightweight human cockpit for oversight and basic operational controls

This plan assumes the current system already has:

- agent contracts and shadow pipeline
- trader/challenger/merge layers
- deterministic execution shell
- runtime status and dashboard plumbing

## File Structure

### New files

- `backend/core/ai/workspace_builder.py`
  Builds the unified Trader-in-Chief workspace payload from existing signal, market, portfolio, memory, and policy context.
- `backend/tests/test_trader_workspace.py`
  Tests workspace shape, section completeness, and JSON-safe content.

### Existing files to modify

- `backend/apps/worker/processor.py`
  Replace piecemeal `agent_world_state` construction with the new workspace builder.
- `backend/core/services/ui_runtime.py`
  Expose workspace and compact operator summaries in runtime payloads.
- `backend/apps/api/routers/ui.py`
  Provide cockpit-facing dashboard/runtime data to the frontend.
- `backend/core/services/signal_meta_compact.py`
  Ensure compact signal payloads retain trader/challenger/merge/thesis information relevant to the cockpit.
- frontend dashboard files once identified during implementation
  Add the lightweight `Trader-in-Chief` cockpit with operational controls, trades, statistics, and export actions.

## Scope

### In scope for this implementation slice

- unified machine-readable trader workspace package
- AI-first workspace payload integration in backend runtime paths
- minimal operator cockpit
- trades table and compact statistics visibility
- export-ready trades/statistics action or endpoint wiring
- operator controls for:
  - enable/disable trading
  - mode switching
  - usable capital limit

### Out of scope for this slice

- advanced Telegram workflow
- large visual charting rebuild
- replacing the full frontend layout
- deep memory retrieval expansion

## Implementation Tasks

### Task 1. Build unified trader workspace package

Create `backend/core/ai/workspace_builder.py`.

The workspace should include sections for:

- market view
- multi-timeframe thesis view
- trade geometry and economics
- portfolio and risk context
- memory and lineage
- policy context

Requirements:

- deterministic, JSON-serializable structure
- no hidden dependence on frontend-specific shape
- safe defaults when optional context is missing

Tests:

- workspace contains required sections
- workspace carries thesis/economics/risk context
- workspace remains JSON-safe

### Task 2. Replace piecemeal `agent_world_state` generation in processor

Update `backend/apps/worker/processor.py` so the agent pipeline uses the new workspace builder instead of ad hoc inline dictionaries.

Requirements:

- preserve current shadow pipeline behavior
- ensure trader/challenger/merge/thesis layers continue to work
- keep hard rails unchanged

Tests:

- existing AI shadow tests remain green
- workspace builder output is present in signal meta

### Task 3. Add workspace runtime summary for operator use

Extend `backend/core/services/ui_runtime.py` with a compact operator-facing workspace summary.

This should not dump the full machine payload to the UI by default.

It should present:

- active mode
- signal flow summary
- trader/challenger/consensus/thesis summary
- hard block reason if any
- recent trade and compact statistics summary

Tests:

- runtime payload exposes workspace summary fields
- summary survives missing optional data

### Task 4. Add lightweight Trader-in-Chief cockpit data path

Update `backend/apps/api/routers/ui.py` so the UI receives the minimum cockpit payload required for the operator view.

Include:

- worker/runtime status
- active mode
- operator controls state
- trades summary
- compact statistics
- recent decision table data
- export-capable trade/stat payload references or inline data

Tests:

- dashboard payload includes workspace-oriented fields
- cached UI path does not break when builder errors

### Task 5. Keep only essential operator controls

Wire or preserve only the controls that remain relevant in the new model:

- trading enabled/disabled
- mode switching (`review`, `paper`, `live` as applicable)
- usable capital limit

Do not center legacy tuning parameters for the old rule-heavy engine in the cockpit.

Tests:

- runtime snapshot exposes these controls
- values stay consistent with settings/backend state

### Task 6. Trades, statistics, and export

Ensure the operator cockpit includes:

- recent trades
- compact statistics summary
- export path for trade/statistics data

Prefer a simple export flow over a complex analytics page in this slice.

Tests:

- trade payload available in UI/dashboard path
- export path returns structured data

### Task 7. Frontend minimal cockpit implementation

Update the frontend to show the `Trader-in-Chief` cockpit rather than over-emphasizing the legacy dashboard model.

The UI should focus on:

- what the trader sees
- what the challenger thinks
- current consensus
- whether the thesis is alive
- recent trades and compact performance summary
- operator controls

Avoid clutter from legacy tuning and non-essential charts.

Tests:

- existing frontend smoke path if available
- backend payload compatibility verified

## Verification Strategy

At each step:

- add or update focused tests first
- verify new tests fail for the right reason
- implement minimal code to pass
- re-run the focused tests
- re-run the backend suite before push

Suggested commands:

- `python -m pytest backend/tests/test_trader_workspace.py -vv`
- `python -m pytest backend/tests/test_ai_agent_shadow.py backend/tests/test_ui_runtime_pipeline.py -vv`
- full backend suite before merge/push

## Notes

- The machine-readable workspace is the primary artifact.
- The human cockpit is a thin operational layer on top of it.
- If a change improves the UI while weakening the trader's actual workspace, it is the wrong trade-off.
