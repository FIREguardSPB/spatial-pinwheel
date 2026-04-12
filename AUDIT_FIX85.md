FIX85 AUDIT

Observed backlog issues addressed:
1. Fake totals on Signals/Trades caused by displaying page-size limits as true totals.
2. Stale chart history caused by cache-only candle endpoint and no periodic refetch on the chart.
3. Empty/idle runtime cards in Settings caused by bootstrap summaries based on sparse recent signal meta instead of current evaluated runtime state.
4. Papers runtime overview errors caused by unsafe direct execution of heavy per-instrument logic without structured failure payloads.
5. Missing worker import for build_symbol_plan.

Verification performed:
- python3 -m compileall -q backend src
- npm exec --yes tsc --noEmit

Notes:
- This package corrects the specific backlog items and improves runtime clarity, but real runtime validation still requires deployment in the target environment.
