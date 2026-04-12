# FIX82 — fast-snapshot coordinator and no-poll bootstrap

## Что исправлено
- Убраны блокирующие refresh-вызовы брокерского расписания из обычных read-path:
  - `build_bot_status()` теперь читает только cached snapshot
  - `GET /settings/trading-schedule` теперь читает только cached snapshot
  - принудительная синхронизация осталась только в `POST /settings/trading-schedule/sync`
- `GET /ui/dashboard` и `GET /ui/settings` больше не тянут `runtime_overview` в bootstrap payload
- `runtime_overview` вынесен в отдельный lazy query на фронте
- Убран page-level polling (`refetchInterval`) у `ui/*` запросов
- В Settings явнее различаются состояния:
  - `загрузка`
  - `не загрузилось`
  - `данных нет`

## Почему это было важно
HAR показал, что `/api/v1/ui/dashboard` ждал >12 секунд и отменялся клиентом (`net::ERR_ABORTED`).
Основной корень — coordinator endpoint тянул тяжелые и потенциально сетевые read-path операции
(расписание брокера и runtime-overview) прямо в bootstrap страницы.

## Что проверить
- На Dashboard должен успешно возвращаться `GET /api/v1/ui/dashboard`
- На Settings должен успешно возвращаться `GET /api/v1/ui/settings`
- `runtime_overview` должен запрашиваться отдельно только когда нужен
- При навигации не должно быть постоянного page-level polling каждые 15 секунд
