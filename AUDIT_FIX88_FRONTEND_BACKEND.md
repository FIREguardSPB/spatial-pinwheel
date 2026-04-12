# FIX88 — аудит фронтенда и взаимодействия с backend

## База аудита
Проверка выполнена по backlog после FIX87 и по текущему коду активных маршрутов:
- DashboardPage / ChartContainer / uiQueries / stream
- SettingsPage / papers runtime panel / settings runtime-overview
- UI coordinator endpoints /ui/*
- signals API and response schemas
- auto-policy runtime cache path

## Найденные проблемы

### 1. Papers tab зависел от одного агрегированного runtime-overview
Вкладка "Бумаги" брала все карточки только из `/settings/runtime-overview`.
Если этот агрегированный запрос тормозил, partially degraded или возвращал пустую часть payload, карточки оставались пустыми, хотя прямые backend endpoints `/symbol-profiles/{instrument}` и `/event-regimes` могли быть рабочими.

### 2. `/settings/runtime-overview?include_globals=false` всё равно тянул тяжёлые global runtime блоки
Даже когда фронту для вкладки "Бумаги" нужны только `effective_plan / symbol_profile / diagnostics / event_regime`, backend всё равно дополнительно строил `ai_runtime / telegram / auto_policy / ml_runtime`.
Это ухудшало latency и делало papers-view слишком хрупким.

### 3. Auto-policy мог висеть в `loading` слишком долго
UI-safe path уже был, но у cache-warmup не было полноценного error/warmup-timeout состояния.
При неудачном фоне карточка могла продолжать показывать `loading`, хотя корректнее показывать error/warmup-timeout или stale-cache.

### 4. `/api/v1/signals` терял `created_ts` и `updated_ts` на response-model слое
ORM-данные содержали эти поля, но pydantic schema `Signal` их не описывала, поэтому ответ API мог терять timestamps.
Это ломало свежесть ленты, сортировку и диагностику "почему сигнал выглядит старым".

### 5. Фронтовый тип `SignalStatus` отставал от backend
Во фронте отсутствовали `execution_error` и `skipped`, хотя backend реально использует их.
Это не всегда роняло сборку, но делало слой типов неполным.

### 6. Chart polling мог перетирать более свежие SSE-свечи более старым HTTP-ответом
ChartContainer на периодическом refetch делал replace целого slice candles.
Если SSE уже добавил новую свечу, а HTTP-ответ пришёл из более старого cache-state, UI откатывался назад и выглядел как "замороженный".

### 7. Dashboard не нормализовал selected instrument против фактического watchlist
Если в store оставался инструмент не из текущего watchlist, дашборд мог работать с неактуальным выбором.

## Что исправлено

### Papers / settings
- Вкладка "Бумаги" теперь использует не только `useRuntimeOverview`, но и прямые hooks:
  - `useSymbolProfileView`
  - `useEventRegimeView`
- Карточки заполняются по fallback-цепочке:
  - Effective plan: runtime-overview -> symbol-profiles.current_plan
  - Symbol profile: runtime-overview -> symbol-profiles.profile
  - Diagnostics: runtime-overview -> symbol-profiles.diagnostics
  - Event regime: runtime-overview -> event-regimes.items[0]
- Ошибки запросов теперь пробрасываются в карточки как текст ошибки, а не как немой "не загрузилось".

### Backend runtime-overview
- При `include_globals=false` route больше не строит тяжёлые глобальные блоки:
  - ai_runtime
  - telegram
  - auto_policy
  - ml_runtime
  - pipeline_counters
- Это делает papers-view легче и быстрее.

### Auto-policy runtime
- Расширен cache state:
  - `last_error`
  - `last_error_at`
  - `warming_started_at`
- Добавлен warmup-timeout.
- Если фоновый прогрев зависает или падает, UI-safe payload теперь может возвращать `error`, а не бесконечный `loading`.
- Добавлен debug endpoint:
  - `GET /api/v1/ui/runtime/auto-policy-debug`

### Signals API / types
- В backend schema `Signal` добавлены:
  - `created_ts`
  - `updated_ts`
- Во frontend type `Signal` добавлены:
  - `created_ts`
  - `updated_ts`
- Во frontend `SignalStatus` добавлены:
  - `execution_error`
  - `skipped`

### Chart / realtime
- Store получил `mergeCandles`, чтобы HTTP refetch не выбрасывал более свежие локальные/SSE candles.
- ChartContainer переключён с `replaceCandles(...)` на `mergeCandles(...)` для backend refetch path.
- Это уменьшает риск визуального отката графика на более старое состояние.

### Dashboard selection hygiene
- DashboardPage теперь принудительно нормализует `selectedInstrument` по текущему watchlist.

## Проверки
- `python3 -m compileall -q backend` — OK
- `PYTHONPATH=backend python3 -m unittest backend.tests.test_degrade_policy backend.tests.test_degrade_policy_cache backend.tests.test_degrade_policy_ui_safe backend.tests.test_trading_schedule_static -v` — OK
- `npm exec --yes tsc --noEmit` — OK

## Что ещё честно требует живого прогона
1. Визуальное подтверждение, что конкретный стенд больше не показывает пустые карточки на вкладке "Бумаги".
2. Проверка weekend / market-closed поведения signal feed на реальном worker run.
3. Проверка того, что график на стенде перестал откатываться назад после SSE + polling races.
