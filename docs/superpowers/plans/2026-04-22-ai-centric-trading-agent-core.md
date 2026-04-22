# AI-Centric Trading Agent Core

## Goal

Replace the rule-heavy decision core as the primary direction of evolution with an AI-centric trading agent architecture, while preserving the existing deterministic execution, risk, telemetry, and persistence rails.

The target system is:

- AI-first in market interpretation, thesis formation, re-entry judgment, and trade management intent
- deterministic in execution, hard-risk controls, broker interaction, audit, and kill-switch behavior
- deployed safely through shadow mode and staged authority expansion

The business goal remains unchanged:

- build a live-feeling, profitable trading agent
- target a minimum practical orientation of roughly 1% daily capital growth over a sufficiently large sample, without turning the system into either a silent guard or an undisciplined overtrader

## Scope

This plan covers the first structured migration of the existing system toward an AI-centered core.

It does not cover:

- deleting the current rule engine outright
- direct full-authority AI execution from day one
- replacing broker, execution, or hard-risk rails with model outputs

## Current System Assets To Preserve

These are strengths, not obstacles, and should remain in place:

- `backend/apps/worker/processor.py`
  Current decision and signal pipeline entry point. Will become the orchestration point for shadow and later live agent evaluation.
- `backend/core/execution/paper.py`
  Paper execution shell. Keep deterministic.
- `backend/core/execution/monitor.py`
  Position monitoring, close outcomes, diagnostics, and feedback context.
- `backend/core/services/worker_status.py`
  Runtime state publication. Extend for AI-agent visibility later.
- `backend/apps/api/routers/ui.py`
  Dashboard payload integration point.
- Existing telemetry/logging/model state
  Decision logs, conviction/review metadata, signal outcomes, position-close diagnostics, runtime status, and pipeline counters should remain the audit backbone.

## Target Architecture

### 1. Trader Agent

Primary cloud model role.

Recommended candidates:

- GPT-5.4
- Claude Opus 4.6
- DeepSeek V3.2 as fallback or lower-cost reasoning path for selected contexts

Responsibilities:

- interpret structured market state
- form higher-timeframe thesis
- decide `take / skip / wait / manage / close / reenter`
- distinguish `bad entry` from `dead thesis`
- express intended trade horizon and management intent

The Trader Agent must produce structured JSON, not free-form text as the contract.

### 2. Challenger / Risk Agent

Second cloud model role.

Responsibilities:

- challenge Trader Agent proposals
- identify hidden risk, overtrading, correlation pressure, regime mismatch, weak economics, or thesis inconsistency
- produce explicit objections and a structured approval/challenge recommendation

This is not a chatty committee. It is a narrow adversarial review role.

### 3. Deterministic Merger

Non-AI logic.

Responsibilities:

- validate Trader and Challenger outputs against schema
- merge structured recommendations
- apply hard-risk rails
- decide whether the AI result is actionable, advisory, or ignored

### 4. Deterministic Execution Shell

Keep existing components for:

- broker execution
- order lifecycle
- sizing caps
- anomaly breakers
- kill switches
- close-only mode
- persistence and audit

## Agent Decision Contract

The AI interface should be schema-first.

Suggested Trader Agent output:

```json
{
  "action": "take",
  "confidence": 0.78,
  "thesis": {
    "direction": "short",
    "timeframe": "15m",
    "type": "continuation",
    "summary": "compression break likely resolves lower",
    "invalidates_if": "15m structure reclaims prior balance high"
  },
  "entry_assessment": {
    "entry_valid": true,
    "entry_quality": "good",
    "bad_entry_but_good_thesis": false,
    "reentry_allowed": false
  },
  "management": {
    "intended_horizon_bars": 8,
    "preserve_winner": true,
    "allow_noise_above_execution_frame": true
  },
  "risk_view": {
    "economics_ok": true,
    "correlation_risk": "low",
    "overtrading_risk": "medium"
  },
  "reasoning": "short explanation"
}
```

Suggested Challenger Agent output:

```json
{
  "stance": "challenge",
  "confidence": 0.71,
  "main_objections": [
    "entry is too extended relative to local execution frame",
    "profit path is partially crowded by nearby resistance"
  ],
  "risk_flags": {
    "regime_mismatch": false,
    "economics_conflict": true,
    "correlation_pressure": false,
    "overtrading": true
  },
  "recommended_adjustment": "wait_for_reentry"
}
```

## Input Contract To The Agents

The agents should not receive raw candles alone. They need a structured world-state package.

Include:

- instrument and sector metadata
- multi-timeframe candle summary
- current signal geometry
- current deterministic decision summary and reasons
- costs/slippage/liquidity/economic filters
- open positions and portfolio concentration
- recent outcomes and local instrument memory
- higher-timeframe thesis context
- current protective mode state
- hard constraints summary

## Memory Model

We should treat memory as three layers:

### Episodic memory

- recent trades
- fast losers
- winners
- recent execution problems

### Thesis memory

- prior higher-timeframe thesis on the instrument
- whether the last failure was `entry invalidation` or `thesis invalidation`
- re-entry lineage

### Portfolio memory

- concentration by symbol/theme/sector
- current correlated exposures
- overuse / fatigue signals

## Hard Rails That Remain Deterministic

These must not be delegated to the agents:

- max daily loss / drawdown stop
- max concurrent positions
- max per-trade risk
- broker degraded mode / paper fallback / close-only mode
- anomaly breaker triggers
- invalid order geometry rejection
- position sizing caps
- instrument bans / non-tradable states

## Migration Strategy

### Phase 1. Shadow Agent

Add Trader Agent and Challenger Agent in advisory mode only.

The current rule-based engine remains authoritative.

Deliverables:

- AI input package builder
- agent client abstraction
- structured output schema validation
- decision logging for AI outputs
- dashboard visibility into AI shadow recommendations

Success criteria:

- stable structured outputs
- latency within acceptable operational bounds
- no impact on current execution behavior

### Phase 2. Ambiguity Authority

Allow AI to influence only narrow ambiguity zones, for example:

- near-miss `take vs reject`
- `bad entry vs dead thesis`
- re-entry eligibility
- hold vs exit ambiguity for healthy winners

Deterministic rails still retain veto power.

### Phase 3. AI-Led Thesis Layer

Move higher-timeframe thesis evaluation and trade management intent primarily into the AI layer.

Rule engine remains a fallback/risk shell.

### Phase 4. AI-Primary Decision Core

Only after sufficient evidence in shadow and limited-authority stages.

## File Structure For Initial Implementation

### New files

- `backend/core/ai/agent_contracts.py`
  Pydantic/dataclass schemas for Trader Agent and Challenger Agent I/O.
- `backend/core/ai/agent_clients.py`
  Provider abstraction for cloud models (OpenAI / Anthropic / DeepSeek).
- `backend/core/ai/trader_agent.py`
  Trader Agent orchestration.
- `backend/core/ai/challenger_agent.py`
  Challenger Agent orchestration.
- `backend/core/ai/agent_merge.py`
  Deterministic merger for structured outputs.
- `backend/core/ai/state_builder.py`
  Builds structured AI world-state from existing system data.
- `backend/tests/test_agent_contracts.py`
  Schema/validation tests.
- `backend/tests/test_agent_merge.py`
  Merge behavior tests.

### Existing files to modify first

- `backend/apps/worker/processor.py`
  Insert shadow-mode agent invocation after deterministic evaluation and before final persistence/execution.
- `backend/apps/api/routers/ui.py`
  Surface agent shadow outputs and summaries in dashboard/runtime payloads.
- `backend/core/services/worker_status.py`
  Publish current AI agent phase/health later in rollout.

## Task Breakdown

### Task 1. Add agent contracts and provider abstraction

Create structured input/output schemas and provider adapters for cloud agents.

Tests:

- schema validation
- required fields
- failure on malformed AI output

### Task 2. Build AI world-state package

Assemble all relevant trading context from the current system into a single structured payload for agent consumption.

Tests:

- payload includes market, portfolio, economics, and memory sections
- payload remains JSON-serializable

### Task 3. Implement Trader Agent in shadow mode

Invoke the Trader Agent from the worker pipeline without affecting execution decisions.

Tests:

- shadow output is persisted/logged
- timeout/failure falls back safely

### Task 4. Implement Challenger Agent in shadow mode

Feed Trader output plus full context into the Challenger Agent and persist its structured review.

Tests:

- challenger output logged cleanly
- malformed output rejected safely

### Task 5. Add deterministic merge layer

Merge Trader + Challenger outputs into a normalized advisory decision object.

Tests:

- proposer/challenger conflict behavior
- merger respects hard veto conditions

### Task 6. Expose AI shadow decisions in runtime/UI

Add agent advisory visibility to runtime payloads and dashboard, so shadow behavior is observable.

Tests:

- payload contains shadow decisions
- dashboard survives AI failures

### Task 7. Add evaluation instrumentation

Track shadow-vs-live agreement, disagreement clusters, and outcome quality for later authority expansion.

Tests:

- logging and metrics paths populate correctly

## Testing Strategy

Required after each phase:

- run focused new unit tests
- run existing backend suite
- validate that execution behavior remains unchanged until authority is explicitly expanded

Suggested verification commands:

- `python -m pytest backend/tests/test_agent_contracts.py backend/tests/test_agent_merge.py -vv`
- `python -m pytest backend/tests/test_ui_runtime_pipeline.py backend/tests/test_decision_engine.py backend/tests/test_processor_selective_throttle.py -vv`
- full backend suite before any merge/push

## What Not To Do

- do not let free-form LLM text drive execution decisions directly
- do not bypass deterministic hard-risk controls
- do not start with many loosely defined agents
- do not replace the execution shell first
- do not grant the AI authority before shadow-mode evidence exists

## Recommended First Implementation Slice

Start with:

1. agent contracts
2. provider abstraction
3. AI world-state builder
4. Trader Agent shadow mode
5. dashboard visibility for shadow output

This slice is enough to create a real AI-centric core foundation without destabilizing live trading.
