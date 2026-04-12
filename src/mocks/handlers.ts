import { http, HttpResponse } from 'msw';

export const mockSignals = [
  {
    id: 'sig_001',
    instrument_id: 'TQBR:SBER',
    ts: Date.now(),
    side: 'BUY',
    entry: 285.5,
    sl: 280,
    tp: 295,
    r: 1.73,
    size: 10,
    status: 'pending_review',
    meta: {
      strategy: 'breakout',
      decision: {
        score: 68,
        decision: 'TAKE',
        reasons: [{ severity: 'warn', msg: 'Нужно подтверждение тренда' }],
      },
    },
  },
];

export const mockSettings = {
  risk_profile: 'balanced',
  risk_per_trade_pct: 0.25,
  daily_loss_limit_pct: 1.5,
  max_concurrent_positions: 4,
  max_trades_per_day: 120,
  fees_bps: 3,
  slippage_bps: 5,
  max_position_notional_pct_balance: 10,
  max_total_exposure_pct_balance: 35,
  signal_reentry_cooldown_sec: 30,
  rr_target: 1.4,
  time_stop_bars: 12,
  close_before_session_end_minutes: 5,
  cooldown_after_losses: { losses: 2, minutes: 30 },
  decision_threshold: 70,
  rr_min: 1.5,
  ai_mode: 'advisory',
  ai_min_confidence: 55,
  ai_primary_provider: 'deepseek',
  ai_fallback_providers: 'deepseek,ollama,skip',
  ollama_url: 'http://localhost:11434',
  ai_override_policy: 'promote_only',
  min_sl_distance_pct: 0.08,
  min_profit_after_costs_multiplier: 1.25,
  min_trade_value_rub: 10,
  min_instrument_price_rub: 0.001,
  trading_session: 'all',
  use_broker_trading_schedule: true,
  trading_schedule_exchange: '',
  correlation_threshold: 0.8,
  max_correlated_positions: 2,
  notification_events: 'signal_created,trade_executed',
  account_balance: 100000,
  trade_mode: 'auto_paper',
  bot_enabled: false,
};

export const mockBotStatus = {
  is_running: false,
  mode: 'auto_paper',
  is_paper: true,
  active_instrument_id: '',
  connection: { market_data: 'connected', broker: 'connected' },
  session: {
    market: 'MOEX',
    timezone: 'Europe/Moscow',
    trading_day: '2026-03-18',
    source: 'broker',
    is_open: true,
    current_session_start: new Date(Date.now() - 60 * 60 * 1000).toISOString(),
    current_session_end: new Date(Date.now() + 60 * 60 * 1000).toISOString(),
    next_open: new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString(),
  },
  warnings: [],
  capabilities: { manual_review: true, auto_paper: true, auto_live: true },
};

export const mockTradingSchedule = {
  source: 'broker',
  exchange: 'MOEX',
  trading_day: '2026-03-18',
  is_trading_day: true,
  is_open: true,
  current_session_start: new Date(Date.now() - 60 * 60 * 1000).toISOString(),
  current_session_end: new Date(Date.now() + 60 * 60 * 1000).toISOString(),
  next_open: new Date(Date.now() + 24 * 60 * 60 * 1000).toISOString(),
  error: null,
  timezone: 'Europe/Moscow',
};

export const mockDailyStats = {
  day_pnl: 125.5,
  trades_count: 3,
  win_rate: 66.7,
  best_trade: 90,
  worst_trade: -30,
  open_positions: 1,
};

export const mockTBankAdmin = {
  available: true,
  provider: 'tbank',
  sandbox: true,
  live_trading_enabled: true,
  selected_account_id: 'sbx_001',
  broker_accounts: [
    { id: 'sbx_001', name: 'Sandbox MOEX 1', type: 'ACCOUNT_TYPE_TINKOFF', status: 'ACCOUNT_STATUS_OPEN', access_level: 'ACCOUNT_ACCESS_LEVEL_FULL_ACCESS', currency: 'RUB', is_selected: true },
    { id: 'sbx_002', name: 'Sandbox MOEX 2', type: 'ACCOUNT_TYPE_TINKOFF', status: 'ACCOUNT_STATUS_OPEN', access_level: 'ACCOUNT_ACCESS_LEVEL_FULL_ACCESS', currency: 'RUB', is_selected: false },
  ],
  bank_accounts: [],
};

export const mockTrades = [
  {
    trade_id: 'trd_001',
    instrument_id: 'TQBR:SBER',
    side: 'BUY',
    price: 285,
    qty: 10,
    ts: Date.now() - 3600_000,
    order_id: 'ord_test_001',
  },
];

export const mockWatchlist = [
  { instrument_id: 'TQBR:SBER', ticker: 'SBER', name: 'Сбербанк', exchange: 'TQBR', is_active: true, added_ts: Date.now() - 86400_000 },
];

const mockUiRuntime = {
  bot_status: mockBotStatus,
  worker_status: { ok: true, phase: 'idle', pid: 12345, current_instrument_count: mockWatchlist.length },
  settings: {
    ...mockSettings,
    telegram_bot_token: '',
    telegram_chat_id: '',
    notification_events: 'signal_created,trade_executed,sl_hit,tp_hit',
  },
  schedule: {
    ...mockTradingSchedule,
    warning: null,
  },
  watchlist: mockWatchlist,
  runtime_overview: {
    effective_plan: { instrument_id: 'TQBR:SBER', scope: 'symbol' },
    symbol_profile: { instrument_id: 'TQBR:SBER', sector: 'banks' },
    diagnostics: { score: 72 },
    event_regime: { state: 'normal' },
    source_notes: ['mock ui runtime'],
  },
  ai_runtime: { provider: 'deepseek', status: 'ok' },
  telegram: { status: 'idle', configured: false },
  auto_policy: { status: 'active', state: 'active' },
  ml_runtime: { status: 'ready', active_models: {} },
  pipeline_counters: { signals_seen: 1 },
};

export const handlers = [
  http.get('/api/v1/signals', () => HttpResponse.json({ items: mockSignals })),
  http.post('/api/v1/signals/:id/approve', () => HttpResponse.json({ status: 'ok' })),
  http.post('/api/v1/signals/:id/reject', () => HttpResponse.json({ status: 'ok' })),

  http.get('/api/v1/settings', () => HttpResponse.json(mockSettings)),
  http.get('/api/v1/ui/settings', () => HttpResponse.json({ runtime: mockUiRuntime })),
  http.get('/api/v1/ui/runtime', () => HttpResponse.json(mockUiRuntime)),
  http.get('/api/v1/ui/signals', () => HttpResponse.json({ items: mockSignals, summary: { visible_count: mockSignals.length, total: mockSignals.length, take: 1, ai_affected: 0, ml_seen: 0 } })),
  http.get('/api/v1/settings/runtime-overview', () => HttpResponse.json(mockUiRuntime.runtime_overview)),
  http.get('/api/v1/symbol-profiles/:id', () => HttpResponse.json({ profile: mockUiRuntime.runtime_overview.symbol_profile, current_plan: mockUiRuntime.runtime_overview.effective_plan, diagnostics: mockUiRuntime.runtime_overview.diagnostics })),
  http.get('/api/v1/event-regimes', () => HttpResponse.json({ items: [mockUiRuntime.runtime_overview.event_regime] })),
  http.put('/api/v1/settings', async ({ request }: any) => {
    const body = await request.json();
    return HttpResponse.json({ ...mockSettings, ...(body as object) });
  }),
  http.get('/api/v1/settings/trading-schedule', () => HttpResponse.json(mockTradingSchedule)),
  http.post('/api/v1/settings/trading-schedule/sync', () => HttpResponse.json(mockTradingSchedule)),
  http.post('/api/v1/settings/telegram/test-send', () => HttpResponse.json({ ok: true })),

  http.get('/api/v1/bot/status', () => HttpResponse.json(mockBotStatus)),
  http.post('/api/v1/bot/start', () => HttpResponse.json({ ...mockBotStatus, is_running: true })),
  http.post('/api/v1/bot/stop', () => HttpResponse.json({ ...mockBotStatus, is_running: false })),
  http.get('/api/v1/state', () => HttpResponse.json(mockBotStatus)),

  http.get('/api/v1/account/daily-stats', () => HttpResponse.json(mockDailyStats)),
  http.get('/api/v1/account/summary', () => HttpResponse.json({ mode: 'tbank', balance: 100000, equity: 100125.5, open_pnl: -42.3, day_pnl: 125.5, total_pnl: 2345.1, open_positions: 1, max_drawdown_pct: 4.2, broker_info: { name: 'T-Bank Invest', type: 'broker', status: 'active' } })),
  http.get('/api/v1/account/history', () => HttpResponse.json({ points: [{ ts: Date.now() - 86400_000 * 3, balance: 100000, equity: 100000, day_pnl: 0 }, { ts: Date.now(), balance: 100000, equity: 100125.5, day_pnl: 125.5 }] })),
  http.get('/api/v1/account/tbank/accounts', () => HttpResponse.json(mockTBankAdmin)),
  http.post('/api/v1/account/tbank/select-account', async ({ request }: any) => {
    const body = await request.json() as { account_id: string };
    return HttpResponse.json({ ok: true, selected_account_id: body.account_id });
  }),
  http.post('/api/v1/account/tbank/sandbox/open-account', () => HttpResponse.json({ ok: true, created_account_id: 'sbx_003' })),
  http.post('/api/v1/account/tbank/sandbox/pay-in', () => HttpResponse.json({ ok: true })),
  http.post('/api/v1/account/tbank/pay-in', () => HttpResponse.json({ ok: true })),
  http.post('/api/v1/account/tbank/transfer', () => HttpResponse.json({ ok: true })),

  http.get('/api/v1/trades', () => HttpResponse.json({ items: mockTrades, total: 1 })),
  http.get('/api/v1/trades/stats', () => HttpResponse.json({ total_trades: 3, win_rate: 66.7, total_pnl: 125.5 })),

  http.get('/api/v1/watchlist', () => HttpResponse.json({ items: mockWatchlist })),
  http.get('/api/v1/worker/status', () => HttpResponse.json({ ok: true, phase: 'idle', current_instrument_count: mockWatchlist.length })),
  http.post('/api/v1/watchlist', async ({ request }: any) => {
    const body = await request.json() as { instrument_id: string; ticker?: string; name?: string; exchange?: string };
    return HttpResponse.json({ ok: true, instrument_id: body.instrument_id });
  }),
  http.delete('/api/v1/watchlist/:id', ({ params }: any) => HttpResponse.json({ deleted: params.id })),

  http.get('/api/v1/instruments/search', ({ request }: any) => {
    const url = new URL(request.url);
    const query = url.searchParams.get('q')?.toLowerCase() ?? '';
    const all = [
      { instrument_id: 'TQBR:SBER', ticker: 'SBER', name: 'Сбербанк', exchange: 'TQBR', type: 'stock' },
      { instrument_id: 'TQBR:GAZP', ticker: 'GAZP', name: 'Газпром', exchange: 'TQBR', type: 'stock' },
    ];
    return HttpResponse.json({ items: all.filter((item) => item.instrument_id.toLowerCase().includes(query) || item.name.toLowerCase().includes(query)) });
  }),

  http.get('/api/v1/ai/stats', () => HttpResponse.json({ total: 0, providers: [] })),
  http.post('/api/v1/backtest', async ({ request }: any) => {
    const body = await request.json() as Record<string, unknown>;
    return HttpResponse.json({
      strategy_name: body?.strategy ?? 'breakout',
      instrument_id: body?.instrument_id ?? 'TQBR:SBER',
      total_trades: 24,
      win_rate: 54.2,
      profit_factor: 1.43,
      max_drawdown_pct: 8.7,
      total_return_pct: 12.3,
      final_balance: 112300,
      equity_curve: [
        { ts: Date.now() - 86400_000 * 7, equity: 100000 },
        { ts: Date.now(), equity: 112300 },
      ],
      trades: [],
    });
  }),
];
