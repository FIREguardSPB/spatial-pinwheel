# FIX20 — AI context / sector-aware fundamentals / richer news context

## Основание
Доработка по двум новым отчётам заказчика:
- AI даёт слишком поверхностное обоснование при высоком geopolitical risk и дорогой нефти.
- Нужно усилить передачу контекста, анализ нефтяных компаний, источники и rule-based sentiment.

## Что изменено

### Backend / AI context
- `backend/apps/worker/ai/prompts.py`
  - промпт переработан в полноценный геополитико-экономический блок;
  - добавлены counts по темам (война/нефть/санкции/ставки);
  - добавлены причинно-следственные связи;
  - добавлен отдельный фундаментальный блок для нефтегазовых тикеров.

- `backend/apps/worker/ai/internet/sentiment.py`
  - rule-based sentiment усилен контекстными паттернами;
  - война / конфликт / санкции теперь дают выраженный негатив;
  - easing/lifting sanctions даёт позитивный сдвиг вместо нейтрализации в ноль.

- `backend/apps/worker/ai/internet/collector.py`
  - добавлены `topic_counts` и `narrative_summary` в InternetContext;
  - geopolitical risk теперь считается на основе topic counts + sentiment + macro;
  - строится narrative summary для prompt.

- `backend/apps/worker/ai/internet/news.py`
  - RSS/Atom parsing переписан через `xml.etree.ElementTree`;
  - добавлены дополнительные источники:
    - Коммерсант
    - Ведомости
    - OilPrice
    - Financial Times
    - Wall Street Journal
    - Nikkei Asia
    - SCMP
  - улучшен dedupe по title.

### Tests
- Добавлен `backend/tests/test_ai_context_improvements.py`
  - war headline => negative
  - sanctions easing headline => positive bias
  - prompt содержит topic counts + oil company context

## Что проверено
- `python3 -m compileall -q backend` — OK
- targeted pytest for new AI context logic — OK

## Что не подтверждается
- Полный runtime-прогон у заказчика не выполнялся в этой среде.
- Полный npm build фронта не прогонялся здесь.
