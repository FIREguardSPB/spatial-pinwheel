# FIX83 — settings runtime cards consistency

## What was fixed

- Fixed false "загружено" badges on settings runtime cards when the actual text was "не загрузилось".
- Stopped Overview/Risk/AI/Telegram/Automation tabs from depending on the slow per-instrument `/settings/runtime-overview` call.
- Added fast runtime payloads directly into `/api/v1/ui/settings` bootstrap:
  - `ai_runtime`
  - `telegram`
  - `auto_policy`
  - `ml_runtime`
  - `pipeline_counters`
- Kept detailed per-instrument runtime overview only for the `Бумаги` tab.
- Clarified source notes text so the UI explicitly says detailed runtime overview loads only on the `Бумаги` tab.

## Why

The UI previously mixed two different notions:
- JSON content text (`не загрузилось`)
- badge state (`загружено`)

This happened because badge logic only recognized `не загружено`, while the actual text returned was `не загрузилось`.

In addition, most settings tabs were unnecessarily waiting on the slow `runtime-overview` query even though they only needed global runtime snapshots.
