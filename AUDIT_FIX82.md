# AUDIT FIX82

## Подтвержденный корень проблемы
По HAR и коду coordinator architecture проблема была не только во фронте.
`/ui/dashboard` и `/ui/settings` включали тяжелые backend read-path вызовы:
- `build_bot_status()` -> `refresh_trading_schedule()`
- `get_trading_schedule()` -> `refresh_trading_schedule()`
- `runtime_overview()` -> построение adaptive plan / AI / ML / diagnostics

Это делало bootstrap страницы слишком тяжелым и приводило к отмене XHR клиентом по timeout.

## Что изменено архитектурно
- bootstrap routes переведены на fast snapshot reading
- тяжелый runtime overview вынесен из bootstrap
- page-level polling убран

## Остаточный риск
Если отдельный `runtime_overview` все еще будет тяжелым на некоторых инструментах,
его нужно будет дробить дальше по секциям (`symbol_profile`, `diagnostics`, `ai_runtime`, `ml_runtime`).
Но теперь это уже не должно ронять Dashboard целиком.
