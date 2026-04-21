# Implementation Plan: Sprint 12 - Higher-TF Approved Outcomes

## Goal

Improve the quality of higher-timeframe `pending_review` rows so the strongest ones are explicitly marked as approval-grade candidates.

## Baseline

- fresh higher-TF pending rows carried `review_readiness`, but lacked any direct indication of whether they were approval-worthy
- this made downstream approval handling weaker and more manual than necessary

## Approach

- enrich `review_readiness` for pending higher-TF signals with an `approval_candidate` decision seed
- keep the gate narrow: only strong higher-TF requested/confirmation setups with solid RR in `auto_paper` mode qualify
