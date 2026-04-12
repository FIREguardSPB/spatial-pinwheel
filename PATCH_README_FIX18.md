Spatial Pinwheel — Fix18 stability/runtime pass

Key changes in this patch:
- Block manual approve for non-TAKE signals on backend and hide approve UI for REJECT/SKIP.
- Worker now uses runtime AI settings from DB/UI (primary/fallback providers, Ollama URL) instead of env-only defaults.
- Non-TAKE signals are finalized as rejected instead of lingering in pending_review.
- T-Bank market-data polling now skips unavailable instruments (e.g. TQBR:AGRO) without killing the loop.
- Bot API router is connected in FastAPI app.
- Chart history polling now refreshes store on every refetch, reducing “frozen chart until page switch”.
- Improved API/SSE user notifications and connection status visibility.
- Added LOG_DIR support and stronger backend logging paths.
- Clean packaging: no __pycache__, *.pyc, node_modules, dist, or build artifacts.

Validation performed in sandbox:
- backend: python3 -m compileall -q .  ✅
- frontend full npm build was not executed here because project dependencies are not installed in the sandbox.
