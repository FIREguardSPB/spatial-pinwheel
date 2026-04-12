FIX55 — прозрачность сигналов

Что добавлено:
- На странице сигналов у каждой строки теперь видно:
  - strategy source: global / symbol / regime
  - ai influence: advisory only / affected decision / off
  - reject reason priority: economics / risk / ai / strategy mismatch / other
- Backend /api/v1/signals теперь возвращает:
  - strategy_name
  - strategy_source
  - ai_influence
  - reject_reason_priority
- Adaptive plan теперь сохраняет strategy_source в meta.

Зачем:
- убрать путаницу, когда глобально включена одна стратегия, а в сигналах видны разные strategy_name;
- показать, где именно выбранная стратегия взялась: из глобального whitelist, из профиля бумаги или из regime-layer;
- показать, реально ли ИИ только консультировал или действительно изменил итог;
- показать приоритетную причину reject/skip без чтения логов.
