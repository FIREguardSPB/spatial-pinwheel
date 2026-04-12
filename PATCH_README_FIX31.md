# FIX31 — critical backlog closure (21.03.2026)

## Closed in this phase

### 1) EconomicFilter now respects runtime settings end-to-end
- Added fully runtime-controlled fields for Economic Filter:
  - `min_tick_floor_rub`
  - `commission_dominance_warn_ratio`
  - `volatility_sl_floor_multiplier`
  - `sl_cost_floor_multiplier`
- Added DB model + schema + settings repository + API wiring for these fields.
- Added Alembic migration: `20260321_01_economic_filter_runtime_controls.py`.
- Removed hardcoded SL floors from the filter logic and made them configurable.
- Fixed `value or default` fallbacks in Decision Engine / settings serialization so valid `0` and `0.0` values are no longer silently replaced by defaults.
- Added debug metrics showing the exact effective Economic Filter config used for each signal.

### 2) Executed paper fills now appear in `/api/v1/trades`
- `GET /api/v1/trades` was previously built only from closed positions, so newly executed paper trades were invisible until the position closed.
- Reworked `/api/v1/trades` into a unified journal:
  - closed round-trip trades from positions/logs;
  - open execution fills from the raw `trades` table.
- Result: an executed signal becomes visible in the trades journal immediately.
- Trade stats/export remain based on closed round-trips only.

### 3) Trading schedule display is now explicitly MSK in UI
- Added explicit schedule timezone field to backend snapshot (`Europe/Moscow`).
- Settings page now renders session times as `HH:MM MSK` and next open as full date/time in MSK.
- This removes ambiguity where schedule values looked like UTC hours.

### 4) Preset `Пулемётчик` corrected + active preset UI state
- Reworked `Пулемётчик` into an actually aggressive preset:
  - `decision_threshold: 38`
  - `signal_reentry_cooldown_sec: 2`
  - `max_concurrent_positions: 14`
  - `risk_per_trade_pct: 0.6`
  - `min_sl_distance_pct: 0.05`
- Added visual active-state detection for presets in Settings UI.
- Active preset is now highlighted on both the button and preset card.
- Added active preset badge in the settings header.

## Validation performed
- `python3 -m compileall -q backend` — OK.
- TypeScript syntax check via `typescript.transpileModule` for modified UI files — OK.

## Not fully validated in container
- Full frontend typecheck/build is still limited by missing local `vite/client` type package in the container environment.
- Runtime DB migration execution and end-to-end broker/paper flow were not executed inside this container.
