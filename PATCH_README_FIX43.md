# FIX43 — DB-backed symbol intelligence, offline trainer, online recalibration

What changed:
- moved per-symbol profiles from file-only runtime storage to DB-backed `symbol_profiles` with automatic JSON migration fallback;
- added `symbol_regime_snapshots` and `symbol_training_runs`;
- added offline training endpoints for per-symbol calibration from candle cache and recent trade history;
- added diagnostics endpoints for symbol character / best hours / blocked hours / regime stats;
- AI prompt now receives symbol profile + diagnostics as second-opinion context;
- online recalibration runs after position close to keep symbol profiles fresh;
- kept JSON export `docs/symbol_profiles.runtime.json` for transparency/debugging.

New API:
- `GET /api/v1/symbol-profiles`
- `GET /api/v1/symbol-profiles/{instrument_id}`
- `PUT /api/v1/symbol-profiles/{instrument_id}`
- `GET /api/v1/symbol-profiles/{instrument_id}/diagnostics`
- `POST /api/v1/symbol-profiles/{instrument_id}/train`
- `POST /api/v1/symbol-profiles/train`
- `GET /api/v1/symbol-profiles/training-runs`

CLI:
- `python -m scripts.train_symbol_profiles --instrument TQBR:SBER --lookback-days 180`

What this phase is:
- not the final “living trader” yet;
- it is the foundation: DB migration + offline trainer + online recalibration + richer AI context.
