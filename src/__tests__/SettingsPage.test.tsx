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

  it('setMockMode stays disabled outside UI demo mode', async () => {
    const { useAppStore } = await import('../store/index');
    useAppStore.getState().setMockMode(true);
    expect(useAppStore.getState().isUiDemoMode).toBe(false);
    expect(useAppStore.getState().isMockMode).toBe(false);
  });
});

describe('SettingsPage', () => {
  it('loads bootstrap settings view', async () => {
    const SettingsPage = (await import('../features/settings/SettingsPage')).default;
    renderWithQuery(<SettingsPage />);
    await waitFor(() => {
      expect(screen.getByText(/runtime и рынок/i)).toBeInTheDocument();
    });
  });

  it('save button triggers PUT to /api/v1/settings', async () => {
    let putCalled = false;
    server.use(
      http.put('/api/v1/settings', async ({ request }: any) => {
        putCalled = true;
        const body = await request.json();
        return HttpResponse.json({ ...mockSettings, ...(body as object) });
      }),
    );

    const SettingsPage = (await import('../features/settings/SettingsPage')).default;
    renderWithQuery(<SettingsPage />);
    await waitFor(() => expect(screen.getByText(/^сохранить$/i)).not.toBeDisabled());
    fireEvent.click(screen.getByText(/^сохранить$/i));
    await waitFor(() => expect(putCalled).toBe(true));
  });

  it('telegram tab shows token field and sends test message', async () => {
    let testSendCalled = false;
    server.use(
      http.post('/api/v1/settings/telegram/test-send', () => {
        testSendCalled = true;
        return HttpResponse.json({ ok: true });
      }),
    );

    const SettingsPage = (await import('../features/settings/SettingsPage')).default;
    renderWithQuery(<SettingsPage />);
    await waitFor(() => screen.getByRole('button', { name: 'Telegram' }));
    fireEvent.click(screen.getByRole('button', { name: 'Telegram' }));

    await waitFor(() => {
      expect(screen.getByTestId('telegram-bot-token')).toBeInTheDocument();
      expect(screen.getByTestId('telegram-chat-id')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /отправить тестовое сообщение/i }));
    await waitFor(() => expect(testSendCalled).toBe(true));
  });
});
