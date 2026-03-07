/**
 * P7-04: API client and hook tests.
 *
 * Tests:
 *  - apiClient baseURL is set correctly
 *  - useSignals hook returns data from API
 *  - useSignalAction sends correct request
 *  - useSettings hook returns settings
 *  - useUpdateSettings sends PUT request
 */
import { describe, it, expect, vi } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { server } from './setup';
import { http, HttpResponse } from 'msw';
import { mockSignals, mockSettings } from '../mocks/handlers';
import type { ReactNode } from 'react';

function wrapper({ children }: { children: ReactNode }) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 0 } },
  });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

// ── API client ────────────────────────────────────────────────────────────────
describe('apiClient', () => {
  it('has correct baseURL', async () => {
    const { apiClient } = await import('../services/api');
    const baseURL = apiClient.defaults.baseURL;
    expect(typeof baseURL).toBe('string');
    expect(baseURL).toMatch(/\/api|localhost/);
  });
});

// ── useSignals hook ───────────────────────────────────────────────────────────
describe('useSignals', () => {
  it('returns signals array from API', async () => {
    const { useSignals } = await import('../features/signals/hooks');
    const { result } = renderHook(() => useSignals(), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(Array.isArray(result.current.data)).toBe(true);
    expect(result.current.data!.length).toBeGreaterThan(0);
  });

  it('returns isLoading=true initially', async () => {
    server.use(
      http.get('/api/v1/signals', async () => {
        await new Promise(r => setTimeout(r, 100));
        return HttpResponse.json(mockSignals);
      })
    );

    const { useSignals } = await import('../features/signals/hooks');
    const { result } = renderHook(() => useSignals(), { wrapper });

    // Initially loading
    expect(result.current.isLoading).toBe(true);
  });

  it('sets isError on fetch failure', async () => {
    server.use(
      http.get('/api/v1/signals', () =>
        HttpResponse.json({ error: 'Server error' }, { status: 500 })
      )
    );

    const { useSignals } = await import('../features/signals/hooks');
    const { result } = renderHook(() => useSignals(), { wrapper });

    await waitFor(() => expect(result.current.isError).toBe(true));
  });

  it('signal has required fields', async () => {
    const { useSignals } = await import('../features/signals/hooks');
    const { result } = renderHook(() => useSignals(), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    const signal = result.current.data![0];
    expect(signal).toHaveProperty('id');
    expect(signal).toHaveProperty('instrument_id');
    expect(signal).toHaveProperty('side');
    expect(signal).toHaveProperty('entry');
    expect(signal).toHaveProperty('sl');
    expect(signal).toHaveProperty('tp');
    expect(signal).toHaveProperty('status');
  });
});

// ── useSignalAction hook ──────────────────────────────────────────────────────
describe('useSignalAction', () => {
  it('sends POST to /signals/:id/action', async () => {
    let capturedBody: any = null;

    server.use(
      http.post('/api/v1/signals/:id/action', async ({ request }) => {
        capturedBody = await request.json();
        return HttpResponse.json({ id: 'sig_001', status: 'approved' });
      })
    );

    const { useSignalAction } = await import('../features/signals/hooks');
    const { result } = renderHook(() => useSignalAction(), { wrapper });

    result.current.mutate({ id: 'sig_001', action: 'approve' });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(capturedBody).toMatchObject({ action: 'approve' });
  });
});

// ── useSettings hook ──────────────────────────────────────────────────────────
describe('useSettings', () => {
  it('returns settings from API', async () => {
    const { useSettings } = await import('../features/settings/hooks');
    const { result } = renderHook(() => useSettings(), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toMatchObject({
      trade_mode: 'paper',
      risk_per_trade_pct: 1.0,
    });
  });

  it('settings has required fields', async () => {
    const { useSettings } = await import('../features/settings/hooks');
    const { result } = renderHook(() => useSettings(), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    const s = result.current.data!;
    for (const field of ['trade_mode', 'risk_per_trade_pct', 'daily_loss_limit_pct',
                          'max_concurrent_positions', 'decision_threshold']) {
      expect(s).toHaveProperty(field);
    }
  });
});

// ── useUpdateSettings hook ────────────────────────────────────────────────────
describe('useUpdateSettings', () => {
  it('sends PUT request with updated values', async () => {
    let capturedBody: any = null;

    server.use(
      http.put('/api/v1/settings', async ({ request }) => {
        capturedBody = await request.json();
        return HttpResponse.json({ ...mockSettings, ...(capturedBody as object) });
      })
    );

    const { useUpdateSettings } = await import('../features/settings/hooks');
    const { result } = renderHook(() => useUpdateSettings(), { wrapper });

    result.current.mutate({ ...mockSettings, risk_per_trade_pct: 2.0 });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(capturedBody).toMatchObject({ risk_per_trade_pct: 2.0 });
  });
});

// ── WatchList API ─────────────────────────────────────────────────────────────
describe('watchlist API', () => {
  it('GET /watchlist returns array', async () => {
    const { apiClient } = await import('../services/api');
    const response = await apiClient.get('/v1/watchlist');
    expect(Array.isArray(response.data)).toBe(true);
  });

  it('POST /watchlist adds instrument', async () => {
    const { apiClient } = await import('../services/api');
    const response = await apiClient.post('/v1/watchlist',
      { instrument_id: 'TQBR:YNDX' });
    expect(response.data).toHaveProperty('instrument_id', 'TQBR:YNDX');
  });
});
