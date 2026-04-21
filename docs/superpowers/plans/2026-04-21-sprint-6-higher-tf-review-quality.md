# Implementation Plan: Sprint 6 - Higher-TF Review Quality

## Goal

Improve the review quality of higher-timeframe survivors so they carry clearer conviction semantics and are easier to distinguish from weak noise.

## Baseline

- higher-TF `pending_review` signals were extremely rare
- many higher-TF rejects already had explicit thesis, but lacked strong conviction semantics
- fresh rejected higher-TF examples often had governor-pass and explicit thesis, yet still looked like generic `REJECT` rows to review tooling

## Approach

- strengthen conviction scoring for explicit higher-TF-led near-threshold setups
- allow `REJECT` higher-TF setups with solid economics to be treated as tradeable `B`-tier candidates in conviction metadata
- allow high-conviction promotion logic to reason over `REJECT` as well as `SKIP`

## Files In Scope

- `backend/apps/worker/processor_support.py`
- `backend/tests/test_processor_selective_throttle.py`

## Success Criteria

- fresh higher-TF-led near-threshold signals can receive `conviction_profile.tier = B`
- promotion metadata is present for strong higher-TF-led rejects near the threshold
- review tooling sees a clearer difference between weak noise and near-tradeable higher-TF candidates
