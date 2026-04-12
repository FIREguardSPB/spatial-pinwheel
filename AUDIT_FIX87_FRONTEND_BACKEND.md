# FIX87 — Аудит фронтенда и взаимодействия с бэкендом

## Что проверялось

Полный проход по frontend/runtime/data-flow слоям последней версии проекта:
- coordinator UI endpoints (`/api/v1/ui/dashboard`, `/api/v1/ui/settings`, `/api/v1/ui/runtime`)
- dashboard candle flow
- SSE invalidation
- signal freshness
- runtime cards в Settings
- явные и скрытые mock/fallback-пути
- устойчивость frontend query-слоя
- безопасная интеграция тяжёлой auto-policy в UI-runtime

## Ключевые найденные проблемы

### 1. Глобальный `placeholderData` был архитектурно опасным

В `src/RootApp.tsx` QueryClient был сконфигурирован так, что **все** query получали `placeholderData: (previousData) => previousData`.

Практический эффект:
- старый dashboard/runtime payload мог переживать смену бумаги/таймфрейма;
- stale данные визуально выглядели как «успешно загруженные»;
- ошибки и loading-state маскировались;
- пользователь видел замороженный интерфейс без честного сигнала о том, что данные уже неактуальны.

### 2. UI-safe слой для auto-policy фактически не был доведён до конца

Даже при наличии cache-логики в `degrade_policy.py`, coordinator-path всё ещё был чувствителен к cold-cache сценарию и мог затягивать тяжёлую policy-оценку в UI-ответ.

Практический эффект:
- `/api/v1/ui/settings`, `/api/v1/ui/dashboard`, `/api/v1/ui/runtime` могли подвисать;
- workaround с `auto_policy: {}` действительно объясним и не был случайным.

### 3. График был уязвим к stale-response и смешиванию серий

В candle/chart слое были слабые места:
- старый запрос мог доехать после переключения бумаги/TF;
- метка «последняя свеча» могла браться не из реально загруженной серии графика;
- signal markers не были надёжно нормализованы по timestamp;
- очистка серии при смене инструмента/TF была недостаточно жёсткой.

Практический эффект:
- «задвоенный» или смешанный график;
- визуально старые свечи;
- новые данные с SSE могли не чинить stale initial-state.

### 4. Runtime-карточки в Settings скрывали полезные ответы backend

Логика в `SettingsPage` трактовала `status: idle | missing | empty` как почти одинаковое «данных нет».

Практический эффект:
- пользователь видел пустые карточки по ML / auto-policy / protective contour,
  хотя backend мог вернуть валидный payload с объяснением текущего idle-состояния.

### 5. Во frontend ещё оставались legacy mock/fallback-пути

Обнаружены остаточные fallback-ветки в UI-слое. Даже там, где они не всегда критичны, они ухудшали доверие к интерфейсу и искажали диагностику.

## Что исправлено в FIX87

### Backend

- Добавлен **UI-safe policy path**:
  - `build_policy_runtime_payload_ui_safe(settings)`
  - empty cache -> быстрый `status=loading`
  - stale cache -> немедленная отдача stale payload
  - прогрев кэша -> отдельный daemon-thread с собственной DB session
- `ui_runtime.py` переведён на UI-safe policy summary.
- `/api/v1/ui/dashboard` теперь отдаёт:
  - `requested_instrument_id`
  - `requested_timeframe`
  - `generated_ts`
- `latest_candle` в dashboard payload теперь включает `timeframe`.

### Frontend

- Убран глобальный `placeholderData` из QueryClient defaults.
- Переписан `ChartContainer`:
  - abort in-flight fetch при смене бумаги/TF;
  - seq-guard против stale response;
  - нормализация timestamps;
  - жёсткая очистка серии на switch;
  - обновление графика через polling + visibility/focus refresh + SSE;
  - markers строятся по `created_ts ?? ts`, с нормализацией к секундам.
- Dashboard latest candle теперь берётся из реальной загруженной candle-series, а не только из coordinator payload.
- Добавлена индикация устаревших свечей.
- `SettingsPage` теперь показывает реальный JSON-payload idle/runtime карточек вместо «данных нет».
- Убраны явные mock fallback-пути из частей dashboard/activity/watchlist слоя, которые влияли на видимые данные.
- Расширена SSE invalidation матрица для coordinator/runtime/settings-состояний.

## Что проверено

- `python3 -m compileall -q backend`
- `PYTHONPATH=backend python3 -m unittest backend.tests.test_degrade_policy backend.tests.test_degrade_policy_ui_safe backend.tests.test_trading_schedule_static -v`
- `npx --yes tsc --noEmit`

## Что не подтверждено в контейнере

- Полный runtime-прогон с живым T-Bank sandbox и вашим worker-cycle.
- Browser-level визуальная проверка после реального запуска Vite + backend + worker.
- Vitest/e2e фронтовые тесты: dev-зависимости для vitest/plugin-react в этом контейнере не установлены.

## Остаточные риски

1. Если backend реально пишет старые свечи в БД или worker не публикует `kline` события, один frontend это не исправит.
2. Если в TradingView series приходят две разные временные шкалы из backend для одной бумаги/TF, нужен уже анализ payload и DB состояния.
3. В проекте ещё есть legacy-слой старых hooks/page-path; часть из них сейчас менее критична, но их лучше дочистить отдельной фазой.
