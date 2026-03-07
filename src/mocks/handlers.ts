/**
 * P7-04: MSW (Mock Service Worker) API handlers.
 * Used in Vitest + @testing-library/react to intercept API calls.
 *
 * Install: npm install -D vitest @testing-library/react @testing-library/user-event
 *          msw jsdom @vitest/coverage-v8
 */
import { http, HttpResponse } from 'msw';

// ── Fixtures ──────────────────────────────────────────────────────────────────
export const mockSignals = [
  {
    id: 'sig_001',
    instrument_id: 'TQBR:SBER',
    side: 'BUY',
    entry: 285.5,
    sl: 280.0,
    tp: 295.0,
    r: 1.73,
    size: 10,
    status: 'pending_review',
    created_ts: Date.now() - 60_000,
    updated_ts: Date.now(),
    meta: {
      decision: { score: 68, decision: 'TAKE' },
      ai_decision: null,
    },
  },
  {
    id: 'sig_002',
    instrument_id: 'TQBR:GAZP',
    side: 'SELL',
    entry: 162.3,
    sl: 165.0,
    tp: 157.0,
    r: 1.96,
    size: 20,
    status: 'approved',
    created_ts: Date.now() - 120_000,
    updated_ts: Date.now(),
    meta: {
      decision: { score: 74, decision: 'TAKE' },
      ai_decision: {
        decision: 'TAKE',
        confidence: 0.82,
        reasoning: 'Strong downward momentum',
        key_factors: ['RSI < 40', 'Below VWAP'],
      },
    },
  },
];

export const mockSettings = {
  trade_mode:              'paper',
  risk_per_trade_pct:      1.0,
  daily_loss_limit_pct:    5.0,
  max_concurrent_positions: 3,
  cooldown_minutes:        30,
  cooldown_losses:         3,
  decision_threshold:      60,
  rr_min:                  1.3,
  mock_mode:               true,
};

export const mockBotStatus = {
  is_running:         true,
  uptime_seconds:     3600,
  signals_processed:  42,
  trades_executed:    7,
  active_instrument:  'TQBR:SBER',
  active_timeframe:   '5m',
  positions:          [],
};

export const mockDailyStats = {
  date:            new Date().toISOString().split('T')[0],
  realized_pnl:    125.50,
  open_pnl:        -42.30,
  trades_count:    3,
  win_count:       2,
  win_rate:        66.7,
  open_positions:  1,
  active_orders:   2,
};

export const mockTrades = [
  {
    id:            'trd_001',
    instrument_id: 'TQBR:SBER',
    side:          'BUY',
    price:         285.0,
    qty:           10,
    ts:            Date.now() - 3600_000,
    realized_pnl:  85.0,
    order_id:      'ord_test_001',
  },
  {
    id:            'trd_002',
    instrument_id: 'TQBR:LKOH',
    side:          'SELL',
    price:         6910.0,
    qty:           2,
    ts:            Date.now() - 7200_000,
    realized_pnl:  40.5,
    order_id:      'ord_test_002',
  },
];

export const mockWatchlist = [
  { id: 'wl_1', instrument_id: 'TQBR:SBER',  added_ts: Date.now() - 86400_000 },
  { id: 'wl_2', instrument_id: 'TQBR:GAZP',  added_ts: Date.now() - 86400_000 },
  { id: 'wl_3', instrument_id: 'TQBR:LKOH',  added_ts: Date.now() - 86400_000 },
];

// ── Handlers ──────────────────────────────────────────────────────────────────
export const handlers = [
  // Signals
  http.get('/api/v1/signals', () =>
    HttpResponse.json(mockSignals)),

  http.post('/api/v1/signals/:id/action', ({ params, request }) =>
    HttpResponse.json({ id: params.id, status: 'approved' })),

  // Settings
  http.get('/api/v1/settings', () =>
    HttpResponse.json(mockSettings)),

  http.put('/api/v1/settings', async ({ request }) => {
    const body = await request.json();
    return HttpResponse.json({ ...mockSettings, ...(body as object) });
  }),

  // Bot control
  http.get('/api/v1/state', () =>
    HttpResponse.json(mockBotStatus)),

  http.post('/api/v1/control', async ({ request }) => {
    const body = await request.json() as { action: string };
    const is_running = body?.action === 'start';
    return HttpResponse.json({ ...mockBotStatus, is_running });
  }),

  // Account
  http.get('/api/v1/account/daily-stats', () =>
    HttpResponse.json(mockDailyStats)),

  http.get('/api/v1/account/summary', () =>
    HttpResponse.json({ balance: 100_000, equity: 100_125.5, open_pnl: -42.3 })),

  // Trades
  http.get('/api/v1/trades', () =>
    HttpResponse.json({ items: mockTrades, total: 2 })),

  http.get('/api/v1/trades/stats', () =>
    HttpResponse.json({ total_trades: 3, win_rate: 66.7, total_pnl: 125.5 })),

  // Watchlist
  http.get('/api/v1/watchlist', () =>
    HttpResponse.json(mockWatchlist)),

  http.post('/api/v1/watchlist', async ({ request }) => {
    const body = await request.json() as { instrument_id: string };
    return HttpResponse.json({ id: 'wl_new', instrument_id: body?.instrument_id });
  }),

  http.delete('/api/v1/watchlist/:id', ({ params }) =>
    HttpResponse.json({ deleted: params.id })),

  // Instruments search
  http.get('/api/v1/instruments/search', ({ request }) => {
    const url   = new URL(request.url);
    const query = url.searchParams.get('q')?.toLowerCase() ?? '';
    const all   = [
      { id: 'TQBR:SBER',  name: 'Сбербанк' },
      { id: 'TQBR:GAZP',  name: 'Газпром' },
      { id: 'TQBR:LKOH',  name: 'Лукойл' },
      { id: 'TQBR:YNDX',  name: 'Яндекс' },
    ];
    return HttpResponse.json(all.filter(i =>
      i.id.toLowerCase().includes(query) || i.name.toLowerCase().includes(query)
    ));
  }),

  // AI stats
  http.get('/api/v1/ai/stats', () =>
    HttpResponse.json({ provider: 'claude', win_rate: 68.2, total_signals: 142 })),

  // Backtest
  http.post('/api/v1/backtest', async ({ request }) => {
    const body = await request.json() as Record<string, unknown>;
    return HttpResponse.json({
      strategy_name:    body?.strategy ?? 'breakout',
      instrument_id:    body?.instrument_id ?? 'TQBR:SBER',
      total_trades:     24,
      win_rate:         54.2,
      profit_factor:    1.43,
      max_drawdown_pct: 8.7,
      total_return_pct: 12.3,
      final_balance:    112_300,
      equity_curve:     [
        { ts: Date.now() - 86400_000 * 7, equity: 100_000 },
        { ts: Date.now() - 86400_000 * 5, equity: 103_500 },
        { ts: Date.now() - 86400_000 * 3, equity: 109_200 },
        { ts: Date.now(),                  equity: 112_300 },
      ],
      trades: [],
    });
  }),
];
