FIX88

Основной фокус:
- frontend/backend audit pass по backlog после FIX87
- papers tab fallback на прямые endpoints
- облегчение /settings/runtime-overview при include_globals=false
- auto-policy warmup/error handling
- восстановление created_ts/updated_ts в signals API
- защита chart realtime от rollback более старыми HTTP slices

Ключевые файлы:
- src/features/settings/SettingsPage.tsx
- src/features/core/uiQueries.ts
- src/features/dashboard/ChartContainer.tsx
- src/features/dashboard/DashboardPage.tsx
- src/store/index.ts
- backend/apps/api/routers/settings.py
- backend/apps/api/routers/ui.py
- backend/core/services/degrade_policy.py
- backend/core/models/schemas.py
- src/types/index.ts
