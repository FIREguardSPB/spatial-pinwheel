# PATCH_README_FIX61

## Какая часть плана закрыта

Это **часть 4 плана**: следующий слой после архитектурной стабилизации, trade-management realism и freshness/walk-forward.

В FIX61 закрыт подблок:
- portfolio allocator 2.0;
- nightly symbol recalibration;
- observability этих двух механизмов в метриках и UI.

## Что изменено

### 1. Portfolio allocator 2.0
- В `core/services/capital_allocator.py` перераспределение капитала теперь учитывает не только score gap, но и:
  - edge improvement входящего сигнала относительно текущей позиции;
  - концентрацию текущей позиции в портфеле;
  - дефицит свободного кэша;
  - age decay позиции.
- Добавлены новые runtime-параметры:
  - `capital_allocator_min_edge_improvement`
  - `capital_allocator_max_position_concentration_pct`
  - `capital_allocator_age_decay_per_hour`
- В meta кандидата теперь возвращаются:
  - `edge_improvement`
  - `current_notional_pct`
  - `portfolio_pressure`

### 2. Nightly recalibration
- Добавлен сервис `core/services/recalibration.py`.
- Worker теперь имеет отдельный цикл `worker-recalibration`, который раз в минуту проверяет, пора ли запускать nightly recalibration.
- Режим планирования:
  - `symbol_recalibration_enabled`
  - `symbol_recalibration_hour_msk`
  - `symbol_recalibration_train_limit`
  - `symbol_recalibration_lookback_days`
- Приоритет кандидатов строится по:
  - активному watchlist;
  - давности последней тренировки;
  - отсутствию/слабости sample size;
  - слабой недавней результативности по инструменту.
- После batch запускается `train_symbol_profile(...)` по top-N инструментам.
- Результат batch пишется в `decision_log` как `symbol_recalibration_batch`.

### 3. API
- Добавлены endpoints:
  - `GET /api/v1/symbol-profiles/recalibration/status`
  - `POST /api/v1/symbol-profiles/recalibration/run`

### 4. Метрики
- `/api/v1/metrics` расширен полями:
  - `avg_reallocation_ratio`
  - `portfolio_concentration_pct`
  - `recalibration_runs_count`
  - `recalibration_symbols_trained`
  - `last_recalibration_ts`

### 5. UI
- В `SettingsPage` добавлены контролы allocator 2.0 и nightly recalibration.
- В `AccountPage` добавлены виджеты:
  - concentration портфеля;
  - recalibration runs / trained symbols;
  - last recalibration ts;
  - average reallocation ratio.

## Что проверено
- `python -m compileall -q backend`

## Что честно не подтверждено без окружения заказчика
- Полный runtime worker/api/db/tbank прогон.
- Полный frontend build/typecheck через npm/vite.
- Фактическое улучшение PF/expectancy на реальном long paper-run.
