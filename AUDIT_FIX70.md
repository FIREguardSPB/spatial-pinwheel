# AUDIT_FIX70

## Что улучшилось

### 1. Аллокатор стал ближе к боевому режиму
Раньше allocator в основном ранжировал edge/score-gap и концентрацию. Теперь он ещё учитывает:
- возраст позиции
- cooldown после partial close
- лимит частичных закрытий
- decay bias
- MFE giveback
- allocator score как более боевой composite

Это уменьшает риск churn, когда капитал переставляется без достаточного улучшения edge.

### 2. Exit-capture теперь не только измеряется, но и участвует в exit decision
Adaptive exit теперь умеет реагировать на ситуацию, когда сделка уже показывала сильный MFE, но текущий retained-profit быстро размывается.

Это важный шаг к поведению “не просто держать по шаблону, а защищать уже достигнутую прибыль”.

### 3. Signal→trade conversion теперь наблюдаема как воронка, а не как одна метрика
Добавлен отдельный trading quality audit, который показывает:
- сколько сигналов родилось
- сколько стало TAKE
- сколько реально было заполнено
- сколько дошло до закрытия
- где система теряет поток: risk reject / execution error / take_not_filled / pending

Это уже полезно для боевого auto_paper аудита.

## Что ещё не доказано
- что стратегия уже стабильно торгует на уровне опытного живого трейдера
- что allocator улучшает PF и expectancy на длинной выборке, а не только красиво выглядит в логике
- что новая MFE-giveback логика exit реально улучшает realized/MFE capture на длительном прогоне

## Следующий правильный шаг
После теста этого архива — переход к следующей фазе:
- строгий transaction path / one signal = one execution attempt ledger
- post-trade attribution по стратегиям и режимам рынка
- walk-forward / regime-sliced audit
- portfolio-level allocator feedback loop по фактическому realized edge
