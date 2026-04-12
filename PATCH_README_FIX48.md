FIX48 — trade journal normalization

What changed
- `GET /api/v1/trades` now uses immutable `position_closed` decision logs as the source of truth for closed trades.
- Default trade journal now returns only closed trades. Optional `include_open=true` can surface open execution fills.
- `GET /api/v1/trades/stats` now computes summary metrics from the same closed-trade source as the table.
- `GET /api/v1/trades/export` now exports the same normalized closed-trade rows.
- Closed-trade PnL prefers `net_pnl` from close logs, avoiding misleading `0.00` values caused by mutable position rows.

Why
- The previous journal mixed closed trades with still-open fills and used mutable `positions` rows for stats, which produced inconsistent totals and misleading `0.00` PnL.

Notes
- The journal is now suitable for monitoring completed trades.
- Open positions/fills remain visible through the positions/orders views; they are no longer mixed into the main closed-trades journal by default.
