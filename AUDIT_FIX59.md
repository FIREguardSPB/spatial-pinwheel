# Deep audit after FIX59

## Что уже закрыто по плану
- **Часть 1 плана**: архитектурная целостность движка — закрыта в FIX58.
- **Часть 2 плана**: trade-management realism — частично закрыта в FIX59.

## Что стало лучше
1. **Capital reallocation стал честнее**.
   Раньше partial close для высвобождения капитала мог считаться по `avg_price`, что делало PnL и reallocation decision нереалистичными. Теперь используется mark-price/derived mark.
2. **Adaptive exit перестал быть "дробилкой"**.
   Появились cooldown и лимит числа частичных фиксаций, значит позиция меньше рискует быть разрезанной из-за шумового повторения одного и того же условия.
3. **Метрики стали ближе к реальной оценке трейдера**.
   Помимо WR/PF теперь есть expectancy, max drawdown, execution errors, breakdown причин выхода.

## Что всё ещё не даёт права честно назвать систему "не хуже опытного трейдера"
- Нет доказанного walk-forward результата по периодам и режимам рынка.
- Нет подтверждения, что текущий decision engine стабильно даёт положительную expectancy после комиссий/проскальзывания.
- Нет полноценного portfolio-level allocator с приоритизацией по regime basket / sector correlation / rolling edge decay.
- Нет продвинутого exit-layer уровня ATR-trail + volatility contraction + liquidity-aware unwind.

## Следующий наиболее ценный слой после FIX59
1. walk-forward / rolling evaluation endpoint и отчёт по стратегиям;
2. edge decay / signal freshness penalty в execution path;
3. portfolio-level allocator по basket/regime, а не только через weak-position partial close;
4. richer exit diagnostics на каждую сделку.
