# AUDIT FIX76

Observed in user video:
- frontend requests to `/api/v1/*` were returning 500 for several core routes;
- Settings page stayed on skeleton indefinitely;
- dashboard/account pages produced cascading errors instead of partial degraded rendering.

Fix76 addresses the frontend failure mode directly:
- uses resilient fallbacks for critical GETs;
- avoids infinite skeleton state on Settings;
- keeps sections usable even when backend returns partial 500s.

This does not claim backend root causes are solved; it makes the UI operable under degraded backend conditions.
