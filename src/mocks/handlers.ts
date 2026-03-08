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
  risk_per_trade_pct: 1,
  daily_loss_limit_pct: 2,
  max_concurrent_positions: 2,
  max_trades_per_day: 8,
  rr_target: 1.5,
  time_stop_bars: 6,
  close_before_session_end_minutes: 10,
  cooldown_after_losses: { losses: 2, minutes: 60 },
  decision_threshold: 70,
  rr_min: 1.5,
  ai_mode: 'off',
  ai_min_confidence: 70,
  ai_primary_provider: 'claude',
  ai_fallback_providers: 'ollama,skip',
  ollama_url: 'http://localhost:11434',
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
  warnings: [],
  capabilities: { manual_review: true, auto_paper: true, auto_live: true },
};

export const mockDailyStats = {
  day_pnl: 125.5,
  trades_count: 3,
  win_rate: 66.7,
  best_trade: 90,
  worst_trade: -30,
  open_positions: 1,
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

export const handlers = [
  http.get('/api/v1/signals', () => HttpResponse.json({ items: mockSignals })),
  http.post('/api/v1/signals/:id/approve', () => HttpResponse.json({ status: 'ok' })),
  http.post('/api/v1/signals/:id/reject', () => HttpResponse.json({ status: 'ok' })),

  http.get('/api/v1/settings', () => HttpResponse.json(mockSettings)),
  http.put('/api/v1/settings', async ({ request }) => {
    const body = await request.json();
    return HttpResponse.json({ ...mockSettings, ...(body as object) });
  }),

  http.get('/api/v1/bot/status', () => HttpResponse.json(mockBotStatus)),
  http.post('/api/v1/bot/start', () => HttpResponse.json({ ...mockBotStatus, is_running: true })),
  http.post('/api/v1/bot/stop', () => HttpResponse.json({ ...mockBotStatus, is_running: false })),
  http.get('/api/v1/state', () => HttpResponse.json(mockBotStatus)),

  http.get('/api/v1/account/daily-stats', () => HttpResponse.json(mockDailyStats)),
  http.get('/api/v1/account/summary', () => HttpResponse.json({ balance: 100000, equity: 100125.5, open_pnl: -42.3 })),

  http.get('/api/v1/trades', () => HttpResponse.json({ items: mockTrades, total: 1 })),
  http.get('/api/v1/trades/stats', () => HttpResponse.json({ total_trades: 3, win_rate: 66.7, total_pnl: 125.5 })),

  http.get('/api/v1/watchlist', () => HttpResponse.json({ items: mockWatchlist })),
  http.post('/api/v1/watchlist', async ({ request }) => {
    const body = await request.json() as { instrument_id: string; ticker?: string; name?: string; exchange?: string };
    return HttpResponse.json({ ok: true, instrument_id: body.instrument_id });
  }),
  http.delete('/api/v1/watchlist/:id', ({ params }) => HttpResponse.json({ deleted: params.id })),

  http.get('/api/v1/instruments/search', ({ request }) => {
    const url = new URL(request.url);
    const query = url.searchParams.get('q')?.toLowerCase() ?? '';
    const all = [
      { instrument_id: 'TQBR:SBER', ticker: 'SBER', name: 'Сбербанк', exchange: 'TQBR', type: 'stock' },
      { instrument_id: 'TQBR:GAZP', ticker: 'GAZP', name: 'Газпром', exchange: 'TQBR', type: 'stock' },
    ];
    return HttpResponse.json({ items: all.filter((item) => item.instrument_id.toLowerCase().includes(query) || item.name.toLowerCase().includes(query)) });
  }),

  http.get('/api/v1/ai/stats', () => HttpResponse.json({ total: 0, providers: [] })),
  http.post('/api/v1/backtest', async ({ request }) => {
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
