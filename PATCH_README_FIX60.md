# PATCH_README_FIX60

## Что закрыто в этой фазе

Это **часть 3 плана**: слой, который приближает систему к более «живому» auto_paper трейдеру не за счёт косметики, а за счёт качества оценки и свежести входа.

В FIX60 закрыт подблок:
- walk-forward / rolling evaluation;
- freshness-guard для stale сигналов;
- расширенная наблюдаемость этих двух механизмов.

## Что изменено

### 1. Walk-forward backtest стал реально out-of-sample
- `BacktestEngine.run_walk_forward()` больше не просто считает все стратегии на test-срезе.
- Теперь используется схема `expanding train -> выбрать лучшую стратегию -> проверить только её на OOS test window`.
- В ответе API теперь есть:
  - `train_scores` по каждой стратегии на фолде;
  - `selected_strategy`;
  - `out_of_sample` метрики выбранной стратегии;
  - агрегированный ranking по OOS-устойчивости.

### 2. Backtest API умеет DE-режим честно
- Если `use_decision_engine=true`, API теперь поднимает runtime settings из БД и действительно передаёт их в `BacktestEngine`.
- Раньше флаг был почти декоративным.

### 3. UI бэктеста расширен
- Добавлен выбор режима:
  - `single`
  - `walk_forward`
- Добавлен выбор числа folds.
- Добавлен выбор списка стратегий-кандидатов для отбора.
- В UI теперь показываются:
  - ranking стратегий по OOS;
  - fold-by-fold leaderboard train;
  - winner на каждом фолде;
  - OOS-метрики по каждому фолду.

### 4. Signal freshness guard встроен в worker pipeline
- Добавлен отдельный сервис `core/services/signal_freshness.py`.
- Введены runtime-настройки:
  - `signal_freshness_enabled`
  - `signal_freshness_grace_bars`
  - `signal_freshness_penalty_per_bar`
  - `signal_freshness_max_bars`
- После event-regime, но до AI merge теперь считается возраст сигнала в барах execution-TF.
- Если сигнал начинает стареть:
  - score снижается;
  - слишком старый TAKE переводится в `SKIP`.

### 5. Метрики и observability
- В decision log добавлен тип `signal_freshness`.
- В `/api/v1/metrics` добавлены:
  - `freshness_penalties_count`
  - `stale_signal_blocks_count`
- В Account UI это выведено как отдельная метрика freshness guards.

## Что проверено
- `python -m compileall -q backend`
- `PYTHONPATH=backend python -m unittest backend.tests.test_signal_freshness -v`
- `PYTHONPATH=backend python -m unittest backend.tests.test_backtest_walk_forward -v`
- `PYTHONPATH=backend python -m unittest backend.tests.test_timeframe_resample -v`
- `PYTHONPATH=backend python -m unittest backend.tests.test_p5_backtest -v`
- TS/TSX-файлы прогнаны через `typescript.transpileModule`

## Что ещё не утверждается без реального прогона
- Результативность на реальном paper/live рынке.
- Что именно эти настройки freshness оптимальны — это уже предмет walk-forward и paper calibration.
