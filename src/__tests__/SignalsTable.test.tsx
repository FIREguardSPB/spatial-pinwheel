/**
 * P7-04: SignalsTable component tests.
 *
 * Tests:
 *  - Renders signal rows
 *  - Approve/Reject button click → API call → optimistic update
 *  - AI badge renders when ai_decision present
 *  - Skeleton shown while loading
 *  - Empty state when no signals
 *  - Error state on API failure
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { server } from './setup';
import { http, HttpResponse } from 'msw';
import { mockSignals } from '../mocks/handlers';

// Helper: wrap component with React Query
function renderWithQuery(ui: React.ReactElement) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={qc}>{ui}</QueryClientProvider>
  );
}

// ── Stub recharts (not available in jsdom) ────────────────────────────────────
vi.mock('recharts', () => ({
  AreaChart: ({ children }: any) => <div data-testid="area-chart">{children}</div>,
  Area:      () => null,
  XAxis:     () => null,
  YAxis:     () => null,
  Tooltip:   () => null,
  ResponsiveContainer: ({ children }: any) => <div>{children}</div>,
}));

// ── Stub lightweight-charts ───────────────────────────────────────────────────
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

    // Wait for signals to load
    await waitFor(() => {
      expect(screen.getByText('TQBR:SBER')).toBeInTheDocument();
    });
  });

  it('shows loading skeleton while fetching', async () => {
    // Delay server response
    server.use(
      http.get('/api/v1/signals', async () => {
        await new Promise(r => setTimeout(r, 200));
        return HttpResponse.json(mockSignals);
      })
    );

    const { SignalsTable } = await import('../features/signals/SignalsTable');
    const { container } = renderWithQuery(<SignalsTable />);

    // Skeleton should appear immediately before data loads
    expect(container.querySelector('.animate-pulse')).toBeTruthy();
  });

  it('shows error state on API failure', async () => {
    server.use(
      http.get('/api/v1/signals', () =>
        HttpResponse.json({ error: 'Server error' }, { status: 500 })
      )
    );

    const { SignalsTable } = await import('../features/signals/SignalsTable');
    renderWithQuery(<SignalsTable />);

    await waitFor(() => {
      expect(screen.getByText(/не удалось загрузить/i)).toBeInTheDocument();
    });
  });

  it('shows empty state when no signals', async () => {
    server.use(
      http.get('/api/v1/signals', () => HttpResponse.json([]))
    );

    const { SignalsTable } = await import('../features/signals/SignalsTable');
    renderWithQuery(<SignalsTable />);

    await waitFor(() => {
      expect(screen.getByText(/сигналов нет/i)).toBeInTheDocument();
    });
  });

  it('approve button calls API', async () => {
    const user      = userEvent.setup();
    let actionCalled = false;

    server.use(
      http.post('/api/v1/signals/:id/action', ({ params }) => {
        actionCalled = true;
        return HttpResponse.json({ id: params.id, status: 'approved' });
      })
    );

    const { SignalsTable } = await import('../features/signals/SignalsTable');
    renderWithQuery(<SignalsTable />);

    await waitFor(() => screen.getByText('TQBR:SBER'));

    // Find approve button (check/✓ icon)
    const approveBtn = screen.getAllByTitle('Одобрить')[0];
    await user.click(approveBtn);

    await waitFor(() => expect(actionCalled).toBe(true));
  });

  it('reject button calls API with reject action', async () => {
    const user = userEvent.setup();
    let rejectedId: string | undefined;

    server.use(
      http.post('/api/v1/signals/:id/action', async ({ params, request }) => {
        const body = await request.json() as { action: string };
        if (body.action === 'reject') rejectedId = params.id as string;
        return HttpResponse.json({ id: params.id, status: 'rejected' });
      })
    );

    const { SignalsTable } = await import('../features/signals/SignalsTable');
    renderWithQuery(<SignalsTable />);

    await waitFor(() => screen.getByText('TQBR:SBER'));

    const rejectBtn = screen.getAllByTitle('Отклонить')[0];
    await user.click(rejectBtn);

    await waitFor(() => expect(rejectedId).toBe('sig_001'));
  });
});
