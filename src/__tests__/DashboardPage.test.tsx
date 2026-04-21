import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

function renderWithQuery(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

vi.mock('recharts', () => ({
  AreaChart: () => null,
  Area: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
  ResponsiveContainer: ({ children }: any) => <div>{children}</div>,
}));

vi.mock('../features/dashboard/ChartContainer', () => ({
  ChartContainer: () => <div>chart</div>,
}));

vi.mock('../features/system/WorkerAnalysisInspector', () => ({
  WorkerAnalysisInspector: () => <div>worker-analysis</div>,
}));

const mutateAsync = vi.fn(async () => ({}));

vi.mock('../features/core/queries', () => ({
  useStartBot: () => ({ isPending: false, mutateAsync }),
  useStopBot: () => ({ isPending: false, mutateAsync }),
}));

const useUiDashboard = vi.fn();
vi.mock('../features/core/uiQueries', () => ({
  useUiDashboard: (...args: any[]) => useUiDashboard(...args),
}));

describe('DashboardPage', () => {
  beforeEach(async () => {
    useUiDashboard.mockReset();
    const { useAppStore } = await import('../store/index');
    useAppStore.setState({
      selectedInstrument: 'TQBR:SBER',
      selectedTimeframe: '1m',
      candles: {
        'TQBR:SBER-1m': [
          { time: 1776744720, open: 1, high: 1, low: 1, close: 1, volume: 1 },
        ],
      },
    });
  });

  it('keeps rendered dashboard content when query is error but stale data exists', async () => {
    const DashboardPage = (await import('../features/dashboard/DashboardPage')).default;
    useUiDashboard.mockReturnValue({
      isLoading: false,
      isError: true,
      refetch: vi.fn(),
      data: {
        runtime: {
          bot_status: {
            is_running: false,
            mode: 'review',
            session: { is_open: true, trading_day: '2026-04-21', market: 'MOEX', current_session_start: '2026-04-21T06:50:00+03:00', current_session_end: '2026-04-21T18:59:59+03:00', next_open: '2026-04-21T19:00:00+03:00' },
            connection: { market_data: 'connected', broker: 'connected' },
            warnings: [],
          },
          worker_status: { ok: false, phase: 'offline' },
          schedule: { is_open: true, is_trading_day: true, trading_day: '2026-04-21', exchange: 'MOEX', current_session_start: '2026-04-21T06:50:00+03:00', current_session_end: '2026-04-21T18:59:59+03:00', next_open: '2026-04-21T19:00:00+03:00' },
          watchlist: [{ instrument_id: 'TQBR:SBER', ticker: 'SBER' }],
        },
        account_summary: { balance: 100000, open_pnl: 0, day_pnl: 0 },
        account_history: { period_days: 7, points: [] },
        positions: { items: [] },
        orders: { items: [] },
        signals: { items: [] },
        latest_candle: { instrument_id: 'TQBR:SBER', timeframe: '1m', latest_ts: 1776744720 },
      },
    });

    renderWithQuery(<DashboardPage />);

    expect(screen.getByText('График инструмента')).toBeInTheDocument();
    expect(screen.getByText((text) => text.includes('Последняя свеча:'))).toBeInTheDocument();
    expect(screen.queryByText('Не удалось загрузить данные дашборда')).not.toBeInTheDocument();
  });

  it('shows explicit worker heartbeat degradation while keeping content', async () => {
    const DashboardPage = (await import('../features/dashboard/DashboardPage')).default;
    useUiDashboard.mockReturnValue({
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
      data: {
        runtime: {
          bot_status: {
            is_running: false,
            mode: 'review',
            session: { is_open: true, trading_day: '2026-04-21', market: 'MOEX', current_session_start: '2026-04-21T06:50:00+03:00', current_session_end: '2026-04-21T18:59:59+03:00', next_open: '2026-04-21T19:00:00+03:00' },
            connection: { market_data: 'connected', broker: 'connected' },
            warnings: ['Worker heartbeat is unavailable'],
          },
          worker_status: { ok: false, phase: 'offline' },
          schedule: { is_open: true, is_trading_day: true, trading_day: '2026-04-21', exchange: 'MOEX', current_session_start: '2026-04-21T06:50:00+03:00', current_session_end: '2026-04-21T18:59:59+03:00', next_open: '2026-04-21T19:00:00+03:00' },
          watchlist: [{ instrument_id: 'TQBR:SBER', ticker: 'SBER' }],
        },
        account_summary: { balance: 100000, open_pnl: 0, day_pnl: 0 },
        account_history: { period_days: 7, points: [] },
        positions: { items: [] },
        orders: { items: [] },
        signals: { items: [] },
        latest_candle: { instrument_id: 'TQBR:SBER', timeframe: '1m', latest_ts: 1776744720 },
      },
    });

    renderWithQuery(<DashboardPage />);

    expect(screen.getByText('График инструмента')).toBeInTheDocument();
    expect(screen.getByText(/Нет heartbeat/i)).toBeInTheDocument();
    expect(screen.getByText(/Worker heartbeat is unavailable/i)).toBeInTheDocument();
  });
});
