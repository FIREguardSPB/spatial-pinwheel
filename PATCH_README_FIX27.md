# FIX27 — stability, research controls, schedule sync, safer AI

## Что сделано
- Сделан детерминированный выбор активной строки `settings` через `settings_repo.get_settings()`.
- Добавлены новые runtime-настройки риска и исполнения:
  - `max_position_notional_pct_balance`
  - `max_total_exposure_pct_balance`
  - `signal_reentry_cooldown_sec`
  - `use_broker_trading_schedule`
  - `trading_schedule_exchange`
  - `ai_override_policy`
  - `is_active`
- Добавлена синхронизация расписания торгов через T-Bank `TradingSchedules` с кешом и fallback на статические окна.
- `bot/status` теперь показывает источник расписания, открыт ли рынок, границы текущей сессии и следующее открытие.
- `RiskManager` переведён на детерминированные настройки и усилен:
  - лимит стоимости одной позиции,
  - лимит суммарной экспозиции,
  - re-entry cooldown по бумаге и направлению.
- AI стал безопаснее по умолчанию:
  - дефолт `ai_mode=advisory`
  - дефолт `ai_primary_provider=deepseek`
  - новая политика `ai_override_policy=promote_only`
  - override больше не обязан быть двусторонним.
- Paper execution и PositionMonitor теперь учитывают оценочные fees/slippage и сохраняют связку:
  - `opened_signal_id`
  - `opened_order_id`
  - `closed_order_id`
  - `entry_fee_est`
  - `exit_fee_est`
  - `total_fees_est`
- Decision Engine получил strategy-aware профиль весов и порога.
- Полностью расширен Settings UI:
  - лимиты риска и экспозиции,
  - max trades/day,
  - re-entry cooldown,
  - комиссии и проскальзывание,
  - режимы сессий,
  - toggle и ручная синхронизация расписания,
  - AI override policy,
  - research scalp preset,
  - новые подсказки/help-content почти для всех новых настроек.
- Обновлены frontend types, mocks и hooks под новый backend-контракт.

## Что проверить у заказчика
1. Применить alembic migration `20260318_01_settings_runtime_controls`.
2. Открыть Settings и проверить, что:
   - отображается schedule snapshot,
   - кнопка `Обновить расписание` работает,
   - после сохранения settings не мигают и не откатываются.
3. Проверить paper-торговлю на 1–2 дня с `ai_mode=advisory`.
4. Сверить, что в логах и сделках появляются fees/slippage поля и order linkage.

## Что проверено здесь
- `python3 -m compileall -q backend src`
- `PYTHONPATH=backend pytest -q backend/tests/test_ai_context_improvements.py backend/tests/test_phase1_multistrategy.py`
