# FIX86v2

## Выполненная часть плана

### P0
- Починен auto-policy runtime для coordinator UI-маршрутов.
- Добавлен реальный TTL-кэш для degrade policy с stale fallback.
- UI coordinator routes переведены на отдельные sync DB-сессии внутри threadpool-path, без проброса request-scoped Session между потоками.

### P1
- Dashboard bootstrap теперь учитывает выбранный timeframe.
- SSE-инвалидация теперь обновляет coordinator dashboard и по событиям `kline`.
- Убрано ложное удержание старого coordinator payload на фронте: для coordinator queries отключён keep-previous-data стиль через `placeholderData`.
- ChartContainer очищает локальный candle-slice при смене бумаги/TF, чтобы не показывать старый инструмент как будто это текущий.

### P2
- Метка последней свечи на дашборде теперь берётся из реально загруженного candle-slice выбранной бумаги/TF, а не из устаревшего coordinator payload.

## Что проверено
- `python3 -m compileall -q backend`
- `PYTHONPATH=backend python3 -m unittest backend.tests.test_degrade_policy backend.tests.test_degrade_policy_cache backend.tests.test_trading_schedule_static -v`
- `npm exec --yes tsc --noEmit`

## Что всё ещё требует стендовой проверки
- живой прогон UI + backend + worker с реальным SSE
- отсутствие таймаутов `/api/v1/ui/*` после возврата auto-policy блока
- обновление графика и сигналов на реальном sandbox token
