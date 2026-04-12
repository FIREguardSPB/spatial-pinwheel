# FIX84 — coordinator/runtime rewrite based on HAR + worker log audit

## What was actually wrong

The failure was not just a frontend rendering problem.

The main root causes were:

1. `ui/settings` and `ui/dashboard` were implemented as `async` FastAPI handlers, but they executed a large amount of synchronous DB / CPU work inline.
2. `ui/settings` bootstrap still pulled expensive runtime sections (`auto_policy`, `pipeline_counters`, `ml_runtime`) and made the page heavy.
3. `/settings/runtime-overview` still built global expensive payloads even when the frontend only needed per-instrument `effective_plan/profile/diagnostics/event_regime`.
4. UI settings page still kept a parent-level `runtime-overview` query alive, which caused unnecessary cancelled requests while navigating tabs.
5. Runtime token resolution still opened nested DB sessions via `get_token()` from UI read-paths.
6. Paper mode and broker provider were semantically mixed: UI could still look like `tbank` transport was the effective runtime even in `auto_paper`.

## What was changed

### Backend

- Added `backend/core/services/runtime_tokens.py`
  - bulk token resolution from the current DB session
  - removed nested `get_token()` style lookups from hot UI read-paths

- Refactored `backend/apps/api/status.py`
  - added `build_bot_status_sync()`
  - added effective runtime transport resolution (`paper` vs `tbank`) based on **trade_mode + token presence + LIVE_TRADING_ENABLED**
  - UI status now reports the **effective** provider instead of blindly echoing env config

- Refactored `backend/apps/api/routers/bot.py`
  - `auto_live` validation now uses DB/runtime token state instead of env-only shortcut

- Added `backend/core/services/ui_runtime.py`
  - lightweight runtime builders for:
    - AI runtime summary
    - Telegram runtime summary
    - auto policy summary
    - ML runtime summary
    - pipeline counters summary
    - watchlist
  - removes the heavy settings bootstrap dependency on full business-metrics scans

- Rewrote `backend/apps/api/routers/ui.py`
  - coordinator endpoints now run sync DB/CPU sections via `run_in_threadpool`
  - `ui/settings`, `ui/dashboard`, `ui/signals`, `ui/activity`, `ui/trades`, `ui/account` now avoid blocking the main async loop with large sync sections

- Refactored `backend/apps/api/routers/account.py`
  - introduced sync snapshot builders:
    - `build_account_summary_sync`
    - `build_account_history_sync`
    - `build_daily_stats_sync`
  - UI account snapshot no longer tries to do live broker portfolio refresh inline

- Refactored `backend/apps/api/routers/settings.py`
  - `/settings/runtime-overview` now has `include_globals=false` by default
  - per-instrument overview no longer computes heavy global runtime sections unless explicitly requested

### Frontend

- Refactored `src/features/core/uiQueries.ts`
  - `useUiDashboard()` and `useUiSettings()` no longer depend on selected instrument
  - changing the selected paper no longer reboots the whole page coordinator query
  - `useRuntimeOverview()` now explicitly requests `include_globals=false`

- Refactored `src/features/settings/SettingsPage.tsx`
  - moved `runtime-overview` query into the `Бумаги` tab component only
  - tabs `Обзор / Риск / AI / Telegram / Автоматика` no longer trigger heavy per-instrument overview fetches
  - fixed state rendering logic so card badges match the actual payload state

- Refactored `src/services/api.ts`
  - cancelled / aborted requests are no longer treated as full API failures for banner/toast logic

- Refactored `src/features/dashboard/ChartContainer.tsx`
  - avoids pointless candle requests when no instrument is selected yet

## Expected effect

- `GET /api/v1/ui/settings` should stop hanging on navigation
- `GET /api/v1/ui/dashboard` should stop blocking the API loop together with other requests
- `runtime-overview` should only load when the `Бумаги` tab is actually open
- tab navigation should stop producing meaningless `loaded` + `не загрузилось` contradictions
- in `auto_paper`, runtime status should no longer look like effective broker transport is forced to live T-Bank

## Verification performed

- `python3 -m compileall -q backend src`
- `npm exec tsc --noEmit`

Both passed before packaging.
