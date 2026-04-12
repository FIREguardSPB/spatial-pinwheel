# FIX44 — final trader engine foundation

This phase moves the project further away from global static thresholds and toward a trader-like architecture:

- **Walk-forward / rolling validation** inside symbol profile training.
- **Event / news regime layer** with persisted event regime snapshots.
- **Capital allocator** that can partially free capital from weaker open positions for stronger new opportunities.
- **Adaptive exit manager** for stale trades, continuation extension, stop tightening, and profit de-risking.
- **Clearer hierarchy** in signal meta: `symbol_brain`, `event_regime`, `event_adjusted_score`, while `RiskManager` remains the global portfolio guard.

## Main backend additions

### Event regime
- New service: `core/services/event_regime.py`
- New table: `symbol_event_regimes`
- New API: `GET /api/v1/event-regimes`
- Signal pipeline now computes a formal event/news regime and stores it in signal meta.
- Event regime can:
  - promote a borderline TAKE when there is a fresh aligned catalyst;
  - de-risk or demote weak TAKEs during a shock regime.

### Walk-forward validation
- `train_symbol_profile()` now runs walk-forward / rolling validation on candle cache.
- Diagnostics include:
  - fold-by-fold results,
  - strategy rankings,
  - robust score,
  - best validated strategy.
- Training runs are recorded as `offline_walk_forward` when validation is available.

### Capital allocator
- New service: `core/services/capital_allocator.py`
- `PaperExecutionEngine` now ranks open positions vs the incoming signal and can reallocate capital more intelligently instead of using only a blunt partial-close heuristic.
- Reallocation decisions are logged as `capital_reallocation`.

### Adaptive exit manager
- New service: `core/services/adaptive_exit.py`
- `PositionMonitor` now supports:
  - early adaptive time stop for stale trades,
  - hold extension for strong continuation,
  - stop tightening after favorable progress,
  - partial profit de-risking.

### Settings / migration
Added runtime settings + migration:
- `capital_allocator_enabled`
- `capital_allocator_min_score_gap`
- `capital_allocator_min_free_cash_pct`
- `capital_allocator_max_reallocation_pct`
- `event_regime_enabled`
- `event_regime_block_severity`
- `adaptive_exit_enabled`
- `adaptive_exit_extend_bars_limit`
- `adaptive_exit_tighten_sl_pct`

Migration file:
- `backend/core/storage/migrations/versions/20260330_02_final_trader_engine.py`

## Notes
- Frontend was intentionally left untouched in this phase to avoid another UI regression wave.
- This is a strong backend foundation, not a claim that the bot is already “finished perfection”.
- The next live validation should focus on:
  - signal → trade conversion,
  - event-regime correctness,
  - adaptive exits on real positions,
  - training quality on long candle histories.
