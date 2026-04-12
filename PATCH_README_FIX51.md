# FIX51 — прозрачность runtime-параметров, adaptive plan inspector, Telegram live-test

## Что добавлено

- `GET /api/v1/settings/runtime-overview?instrument_id=...`
  - показывает иерархию настроек: global guardrails / global defaults / adaptive runtime
  - возвращает `symbol_profile`, `effective_plan`, `diagnostics`, `event_regime`, `worker`, `ai_runtime`, `telegram`
- `POST /api/v1/settings/telegram/test-send`
  - отправляет реальное тестовое сообщение в Telegram через текущую конфигурацию
- Settings UI:
  - новый блок «Прозрачность системы»
  - новый блок «Инспектор адаптивного плана по бумаге»
  - явное разделение: что можно менять вручную, что лучше не трогать, что бот считает сам
  - Telegram runtime status + реальная тестовая отправка
- Dashboard:
  - tooltip на выбранной бумаге в selector показывает текущий effective plan по бумаге

## Зачем

Главная цель — убрать путаницу между:
- глобальными настройками риска,
- базовыми настройками движка,
- реальными активными per-symbol параметрами.

Теперь без просмотра логов видно:
- участвует ли AI,
- есть ли живой adaptive plan по бумаге,
- что реально выставлено по threshold / hold / re-entry / strategy,
- готов ли Telegram канал уведомлений.
