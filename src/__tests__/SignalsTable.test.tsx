import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { server } from './setup';
import { http, HttpResponse } from 'msw';
import { mockSignals } from '../mocks/handlers';

function renderWithQuery(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

vi.mock('recharts', () => ({
  AreaChart: ({ children }: any) => <div data-testid="area-chart">{children}</div>,
  Area: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
  ResponsiveContainer: ({ children }: any) => <div>{children}</div>,
}));

vi.mock('lightweight-charts', () => ({
  createChart: () => ({
    applyOptions: vi.fn(),
    addAreaSeries: () => ({ setData: vi.fn(), applyOptions: vi.fn() }),
    timeScale: () => ({ fitContent: vi.fn() }),
    resize: vi.fn(),
    remove: vi.fn(),
  }),
}));

describe('SignalsTable', () => {
  it('renders pending signal rows', async () => {
    const { SignalsTable } = await import('../features/signals/SignalsTable');
    renderWithQuery(<SignalsTable />);
    await waitFor(() => {
      expect(screen.getByText('TQBR:SBER')).toBeInTheDocument();
    });
  });

  it('shows loading skeleton while fetching', async () => {
    server.use(http.get('/api/v1/signals', async () => {
      await new Promise((r) => setTimeout(r, 200));
      return HttpResponse.json({ items: mockSignals });
    }));
    const { SignalsTable } = await import('../features/signals/SignalsTable');
    const { container } = renderWithQuery(<SignalsTable />);
    expect(container.querySelector('.animate-pulse')).toBeTruthy();
  });

  it('falls back to empty state on API failure', async () => {
    server.use(http.get('/api/v1/signals', () => HttpResponse.json({ error: 'Server error' }, { status: 500 })));
    const { SignalsTable } = await import('../features/signals/SignalsTable');
    renderWithQuery(<SignalsTable />);
    await waitFor(() => {
      expect(screen.getByText(/сигналов нет/i)).toBeInTheDocument();
    });
  });

  it('shows empty state when no signals', async () => {
    server.use(http.get('/api/v1/signals', () => HttpResponse.json({ items: [] })));
    const { SignalsTable } = await import('../features/signals/SignalsTable');
    renderWithQuery(<SignalsTable />);
    await waitFor(() => {
      expect(screen.getByText(/сигналов нет/i)).toBeInTheDocument();
    });
  });

  it('approve button calls API', async () => {
    const user = userEvent.setup();
    let actionCalled = false;
    server.use(http.post('/api/v1/signals/:id/approve', () => {
      actionCalled = true;
      return HttpResponse.json({ status: 'ok' });
    }));
    const { SignalsTable } = await import('../features/signals/SignalsTable');
    renderWithQuery(<SignalsTable />);
    await waitFor(() => screen.getByText('TQBR:SBER'));
    await user.click(screen.getAllByTitle('Одобрить')[0]);
    await waitFor(() => expect(actionCalled).toBe(true));
  });

  it('reject button calls API', async () => {
    const user = userEvent.setup();
    let actionCalled = false;
    server.use(http.post('/api/v1/signals/:id/reject', () => {
      actionCalled = true;
      return HttpResponse.json({ status: 'ok' });
    }));
    const { SignalsTable } = await import('../features/signals/SignalsTable');
    renderWithQuery(<SignalsTable />);
    await waitFor(() => screen.getByText('TQBR:SBER'));
    await user.click(screen.getAllByTitle('Отклонить')[0]);
    await waitFor(() => expect(actionCalled).toBe(true));
  });
});
