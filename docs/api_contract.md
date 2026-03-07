# API Contract: Decision Engine v1

## Signal Meta Format
The `signal.meta.decision_engine` object contains the quality evaluation results.

```json
{
  "decision": "TAKE" | "SKIP" | "REJECT",
  "score": 85, // Integer 0-100
  "threshold": 70, // Configured threshold
  "reasons": [
    {
      "code": "MOMENTUM_OK",
      "severity": "info", // info | warn | block
      "msg": "RSI bullish (55.0)"
    },
    {
      "code": "LEVEL_TOO_CLOSE",
      "severity": "warn",
      "msg": "Level too close (Ratio 0.5)"
    }
  ],
  "metrics": {
    "ema50": 265.5,
    "rsi14": 55.0,
    "atr14": 1.2,
    "macd_hist": 0.5,
    "sl_atr": 1.5,
    "nearest_level": 270.0 // float OR null (if not found, P0 Fix)
  }
}
```

## Reason Codes (v1.1.1)
### Hard Blocks (Severity: BLOCK)
- `INVALID_SIGNAL`: Logical error (SL > Entry etc)
- `NO_MARKET_DATA`: Missing candles
- `VOLATILITY_SANITY_BAD`: Stop too tight (<0.3 ATR) or wide (>5.0 ATR)
- `RR_TOO_LOW`: R < Target (default 1.5)

### Soft Scores (Severity: INFO/WARN)
- `REGIME_MATCH` (w_regime)
- `VOLATILITY_SANITY_OK` (w_vol)
- `MOMENTUM_OK` (w_mom) / `MOMENTUM_WEAK` / `RSI_OVERHEAT`
- `LEVEL_CLEARANCE_OK` (w_levels) / `LEVEL_TOO_CLOSE` / `LEVEL_UNKNOWN` (Neutral)
- `COSTS_OK` (w_costs) / `COSTS_TOO_HIGH`
- `LIQUIDITY_UNKNOWN` (w_liquidity, WARN)

## Changes in v1.1 (Audit Fixes)
1. **MACD**: Now influences score (Positive histogram boosts momentum).
2. **RR Code**: Returns `RR_TOO_LOW` instead of `COSTS_TOO_HIGH` for hard rejects.
3. **Levels**: Logic updated to find nearest level *in direction of trade*.
4. **Liquidity**: Severity changed to `WARN`.

---
## P6 Additional Endpoints

### GET /v1/trades
Query: `instrument_id`, `side`, `date_from`, `date_to`, `limit`, `offset`
Returns: `{ items: Trade[], total: int }`

### GET /v1/trades/stats
Returns: `{ total_trades, win_rate, total_pnl, profit_factor }`

### GET /v1/trades/export
Returns: CSV file (`Content-Type: text/csv`)

### GET /v1/account/summary
Returns: `{ balance, equity, open_pnl, margin_used }`

### GET /v1/account/daily-stats
Returns: `{ date, realized_pnl, open_pnl, trades_count, win_count, win_rate, open_positions }`

### GET /v1/account/history
Query: `days` (default: 30)
Returns: `[{ ts, equity, balance, day_pnl }]`

### GET /v1/watchlist
Returns: `[{ id, instrument_id, added_ts }]`

### POST /v1/watchlist
Body: `{ instrument_id: string }`

### DELETE /v1/watchlist/{id}

### GET /v1/instruments/search
Query: `q` (ticker or name fragment)
Returns: `[{ id, name }]`
