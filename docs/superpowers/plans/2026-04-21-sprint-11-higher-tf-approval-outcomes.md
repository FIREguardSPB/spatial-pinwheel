# Implementation Plan: Sprint 11 - Higher-TF Approval Outcomes

## Goal

Reduce higher-timeframe `pending_review` stalls by ensuring decision-flow failures after persistence do not leave review rows hanging indefinitely.

## Baseline

- some higher-TF rows were stuck in `pending_review` for many minutes
- matching decision logs showed only `signal_created`, with no later `decision_engine` or `signal_pipeline` logs
- this indicates a post-persist decision-flow abort that left the signal in a misleading pending state

## Approach

- add defensive handling around late decision flow
- if decision flow crashes or returns `None` after persistence, mark the signal as `rejected` with diagnostic metadata
- preserve normal `pending_review` behavior for healthy paths

## Files In Scope

- `backend/apps/worker/processor.py`

## Success Criteria

- decision-flow aborts no longer leave stale higher-TF `pending_review` rows behind
- failed post-persist signals carry `decision_flow_error` diagnostics
- healthy higher-TF `pending_review` rows remain available for review
