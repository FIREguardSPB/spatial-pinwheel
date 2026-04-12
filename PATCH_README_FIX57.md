# FIX57 — Multi-timeframe execution engine

## Что добавлено
- Полноценный `timeframe_engine` для resample 1m -> 5m/15m/30m/1h/4h/1d.
- `AdaptiveSymbolPlan` теперь считает:
  - `analysis_timeframe`
  - `execution_timeframe`
  - `confirmation_timeframe`
  - `timeframe_source`
- `SignalProcessor` больше не анализирует только текущую 1m-историю:
  - стратегия прогоняется по адаптивному рабочему таймфрейму;
  - если он не дал сигнал, идёт fallback-поиск по наборам TF;
  - сигнал с HTF привязывается к execution-цене 1m;
  - snapshot для DecisionEngine строится на analysis TF + HTF trend.
- Rescue-pass теперь умеет реально переключиться на suggested timeframe и пересобрать сигнал на другом TF, а не только менять SL/TP.
- В signals API/UI добавлены поля прозрачности:
  - `analysis_timeframe`
  - `execution_timeframe`
  - `confirmation_timeframe`
  - `timeframe_selection_reason`
- В dashboard/settings inspector отображается `TF: analysis -> execution`.

## Что важно
- Это backend-эволюция и прозрачность effective-plan; фронт не перепроектировался полностью.
- Полный runtime с реальным брокером/worker здесь не поднимался — проверена синтаксическая целостность backend через `compileall`.
