# Implementation Plan: Sprint 10 - Higher-TF Execution Conversion

## Goal

Increase conversion of strong higher-timeframe candidates toward execution-ready outcomes by reducing overly broad governor suppression for explicit higher-TF-led setups.

## Baseline

- fresh higher-TF outcomes are still dominated by `rejected`
- many strong candidates already carry:
  - `review_readiness`
  - `conviction_profile`
  - explicit `higher_tf_thesis`
- but a dominant blocker in rejection metadata is:
  - `performance governor suppression`

This suggests the next bottleneck is not thesis quality itself, but governor strictness for higher-TF-led candidates.

## Scope

- keep performance governor discipline intact for clearly weak slices
- add minimal higher-TF-aware relief only for strong candidates
- do not broadly disable suppression

## Files In Scope

- `backend/apps/worker/processor.py`
- `backend/tests/test_processor_selective_throttle.py`

## Success Criteria

- strong higher-TF-led candidates are less likely to die only because of generic governor suppression
- weak/suppressed low-quality slices still block
- fresh live higher-TF signals show a better chance to reach `pending_review` or better
