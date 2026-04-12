# FIX78 — frontend reboot around backend contracts

## Что сделано

Вместо очередных локальных правок переписан основной frontend-shell по принципу **backend-first**:

- единый слой запросов `src/features/core/queries.ts`
- единые query keys для базовых данных
- убран глобальный SSE connect из `RootApp`
- отключена старая health-driven деградация всего UI
- переписаны страницы:
  - Dashboard
  - Settings
  - Signals
  - Trades
  - Activity
  - Account
  - Backtest
- добавлены новые простые блоки UI:
  - `PageShell`
  - `Surface`
  - `QueryBlock`
  - `SimpleTable`
  - `StatGrid`
- `api.ts` переведён в более тихий read-only режим:
  - GET-ошибки не спамят toast
  - page-level ошибки обрабатываются локально
- `backend/apps/api/main.py`:
  - health больше не считает систему "мертвой" в paper/review только из-за отсутствия live T-Bank токенов

## Основная идея

Не лечить старый фронт ещё одним слоем fallbacks, а сделать новый минимальный рабочий frontend поверх реально существующих backend endpoints.

## Что теперь должно стать лучше

- страницы не должны стартовать десятками дублирующих запросов
- Settings не должны зависать из-за одного упавшего поля
- Dashboard должен показывать реальные runtime-данные, а не пустые виджеты
- расписание должно рендериться из `GET /settings/trading-schedule`
- watchlist должен открываться и редактироваться из одного места
- ошибки должны быть локальными для страницы, а не превращать весь UI в красную аварию

## Что не трогалось сознательно

- старые heavy analytics panels
- старые widget-level hooks и часть сложных компонент
- live stream / SSE как обязательная часть UI

## Проверка

- `npx tsc --noEmit` — OK
- `python3 -m compileall -q backend` — OK

