# FIX67

## Что закрыто

- Восстановлен frontend reproducible baseline:
  - `package-lock.json`
  - `packageManager` в `package.json`
  - `.nvmrc`
  - `.npmrc`
- Мобильная навигация больше не ограничена первыми 5 разделами.
- `SettingsPage` получил поиск по секциям и фильтрацию по смысловым группам.
- `SignalProcessor.process()` разрезан на фазы:
  - `_prepare_signal_context`
  - `_apply_risk_and_sizing`
  - `_persist_signal`
  - `_run_decision_flow`
  - `_publish_and_notify`
  - `_execute_signal`
- В `signals.py` добавлены `commit=False` режимы для `create_signal` и `update_signal_status`.
- Execution timeframe policy вынесена в `_select_execution_timeframe(...)` и теперь учитывает low-vol / higher-analysis сценарии.
- Добавлены backend-тесты на execution timeframe policy.

## Что реально проверено

- `python3 -m compileall -q backend`
- `PYTHONPATH=backend python3 -m unittest discover -s backend/tests -p 'test_*.py'`

## Ограничения проверки

- `npm ci` в контейнере упирается в ошибку аутентификации registry (`E401`), поэтому полный install/build/lint/test фронта здесь честно не подтверждён.
