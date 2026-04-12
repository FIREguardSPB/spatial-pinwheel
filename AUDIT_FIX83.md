# AUDIT FIX83

## Root cause

The settings page had a semantic state bug:
- card text could show `не загрузилось`
- badge still showed `загружено`

That mismatch came from string-based status inference instead of explicit state handling.

A second design problem was that multiple tabs used the heavy per-instrument runtime overview query even when they only needed global snapshots already derivable from active settings and recent runtime state.

## Remediation

- Switched runtime cards to an explicit state model: `loading | error | empty | loaded`.
- Moved fast runtime slices into the coordinator bootstrap payload for settings.
- Limited `/settings/runtime-overview` to the `Бумаги` tab, where detailed per-instrument diagnostics actually belong.

## Expected result

- No more `загружено` badge when content says `не загрузилось`.
- Overview / Risk / AI / Telegram / Automation should render from fast bootstrap data.
- Only the papers tab should rely on the heavier detailed overview request.
