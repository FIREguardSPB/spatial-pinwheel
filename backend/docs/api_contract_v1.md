# API Contract v1 - Backend MVP

Base prefix: `/api/v1`

## 3.1 System
- `GET /health` -> `{ "status": "ok", "version": "v1" }`

## 3.2 Bot control
- `GET /bot/status`
- `POST /bot/start` body: `{ "mode": "review"|"paper"|"live", "paper": true|false }`
- `POST /bot/stop`

## 3.3 Settings (Risk)
- `GET /settings`
- `PUT /settings`

## 3.4 Instruments
- `GET /instruments?query=&limit=`

## 3.5 Candles
- `GET /candles/{instrument_id}?tf=15m&from=&to=&limit=`

## 3.6 Signals
- `GET /signals?status=&instrument_id=&limit=&cursor=`
- `POST /signals/{signal_id}/approve`
- `POST /signals/{signal_id}/reject`
- **Statuses**: `pending_review`, `approved`, `rejected`, `executed`, `expired`

## 3.7 State
- `GET /state/orders`
- `GET /state/positions`
- `GET /state/trades`

## 3.8 Decision log
- `GET /decision-log?limit=&cursor=`

## 4 SSE /stream
- Endpoint: `GET /api/v1/stream`
- Unified Payload Format: `{ "type": "string", "ts": 1234567890000, "data": { ... } }`
- Events: `bot_status`, `kline`, `signal_created`, `signal_updated`, `orders_updated`, `positions_updated`, `trade_filled`
- Keepalive: every 20s
