FIX85

What was corrected
- UI signal/trade counts no longer present page-size values as global totals.
- Dashboard now exposes latest candle timestamp from cache and chart history is polled every 30s.
- Candle API refreshes stale market history from T-Bank market data whenever runtime tokens are present, even in paper execution mode.
- Settings runtime cards use explicit loaded/error/empty states.
- Settings bootstrap now returns current auto-policy and ML runtime summaries instead of idle placeholders.
- Runtime overview for Papers was wrapped in a safe sync helper and returns structured per-block error payloads instead of collapsing the whole panel.
- Worker import for build_symbol_plan is present.
- Account page now exposes paper reset action and account history includes flat-equity metadata.

Files changed
- backend/apps/api/routers/ui.py
- backend/core/services/ui_runtime.py
- backend/apps/api/routers/candles.py
- backend/apps/api/routers/settings.py
- backend/apps/api/routers/account.py
- backend/apps/worker/main.py
- backend/core/storage/repos/state.py
- backend/core/storage/repos/signals.py
- src/features/core/uiQueries.ts
- src/features/dashboard/DashboardPage.tsx
- src/features/dashboard/ChartContainer.tsx
- src/features/signals/SignalsPage.tsx
- src/features/trades/TradesPage.tsx
- src/features/account/AccountPage.tsx
- src/features/settings/SettingsPage.tsx
