# Implementation Plan: Sprint 7 - Higher-TF Actionability

## Goal

Improve the approval and execution readiness of higher-timeframe `pending_review` signals by ensuring they already carry useful review metadata at the moment they are created.

## Baseline

- fresh higher-TF `pending_review` signals were reaching review with sparse metadata
- they often had explicit `higher_tf_thesis`, but lacked:
  - `conviction_profile`
  - `decision_merge`
  - `high_conviction_promotion`
  - a compact review summary for human/operator review

This made them action-poor even when the higher-TF thesis itself was good.

## Approach

- add a compact `review_readiness` seed before persistence
- preserve core higher-TF context immediately, even if the later decision flow has not fully enriched the row yet
- keep the change small and local to signal persistence

## Files In Scope

- `backend/apps/worker/processor_support.py`
- `backend/apps/worker/processor.py`
- `backend/tests/test_processor_selective_throttle.py`

## Success Criteria

- fresh higher-TF `pending_review` signals include a compact `review_readiness` payload
- that payload carries thesis timeframe, thesis type/structure, selection reason, execution timeframe, strategy name, and initial RR
- review tooling sees actionable metadata immediately instead of a sparse row
