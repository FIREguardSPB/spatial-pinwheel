# spatial-pinwheel fix17 — SSE/runtime/store/execution alignment

## Что исправлено
- Исправлен фронтенд-краш `clearCandles is not a function`.
- В zustand-store добавлены поля/методы runtime-источника: `clearCandles`, `setBackendSource`, `sourceLabel`, `brokerProvider`, `brokerSandbox`.
- Подключение SSE перенесено из module side-effect в lifecycle React-компонента, чтобы убрать дублирующиеся подключения при HMR/DevTools.
- В dev-режиме отключён `React.StrictMode`, чтобы снизить конфликты с remount/HMR и lightweight-charts.
- Убрана агрессивная очистка `innerHTML` у контейнера графика; cleanup сделан безопаснее.
- `vite.config.ts` переведён на `loadEnv()`, чтобы proxy реально читал `.env`; дефолтный dev proxy в корневом `.env` выставлен на `127.0.0.1:8001`.
- SSE `/api/v1/stream` переписан устойчивее: keepalive, заголовки для proxy, логирование Redis subscribe/read ошибок, безопасное закрытие pubsub.
- В health удалена ложная метка `stub_paper_fallback`; теперь health отражает реальный REST execution mode для T-Bank.
- Добавлены отсутствовавшие runtime-config поля: `LIVE_TRADING_ENABLED`, `TBANK_ORDER_TIMEOUT_SEC`, `TBANK_ORDER_POLL_INTERVAL_SEC`, `DEEPSEEK_BASE_URL`, `DEEPSEEK_MODEL`.
- SQLAlchemy/Pydantic приведены к уже используемому контракту: `bot_enabled`, `ai_primary_provider`, `ai_fallback_providers`, `ollama_url`.
- Исправлены manual order routes: теперь они корректно отправляют market/limit ордера в T-Bank через REST order endpoints и правильные сигнатуры адаптера.
- В адаптер добавлен `post_limit_order()`.
- В worker исправлен баг с `_command_listener`, который использовал runtime token/account вне области видимости.
- Исправлена цепочка Alembic migration head: `20260309_01_manual_orders_ai_flags` теперь продолжает актуальную ветку.
- Добавлено логирование unhandled asyncio/API exceptions.

## Что проверено здесь
- `python3 -m compileall -q backend` — успешно.

## Что не подтверждено здесь
- Полный runtime-запуск backend/frontend в окружении заказчика.
- Полный TypeScript build без установки npm-зависимостей в этой песочнице.

## Что проверить у заказчика первым
1. `GET /api/v1/health`
2. `GET /api/v1/settings`
3. `GET /api/v1/state/orders`
4. `GET /api/v1/state/positions`
5. `GET /api/v1/stream`
6. manual market / limit order в sandbox
7. работу фронта с открытыми DevTools
