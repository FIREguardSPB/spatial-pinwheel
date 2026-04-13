import { describe, it, expect } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { server } from './setup';
import { http, HttpResponse } from 'msw';
import { PresetsPanel } from '../features/settings/components/PresetsPanel';
import { mockSettings, mockPresets } from '../mocks/handlers';

function renderWithQuery(ui: React.ReactElement) { const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } }); return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>); }

describe('PresetsPanel', () => {
  it('loads presets list and shows selected preset details', async () => {
    renderWithQuery(<PresetsPanel currentSettings={mockSettings as any} currentWatchlist={['TQBR:SBER']} onRefresh={() => undefined} />);
    await waitFor(() => expect(screen.getByText(/Presets конфигурации/i)).toBeInTheDocument());
    await waitFor(() => expect(screen.getByDisplayValue(/Balanced/i)).toBeInTheDocument());
    expect(screen.getByText(/Baseline paper preset/i)).toBeInTheDocument();
  });

  it('creates preset from current settings', async () => {
    let called = false;
    server.use(http.post('/api/v1/settings/presets', async ({ request }: any) => { called = true; const body = await request.json(); return HttpResponse.json({ preset: { id: 'preset_custom_test', name: body.name, description: body.description || '', settings_json: { ...mockSettings, watchlist: ['TQBR:SBER'] }, created_at: Date.now(), updated_at: Date.now(), is_system: false }, created: true }); }));
    renderWithQuery(<PresetsPanel currentSettings={mockSettings as any} currentWatchlist={['TQBR:SBER']} onRefresh={() => undefined} />);
    await waitFor(() => expect(screen.getByRole('button', { name: /Сохранить текущую как/i })).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: /Сохранить текущую как/i }));
    fireEvent.change(screen.getByPlaceholderText(/Например, Sniper intraday/i), { target: { value: 'My preset' } });
    fireEvent.change(screen.getByPlaceholderText(/Что это за конфигурация/i), { target: { value: 'Test description' } });
    fireEvent.click(screen.getByRole('button', { name: /Сохранить snapshot/i }));
    await waitFor(() => expect(called).toBe(true));
  });

  it('applies selected user preset', async () => {
    let applyCalled = false;
    server.use(http.post('/api/v1/settings/presets/:id/apply', ({ params }: any) => { applyCalled = true; const preset = mockPresets.find((item) => item.id === params.id) || mockPresets[1]; return HttpResponse.json({ ok: true, preset, applied: { changed_keys: ['risk_profile'], diff_summary: ['Профиль риска: balanced → conservative'] } }); }));
    renderWithQuery(<PresetsPanel currentSettings={mockSettings as any} currentWatchlist={['TQBR:SBER']} onRefresh={() => undefined} />);
    await waitFor(() => expect(screen.getByDisplayValue(/Balanced/i)).toBeInTheDocument());
    fireEvent.change(screen.getByLabelText(/Доступные presets/i), { target: { value: 'preset_user_sniper' } });
    fireEvent.click(screen.getByRole('button', { name: /^Применить$/i }));
    await waitFor(() => expect(screen.getByText(/Применить preset Sniper intraday/i)).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: /Применить preset/i }));
    await waitFor(() => expect(applyCalled).toBe(true));
  });
});
