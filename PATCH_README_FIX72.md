# PATCH_README_FIX72

## Что добавлено

Фаза FIX72 реализует управляющий слой поверх performance layer:

- dynamic strategy/regime whitelist
- adaptive risk budget by validated slice
- automatic suppression of weak slices
- постторговый learning loop для allocator и execution priority

## Backend

### Новый сервис
- `backend/core/services/performance_governor.py`

Сервис строит validated slices по стратегии и режиму рынка на основе:
- сигналов
- decision log
- закрытых позиций
- фактического post-trade результата

### Что он считает
- `slice_rows`
- `strategy_rows`
- `regime_rows`
- `whitelist_by_regime`
- `boosted_slices`
- `suppressed_slices`
- `recommendations`

### Что он применяет в execution pipeline
- `risk_multiplier`
- `threshold_adjustment`
- `execution_priority`
- `allocator_priority_multiplier`
- `suppressed`
- `allowed`

### Интеграция в worker
- weak slice может быть автоматически подавлен
- validated strong slice может получить risk boost
- слабый slice получает risk cut и threshold penalty
- strict whitelist может запретить стратегию вне подтверждённого whitelist режима

### Learning loop
Информация governor теперь влияет на:
- `effective_threshold`
- размер позиции через risk multiplier
- execution priority
- allocator candidate selection
- min gap / edge-improvement для reallocation

## API

Добавлен endpoint:
- `GET /api/v1/validation/performance-governor?days=45`

## Settings / runtime controls

Добавлены новые настройки:
- `performance_governor_enabled`
- `performance_governor_lookback_days`
- `performance_governor_min_closed_trades`
- `performance_governor_strict_whitelist`
- `performance_governor_auto_suppress`
- `performance_governor_max_execution_error_rate`
- `performance_governor_min_take_fill_rate`
- `performance_governor_pass_risk_multiplier`
- `performance_governor_fail_risk_multiplier`
- `performance_governor_threshold_bonus`
- `performance_governor_threshold_penalty`
- `performance_governor_execution_priority_boost`
- `performance_governor_execution_priority_penalty`
- `performance_governor_allocator_boost`
- `performance_governor_allocator_penalty`

Есть Alembic migration:
- `backend/core/storage/migrations/versions/20260401_04_performance_governor_controls.py`

## Forensics

Forensic export теперь включает:
- `performance_governor.json`

## Frontend

### Account
Добавлен новый блок:
- `Performance governor`

В нём отображаются:
- общий статус governor
- validated/suppressed slices
- whitelist by regime
- recommendations learning loop

### Settings
Добавлен новый runtime-блок управления governor.

## Проверка

Проверено локально:
- `python3 -m compileall -q backend`
- `PYTHONPATH=backend python3 -m unittest backend.tests.test_performance_governor backend.tests.test_degrade_policy backend.tests.test_trading_quality_audit backend.tests.test_performance_layer -v`
- transpile-проверка TS/TSX через `typescript.transpileModule`

## Ограничения

Не подтверждено в этой среде:
- полный runtime-прогон с вашей БД / Redis / worker / broker API
- реальный эффект на PF / expectancy / drawdown без auto_paper прогона на вашей истории
