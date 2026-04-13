# Sprint 2 diagnostic note — `take_fill` imbalance

## Scope of this note
This repository snapshot does not include the live production database, so this note documents the **code-level diagnostic finding** and the new inspection path, not live empirical class ratios.

## Main finding
The pre-hardening `take_fill` dataset builder treated a TAKE signal as negative mainly when:
- the signal was not marked `executed`, and
- no closed position could be matched back to it.

That approach was simple but weak in two ways:
1. it mixed several operationally different negatives into one generic `0` label,
2. it made the class imbalance hard to explain by component.

## Hardening outcome
The dataset builder now keeps the binary label for training, but adds explicit negative attribution metadata and diagnostics.

For each TAKE row it records:
- `fill_outcome`
- `label_source`

This allows diagnostics to answer whether the negatives are dominated by:
- deterministic risk blocks,
- execution errors,
- pending/approved but unfilled ideas,
- generic rejected or expired paths.

## What to verify on a live environment
1. Open `/api/v1/ml/dataset`.
2. Inspect `datasets.take_fill.stats.fill_outcomes`.
3. Inspect `datasets.take_fill.stats.diagnostics.by_fill_outcome`.
4. Compare the dominant negative buckets against `/api/v1/ml/attribution` for the same window.

## Interpretation guidance
- If `execution_risk_block` dominates, the model is learning post-decision execution friction rather than market fillability.
- If `approved_not_executed` / `pending_not_executed` dominate, the issue is orchestration / lifecycle delay rather than fill quality.
- If `rejected` dominates without paired decision logs, historical attribution coverage is incomplete and should be improved in runtime logging rather than hidden in ML preprocessing.
