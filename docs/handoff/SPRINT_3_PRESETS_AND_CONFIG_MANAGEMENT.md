# Sprint 3 — Presets and Config Management

## Why this sprint exists
After stabilizing the ML overlay and attribution layer, we need a **safe, fast way to experiment with different trading configurations**. Currently, changing settings (risk_profile, thresholds, AI mode, ML parameters) requires manual edits in the UI, which is error‑prone and slow when comparing multiple calibrated variants.

Presets allow us to:
- save the current configuration as a named snapshot (e.g., “Sniper”, “Machine‑gunner”, “Balanced”, “Experiment 1”),
- switch between presets with one click,
- avoid accidental misconfiguration,
- speed up the search for optimal parameters.

## Sprint objective
Implement a **preset management system** that lets users save, load, list, and delete configuration snapshots.

## Scope

### A. Database & models
1. Create a new table `settings_presets` with columns:
   - `id` (text primary key, e.g., `preset_sniper_20260413`),
   - `name` (human‑readable label),
   - `description` (optional),
   - `settings_json` (JSONB with the full snapshot of `settings` columns),
   - `created_at` (timestamp),
   - `updated_at` (timestamp),
   - `is_system` (boolean, defaults to false; system presets are read‑only).
2. Add a SQLAlchemy model `SettingsPreset` and a repository with CRUD methods.

### B. Backend API
1. New router `/api/v1/settings/presets` with endpoints:
   - `GET /` – list all presets (system + user),
   - `POST /` – create a new preset from current settings (requires `name`),
   - `GET /{id}` – retrieve a single preset,
   - `PUT /{id}` – update a preset (only user‑created),
   - `DELETE /{id}` – delete a preset (only user‑created),
   - `POST /{id}/apply` – apply the preset to the live settings (merges `settings_json` into the `settings` table).
2. The `apply` endpoint must:
   - validate that the preset JSON matches the current `settings` schema,
   - preserve runtime‑only fields (e.g., `runtime_tokens`, `sandbox_account_id`) unless explicitly included,
   - log the application as a decision‑log event.

### C. Frontend UI
1. Add a **Presets panel** inside the existing `SettingsPage`.
2. Panel elements:
   - dropdown/list of available presets with name, description, creation time,
   - “Save current as…” button (opens a modal with name/description fields),
   - “Apply” button (with confirmation dialog),
   - “Delete” button (only for user‑created presets, with confirmation).
3. Show a brief diff summary when applying (e.g., “This will change risk_profile from ‘aggressive’ to ‘balanced’, ai_mode from ‘override’ to ‘advisor’…”).
4. Keep the UI lightweight; reuse existing SettingsPage styling.

### D. Initial system presets
Create three read‑only system presets as starting points:
- **Sniper** – tight filters, high RR threshold, low daily trade count (conservative),
- **Machine‑gunner** – relaxed filters, moderate RR, higher trade count (aggressive),
- **Balanced** – default production‑like settings (current baseline).

System presets are stored as migration seeds and cannot be deleted or overwritten.

### E. Tests
1. Unit tests for the `SettingsPreset` repository (CRUD, apply logic).
2. Integration tests for the new API endpoints.
3. Frontend unit tests for the new PresetsPanel component.
4. Ensure that applying a preset does not break existing settings validation.

## Out of scope
- Automatic preset creation based on trading history.
- Preset versioning or branching.
- Syncing presets with external storage (Git, cloud).
- Preset‑specific backtesting (can be a future sprint).
- Editing system presets (they are read‑only references).

## Deliverables
1. Database migration for `settings_presets` table.
2. Backend API fully implemented and tested.
3. Frontend Presets panel integrated into SettingsPage.
4. Three system presets seeded.
5. Short user‑guide note in `docs/runbook_presets.md`.

## Acceptance criteria
Sprint is accepted only if all of the following are true:
- User can save current settings as a named preset via UI.
- User can see the list of presets (system + user) in the UI.
- User can apply any preset; after application, the live settings reflect the preset’s values.
- User‑created presets can be deleted; system presets cannot.
- All backend tests pass (including new preset‑related tests).
- Frontend preset panel does not increase page‑load time significantly.
- Applying a preset does not erase runtime‑only fields (tokens, sandbox accounts).
- The preset’s JSON snapshot includes all relevant trading settings (risk_profile, trade_mode, ai_mode, ml_enabled, thresholds, filters, etc.) but excludes secrets (passwords, API keys).

## Technical notes
### Schema inclusion
The `settings_json` column should contain a subset of the `settings` table that is safe to snapshot. Exclude:
- `runtime_tokens`, `sandbox_account_id`, `tbank_access_token`, `telegram_bot_token`, any credentials.
- `last_modified`, `created_at` (these are metadata, not configuration).

Include:
- `risk_profile`, `risk_per_trade_pct`, `daily_loss_limit_pct`, `max_concurrent_positions`, `max_trades_per_day`,
- `trade_mode`, `ai_mode`, `ai_min_confidence`, `ai_provider`,
- `ml_enabled`, `ml_take_probability_threshold`, `ml_fill_probability_threshold`, `ml_allow_take_veto`,
- `time_stop_bars`, `atr_stop_soft_min`, `atr_stop_soft_max`, `rr_min`, `rr_target`,
- `economic_filter_enabled`, `volume_filter_enabled`, `correlation_filter_enabled`,
- `trading_session`, `watchlist` (array of instrument IDs),
- any other trading‑decision parameters.

### Merge strategy
When applying a preset, do a **shallow merge**: keys present in the preset replace the live values; keys absent in the preset are left unchanged. This allows partial updates (e.g., only change risk_profile) if needed.

### Idempotency
Saving the same preset name twice should either update the existing preset (if user‑owned) or fail with a conflict (if system). Decide on PUT‑vs‑POST semantics early.

## Key files to change
- `backend/core/storage/models.py` – add `SettingsPreset` model.
- `backend/core/storage/repos/settings.py` – extend with preset CRUD methods.
- `backend/apps/api/routers/settings.py` – add preset endpoints (or create new router `presets.py`).
- `backend/core/storage/migrations/versions/20260413_01_settings_presets.py` – migration.
- `src/features/settings/SettingsPage.tsx` – add PresetsPanel.
- `src/features/settings/components/PresetsPanel.tsx` – new component.
- `src/services/api.ts` – add preset API calls.
- `backend/tests/test_settings_presets.py` – new test suite.
- `docs/runbook_presets.md` – short usage guide.

## References
- Existing settings schema: `backend/core/storage/models.py` (class `Settings`).
- Current UI for settings: `src/features/settings/SettingsPage.tsx`.
- API pattern: `backend/apps/api/routers/settings.py`.

## Success metrics
- Time to switch between two calibrated configurations reduced from minutes to seconds.
- No accidental misconfiguration because of manual edits.
- At least three meaningful system presets available on day one.

---

*This document is the developer’s task for Sprint 3. Any questions about scope or implementation should be discussed before coding begins.*