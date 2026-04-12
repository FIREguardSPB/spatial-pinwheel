# PATCH_README_FIX68

## Что реализовано

### Часть 11 плана — forensic / auto-policy / декомпозиция

В этом пакете закрыт следующий незавершённый этап из продолжения прошлой переписки:

1. **Единый forensic export**
   - добавлен backend-сервис `backend/core/services/forensic_export.py`
   - добавлен API `GET /api/v1/forensics/export?days=30[&instrument_id=...]`
   - экспорт собирает единый ZIP с:
     - `summary.json`
     - `settings.json`
     - `metrics.json`
     - `paper_audit.json`
     - `validation.json`
     - `signals.jsonl`
     - `decision_log.jsonl`
     - `traces.jsonl`
     - `trades.csv`
     - `orders.csv`
     - `positions.json`
     - `profiles.json`
     - `training_runs.json`
     - `event_regimes.json`
     - `effective_symbol_plans.json`

2. **Automatic degrade/freeze policy**
   - добавлен сервис `backend/core/services/degrade_policy.py`
   - добавлены runtime-настройки policy в `settings`
   - добавлена Alembic migration `20260401_03_forensics_auto_policy.py`
   - policy использует бизнес-метрики за lookback-окно и может:
     - перевести систему в `degraded`
     - перевести систему в `frozen`
     - автоматически срезать `risk_multiplier`
     - автоматически повышать effective threshold
     - блокировать новые входы при freeze
   - policy интегрирована в `SignalProcessor`
   - policy выводится в `runtime-overview`

3. **UI наблюдаемости**
   - в Settings добавлен отдельный блок:
     - состояние auto-policy
     - причины перехода в degraded/frozen
     - ключевые метрики окна
     - кнопка скачивания forensic export
     - editable controls для настройки thresholds

4. **Декомпозиция крупных модулей**
   - `backend/apps/worker/processor.py` → вынесены helper-функции в `backend/apps/worker/processor_support.py`
   - `backend/apps/broker/tbank/adapter.py` → вынесены instrument/timestamp helpers в `backend/apps/broker/tbank/adapter_support.py`
   - `backend/core/services/symbol_adaptive.py` → вынесены timeframe helpers в `backend/core/services/symbol_adaptive_timeframes.py`
   - `src/features/settings/SettingsPage.tsx` → UI-блоки вынесены в:
     - `src/features/settings/components/TransparencyPanels.tsx`
     - `src/features/settings/components/ForensicsPolicyPanel.tsx`

## Какая часть плана выполнена

- fix58 — часть 1
- fix59 — часть 2
- fix60 — часть 3
- fix61 — часть 4
- fix62 — часть 5
- fix63 — часть 6
- fix64 — часть 7
- fix65 — часть 8
- fix66 — часть 9
- fix67 — часть 10
- **fix68 — часть 11: forensic export + automatic degrade/freeze policy + decomposition**

## Что проверено

- `python3 -m compileall -q backend` — ок
- `PYTHONPATH=backend python3 -m unittest backend.tests.test_degrade_policy -v` — ок
- `PYTHONPATH=backend python3 -m unittest backend.tests.test_timeframe_resample -v` — ок

## Что честно не подтверждено в контейнере

- полный runtime worker/api/db/tbank прогон
- полный фронтовый build/typecheck через npm/vite
- реальная выгрузка forensic export против живой БД
