# Implementation Plan: Sprint 14 - First Midday TAKE

## Goal

Remove the dominant false-negative higher-timeframe hard block that was preventing strong `15m` candidates from even reaching a fair decision phase.

## Baseline

- dominant reject cluster:
  - `15m`
  - `selection_reason = requested`
  - `NO_MARKET_DATA`
  - hard reject before meaningful scoring
- many of these rows had only `38-39` candles, which is borderline-but-usable for higher-TF continuation logic

## Approach

- lower higher-TF data sufficiency floor slightly for `15m/30m/1h`
- keep 1m behavior unchanged
- keep the fallback narrow and pair it with a shorter higher-TF EMA fallback already introduced earlier

## Success Criteria

- requested `15m` candidates no longer hard-fail on `39` candles
- fresh live higher-TF signals show fewer immediate `NO_MARKET_DATA` rejections
