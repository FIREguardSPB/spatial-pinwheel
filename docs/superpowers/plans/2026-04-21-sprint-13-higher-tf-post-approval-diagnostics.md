# Implementation Plan: Sprint 13 - Higher-TF Post-Approval Diagnostics

## Goal

Stabilize the next layer after Sprint 12 by making the pending queue more diagnostic and easier to reason about for later approval/execution steps.

## Baseline

- higher-TF candidates needed clearer machine-readable signals about why they were strong enough for promotion versus why they should remain review-only

## Approach

- attach `approval_reason` alongside `approval_candidate`
- preserve this inside `review_readiness` so operators and later automation can differentiate strong candidates from ordinary review rows without reconstructing the whole pipeline
