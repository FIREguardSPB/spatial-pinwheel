# FIX59 — trade management realism + observability pass

## Какая часть плана закрыта
- **Часть 1 плана (архитектурная стабилизация)** — уже закрыта в FIX58.
- **Часть 2 плана (механика более "живого" трейдера)** — в FIX59 закрыт подблок:
  - реалистичность capital reallocation,
  - защита от over-management позиции,
  - расширенная наблюдаемость по quality-of-trading.

## Что изменено
- `capital_allocator_min_free_cash_pct` теперь реально участвует в решении о перераспределении капитала.
- Reallocation partial close в paper больше не закрывается по `avg_price`; используется оценка mark-price (`last_mark_price` или вывод из `unrealized_pnl`).
- В `positions` добавлены поля:
  - `partial_closes_count`
  - `last_partial_close_ts`
  - `last_mark_price`
  - `last_mark_ts`
- В настройки добавлены:
  - `adaptive_exit_partial_cooldown_sec`
  - `adaptive_exit_max_partial_closes`
- Adaptive exit больше не режет позицию бесконечно на каждом тике: есть cooldown и limit на число partial close.
- `PositionMonitor` теперь сохраняет mark-price на каждом тике.
- `/api/v1/metrics` расширен:
  - `expectancy_per_trade`
  - `max_drawdown_pct`
  - `execution_error_count`
  - `adaptive_partial_closes_count`
  - `capital_reallocations_count`
  - `exit_reason_breakdown`
- UI показывает новые метрики на dashboard/account.

## Что проверено локально
- `python -m compileall -q backend`
- `python -m unittest backend.tests.test_timeframe_resample -v`
- `python -m unittest backend.tests.test_adaptive_exit_manager -v`

## Что ещё не доказано одним кодом
- Что текущие стратегии уже дают PF/expectancy уровня опытного дискреционного трейдера.
- Что allocator/exit логика оптимальна на реальном MOEX потоке. Это нужно подтверждать auto_paper прогоном.
