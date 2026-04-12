# Spatial Pinwheel — developer handoff

## 1. What this project is
Spatial Pinwheel is an automated MOEX trading system with a React frontend, FastAPI API, async worker runtime, PostgreSQL/Redis state, T-Bank market/execution integration, deterministic risk/execution core, and an AI/ML overlay used as a second-opinion layer rather than as an uncontrolled trading brain.

The project is not a toy dashboard. It is an operational trading stack with these main goals:
- generate intraday trade signals on MOEX instruments,
- apply deterministic scoring, guardrails, and risk checks,
- execute in paper mode and optionally through T-Bank,
- provide live UI observability for signals, trades, account state, and runtime health,
- accumulate data for attribution, ML overlay, and later strategy improvement.

## 2. Product philosophy
Current engineering direction is **surgical evolution, not rewrite**.

Project principles:
- reliability > delivery speed,
- deterministic execution > “smart looking” heuristics,
- observability is mandatory,
- AI must not bypass hard guardrails,
- read-side/UI problems must not compromise trading core.

## 3. High-level architecture
### Frontend
- React + TypeScript + Vite
- main screens: dashboard, signals, trades, account, backtest, settings
- uses REST + SSE/event stream
- currently production-like usage should prefer backend-served frontend rather than long-lived Vite dev mode

### Backend API
- FastAPI app in `backend/apps/api`
- exposes REST endpoints for signals, trades, settings, account, ML status, runtime state, UI read-models
- also serves SSE stream and backend-served frontend

### Worker
- async runtime in `backend/apps/worker`
- polls/builds candles, runs strategies, Decision Engine, risk checks, execution, monitoring, and notifications
- this is the actual trading runtime, not just a helper process

### Storage / infra
- PostgreSQL via SQLAlchemy models/repos
- Redis for bus/coordination/status
- systemd services are used in real operation
- T-Bank is the current broker/data integration path

### Decision / execution model
Signal lifecycle is roughly:
1. market data/candle preparation
2. strategy candidate generation
3. Decision Engine scoring and filtering
4. AI overlay second opinion
5. risk/capital allocation checks
6. execution in paper or broker mode
7. trade/position/tracing persistence
8. UI/Telegram/runtime observability

## 4. Current state as of 2026-04-12
### Already done before this handoff
Sprint 0 established baseline and localized the main weak points:
- performance hotspot in `performance_governor`,
- UI/read-side instability,
- trade page timeout due to wrong heavy endpoint usage,
- memory sensitivity in worker/API runtime.

### Sprint 1 Stage 1 done
Read-side/UI stabilization was performed:
- heavy UI polling churn reduced,
- `TradesPage` switched to fast `/api/v1/ui/trades` read-model,
- signals/dashboard payload pressure reduced,
- frontend read-side became meaningfully more stable.

### Sprint 1 Stage 2 done
Runtime + ML stabilization was performed:
- API heavy read-path was stabilized,
- candles path stopped doing unnecessary remote fetches when local cache already has data,
- worker/API memory blow-up was mitigated with runtime guards,
- ML `trade_outcome` dataset source was corrected from mutable `positions` rows to immutable `position_closed` decision logs,
- `take_fill` model now supports rare-class fallback instead of crashing on stratified split,
- both `trade_outcome` and `take_fill` are currently active in ML runtime.

## 5. Important technical truths you must not break
1. **Do not let AI bypass deterministic hard blocks.**
   AI is an overlay, not sovereign execution authority.

2. **Do not reintroduce heavy read-side endpoints into frontend hot paths.**
   UI read-models must stay lightweight and purpose-built.

3. **Do not assume “service active” means “runtime healthy”.**
   We already had cases where API looked alive but requests hung or workers degraded under memory pressure.

4. **Use immutable logs for training/forensics when possible.**
   Mutable runtime tables can lie by omission or overwrite history.

5. **Do not solve stability issues by just raising timeouts/memory forever.**
   Root-cause and payload discipline matter.

## 6. Key directories
- `src/` — frontend
- `backend/apps/api/` — API
- `backend/apps/worker/` — trading runtime
- `backend/core/` — execution, ML, risk, services, storage
- `docs/` — architecture, ADRs, runbooks, baselines

## 7. How to think about the system
Treat Spatial Pinwheel as three coupled systems:
- **trading core**: signal -> decision -> risk -> execution,
- **observability/read-side**: UI/runtime/account/trades visibility,
- **learning layer**: attribution, ML overlay, later offline improvements.

When changing one of them, verify you are not silently degrading the other two.

## 8. What needs the most caution right now
- API and worker memory behavior under repeated heavy reads,
- ML data quality, especially the class imbalance in `take_fill`,
- preserving fast UI read-models,
- keeping training/forensic datasets sourced from immutable event history.

## 9. Recommended local verification after changes
Minimum smoke before declaring success:
- API health responds,
- dashboard responds,
- signals page responds,
- trades page responds via UI read-model,
- worker is alive and producing runtime updates,
- `/api/v1/ml/status` returns active models if ML code was touched,
- no regression in read-side latency or obvious RSS explosion.

## 10. Primary references
- `README.md`
- `docs/architecture.md`
- `docs/adr/ADR-no-rewrite-surgical-evolution.md`
- `docs/techspec/sprint-0-baseline.md`
- `docs/handoff/SPRINT_2_ML_DATA_QUALITY_AND_ATTRIBUTION.md`
