# FIX81 — coordinator-first frontend/backend rewrite

## Что изменено

### Backend
- Добавлен новый router `backend/apps/api/routers/ui.py`.
- Добавлены агрегирующие endpoint'ы:
  - `GET /api/v1/ui/runtime`
  - `GET /api/v1/ui/dashboard`
  - `GET /api/v1/ui/settings`
  - `GET /api/v1/ui/signals`
  - `GET /api/v1/ui/activity`
  - `GET /api/v1/ui/trades`
  - `GET /api/v1/ui/account`
- Цель: убрать каскад из десятков мелких запросов на каждую страницу и перейти к page-bootstrap payload.

### Frontend
- Добавлен единый слой page-bootstrap hooks: `src/features/core/uiQueries.ts`.
- Переписаны страницы:
  - `DashboardPage`
  - `SettingsPage`
  - `SignalsPage`
  - `ActivityPage`
  - `TradesPage`
  - `AccountPage`
- Все эти страницы теперь опираются на один coordinator endpoint на страницу вместо пачки разрозненных query.
- `ChartContainer` перестал сам дёргать позиции отдельным запросом: позиции приходят из bootstrap payload дашборда.
- HTTP timeout поднят до 12 секунд, чтобы запросы не умирали в browser queue через 4 секунды.
- `/ui/*` добавлены в мягкие read-only path rules клиента.

## Архитектурная цель
Сместить фронт с "много независимых виджетов, каждый сам ходит в API" на модель:
- один bootstrap запрос на страницу,
- отдельно только тяжёлые/специфические данные вроде свечей,
- меньше дублирования query keys,
- меньше гонок и отменённых запросов,
- более понятные состояния загрузки.

## Что проверить в первую очередь
1. На странице настроек больше не должно быть каскада из `status`, `runtime-overview`, `watchlist`, `settings`, `ai/runtime` одновременно.
2. На Dashboard должно быть заметно меньше сетевых запросов.
3. При навигации между `Настройки / Сигналы / События / Счёт / Сделки` не должно происходить массового `ERR_ABORTED` по старой схеме.
4. График дашборда должен жить отдельно и не тянуть за собой лишние runtime GET.
