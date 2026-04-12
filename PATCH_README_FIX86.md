# Spatial Pinwheel — FIX86

## Что закрыто в этой фазе

1. **Устранён блокирующий auto-policy runtime path**
   - `backend/core/services/degrade_policy.py`
   - добавлен короткий TTL-кэш для `evaluate_degrade_policy()`;
   - `build_policy_runtime_payload()` больше не валит UI-координаторы: при ошибке отдаёт безопасный payload (`status=error` или `status=stale-cache`) вместо зависания;
   - `backend/core/services/ui_runtime.py` теперь возвращает policy snapshot без принудительного перезаписывания статуса.

2. **Полностью убран mock-fallback из свечей API**
   - `backend/apps/api/routers/candles.py`
   - если реальных свечей нет, backend возвращает `503 No real candle data available`;
   - случайная генерация свечей удалена.

3. **Подключён реальный live-bootstrap фронта**
   - `src/RootApp.tsx`
   - теперь при старте приложения реально поднимаются:
     - `useBackendRuntime()`
     - SSE stream (`streamService.connect()`)
     - привязка `QueryClient` к stream-service.

4. **SSE теперь обновляет coordinator-страницы, а не только legacy hooks**
   - `src/services/stream.ts`
   - добавлена invalidation для:
     - `['ui', 'dashboard']`
     - `['ui', 'signals']`
     - `['ui', 'trades']`
     - `['ui', 'account']`
     - `['ui', 'runtime']`

5. **UI bootstrap переведён на более живое обновление**
   - `src/features/core/uiQueries.ts`
   - coordinator queries получили `refetchInterval` + `refetchOnWindowFocus`;
   - `useUiDashboard()` теперь учитывает `instrument_id` в query key и params.

6. **Dashboard latest candle стал привязан к выбранной бумаге**
   - `backend/apps/api/routers/ui.py`
   - `/api/v1/ui/dashboard?instrument_id=...` теперь возвращает latest candle именно по выбранному инструменту.

7. **Устранено залипание старых свечей и «двойных веток» на графике**
   - `src/features/dashboard/ChartContainer.tsx`
   - удалён UI demo mock-path из графика;
   - добавлена нормализация времени свечей (ms→sec), дедупликация и сортировка;
   - ускорён регулярный refetch истории;
   - realtime update теперь тоже нормализует timestamps.

8. **Сигнальная лента больше ориентируется на фактическое время создания записи**
   - `backend/core/storage/repos/signals.py`
   - сортировка по `created_ts desc, ts desc`;
   - summary `latest_signal_ts` теперь считается по `created_ts`.
   - `src/features/signals/SignalsPage.tsx` показывает `created_ts` как основное время, а время свечи — отдельно.

9. **Убран persist старых свечей и mock-режима в store**
   - `src/store/index.ts`
   - persisted state больше не хранит historical candles и `isMockMode`;
   - storage version повышен до `v4`, миграция сбрасывает старые mock/candles артефакты.

10. **Mock source больше не активируется скрыто из runtime health**
   - `src/features/system/useBackendRuntime.ts`
   - `mock` допускается только в явном `UI demo mode`, а не как автоматический fallback обычного runtime.

## Проверки

- `python3 -m compileall -q backend` — OK
- `PYTHONPATH=backend python3 -m unittest backend.tests.test_degrade_policy backend.tests.test_degrade_policy_cache backend.tests.test_trading_schedule_static -v` — OK
- `tsc --noEmit` — OK

## Добавленные тесты

- `backend/tests/test_degrade_policy_cache.py`
  - проверяет короткий TTL-кэш auto-policy;
  - проверяет безопасный fallback payload при исключении.

## Что важно после установки

1. Перезапустить backend API.
2. Перезапустить worker.
3. Полностью перезагрузить frontend страницу (чтобы сбросить старый persisted Zustand store).
4. Проверить, что в DevTools на Dashboard / Settings / Signals идут coordinator-запросы `/api/v1/ui/...`, а SSE-соединение удерживается без мгновенного disconnect.

## Что не заявляется

Этот фикс устраняет блокеры runtime/UI и удаляет mock-фоллбеки, но **сам по себе не доказывает торговое качество уровня опытного трейдера**. Он возвращает системе корректный реальный контур данных и наблюдаемость.
