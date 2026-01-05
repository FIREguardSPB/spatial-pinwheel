# API Contract v1

## Time Units (Standardization)
All timestamps in this API contract must strictly adhere to the following units.

### 1. Candles (Market Data)
- **Unit**: **Unix Seconds** (Integer)
- **Endpoints**:
  - `GET /api/v1/candles/{instrument}` returns `time` in seconds.
  - SSE `/api/v1/stream` event `kline` payload `candle.time` is in seconds.
- **Rationale**: Compatibility with lightweight-charts and convention.

### 2. Signals
- **Unit**: **Unix Seconds** (Integer)
- **Endpoints**:
  - `GET /api/v1/signals` returns `ts` in seconds.
- **Rationale**: Standardized with Candle time units.
- **Note**: DB stores ms, API layer transforms to seconds.

### 3. Positions / Orders
- **Unit**: **Unix Milliseconds** (Integer)
- **Fields**: `opened_ts`, `created_ts`, `updated_ts`.

## Throttling Policy
- **Market Data Stream**: `kline` events are throttled to max **1 update per second per instrument**.
- **Reason**: To prevent frontend overload and Redis spamming.
