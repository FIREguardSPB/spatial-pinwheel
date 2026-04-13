import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import { ConfirmModal } from '../../../components/ui/UIComponents';
import { Surface, StatusChip, ValueRow } from '../../core/PageBlocks';
import { fmtDateTime } from '../../core/format';
import type { RiskSettings, SettingsPreset, SettingsPresetApplyResponse, SettingsPresetListResponse, SettingsPresetMutationResponse } from '../../../types';
import { applySettingsPreset, createSettingsPreset, deleteSettingsPreset, listSettingsPresets } from '../../../services/api';

const LABELS: Record<string, string> = {
  risk_profile: 'Профиль риска',
  risk_per_trade_pct: 'Риск на сделку, %',
  daily_loss_limit_pct: 'Дневной лимит потерь, %',
  max_concurrent_positions: 'Макс. позиций',
  max_trades_per_day: 'Макс. сделок в день',
  trade_mode: 'Режим торговли',
  ai_mode: 'Режим AI',
  ai_min_confidence: 'Мин. уверенность AI',
  decision_threshold: 'Decision threshold',
  rr_min: 'Минимальный RR',
  rr_target: 'Целевой RR',
  ml_enabled: 'ML overlay',
  ml_take_probability_threshold: 'ML take threshold',
  ml_fill_probability_threshold: 'ML fill threshold',
  ml_allow_take_veto: 'ML take veto',
  signal_reentry_cooldown_sec: 'Cooldown re-entry',
  worker_bootstrap_limit: 'Worker bootstrap limit',
  trading_session: 'Торговая сессия',
  watchlist: 'Watchlist',
};

function summarizeDiff(currentSettings: RiskSettings | null, currentWatchlist: string[], preset: SettingsPreset | null, limit = 5): string[] {
  if (!preset || !currentSettings) return [];
  const lines: string[] = [];
  for (const [key, value] of Object.entries(preset.settings_json ?? {})) {
    if (lines.length >= limit) break;
    if (key === 'watchlist') {
      const next = Array.isArray(value) ? value : [];
      if (JSON.stringify(currentWatchlist) !== JSON.stringify(next)) lines.push(`${LABELS[key] ?? key}: ${currentWatchlist.length} → ${next.length} бумаг`);
      continue;
    }
    const currentValue = (currentSettings as unknown as Record<string, unknown>)[key];
    if (JSON.stringify(currentValue) === JSON.stringify(value)) continue;
    lines.push(`${LABELS[key] ?? key}: ${String(currentValue ?? '—')} → ${String(value ?? '—')}`);
  }
  return lines;
}

function SavePresetModal({ onClose, onSubmit, loading }: { onClose: () => void; onSubmit: (payload: { name: string; description: string }) => void; loading: boolean; }) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="w-full max-w-lg rounded-2xl border border-gray-700 bg-gray-900 p-6 shadow-2xl">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h3 className="text-lg font-semibold text-white">Сохранить текущую конфигурацию</h3>
            <p className="mt-1 text-sm text-gray-400">Создаётся snapshot live settings без секретов и runtime-only полей.</p>
          </div>
          <button type="button" onClick={onClose} className="rounded-lg border border-gray-700 bg-gray-800 px-3 py-1.5 text-sm text-gray-300 hover:bg-gray-700">Закрыть</button>
        </div>
        <div className="mt-5 space-y-4">
          <label className="block text-sm text-gray-300"><span className="mb-1 block">Имя preset</span><input value={name} onChange={(e) => setName(e.target.value)} className="w-full rounded-xl border border-gray-700 bg-gray-950 px-3 py-2 text-white outline-none focus:border-blue-500" placeholder="Например, Sniper intraday" /></label>
          <label className="block text-sm text-gray-300"><span className="mb-1 block">Описание</span><textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3} className="w-full rounded-xl border border-gray-700 bg-gray-950 px-3 py-2 text-white outline-none focus:border-blue-500" placeholder="Что это за конфигурация и когда её применять" /></label>
        </div>
        <div className="mt-5 flex justify-end gap-3">
          <button type="button" onClick={onClose} className="rounded-lg border border-gray-700 bg-gray-800 px-4 py-2 text-sm text-gray-300 hover:bg-gray-700">Отмена</button>
          <button type="button" disabled={loading} onClick={() => { if (!name.trim()) { toast.error('Укажи имя preset'); return; } onSubmit({ name: name.trim(), description: description.trim() }); }} className="rounded-lg bg-blue-700 px-4 py-2 text-sm font-medium text-white hover:bg-blue-600 disabled:opacity-60">{loading ? 'Сохранение…' : 'Сохранить snapshot'}</button>
        </div>
      </div>
    </div>
  );
}

export function PresetsPanel({ currentSettings, currentWatchlist, onRefresh }: { currentSettings: RiskSettings | null; currentWatchlist: string[]; onRefresh: () => void; }) {
  const qc = useQueryClient();
  const [selectedId, setSelectedId] = useState('');
  const [saveOpen, setSaveOpen] = useState(false);
  const [confirmApply, setConfirmApply] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const presetsQuery = useQuery<SettingsPresetListResponse>({ queryKey: ['settings', 'presets'], queryFn: listSettingsPresets, staleTime: 0 });
  const createMutation = useMutation<SettingsPresetMutationResponse, any, { name: string; description?: string }>({ mutationFn: createSettingsPreset, onSuccess: async (data) => { toast.success(data.created === false ? 'Preset обновлён из текущих настроек' : 'Preset сохранён'); setSaveOpen(false); await qc.invalidateQueries({ queryKey: ['settings', 'presets'] }); if (data.preset?.id) setSelectedId(data.preset.id); onRefresh(); } });
  const applyMutation = useMutation<SettingsPresetApplyResponse, any, string>({ mutationFn: applySettingsPreset, onSuccess: async (data) => { toast.success(`Preset ${data.preset.name} применён`); setConfirmApply(false); await qc.invalidateQueries({ queryKey: ['settings', 'presets'] }); onRefresh(); } });
  const deleteMutation = useMutation<any, any, string>({ mutationFn: deleteSettingsPreset, onSuccess: async () => { toast.success('Preset удалён'); setConfirmDelete(false); setSelectedId(''); await qc.invalidateQueries({ queryKey: ['settings', 'presets'] }); onRefresh(); } });
  const presets = presetsQuery.data?.items ?? [];
  const selectedPreset = useMemo(() => presets.find((item) => item.id === selectedId) ?? presets[0] ?? null, [presets, selectedId]);
  const diffSummary = useMemo(() => summarizeDiff(currentSettings, currentWatchlist, selectedPreset), [currentSettings, currentWatchlist, selectedPreset]);
  useEffect(() => { if (!presets.length) { if (selectedId) setSelectedId(''); return; } if (!selectedId || !presets.some((item) => item.id === selectedId)) setSelectedId(presets[0].id); }, [presets, selectedId]);
  return (<>
    <Surface title="Presets конфигурации" description="Быстрые snapshots безопасной части settings. Секреты и runtime-only поля в preset не попадают." right={<StatusChip tone="blue">{presets.length} preset{presets.length === 1 ? '' : 's'}</StatusChip>}>
      <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
        <div className="space-y-4">
          <label className="block text-sm text-gray-300"><span className="mb-1 block">Доступные presets</span><select aria-label="Доступные presets" value={selectedPreset?.id ?? ''} onChange={(e) => setSelectedId(e.target.value)} className="w-full rounded-xl border border-gray-700 bg-gray-950 px-3 py-2 text-white outline-none focus:border-blue-500">{presets.map((preset) => <option key={preset.id} value={preset.id}>{preset.name}{preset.is_system ? ' · system' : ''}</option>)}</select></label>
          <div className="flex flex-wrap gap-2">
            <button type="button" onClick={() => setSaveOpen(true)} className="rounded-lg bg-blue-700 px-3 py-2 text-sm font-medium text-white hover:bg-blue-600">Сохранить текущую как…</button>
            <button type="button" disabled={!selectedPreset || applyMutation.isPending} onClick={() => setConfirmApply(true)} className="rounded-lg bg-emerald-700 px-3 py-2 text-sm font-medium text-white hover:bg-emerald-600 disabled:opacity-60">{applyMutation.isPending ? 'Применение…' : 'Применить'}</button>
            <button type="button" disabled={!selectedPreset || selectedPreset.is_system || deleteMutation.isPending} onClick={() => setConfirmDelete(true)} className="rounded-lg bg-rose-700 px-3 py-2 text-sm font-medium text-white hover:bg-rose-600 disabled:opacity-60">{deleteMutation.isPending ? 'Удаление…' : 'Удалить'}</button>
            <button type="button" onClick={() => presetsQuery.refetch()} className="rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-200 hover:bg-gray-700">Обновить список</button>
          </div>
          {presetsQuery.isLoading ? <div className="text-sm text-gray-400">Загрузка presets…</div> : null}
          {presetsQuery.isError ? <div className="text-sm text-rose-300">Не удалось загрузить presets</div> : null}
        </div>
        <div className="rounded-xl border border-gray-800 bg-gray-950/70 p-4">{selectedPreset ? <div className="space-y-2 text-sm"><div className="flex items-center gap-2"><div className="text-base font-semibold text-white">{selectedPreset.name}</div><StatusChip tone={selectedPreset.is_system ? 'warn' : 'good'}>{selectedPreset.is_system ? 'system' : 'user'}</StatusChip></div><ValueRow label="Описание" value={selectedPreset.description || '—'} /><ValueRow label="Создан" value={fmtDateTime(selectedPreset.created_at)} /><ValueRow label="Обновлён" value={fmtDateTime(selectedPreset.updated_at)} /><ValueRow label="Ключей в snapshot" value={Object.keys(selectedPreset.settings_json ?? {}).length} /><div className="pt-2"><div className="mb-2 text-xs uppercase tracking-wide text-gray-500">Что изменится при apply</div>{diffSummary.length ? <ul className="space-y-1 text-sm text-gray-300">{diffSummary.map((line) => <li key={line}>• {line}</li>)}</ul> : <div className="text-sm text-gray-500">С выбранным preset сейчас нет видимых отличий.</div>}</div></div> : <div className="text-sm text-gray-500">Presets пока не загружены.</div>}</div>
      </div>
    </Surface>
    {saveOpen ? <SavePresetModal onClose={() => setSaveOpen(false)} loading={createMutation.isPending} onSubmit={(payload) => createMutation.mutate(payload)} /> : null}
    {confirmApply && selectedPreset ? <ConfirmModal title={`Применить preset ${selectedPreset.name}?`} description={diffSummary.length ? diffSummary.join(' · ') : 'Изменения минимальны или уже совпадают с текущими значениями.'} confirmLabel="Применить preset" cancelLabel="Отмена" variant="warning" onCancel={() => setConfirmApply(false)} onConfirm={() => applyMutation.mutate(selectedPreset.id)} /> : null}
    {confirmDelete && selectedPreset ? <ConfirmModal title={`Удалить preset ${selectedPreset.name}?`} description="Системные presets удалить нельзя. Пользовательский preset будет удалён без возможности восстановления." confirmLabel="Удалить" cancelLabel="Отмена" variant="danger" onCancel={() => setConfirmDelete(false)} onConfirm={() => deleteMutation.mutate(selectedPreset.id)} /> : null}
  </>);
}
