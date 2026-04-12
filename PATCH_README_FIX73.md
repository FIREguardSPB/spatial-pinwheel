# FIX73 — Trainable ML core

Что сделано в этой фазе:

- В проект добавлен реальный обучаемый ML-контур, а не только инференс внешних LLM.
- Добавлены dataset builder, model registry, trainer, runtime inference overlay и scheduled retrain.
- ML теперь обучается на накопленных сигналах и закрытых сделках.
- ML-влияние встроено в боевой pipeline: threshold / veto weak TAKE / risk multiplier / execution priority / allocator priority.
- Добавлены API-эндпоинты для ML status, dataset inspection и ручного запуска обучения.
- Добавлены runtime-настройки ML в settings и базовый UI-слой на Settings/Account.

Ключевые backend-модули:

- `backend/core/ml/dataset.py`
- `backend/core/ml/trainer.py`
- `backend/core/ml/registry.py`
- `backend/core/ml/runtime.py`
- `backend/apps/api/routers/ml.py`

Интеграция:

- `backend/apps/worker/processor.py`
- `backend/apps/worker/main.py`
- `backend/core/services/forensic_export.py`
- `backend/core/services/capital_allocator.py`

Что это означает честно:

- Теперь в проекте есть реальное supervised ML-обучение на табличных признаках из собственной торговли.
- Это не является full LLM fine-tuning pipeline для весов большой языковой модели.
- Но это уже настоящий train → save model → reload → predict → affect trading loop контур.

Проверено:

- `python3 -m compileall -q backend`
- `PYTHONPATH=backend python3 -m unittest backend.tests.test_ml_dataset backend.tests.test_ml_trainer backend.tests.test_ml_runtime backend.tests.test_performance_governor backend.tests.test_timeframe_resample -v`
- `npx tsc --noEmit`
