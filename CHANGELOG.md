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
