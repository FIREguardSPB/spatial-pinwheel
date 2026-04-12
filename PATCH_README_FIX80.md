# FIX80 — runtime clarity / schedule sanity / signals transparency

## Что исправлено

### 1. Кнопки запуска/остановки
- кнопки теперь отражают текущее состояние `is_running`
- у запущенного бота кнопка запуска показывает `Запущен`
- у остановленного бота кнопка остановки показывает `Остановлен`
- pending-состояния подписаны как `Запуск…` / `Остановка…`

### 2. Расписание биржи
- static fallback больше не показывает `broker schedule unavailable` как ошибку
- для fallback выводится `warning`, а не red-error
- добавлен sanity-guard: если broker schedule внезапно уводит `next_open` слишком далеко (например на понедельник вместо пятницы), snapshot корректируется static-логикой MOEX

### 3. Сигналы
- SignalsPage теперь показывает:
  - кто принял final decision
  - как повлиял AI
  - как отработал ML overlay
  - блокировал ли сигнал защитный контур / governor
- добавлены summary-виджеты по TAKE / AI-affected / guardrail-blocked

### 4. Терминология protective layer
- UI в настройках больше не подаёт `auto freeze` как нечто непонятное
- теперь это объясняется как защитный контур / блокировка новых входов / режим деградации

## Проверки
- `python3 -m compileall -q backend`
- `PYTHONPATH=backend python3 -m unittest backend.tests.test_trading_schedule_static -v`
- `npx tsc --noEmit`
