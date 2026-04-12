# AUDIT FIX73 — Trainable ML core

## Что изменилось по сути

Ранее в проекте присутствовали:
- LLM inference через внешние провайдеры
- логирование AI-решений
- экспорт JSONL для потенциального future fine-tuning
- оптимизация параметров и recalibration

Но отсутствовал настоящий обучаемый ML-контур.

В FIX73 это исправлено:
- есть обучаемый supervised ML layer
- есть model registry
- есть scheduled retrain
- есть runtime inference overlay
- есть влияние модели на live/paper signal pipeline

## Что теперь реально можно утверждать

Можно утверждать:
- в проекте есть trainable ML subsystem
- система накапливает опыт и учится на собственных сигналах/сделках
- обученные модели реально переиспользуются в execution loop

Нельзя пока утверждать:
- что LLM fine-tuning с обновлением весов уже реализован end-to-end
- что ML уже статистически доказал устойчивое превосходство на длинном auto_paper прогоне
- что текущий supervised feature set уже оптимален

## Остаточные риски

1. Модель пока табличная (logistic regression), а не sequence/deep model.
2. Качество обучения зависит от качества разметки signal→fill→closed outcome.
3. Нужен длинный сравнительный прогон до/после FIX73.
4. Нужен контроль false veto / false boost.

## Следующий правильный шаг

- strategy-level feature expansion
- meta-labeling for stop/skip/hold
- separate fill model calibration
- online evaluation dashboards for ML drift / calibration / precision-recall
- затем уже optional LLM fine-tuning pipeline как отдельный проектный слой
