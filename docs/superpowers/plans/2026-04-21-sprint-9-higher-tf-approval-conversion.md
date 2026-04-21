# Implementation Plan: Sprint 9 - Higher-TF Approval Conversion

## Goal

Improve conversion readiness for higher-timeframe candidates by ensuring even pre-persist or early-persist `pending_review` signals carry enough metadata to be meaningfully reviewed and promoted later.

## Baseline

- higher-TF conversion to `approved` remained near zero
- many higher-TF `pending_review` rows appeared with `final_decision = None`
- some rows lacked `conviction_profile` and `decision_merge` entirely because the pipeline halted before full late-stage enrichment

## Approach

- enrich early `pending_review` rows with compact actionability metadata
- preserve reviewability even when the signal does not complete the entire late decision flow
- keep hard risk discipline intact

## Files In Scope

- `backend/apps/worker/processor_support.py`
- `backend/apps/worker/processor.py`
- `backend/tests/test_processor_selective_throttle.py`

## Success Criteria

- fresh higher-TF `pending_review` rows always include a useful `review_readiness` payload
- pre-persist blocked higher-TF rows also include a compact conviction / decision seed instead of a nearly empty row
- review tooling has better material for later approval decisions
