# PATCH_README_FIX70

## Что закрыто

Эта фаза закрывает следующий боевой слой после fix69:
- allocator quality layer
- exit-capture quality layer
- signal→trade conversion audit

## Что добавлено

### Backend
- `core/services/trading_quality_audit.py`
  - единый аудит по слоям:
    - signal funnel
    - TAKE→fill conversion
    - execution errors / risk rejects
    - allocator diagnostics
    - exit-capture diagnostics
    - recent signal journeys
- новый endpoint:
  - `GET /api/v1/validation/trading-quality?days=30`
- forensic export теперь включает:
  - `trading_quality_audit.json`

### Trading logic
- усилен `core/services/capital_allocator.py`
  - anti-churn логика
  - учёт возраста позиции
  - cooldown после partial close
  - учёт partial close saturation
  - учёт decay / MFE giveback
  - richer candidate meta для forensic и аудита
- усилен `core/services/adaptive_exit.py`
  - MFE-giveback based exits / partial de-risk
- расширен `core/services/exit_diagnostics.py`
  - `exit_capture_grade`
  - `missed_tp_value_rub`
  - `missed_mfe_value_rub`
  - capture bands

### Frontend
- `AccountPage` теперь показывает отдельный блок:
  - Trading quality audit
  - allocator metrics
  - exit-capture metrics
  - top bottlenecks
  - recent signal journeys
  - strategy conversion / pnl table

## Проверка
- `python3 -m compileall -q backend` — ok
- `PYTHONPATH=backend python3 -m unittest ...` — ok
- `npx tsc --noEmit` — ok

## Что это даёт
- меньше бессмысленного churn от allocator
- лучшее удержание уже заработанной внутри сделки прибыли
- прозрачная воронка потерь signal→trade
- возможность быстро видеть, где именно система теряет боевое качество
