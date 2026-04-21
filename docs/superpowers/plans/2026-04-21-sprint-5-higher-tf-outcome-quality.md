# Implementation Plan: Sprint 5 - Higher-TF Outcome Quality

## Goal

Improve the quality of higher-timeframe survivors so strong `5m/15m` signals are less likely to die at the last generic policy gate.

## Baseline

Post-Sprint-4 higher-TF signals were still dominated by `rejected`, with the main path being:

- `pre_persist_block.code = auto_freeze_selective_throttle`
- reasons such as `Breakout below 20-bar range` and `Breakout above 20-bar range`

Fresh rejected higher-TF examples showed:

- explicit `higher_tf_thesis` present
- `selection_reason = requested/confirmation`
- governor not suppressed
- score gaps commonly around `-7 .. -9`

This showed the prior Sprint 4 relief (`threshold - 1`) was too narrow for real live higher-TF setups.

## Scope

- keep hard risk blocks and exposure caps intact
- widen selective-throttle relief only for strong higher-TF-led candidates
- validate live that at least some higher-TF signals now survive into `pending_review`

## Files In Scope

- `backend/apps/worker/processor_support.py`
- `backend/tests/test_processor_selective_throttle.py`

## Success Criteria

- higher-TF-led candidates with explicit thesis and decent RR are not auto-killed only because they are short of TAKE by a small score margin in frozen mode
- hard risk caps remain enforced
- fresh live higher-TF signals can reach `pending_review`
