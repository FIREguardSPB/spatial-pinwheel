# PATCH_README_FIX87

## Фаза

FIX87 — полный аудит frontend/backend interaction + one-pass remediation.

## Что сделано

### P0
- Починен UI-safe runtime path для auto-policy.
- Добавлен быстрый loading/stale-cache ответ вместо блокировки coordinator UI endpoints.
- Убран глобальный stale placeholderData из всего frontend query-слоя.

### P1
- Переписан dashboard chart flow для борьбы со stale response.
- Усилена SSE invalidation для coordinator/runtime/settings.
- Latest candle на dashboard теперь коррелирует с выбранной бумагой/TF.
- Улучшено отображение runtime payload в Settings.

### P2
- Убраны часть legacy mock/fallback веток из frontend data-path.
- Добавлен unit test для UI-safe policy path.

## Ключевые файлы

### Backend
- `backend/core/services/degrade_policy.py`
- `backend/core/services/ui_runtime.py`
- `backend/apps/api/routers/ui.py`
- `backend/tests/test_degrade_policy_ui_safe.py`

### Frontend
- `src/RootApp.tsx`
- `src/features/dashboard/ChartContainer.tsx`
- `src/features/dashboard/DashboardPage.tsx`
- `src/features/dashboard/InstrumentSelector.tsx`
- `src/features/activity/hooks.ts`
- `src/features/settings/SettingsPage.tsx`
- `src/services/stream.ts`
- `src/features/core/uiQueries.ts`

## Проверки

- backend compile: OK
- selected backend unit tests: OK
- TypeScript typecheck: OK

## Важно после установки

1. Полностью перезапустить backend, worker, frontend.
2. Очистить persisted browser state / сделать hard reload.
3. Проверить:
   - `/api/v1/ui/settings`
   - `/api/v1/ui/dashboard?instrument_id=...&timeframe=...`
   - `/api/v1/ui/runtime`
   - live-update dashboard после появления новой свечи/сигнала.
