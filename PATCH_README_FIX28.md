# FIX28 — audit hardening, observability, timezone, trade linkage

## Что исправлено

### Критичные баги из аудита
- `qty=0` в `/api/v1/trades`:
  - добавлен `qty/opened_qty` в payload `position_closed`;
  - добавлен `opened_qty` в `positions`;
  - `trades` теперь умеет брать количество из явной связи, а не только из close-log.
- починена атрибуция `signal -> trade`:
  - добавлен `signal_id` в `trades`;
  - paper/live execution сохраняют связь сделки с сигналом.
- `RiskManager` теперь считает начало дня по `Europe/Moscow`, а не по UTC.
- `max_trades_per_day` теперь считает именно входы (`decision_log.trade_filled`), а не сырые fills из `trades`.
- `EconomicFilter` и `DecisionEngine` выровнены по runtime-настройкам из БД:
  - `min_sl_distance_pct=0.08`
  - `min_profit_after_costs_multiplier=1.25`
  - `min_instrument_price_rub=1.0`
- `/api/v1/settings` теперь возвращает метаданные активной строки:
  - `id`
  - `updated_ts`
  - `is_active`
- worker на старте логирует активную конфигурацию с ключевыми risk-полями.

### UI / наблюдаемость
- Settings page показывает `settings_id`, `updated`, `active`.
- Trades page:
  - badge `manual rules` заменён на `rules engine`;
  - кнопка сброса фильтров нормально стилизована;
  - в деталях сделки показывается `signal_id`, стратегия, источник решения.
- Dashboard:
  - Open Positions теперь показывает только реально открытые позиции (`qty > 0`);
  - по клику на позицию показываются детали;
  - по клику на ордер показываются детали.
- Chart time formatting принудительно приведён к `Europe/Moscow` для осей и formatter'ов.
- `/health` теперь возвращает:
  - `server_time_utc`
  - `server_time_msk`
  - `timezone`

### Операционка
- worker автоматически игнорирует неподдерживаемые proxy env вида `socks://...`, которые ломали httpx/aiohttp.

## Миграция
Новая alembic migration:
- `20260321_01_audit_fixes`

Она добавляет:
- `trades.signal_id`
- `positions.opened_qty`

## Что проверить после раскатки
1. Выполнить alembic upgrade.
2. Открыть `/settings` и убедиться, что видны `settings_id` и время обновления.
3. Открыть dashboard:
   - в "Открытых позициях" не должно быть закрытых позиций;
   - клик по позиции/ордеру открывает детали.
4. После новой paper-сделки проверить `/api/v1/trades`:
   - `qty` больше не 0;
   - есть `signal_id`.
5. Проверить, что worker стартует даже при `all_proxy=socks://...`.
