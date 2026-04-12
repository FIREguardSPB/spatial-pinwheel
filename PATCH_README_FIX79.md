# FIX79 — settings entities + chart + schedule sanity

## What changed

### Backend
- Reworked static/broker schedule next-open logic in `backend/core/services/trading_schedule.py`
- Added explicit MOEX 2026 trading-day fallback rules for static schedule sanity
- Fixed `next_open` so an already-open session points to the next trading open, not to the same-day session start
- Added/updated tests in `backend/tests/test_trading_schedule_static.py`

### Frontend
- Rebuilt `SettingsPage` into entity-based sections:
  - Overview
  - Trading
  - Risk
  - AI
  - Telegram
  - Automation
  - Instruments
- Restored chart on Dashboard
- Added equity curve on Dashboard
- Added instrument selector + timeframe selector on Dashboard
- Restored richer runtime visibility through dedicated settings sections
- Added Telegram test-send action in Settings
- Added runtime overview panels for effective plan / symbol profile / diagnostics / event regime

## Validation
- `python3 -m compileall -q backend`
- `PYTHONPATH=backend python3 -m unittest backend.tests.test_trading_schedule_static -v`
- `npx tsc --noEmit`
