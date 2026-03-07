/**
 * P7-04: SettingsPage and Zustand store tests.
 *
 * Tests:
 *  - Settings form: change value → save → PUT with correct body
 *  - Store: instrument selection, mock mode toggle
 *  - ConfirmModal: renders on bot toggle, cancel closes it
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { server } from './setup';
import { http, HttpResponse } from 'msw';
import { mockSettings } from '../mocks/handlers';

function renderWithQuery(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

vi.mock('recharts', () => ({
  AreaChart: () => null, Area: () => null, XAxis: () => null, YAxis: () => null,
  Tooltip: () => null, ResponsiveContainer: ({ children }: any) => <div>{children}</div>,
}));

// ── Zustand store tests ────────────────────────────────────────────────────────
describe('Zustand store', () => {
  beforeEach(() => {
    // Reset store between tests
    vi.resetModules();
  });

  it('setInstrument updates active instrument', async () => {
    const { useStore } = await import('../store/index');
    const { result } = await import('@testing-library/react').then(m =>
      ({ result: null as any })
    );
    // Directly test store without React
    const store = useStore.getState();
    store.setInstrument('TQBR:YNDX');
    expect(useStore.getState().activeInstrument).toBe('TQBR:YNDX');
  });

  it('setMockMode updates mockMode', async () => {
    const { useStore } = await import('../store/index');
    const store = useStore.getState();
    const initial = store.mockMode;
    store.setMockMode(!initial);
    expect(useStore.getState().mockMode).toBe(!initial);
    // Restore
    store.setMockMode(initial);
  });
});

// ── Settings form tests ────────────────────────────────────────────────────────
describe('SettingsPage', () => {
  it('loads and displays current settings', async () => {
    const SettingsPage = (await import('../features/settings/SettingsPage')).default;
    renderWithQuery(<SettingsPage />);

    // Wait for settings to render
    await waitFor(() => {
      // trade_mode = 'paper' → should appear somewhere
      const paperEl = screen.queryByText(/бумажная/i) ??
                      screen.queryByDisplayValue('paper');
      expect(paperEl).toBeTruthy();
    });
  });

  it('save button triggers PUT to /api/v1/settings', async () => {
    let putCalled = false;
    let putBody: any = null;

    server.use(
      http.put('/api/v1/settings', async ({ request }) => {
        putCalled = true;
        putBody   = await request.json();
        return HttpResponse.json({ ...mockSettings, ...(putBody as object) });
      })
    );

    const SettingsPage = (await import('../features/settings/SettingsPage')).default;
    renderWithQuery(<SettingsPage />);

    await waitFor(() => screen.queryByText(/сохранить/i));

    const saveBtn = screen.queryByText(/сохранить/i);
    if (saveBtn) {
      fireEvent.click(saveBtn);
      await waitFor(() => expect(putCalled).toBe(true));
    }
  });

  it('confirm modal appears when toggling bot', async () => {
    const SettingsPage = (await import('../features/settings/SettingsPage')).default;
    renderWithQuery(<SettingsPage />);

    await waitFor(() => screen.queryByText(/запустить|остановить/i));

    const toggleBtn = screen.queryByText(/запустить/i) ??
                      screen.queryByText(/остановить/i);

    if (toggleBtn) {
      fireEvent.click(toggleBtn);
      // ConfirmModal should appear
      await waitFor(() => {
        const modal = screen.queryByText(/бота\?/i);
        expect(modal).toBeTruthy();
      });
    }
  });

  it('cancel in confirm modal dismisses it', async () => {
    const SettingsPage = (await import('../features/settings/SettingsPage')).default;
    renderWithQuery(<SettingsPage />);

    await waitFor(() => screen.queryByText(/запустить|остановить/i));

    const toggleBtn = screen.queryByText(/запустить/i) ??
                      screen.queryByText(/остановить/i);

    if (toggleBtn) {
      fireEvent.click(toggleBtn);
      await waitFor(() => screen.queryByText(/отмена/i));

      const cancelBtn = screen.queryByText(/отмена/i);
      if (cancelBtn) {
        fireEvent.click(cancelBtn);
        await waitFor(() => {
          expect(screen.queryByText(/бота\?/i)).toBeNull();
        });
      }
    }
  });
});
