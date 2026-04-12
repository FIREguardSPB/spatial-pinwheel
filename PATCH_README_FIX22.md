# Spatial Pinwheel — FIX22

## Что исправлено

### 1) Ложный `Ratio 0.00` / уровень слишком близко
- Переписан расчёт ближайшего opposing level в `DecisionEngine`.
- Теперь для BUY берётся ближайшее сопротивление **выше entry**, для SELL — ближайшая поддержка **ниже entry**.
- Текущий бар исключён из поиска, поэтому система больше не подсовывает в качестве уровня сам текущий entry.
- Если уровня в lookback нет, возвращается `LEVEL_UNKNOWN`, а не фейковый `0.00`.
- Сообщения стали явнее: `Nearest resistance/support too close`, чтобы не путать это с ATR stop ratio.
- В metrics добавлены:
  - `nearest_level`
  - `level_clearance_ratio`
  - `stop_atr_ratio`
  - `macd_hist`

### 2) Время торговых сессий MOEX
- `session.py` переписан под режимы morning / main / evening.
- По умолчанию и для старых настроек бот теперь не режет утренние сигналы с 06:50 МСК.
- В `check_session()` и `should_close_before_session_end()` передаётся session mode из настроек.
- Добавлена миграция, которая переводит default `trading_session` на `all`.

### 3) AI confidence threshold
- Базовый `ai_min_confidence` снижен с 70 до 60.
- Обновлены backend defaults, schema, settings API, migration и frontend defaults.

### 4) Логирование AI reasoning
- В provider log теперь попадает краткое AI reasoning.
- В merge log воркера теперь тоже пишется краткая причина решения AI.

## Что проверено
- `python3 -m compileall -q backend` — ok
- Ручная проверка session utils на 08:00 MSK:
  - `is_trading_session('all') == True`
  - `is_trading_session('main') == True`
  - `minutes_until_session_end('all')` даёт конец полного торгового окна, а не только хвост утренней сессии.
- Ручная проверка `score_levels()`:
  - микро-расстояния больше не печатаются как `0.00`, минимальное отображение — `0.01`,
  - отсутствие релевантного уровня даёт `LEVEL_UNKNOWN`, а не ложный near-zero ratio.

## Что честно не подтверждено в этой среде
- Полный runtime прогон приложения на окружении заказчика.
- Полный frontend build (в песочнице нет project dependencies).
- Полный pytest suite (в песочнице отсутствует SQLAlchemy и часть проектных зависимостей).
