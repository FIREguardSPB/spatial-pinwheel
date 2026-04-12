# FIX63

## Какая часть плана выполнена

- Часть 6 плана закрыта в FIX63.
- Фокус: portfolio optimizer 2.0 + lifecycle excursion tracking + live trader checklist.

## Что добавлено

- Covariance/risk-budget/regime-aware portfolio optimizer overlay.
- Optimizer now influences signal sizing and capital reallocation.
- New runtime settings for portfolio optimizer.
- Lifecycle MAE/MFE tracking for every open position.
- New `position_excursions` table and trace exposure in `/api/v1/trace/{trace_id}`.
- Exit diagnostics now include MFE/MAE and realized-to-MFE capture.
- Business metrics and paper audit now expose optimizer/excursion metrics.
- UI controls for optimizer and UI metrics for optimizer / MFE capture.
