# Fixes applied

## Frontend
- Fixed invalid JSX structure in `src/components/Layout.tsx`.
- Fixed broken return structure in `src/features/settings/SettingsPage.tsx`.
- Fixed keyed fragment rendering in `src/features/signals/SignalsTable.tsx`.
- Standardized frontend API base default to `/api/v1` in `api.ts`, `stream.ts`, and export URLs.
- Added theme persistence and document-level dark theme toggle.

## Backend
- Added missing settings fields for OpenAI, Claude, Telegram, and cache TTLs in `backend/core/config.py`.
- Kept `compileall` clean for backend after modifications.

## Docker / docs
- Reworked root `Dockerfile` to a multistage frontend build with an nginx healthcheck.
- Added frontend and worker healthchecks in `backend/infra/docker-compose.yml`.
- Updated `.env.example` with required AI/Telegram settings.
- Rewrote `README.md` quick start to match actual compose paths and ports.

## Verification actually performed
- `python -m compileall backend` — passed.
- Frontend dependency installation/build could not be fully completed in this container because npm packages are not available here.
- I verified the frontend code changes at source level and removed the known JSX syntax errors that were blocking compilation earlier.

## 2026-03-08 migration completion fix
- Added Alembic revision `20260308_03` to create missing tables `watchlist`, `account_snapshots`, `ai_decisions` and missing `settings` columns in an idempotent way.
- Migration is safe on environments where some columns/tables were created manually.
