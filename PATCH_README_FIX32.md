# FIX32 — worker architecture, runtime final_decision, watchlist/runtime status

## Что сделано

### 1) Worker больше не зависит от stream/polling для запуска анализа
- Убран старый сценарий, где анализ жил внутри `async for tick in market_stream`.
- Введены отдельные фоновые циклы:
  - market polling loop
  - analysis loop
  - watchlist refresh loop
  - command listener
- Теперь worker продолжает анализ даже когда REST polling не выдаёт новые свечи на каждом проходе.

### 2) Снижение нагрузки на T-Bank API
- Введён tiered polling:
  - core tickers — чаще
  - tail tickers — реже
- Добавлен runtime refresh watchlist без рестарта worker.
- Начальный bootstrap ограничен `WORKER_BOOTSTRAP_LIMIT` (по умолчанию 10 инструментов), остальная история догружается постепенно.
- Для несуществующих инструментов добавлен negative cache (`TBANK_MISSING_INSTRUMENT_TTL_SEC`, по умолчанию 600 сек), чтобы не спамить `FindInstrument` на каждом цикле.

### 3) final_decision теперь явно виден в API сигналов
- В schema `Signal` добавлено top-level поле `final_decision`.
- `/api/v1/signals` теперь явно заполняет `final_decision` из `meta.final_decision` или `meta.decision.decision`.
- Это устраняет рассинхрон API, когда meta уже содержит TAKE, а top-level выглядел как null/пусто.

### 4) Мониторинг worker
- Добавлен Redis-backed endpoint `GET /api/v1/worker/status`.
- Worker публикует в статус:
  - текущую фазу (`bootstrap`, `polling`, `analysis`, `idle`, `stopped`)
  - количество инструментов
  - последнюю poll/analyze статистику
  - последний TAKE
  - unresolved instruments
  - last_error
- Во frontend добавлен базовый индикатор worker status в `ConnectionStatus`.

### 5) Watchlist без перезапуска worker
- Worker периодически перечитывает активный watchlist из БД.
- Добавление/удаление инструментов через уже существующий UI/API теперь подхватывается runtime.

## Что проверено
- `python3 -m compileall -q backend` — ok
- изменённые TS/TSX-файлы прогнаны через `typescript.transpileModule` — ok

## Ограничения
- Полный e2e runtime-прогон с реальным T-Bank API, Redis и UI в контейнере не выполнялся.
- Полный production frontend build не подтверждён из-за отсутствия полного `node_modules` окружения.
