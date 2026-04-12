# PATCH_README_FIX30

## Что добавлено в этой фазе

### Backend stability
- AI router теперь не падает на исключении отдельного провайдера и продолжает fallback-цепочку.
- В auto_live execution используется runtime-разрешение `TBANK_TOKEN` / `TBANK_ACCOUNT_ID` из DB/env, а не только import-time config.
- Поток market data теперь пропускает неразрешимые инструменты вместо падения всего стрима.
- Ключевые API endpoints (`/state`, `/state/orders`, `/state/trades`, `/state/positions`, `/account/summary`, `/account/history`, `/account/daily-stats`, `/candles/{ticker}`) переведены на safe fallback pattern с логированием ошибок.

### Diagnostics / observability
- Добавлен endpoint `GET /api/v1/ai/runtime`:
  - active AI mode,
  - primary/fallback provider chain,
  - token/provider availability,
  - last AI decision snapshot.
- Ошибки backend/API теперь лучше surfaced в UI с request-id/path/status.

### Frontend resilience / UX
- Добавлен глобальный `RuntimeStatusBanner` в layout.
- Улучшен `ConnectionStatus`: теперь различает degraded backend и disconnected API.
- Axios interceptor пишет runtime-error в store и ограничивает повторяющиеся toast-уведомления (throttle).
- После восстановления SSE-stream автоматически инвалидируются ключевые query cache entries.
- График принудительно refetch-ит историю при возвращении вкладки/фокуса.
- В Settings добавлен блок `AI runtime diagnostics`, чтобы видеть реальную provider chain и последний AI-вызов.

## Что я реально проверил
- `python3 -m compileall -q backend` — OK.
- `pytest backend/tests/test_audit_fixes.py` по-прежнему не проходит полностью не из-за патча, а из-за отсутствующего `sqlalchemy` в окружении контейнера.
- TypeScript / frontend production build в контейнере честно не подтверждён: локально отсутствуют установленные npm type deps (`vite/client` и др. через node_modules).

## Что ещё остаётся вне этой фазы
- Полная portfolio-level orchestration (частичные выходы, лестницы фиксации, ребаланс риска между инструментами).
- Расширенная стратегия / execution analytics panel.
- Полный runtime smoke в пользовательском docker/desktop окружении.
