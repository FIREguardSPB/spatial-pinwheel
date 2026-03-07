# Spatial Pinwheel — Architecture

## Overview

```
┌────────────────────────────────────────────────────────────────────┐
│                        Frontend (React)                             │
│  DashboardPage  SignalsPage  TradesPage  BacktestPage  Settings    │
│         └── @tanstack/react-query ──── SSE (EventSource)          │
└─────────────────────────┬──────────────────────────────────────────┘
                           │ HTTP REST + SSE
┌─────────────────────────▼──────────────────────────────────────────┐
│                    FastAPI (apps/api/)                               │
│  /signals  /settings  /watchlist  /trades  /account  /backtest     │
│  /instruments  /ai/*  /control  /state  /klines  /stream (SSE)     │
└──────┬──────────────────────────┬──────────────────────────────────┘
       │ Redis (command queue)    │ PostgreSQL (SQLAlchemy)
┌──────▼──────────────────────┐  │
│       Worker (asyncio)      │  │
│  ┌─────────────────────┐   │  │
│  │  Decision Engine    │   │  │
│  │  BreakoutStrategy   │◄──┘  │
│  │  MeanReversion      │      │
│  │  VWAPBounce         │      │
│  │  StrategySelector   │      │
│  └────────┬────────────┘      │
│           │                   │
│  ┌────────▼────────────┐      │
│  │   Risk Manager      │      │
│  │   Position Monitor  │      │
│  └────────┬────────────┘      │
│           │                   │
│  ┌────────▼────────────┐      │
│  │  Paper / TBank      │      │
│  │  Execution Broker   │      │
│  └─────────────────────┘      │
└─────────────────────────────── ┘
         │
┌────────▼──────────┐  ┌──────────────────────────────────────┐
│  Telegram Bot     │  │  AI Module (P4)                       │
│  Notifications    │  │  ClaudeProvider / OpenAIProvider       │
└───────────────────┘  │  OllamaProvider / WebScraper          │
                       └──────────────────────────────────────┘
```

## Directory Structure

```
spatial-pinwheel/
├── src/                         # Frontend (React + TypeScript)
│   ├── App.tsx                  # Routes: /, /signals, /trades, /account, /backtest, /settings
│   ├── components/
│   │   ├── Layout.tsx           # Nav sidebar + footer
│   │   ├── help/HelpSystem.tsx  # Glossary + InfoTooltip
│   │   └── ui/UIComponents.tsx  # ConfirmModal, Skeleton, EmptyState, ErrorState
│   ├── features/
│   │   ├── dashboard/           # DashboardPage, InstrumentSelector, PnLWidgets, StatsWidgets
│   │   ├── signals/             # SignalsPage, SignalsTable, SignalCard (mobile), AIDecisionCard
│   │   ├── trades/              # TradesPage
│   │   ├── account/             # AccountPage
│   │   ├── backtest/            # BacktestPage
│   │   └── settings/            # SettingsPage, AISettingsPanel
│   ├── services/api.ts          # Axios apiClient
│   ├── store/index.ts           # Zustand global state
│   └── constants/helpContent.ts # 30 financial glossary terms
│
├── backend/
│   ├── apps/
│   │   ├── api/                 # FastAPI app + all routers
│   │   ├── worker/              # Main trading loop + DecisionEngine
│   │   └── backtest/            # BacktestEngine
│   ├── core/
│   │   ├── execution/           # PaperBroker, TBankBroker, PositionMonitor
│   │   ├── risk/                # RiskManager, CorrelationFilter
│   │   ├── strategy/            # BreakoutStrategy, MeanReversion, VWAPBounce
│   │   ├── storage/             # SQLAlchemy models + repos
│   │   ├── notifications/       # TelegramNotifier
│   │   ├── ai/                  # AI providers (Claude, OpenAI, Ollama)
│   │   └── utils/               # session.py (MOEX trading hours)
│   └── tests/                   # Unit + integration tests
│
├── infra/
│   ├── docker-compose.yml
│   └── nginx/nginx.conf
│
└── docs/                        # This directory
```

## Data Flow

1. **Worker** subscribes to MOEX market data (T-Bank gRPC or mock)
2. Candles buffered in-memory per instrument
3. **StrategySelector** picks best strategy; `strategy.analyze()` returns signal or None
4. **DecisionEngine** scores signal (0–100) against 7 weighted criteria
5. If score ≥ threshold → signal saved to DB with status `pending_review` (or auto-approved in `live` mode)
6. FastAPI SSE `/stream` pushes `signal_created` event to Frontend
7. User approves (or auto-approve) → Worker picks up via Redis command queue
8. **RiskManager** validates against position limits, daily loss, cooldown
9. **Broker** executes trade (Paper or T-Bank live)
10. **PositionMonitor** checks SL/TP/TimeStop on every tick

## SSE Events

| Event              | Payload                             |
|--------------------|-------------------------------------|
| `kline`            | `{ instrument_id, candle }`         |
| `signal_created`   | `{ signal_id }`                     |
| `signal_updated`   | `{ signal_id, status }`             |
| `positions_updated`| `{ instrument_id }`                 |
| `trade_filled`     | `{ trade_id, reason, pnl }`         |
| `bot_status`       | `{ is_running, ... }`               |
| `heartbeat`        | `{ ts }`                            |
