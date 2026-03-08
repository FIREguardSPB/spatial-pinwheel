import { describe, it, expect } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { server } from './setup';
import { http, HttpResponse } from 'msw';
import { mockSignals, mockSettings } from '../mocks/handlers';
import type { ReactNode } from 'react';

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 0 } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

describe('apiClient', () => {
  it('has correct baseURL', async () => {
    const { apiClient } = await import('../services/api');
    const baseURL = apiClient.defaults.baseURL;
    expect(typeof baseURL).toBe('string');
    expect(baseURL).toMatch(/\/api|localhost/);
  });
});

describe('useSignals', () => {
  it('returns signals array from API', async () => {
    const { useSignals } = await import('../features/signals/hooks');
    const { result } = renderHook(() => useSignals(), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(Array.isArray(result.current.data)).toBe(true);
    expect(result.current.data![0]).toHaveProperty('instrument_id');
  });

  it('sets isError on fetch failure', async () => {
    server.use(http.get('/api/v1/signals', () => HttpResponse.json({ error: 'Server error' }, { status: 500 })));
    const { useSignals } = await import('../features/signals/hooks');
    const { result } = renderHook(() => useSignals(), { wrapper });
    await waitFor(() => expect(result.current.isError).toBe(true));
  });
});

describe('useSignalAction', () => {
  it('sends POST to /signals/:id/approve', async () => {
    let called = false;
    server.use(http.post('/api/v1/signals/:id/approve', async () => {
      called = true;
      return HttpResponse.json({ status: 'ok' });
    }));

    const { useSignalAction } = await import('../features/signals/hooks');
    const { result } = renderHook(() => useSignalAction(), { wrapper });
    result.current.mutate({ id: 'sig_001', action: 'approve' });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(called).toBe(true);
  });
});

describe('useSettings', () => {
  it('returns settings from API', async () => {
    const { useSettings } = await import('../features/settings/hooks');
    const { result } = renderHook(() => useSettings(), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toMatchObject({ trade_mode: 'auto_paper', risk_per_trade_pct: 1 });
  });

  it('settings has required fields', async () => {
    const { useSettings } = await import('../features/settings/hooks');
    const { result } = renderHook(() => useSettings(), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    const s = result.current.data!;
    for (const field of ['trade_mode', 'risk_per_trade_pct', 'daily_loss_limit_pct', 'max_concurrent_positions', 'decision_threshold']) {
      expect(s).toHaveProperty(field);
    }
  });
});

describe('useUpdateSettings', () => {
  it('sends PUT request with updated values', async () => {
    let capturedBody: any = null;
    server.use(
      http.put('/api/v1/settings', async ({ request }) => {
        capturedBody = await request.json();
        return HttpResponse.json({ ...mockSettings, ...(capturedBody as object) });
      }),
    );
    const { useUpdateSettings } = await import('../features/settings/hooks');
    const { result } = renderHook(() => useUpdateSettings(), { wrapper });
    result.current.mutate({ ...mockSettings, risk_per_trade_pct: 2 } as any);
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(capturedBody).toMatchObject({ risk_per_trade_pct: 2 });
  });
});
