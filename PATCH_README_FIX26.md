# FIX26 — economic viability guards + micro-level protection

## Что сделано
- Добавлен `EconomicFilter` в `backend/core/risk/economic.py`.
- Decision Engine теперь ставит hard reject за:
  - low-price инструменты ниже порога
  - микро-уровни SL/TP
  - слишком маленькую ожидаемую прибыль после costs
  - слишком маленькую стоимость позиции
- В `metrics` добавлены абсолютные и процентные economics-поля:
  - `entry_price_rub`, `position_value_rub`, `sl_distance_rub/pct`, `tp_distance_rub/pct`
  - `round_trip_cost_rub/pct`, `min_required_sl_*`, `min_required_profit_*`
  - `expected_profit_after_costs_rub`, `breakeven_move_pct`
  - `commission_dominance_ratio`, `economic_warning_flags`, `economic_filter_valid`
- AI prompt upgraded to `intraday_dynamic_v2_economic`:
  - отдельный блок `ЭКОНОМИКА СДЕЛКИ`
  - warnings `MICRO_LEVELS_WARNING`, `COMMISSION_DOMINANCE_WARNING`, `LOW_PRICE_WARNING`
  - абсолютные значения в RUB и процентах
- Frontend signals UI:
  - цены для бумаг < 10 RUB показываются с 4 знаками
  - выводятся cost/min profit/after-costs
  - визуальные предупреждения об экономическом риске
- Settings UI/API/DB:
  - `min_sl_distance_pct`
  - `min_profit_after_costs_multiplier`
  - `min_trade_value_rub`
  - `min_instrument_price_rub`
- Добавлена migration `20260315_02_economic_filters.py`.

## Что проверено
- `python3 -m compileall -q backend src`
- `PYTHONPATH=backend pytest -q backend/tests/test_ai_context_improvements.py` → 7 passed
- ручные python-checks на новый `EconomicFilter` и `build_user_prompt()`

## Что не подтверждено здесь
- полный runtime-прогон у заказчика
- полный frontend build
- полный pytest suite (в песочнице не установлен `sqlalchemy`)
