# E2E Smoke Test Plan (Manual)

**Version:** 1.0.0
**Date:** 2024-05
**Scope:** Critical User Journeys (CUJ) for Pre-Release Verification.

---

## Scenario 1: Dashboard & Data Continuity
**Goal**: Verify chart rendering and data loading.

1.  **Open Dashboard**: Navigate to \`/\`.
    *   *Check*: Page loads without white screen.
    *   *Check*: "MOCK MODE" banner is visible (if env set) or System status is Green.
2.  **Chart Check**:
    *   *Check*: Candlesticks are visible.
    *   *Check*: Price scale on the right, Time scale at the bottom.
3.  **Instrument Switch**:
    *   Select `BTCUSDT` then switch to `ETHUSDT` via selector.
    *   *Check*: Chart clears and reloads data for new instrument. Connection status remains stable.

---

## Scenario 2: Signal Management
**Goal**: Verify signal processing flow.

1.  **Open Signals**: Navigate to \`/signals\`.
    *   *Check*: Table is populated with rows (Mock or Real).
2.  **Approve Action**:
    *   Find a signal with status `PENDING` (Clock icon).
    *   Click the **Green Check** (Approve) button.
    *   *Check*: Row immediately updates to `APPROVED` (Green badge).
    *   *Check*: If in Mock Mode, console logs action. If Real, Toast "Signal Approved" appears.

---

## Scenario 3: Configuration & Safety
**Goal**: Verify critical settings and sensitive data handling.

1.  **Change Preset**:
    *   Go to \`/settings\`.
    *   Click "Aggressive" preset.
    *   *Check*: Risk values update (e.g., Risk Per Trade -> 2%).
2.  **Save Config**:
    *   Click **Save Configuration**.
    *   *Check*: Success Toast "Settings updated" appears.
3.  **Token Privacy**:
    *   Type in "Auth Token" field.
    *   *Check*: Text is masked (`••••`).
    *   Click "Set".
    *   *Check*: Token is saved to store (can verify via DevTools or by network request hitting with Bearer header).
