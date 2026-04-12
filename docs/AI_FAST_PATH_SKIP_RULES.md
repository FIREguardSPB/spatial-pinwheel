# AI Fast-Path / Skip-AI Rules

## Цель
Сократить latency и стоимость AI-вызовов в intraday pipeline, не жертвуя качеством решений.

Ключевой принцип:
**AI не должен вызываться там, где deterministic layers уже доказали, что сделка несостоятельна.**

## Где AI точно не нужен
AI пропускается, если до AI-слоя уже выполнено хотя бы одно из условий:

1. **Decision Engine hard blockers**
   - есть хотя бы одна причина `Severity.BLOCK`
   - типичные примеры:
     - `SESSION_CLOSED`
     - `NO_MARKET_DATA`
     - `ECONOMIC_INVALID`
     - `ECONOMIC_LOW_PRICE`
     - `ECONOMIC_MICRO_LEVELS`
     - `ECONOMIC_PROFIT_TOO_SMALL`
     - `ECONOMIC_MIN_TRADE_VALUE`
     - `ECONOMIC_COMMISSION_DOMINANCE`
     - risk-limit/cooldown/max-positions hard blocks

2. **Performance Governor suppression**
   - `performance_governor.suppressed == true`
   - если governor уже подавил сигнал, AI не должен тратиться на повторную оценку

3. **Signal Freshness hard block**
   - `signal_freshness.blocked == true`
   - если сигнал уже считается устаревшим для исполнения, AI не должен его реанимировать

4. **Final pre-AI decision уже `REJECT`**
   - если после DE + event regime + freshness финальное pre-AI решение уже `REJECT`, AI вызов не нужен

## Где AI всё ещё нужен
AI **не пропускается** для soft/gray-zone кейсов:

- soft `SKIP` без hard blockers
- near-threshold setups
- неоднозначный context / regime conflict
- случаи, где AI может:
  - понизить уверенность,
  - подтвердить skip,
  - в `override/promote_only` режиме поднять выживший сигнал до `TAKE`

То есть:
**hard reject / hard suppression -> без AI**
**soft ambiguity / survivor setup -> AI участвует**

## Реализация в коде
Введён модуль:
- `backend/apps/worker/ai/fast_path.py`

Точка применения:
- `backend/apps/worker/processor.py`

Логика:
- до вызова `AIProviderRouter.analyze(...)` оценивается deterministic pre-AI state
- если срабатывает fast-path:
  - AI не вызывается
  - сохраняется `ai_fast_path` в `signal.meta`
  - пишется `decision_log` типа `ai_fast_path_skip`
  - `final_decision` остаётся deterministic

## Для UI / forensics
В `signal.meta.ai_fast_path` сохраняется:
- `applied`
- `final_decision`
- `pre_ai_decision`
- `reason`
- `triggers`
- `blocker_codes`

Это нужно для:
- пост-мортема,
- UI-пояснений,
- оценки, сколько AI-вызовов реально сэкономили.

## Ожидаемый эффект
1. Меньше latency на заведомо мёртвых сигналах
2. Меньше стоимости AI-провайдеров
3. Более предсказуемый pipeline
4. Чище разделение:
   - deterministic hard filters
   - AI only for survivors

## Не делать
- Не давать AI права переопределять hard economics / hard risk blocks
- Не расширять fast-path на soft `SKIP` без анализа причин
- Не использовать fast-path как замену ML/DE; это только gating layer перед AI
