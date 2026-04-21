# Implementation Plan: Sprint 3 - Higher-TF Dominance

## Goal

Move the system from "higher timeframes are often selected" to "higher timeframes explicitly lead the trade idea".

Current live baseline:

- current-day signals sampled: 31
- `timeframe_selection_reason`:
  - `requested`: 17
  - `fallback`: 6
  - `execution_fallback`: 6
  - `confirmation`: 2
- `thesis_timeframe`:
  - `15m`: 15
  - `5m`: 10
  - `1m`: 6
- explicit `higher_tf_thesis` present in only 1 signal

This means higher TF selection is already happening, but explicit thesis semantics are still too sparse.

## Scope

- Increase the share of higher-TF-led metadata in live signals.
- Reduce reliance on `execution_fallback` where a higher-TF explanation exists.
- Preserve Sprint 1 worker stability gains.

## Files In Scope

- `backend/apps/worker/processor_support.py`
  - Selection metadata, promotion logic, higher-TF thesis attachment.
- `backend/core/services/timeframe_engine.py`
  - Higher-TF thesis generation and fallback thesis shaping.
- `backend/tests/test_timeframe_thesis_selection.py`
  - Regression tests for explicit thesis persistence and fallback reduction.

## Tasks

### 1. Add failing tests

- Add tests showing that when `5m/15m` wins, `higher_tf_thesis` is explicitly populated.
- Add tests showing that when `1m` is only used as execution while higher-TF context is aligned, metadata reflects higher-TF leadership.
- Add tests that keep `1m execution_fallback` only for genuine no-higher-TF cases.

### 2. Strengthen metadata semantics

- Ensure selected higher-TF signals always carry explicit higher-TF thesis payloads.
- Ensure promoted higher-TF context is retained in persisted metadata.
- Avoid broad rewrites; keep changes local to the current selection path.

### 3. Verify with live evidence

- Re-run targeted backend tests.
- Sample current-day signals and inspect:
  - `timeframe_selection_reason`
  - `thesis_timeframe`
  - presence of `higher_tf_thesis`

## Success Criteria

- `higher_tf_thesis` is no longer rare in higher-TF-selected signals.
- `execution_fallback` remains only where higher TF genuinely produced nothing useful.
- No regression in worker stabilization or dashboard behavior.
