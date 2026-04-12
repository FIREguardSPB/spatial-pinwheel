# FIX71 — Performance Layer

## Что добавлено

- Новый performance layer API: `GET /api/v1/validation/performance-layer`
- Post-trade attribution:
  - по стратегиям
  - по режимам рынка
  - по срезам `strategy × regime`
  - по внутридневным session-buckets
- Walk-forward слой поверх реального candle cache и watchlist:
  - OOS score
  - OOS PF
  - selected strategy per instrument
  - pass/fail per instrument
- Новый блок на фронте в `AccountPage`:
  - performance summary
  - strategy × regime attribution
  - walk-forward by instrument
  - dominant draggers / recommendations
- Forensic export теперь включает `performance_layer.json`

## Основные файлы

- `backend/core/services/performance_layer.py`
- `backend/apps/api/routers/validation.py`
- `backend/core/services/forensic_export.py`
- `backend/tests/test_performance_layer.py`
- `src/features/account/AccountPage.tsx`
- `src/types/index.ts`

## Проверка

- `python3 -m compileall -q backend`
- `PYTHONPATH=backend python3 -m unittest backend.tests.test_performance_layer backend.tests.test_trading_quality_audit backend.tests.test_live_validation backend.tests.test_backtest_walk_forward -v`
- `node + typescript.transpileModule` для `AccountPage.tsx`

## Ограничения

- Полный frontend build в контейнере не подтверждён из-за отсутствующих локальных type packages (`vite/client`, `node`) в окружении.
- Walk-forward опирается на то, что в candle cache уже накоплена достаточная история.
