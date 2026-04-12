- FIX25: intraday AI prompt refactor — scalp-first prompt, dynamic macro/geo relevance, prompt hashing, ai_min_confidence=55.
# Changelog

## [v1.1.0] - 2026-01-03
### Added
- **T-Bank Integration**: Replaced `tinkoff-investments` with direct `grpcio` implementation.
- **Sandbox Support**: Switch between Sandbox and Prod via `TBANK_SANDBOX` env variable.
- **Docker Profiles**: Added `mock` and `tbank_sandbox` profiles for easy start.

### Changed
- **Decimal Precision**: Strict `Decimal` arithmetic used throughout the pipeline.
- **Throttling**: SSE `kline` events throttled to 1/sec per instrument.
- **Versioning**: Project bumped to v1.1.0.
## FIX24 — 2026-03-13
- Removed settings flicker with skeleton-based loading.
- Added structured AI/DE merge logging and richer signal/trade decision logs.
- Added base multi-strategy support via comma-separated strategy_name and CompositeStrategy.


## FIX27 — 2026-03-18
- Deterministic active settings selection and new runtime risk controls.
- Broker trading schedule sync/cache with UI preview and manual refresh.
- Safer AI defaults (advisory + promote_only), cost-aware paper close chain, expanded settings UI.
