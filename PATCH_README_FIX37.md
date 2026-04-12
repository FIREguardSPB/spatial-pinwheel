# PATCH README — FIX37

База: `trader_project_fix36_clean.zip`

## Что реализовано в этой фазе

### 1) RiskManager / capital management
- runtime-настройки расширены полями:
  - `strong_signal_score_threshold`
  - `strong_signal_position_bonus`
  - `partial_close_threshold`
  - `partial_close_ratio`
  - `min_position_age_for_partial_close`
  - `worker_bootstrap_limit`
- добавлен endpoint `POST /api/v1/risk/reset_daily`
- дневные лимиты RiskManager теперь можно сбрасывать без перезапуска
- в paper-execution добавлена частичная разгрузка позиции под сильный сигнал и повторная проверка риска

### 2) Trace / strategy observability
- `strategy` и `trace_id` теперь сохраняются в `orders`, `trades`, `positions`
- добавлен endpoint `GET /api/v1/trace/{trace_id}`
- сделки и связанные сущности можно собирать в одну цепочку signal → order → position → trade

### 3) Business metrics / monitoring
- добавлен endpoint `GET /api/v1/metrics`
- метрики включают:
  - total/daily PnL
  - win rate
  - profit factor
  - conversion rate signal → trade
  - avg holding time
  - avg profit / avg loss
  - best/worst trade
  - strategy breakdown
  - instrument breakdown
  - pnl/equity curves

### 4) Historical AI context
- добавлен grounded historical context analyzer:
  - использует недавние сигналы/позиции из БД
  - опционально читает markdown-memory из `HISTORICAL_CONTEXT_DIR`
- historical context включён в `AIContext` и в user prompt для AI

### 5) Backtest improvements
- `POST /api/v1/backtest` теперь умеет работать:
  - либо с `candles` из тела запроса,
  - либо напрямую с кэшем свечей из БД (`timeframe`, `history_limit`)
- frontend backtest page переведён на реальный API backtest с выбором источника данных

### 6) T-Bank API monitoring
- в adapter добавлены счётчики REST-запросов
- собираются:
  - `requests_total`
  - `success_total`
  - `error_total`
  - `requests_by_method`
  - `recent_requests_60s`
  - `requests_per_sec`
  - last rate-limit headers (если пришли)
  - recommendation по нагрузке
- worker публикует это в runtime status
- добавлен endpoint `GET /api/v1/tbank/stats`

### 7) Worker / bootstrap
- `worker_bootstrap_limit` теперь берётся из runtime settings
- watchlist refresh учитывает этот лимит при дозагрузке истории

### 8) Frontend
- dashboard использует `/api/v1/metrics` для live business metrics
- account page показывает:
  - business metrics 7d
  - T-Bank API load stats
- settings page расширена:
  - новый пресет `Баланс`
  - RiskManager 2.0 поля
  - bootstrap limit
  - кнопка ручного сброса дневных лимитов
- backtest page умеет запускать реальный backtest из candle cache

## Что проверено
- `python3 -m compileall -q backend` — OK
- изменённые TS/TSX-файлы прогнаны через `typescript.transpileModule` — OK

## Что честно НЕ подтверждено в контейнере
- полный runtime paper/live прогон с реальным T-Bank API не выполнялся
- полный frontend production build не подтверждён через `vite build`, потому что в контейнере нет проектных `node_modules`
- historical context реализован как практичный grounded слой (БД + memory markdown), а не как полноценный векторный retrieval по графу знаний 571k документов
