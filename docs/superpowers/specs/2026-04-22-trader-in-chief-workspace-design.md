# Trader-in-Chief Workspace Design

## Goal

Build an AI-first workspace where the main trader agent receives the richest, most complete machine-readable operating context before decision-making, while the human operator gets a minimal, useful cockpit rather than a legacy rule-engine dashboard.

This workspace is primarily for the main AI trader. The human UI is secondary and should remain intentionally lightweight.

## Design Decision

The agreed priority is:

- AI-first workspace first
- human-facing cockpit second

The system should no longer optimize around a dashboard designed for tuning the old rule-heavy engine.

## Primary Outcome

The `Trader-in-Chief` agent must receive a unified structured workspace instead of fragmented signal metadata or post-filter leftovers.

This workspace becomes the main source of truth for:

- market interpretation
- thesis formation
- entry quality judgment
- thesis alive/dead judgment
- re-entry eligibility
- winner management intent
- portfolio-aware prioritization

## Workspace Structure

### 1. Market View

The AI trader should receive:

- instrument id
- sector/theme
- session state
- market regime
- volatility state
- liquidity/volume quality
- event and sentiment context when available

### 2. Multi-Timeframe Thesis View

The workspace must include:

- execution timeframe
- local timeframe
- thesis timeframe
- confirmation timeframe if relevant
- alignment or divergence between timeframes
- structure summary
- thesis classification (continuation, breakout, reclaim, reversal, context alignment)
- explicit thesis invalidation condition

### 3. Trade Geometry And Economics

The workspace must include:

- entry, SL, TP, RR
- ATR-relative stop width
- nearest opposing level
- stop distance and expected profit after costs
- commission dominance
- economic warning flags
- slippage/liquidity warnings

### 4. Portfolio And Risk Context

The workspace must include:

- open positions
- concentration and correlated exposure
- current risk usage
- current hard constraints
- broker/execution health
- current safety-shell status

### 5. Memory And Lineage

The workspace must include:

- recent similar trades
- fast-failure history
- previous attempts on the same thesis or instrument
- entry invalidation versus thesis invalidation history
- re-entry lineage
- winner/loser analogs if available

### 6. Policy Context

The workspace must explicitly separate:

- hard blockers
- soft blockers
- advisory-only warnings

The old mistake was letting soft layers act like silent decision-makers. This design must make that impossible or obvious.

## Trader Output Requirements

The main trader should produce a structured decision object with at least:

- `primary_action`
- `thesis_state`
- `entry_validity`
- `reentry_allowed`
- `winner_management_intent`
- `risk_posture`
- `confidence`
- `hard_blocked`
- `hard_block_reason`
- `requested_supporting_actions`

## Human Cockpit

The human-facing UI should be intentionally minimal.

### Keep in the cockpit

- worker/runtime status
- active mode
- operator controls for:
  - enable/disable trading
  - mode switching (`review` / `paper` / `live` as applicable)
  - account capital usage limit / usable balance scope
- signal flow summary
- current Trader-in-Chief view:
  - trader decision
  - challenger stance
  - consensus
  - thesis state
  - hard block reason if any
- recent decisions table
- recent trades
- compact statistics summary
- export capability for trade/statistics data
- basic mode/settings controls only where still operationally relevant

### Optional but useful later

- Telegram notifications for selected operations or events

This is explicitly non-priority for the first implementation slice.

### Remove from the center

- decorative charts that do not help decision oversight
- legacy tuning panels tied to the old rule-heavy engine
- dense low-value control surfaces for non-technical operator use

## Product Direction

The application is being symbolically reframed as:

- `Trader-in-Chief`

This is not just a name change. It signals that the system is organized around the main AI trader rather than around a rule-engine dashboard.

## Implementation Strategy

### Iteration 1

- build the machine-readable Trader workspace package
- expose it through internal runtime/API paths
- build a minimal operator cockpit focused on state, decisions, trades, and summary stats
- include export-ready trade/stat data in the UI/API payloads

### Iteration 2

- richer memory retrieval and thesis lineage
- stronger challenger specialization
- better operator summaries and post-trade analytics
- Telegram notification hooks for selected events

## Constraints

- the AI-first workspace comes before dashboard beautification
- the human operator UI must stay understandable and low-friction
- deterministic hard-risk and execution rails remain outside the trader as safety shell
- legacy rule-engine-oriented surfaces should not regain central status

## Success Criteria

This design is successful when:

- the main trader receives a unified, rich world-state before making decisions
- the operator can see the essential state of the trader and recent trade outcomes without being buried in internal tuning detail
- trades and compact statistics are visible and exportable
- the system clearly distinguishes hard safety constraints from soft contextual judgment
