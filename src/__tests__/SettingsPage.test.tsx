import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { server } from './setup';
import { http, HttpResponse } from 'msw';
import { mockSettings } from '../mocks/handlers';

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

describe('Zustand store', () => {
  beforeEach(() => {
    vi.resetModules();
  });

  it('setSelectedInstrument updates selected instrument', async () => {
    const { useAppStore } = await import('../store/index');
    useAppStore.getState().setSelectedInstrument('TQBR:YNDX');
    expect(useAppStore.getState().selectedInstrument).toBe('TQBR:YNDX');
  });

  it('setMockMode updates mock mode', async () => {
    const { useAppStore } = await import('../store/index');
    const initial = useAppStore.getState().isMockMode;
    useAppStore.getState().setMockMode(!initial);
    expect(useAppStore.getState().isMockMode).toBe(!initial);
  });
});

describe('SettingsPage', () => {
  it('loads and displays current settings', async () => {
    const SettingsPage = (await import('../features/settings/SettingsPage')).default;
    renderWithQuery(<SettingsPage />);
    await waitFor(() => {
      expect(screen.getByText(/режим торговли/i)).toBeTruthy();
    });
  });

  it('save button triggers PUT to /api/v1/settings', async () => {
    let putCalled = false;
    server.use(
      http.put('/api/v1/settings', async ({ request }) => {
        putCalled = true;
        const body = await request.json();
        return HttpResponse.json({ ...mockSettings, ...(body as object) });
      }),
    );

    const SettingsPage = (await import('../features/settings/SettingsPage')).default;
    renderWithQuery(<SettingsPage />);
    await waitFor(() => screen.getByText(/сохранить конфигурацию/i));
    fireEvent.click(screen.getByText(/сохранить конфигурацию/i));
    await waitFor(() => expect(putCalled).toBe(true));
  });

  it('confirm modal appears when toggling bot', async () => {
    const SettingsPage = (await import('../features/settings/SettingsPage')).default;
    renderWithQuery(<SettingsPage />);
    await waitFor(() => screen.getByText(/запустить бота|остановить бота/i));
    fireEvent.click(screen.getByText(/запустить бота|остановить бота/i));
    await waitFor(() => {
      expect(screen.getByText(/запустить бота\?|остановить бота\?/i)).toBeTruthy();
    });
  });
});
