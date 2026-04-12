# FIX29 — backlog continuation / platform hardening

Implemented in this patch:

1. **Persistent candle cache**
   - Added `candle_cache` model + Alembic migration `20260321_02_candle_cache.py`.
   - API `/candles/{ticker}` now serves cached history first and backfills cache from T-Bank when needed.
   - Worker bootstraps from cache before broker history fetch.
   - Worker persists newly closed candles during live loop.

2. **Consistent Moscow trading day boundary**
   - Added shared `start_of_day_ms()` helper in `core/utils/time.py`.
   - Account/day PnL and worker snapshot logic now use MSK day start instead of UTC midnight.

3. **Proxy-safe outbound HTTP**
   - Added `core/utils/http_client.py`.
   - All important `httpx.AsyncClient(...)` call sites now use `trust_env=False` through a shared helper.
   - This protects worker/API from broken `ALL_PROXY/http_proxy/https_proxy` environment values.

4. **Dynamic instrument search via T-Bank**
   - Added live `search_instruments()` support in T-Bank adapter.
   - `/api/v1/instruments/search` now merges broker results with static fallback catalog.

5. **Traceability: signal -> order -> position -> trade**
   - Signal processor now stamps each signal with `trace_id` in `signal.meta`.
   - Trades journal returns `trace_id`, `opened_order_id`, `closed_order_id`.
   - UI deals panel now shows these fields in expanded details.

6. **Richer UI details for operations**
   - Open positions panel now shows signal/order linkage, opened qty and fee estimate.
   - Active orders panel now shows `related_signal_id`.
   - Trades journal expanded block now shows trace/open-order/close-order linkage.

7. **Execution style presets in settings**
   - Added two additional operator presets:
     - `Снайпер`
     - `Пулемётчик`

## Notes / current limits

- This patch **does not yet implement** full portfolio-level capital reallocation, partial close ladders, or vector-memory / knowledge graph logic. Those need a separate larger phase.
- Backend Python syntax was checked with `python -m compileall backend`.
- Automated backend tests available in this environment are partially blocked by missing installed dependency `sqlalchemy` in the test runner environment.
- Frontend production build verification in this environment is blocked because node type packages are not installed locally (`vite/client`, `node` type defs missing without dependency install).
