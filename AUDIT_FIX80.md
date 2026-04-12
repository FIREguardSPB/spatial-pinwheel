# AUDIT FIX80

## Что именно было источником путаницы
1. UI не показывал operator-state для start/stop.
2. Static fallback ошибочно выглядел как поломка, хотя это был всего лишь режим без broker schedule.
3. Broker schedule мог давать нелогичный `next_open`, который UI отображал как истину.
4. Signals page почти не объясняла decision chain: DE / AI / ML / guardrails.

## Что исправлено
- operator-state для кнопок
- warning вместо fake-error для static schedule
- sanity override broker next_open
- прозрачная decision chain в Signals

## Что ещё остаётся реальным риском
- если worker реально падает после старта, это уже отдельная backend/runtime проблема, а не кнопки
- если график не показывает свечи, надо уже смотреть endpoint `/candles/{instrument}` на реальных данных и worker streaming, а не только shell UI
