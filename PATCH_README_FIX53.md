# FIX53 — unblock paper trading after FIX49–FIX52

What was fixed:

1. RiskManager re-entry cooldown
- cooldown now blocks only after an *executed* signal/trade for the same instrument+side
- non-executed candidate signals no longer keep resetting the cooldown forever

2. Candle cache duplicate key crashes
- candle upserts use PostgreSQL `ON CONFLICT DO UPDATE`
- fallback path handles integrity races safely for non-Postgres environments

3. EconomicFilter second-tier defaults
- softer defaults for low-price paper testing:
  - `min_trade_value_rub` -> 10.0
  - `min_instrument_price_rub` -> 0.001
- aligned in backend defaults and frontend defaults

4. Adaptive re-entry tuning
- seeded symbol profiles now start with much shorter re-entry values
- auto-paper mode clamps effective adaptive re-entry to a small range

5. Symbol adaptive diagnostics stability
- `trend_strength` is clamped to avoid numeric overflow in regime snapshots

6. Pipeline diagnostics
- `/api/v1/settings/runtime-overview` now includes `pipeline_counters`
  - `blocked_total`
  - `take_total`
  - `opened_total`
  - `blocked_by`

Validation done:
- `python3 -m compileall -q backend src`
