# FIX40

## Что исправлено
- Исправлена интерпретация broker schedule для `MOEX_PLUS_WEEKEND`.
- Для weekend-сессии больше не используются аномальные ранние premarket/internal-start значения из ответа брокера.
- В UI/статусе weekend-сессия теперь нормализуется к реальному окну weekend trading: старт weekend auction/session и окончание основной weekend-сессии.

## Симптом
На странице настроек weekend-расписание показывало `02:00 MSK -> 23:50 MSK`, что неверно для MOEX additional weekend session.

## Корень проблемы
Код объединял все broker-времена в одно "all"-окно и для `MOEX_PLUS_WEEKEND` захватывал внутренние/вспомогательные поля времени, которые не должны отображаться как начало торговой сессии.

## Результат
- `current_session_start` для weekend now не уходит в `02:00 MSK`.
- `current_session_end` для weekend now не уходит в `23:50 MSK`.
- `is_open` и `next_open` рассчитываются на нормализованных weekend bounds.
