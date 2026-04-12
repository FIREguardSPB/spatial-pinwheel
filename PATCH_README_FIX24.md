# FIX24 — Phase 1 foundation (settings flicker, merge logging, multi-strategy base)

## Что сделано

### 1) Frontend: убрано мигание настроек
- `useSettings()` больше не подсовывает `initialData`, из-за которого сначала рисовались дефолты, а потом реальные настройки.
- В `SettingsPage` добавлен skeleton-loading.
- Форма гидратируется только один раз после первой успешной загрузки, чтобы фоновый refetch не перетирал локальные правки пользователя.

### 2) Backend: расширено логирование AI/DE merge
- Добавлен структурированный payload для merge:
  - `de_decision`
  - `de_score`
  - `de_has_blockers`
  - `ai_decision`
  - `ai_confidence`
  - `ai_min_confidence`
  - `ai_provider`
  - `final_decision`
  - `merge_reason`
- Логи пишутся как в обычный logger, так и в `decision_log` (`type=ai_de_merge`).
- В `signal.meta` сохраняется `decision_merge`.

### 3) Детальное логирование signal/trade pipeline
- `signal_created`
- `signal_risk_block`
- `decision_engine`
- `signal_pipeline`
- `execution_intent`
- `trade_filled`

Во все критичные записи добавлены расширенные payload-поля для последующего пост-мортема.

### 4) Базовый мультистратегийный слой (Phase 1)
- Добавлен `CompositeStrategy`.
- `strategy_name` теперь поддерживает строку из нескольких стратегий, например:
  - `breakout,mean_reversion,vwap_bounce`
- Стратегии запускаются параллельно на одном history-контексте, затем выбирается лучший кандидат по детерминированному weighted-score.
- В payload/meta сохраняется информация о кандидатах и выбранной стратегии.

### 5) Frontend: базовое управление несколькими стратегиями
- В Settings UI добавлен блок выбора стратегий.
- Активные стратегии сохраняются в тот же `strategy_name` как comma-separated список.

## Что проверено
- `python3 -m compileall -q backend`
- `pytest -q backend/tests/test_phase1_multistrategy.py` → `4 passed`

## Что не подтверждаю
- Полный runtime-прогон всего проекта у заказчика.
- Полный frontend build в песочнице без установленных npm dependencies.
