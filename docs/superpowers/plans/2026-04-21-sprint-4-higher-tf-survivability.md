# Implementation Plan: Sprint 4 - Higher-TF Survivability

## Goal

Increase the share of higher-timeframe signals that survive into actionable outcomes instead of being rejected too early by generic throttles.

## Live Baseline

Current-day rejected higher-TF signals:

- `15m`: 15
- `5m`: 9

Dominant rejection reasons:

- `Breakout below 20-bar range`: 18
- `Breakout above 20-bar range`: 3
- `No size left after exposure caps`: 3

Dominant merge reasons:

- `DE hard block preserved; selective throttle`: 12
- `event regime calm observed; selective throttle`: 5
- `event regime calm observed; ML overlay veto; selective throttle`: 4

This suggests higher-TF candidates are already being formed, but many are being discarded by broad throttle logic before they can express the intended thesis.

## Scope

- Keep worker stability intact.
- Reduce unnecessary rejections for strong higher-TF setups.
- Preserve hard risk blocks and genuine exposure limits.

## Files In Scope

- `backend/apps/worker/processor.py`
  - Decision merge and selective throttle behavior.
- `backend/apps/worker/processor_support.py`
  - Higher-TF metadata used to determine if a signal deserves selective-throttle relief.
- `backend/tests/` targeted tests
  - Regression coverage for higher-TF survivability without weakening hard risk controls.

## Tasks

### 1. Add failing tests

- Add tests showing that strong higher-TF-led signals are not rejected solely by generic selective throttle when no hard risk block exists.
- Keep tests proving hard blocks and exposure caps still reject.

### 2. Implement minimal selective-throttle relief

- Use existing higher-TF metadata (`thesis_timeframe`, `higher_tf_thesis`, selection reason) to identify higher-quality higher-TF setups.
- Apply relief only when:
  - the signal is higher-TF-led
  - there is no hard block
  - no real exposure/risk cap is violated

### 3. Verify live outcome mix

- Re-run targeted backend tests.
- Sample current-day signals and inspect whether higher-TF rejections fall while hard-risk rejections remain.

## Success Criteria

- Fewer higher-TF signals are rejected only by generic selective throttle.
- Hard blocks and real risk caps remain enforced.
- Higher-TF-led signals have a better chance to become actionable outcomes.
