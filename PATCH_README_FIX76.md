# FIX76

## What changed
- Settings page no longer hangs forever when `/settings` fails or stalls; it now falls back to local defaults and renders degraded mode.
- Core frontend queries now degrade safely instead of throwing hard UI failures:
  - `/settings`
  - `/state`
  - `/watchlist`
  - `/signals`
  - `/account/summary`
  - `/account/history`
  - `/account/daily-stats`
  - `/metrics`
  - `/account/tbank/accounts`
  - `/tbank/stats`
- Reduced false global backend-dead UX by treating more routes as soft/degraded.
- Instrument selector, dashboard widgets, manual order panel, account page and activity page now keep rendering with fallback/empty data.

## Main symptom fixed
The Settings page previously stayed on skeleton forever because `formState` was never initialized after `/settings` error. That logic is fixed.
