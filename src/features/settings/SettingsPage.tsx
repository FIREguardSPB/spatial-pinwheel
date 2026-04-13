import { useEffect, useMemo, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { PageShell, QueryBlock, RetryButton, StatusChip, Surface, ValueRow } from '../core/PageBlocks';
import { fmtBool, fmtDateTime, fmtMode } from '../core/format';
import { useStartBot, useStopBot, useSyncTradingSchedule, useUpdateSettings } from '../core/queries';
import { useEventRegimeView, useRuntimeOverview, useSymbolProfileView, useUiSettings } from '../core/uiQueries';
import { useTestTelegram } from './hooks';
import { WorkerAnalysisInspector } from '../system/WorkerAnalysisInspector';
import { PresetsPanel } from './components/PresetsPanel';
import { useAppStore } from '../../store';
import type { RiskSettings } from '../../types';

const TABS = [
  ['overview', 'Обзор'],
  ['trading', 'Торговля'],
  ['risk', 'Риск'],
  ['ai', 'AI'],
  ['telegram', 'Telegram'],
  ['automation', 'Автоматика'],
  ['papers', 'Бумаги'],
] as const;

type TabKey = typeof TABS[number][0];

function textValue(value: unknown): string {
  if (value === null || value === undefined) return '';
  return String(value);
}

function jsonText(value: unknown): string {
  if (value === null || value === undefined) return 'не загружено';
  if (typeof value === 'object' && value && Object.keys(value as Record<string, unknown>).length === 0) return 'данных нет';
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}


type RuntimeCardStatus = 'loading' | 'error' | 'empty' | 'idle' | 'loaded';

type RuntimeCardState = { status: RuntimeCardStatus; value: unknown };

function runtimeBlockValue(query: { isLoading: boolean; isError: boolean; error?: unknown }, value: unknown): RuntimeCardState {
  if (query.isLoading) return { status: 'loading', value: null };
  if (query.isError) {
    const message = query.error instanceof Error ? query.error.message : String(query.error || 'не загрузилось');
    return { status: 'error', value: message };
  }
  if (value && typeof value === 'object' && 'status' in (value as Record<string, unknown>)) {
    const marker = String((value as Record<string, unknown>).status || '');
    if (marker === 'loading') return { status: 'loading', value };
    if (marker === 'error') return { status: 'error', value };
    if (marker === 'idle' || marker === 'empty' || marker === 'missing') return { status: 'idle', value };
    return { status: 'loaded', value };
  }
  if (value === null || value === undefined) return { status: 'empty', value: null };
  if (typeof value === 'string') {
    const trimmed = value.trim().toLowerCase();
    if (!trimmed) return { status: 'empty', value: null };
    if (trimmed.includes('не загруз')) return { status: 'error', value };
    if (trimmed.includes('данных нет') || trimmed.includes('no active')) return { status: 'empty', value };
    return { status: 'loaded', value };
  }
  if (typeof value === 'object' && value && Object.keys(value as Record<string, unknown>).length === 0) return { status: 'empty', value };
  return { status: 'loaded', value };
}

function NumberField({ label, value, onChange, step = 1 }: { label: string; value: number | undefined; onChange: (value: number) => void; step?: number }) {
  return (
    <label className="space-y-1 text-sm">
      <div className="text-gray-400">{label}</div>
      <input type="number" value={value ?? ''} onChange={(e) => onChange(Number(e.target.value))} step={step} className="w-full rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-white" />
    </label>
  );
}

function TextField({
  label,
  value,
  onChange,
  name,
  placeholder,
  testId,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  name?: string;
  placeholder?: string;
  testId?: string;
}) {
  return (
    <label className="space-y-1 text-sm">
      <div className="text-gray-400">{label}</div>
      <input
        name={name}
        placeholder={placeholder}
        data-testid={testId}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-white"
      />
    </label>
  );
}

function SelectField({ label, value, onChange, options }: { label: string; value: string; onChange: (value: string) => void; options: Array<[string, string]> }) {
  return (
    <label className="space-y-1 text-sm">
      <div className="text-gray-400">{label}</div>
      <select value={value} onChange={(e) => onChange(e.target.value)} className="w-full rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-white">
        {options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
      </select>
    </label>
  );
}

function ToggleField({ label, checked, onChange }: { label: string; checked: boolean; onChange: (next: boolean) => void }) {
  return (
    <label className="flex items-center gap-3 rounded-lg border border-gray-800 bg-gray-950/60 px-3 py-2 text-sm text-gray-200">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} className="h-4 w-4" />
      <span>{label}</span>
    </label>
  );
}

export default function SettingsPage() {
  const selectedInstrument = useAppStore((s) => s.selectedInstrument);
  const setSelectedInstrument = useAppStore((s) => s.setSelectedInstrument);
  const page = useUiSettings();
  const saveMutation = useUpdateSettings();
  const startBot = useStartBot();
  const stopBot = useStopBot();
  const syncSchedule = useSyncTradingSchedule();
  const qc = useQueryClient();
  const [tab, setTab] = useState<TabKey>('overview');
  const [form, setForm] = useState<RiskSettings | null>(null);

  const runtime = page.data?.runtime;
  const settings = runtime?.settings;
  const botStatus = runtime?.bot_status;
  const workerStatus = runtime?.worker_status;
  const schedule = runtime?.schedule;
  const watchlist = useMemo(() => runtime?.watchlist ?? [], [runtime?.watchlist]);
  const overview = runtime?.runtime_overview ?? null;
  const aiRuntime = runtime?.ai_runtime ?? null;
  const telegramRuntime = runtime?.telegram ?? null;
  const autoPolicyRuntime = runtime?.auto_policy ?? null;
  const mlRuntime = runtime?.ml_runtime ?? null;
  const pipelineCounters = runtime?.pipeline_counters ?? null;
  const testTelegram = useTestTelegram();

  useEffect(() => {
    if (settings) setForm(settings);
  }, [settings]);

  useEffect(() => {
    if (!watchlist.length) return;
    if (!watchlist.some((item) => item.instrument_id === selectedInstrument)) {
      setSelectedInstrument(watchlist[0].instrument_id);
    }
  }, [watchlist, selectedInstrument, setSelectedInstrument]);

  const currentMode = botStatus?.mode ?? form?.trade_mode ?? 'review';
  const isRunning = Boolean(botStatus?.is_running);

  const patch = (next: Partial<RiskSettings>) => setForm((prev) => ({ ...(prev ?? settings ?? {} as RiskSettings), ...next }));

  const reloadAll = () => {
    qc.invalidateQueries({ queryKey: ['ui'] });
    qc.invalidateQueries({ queryKey: ['settings', 'runtime-overview'] });
    page.refetch();
  };

  const sourceNotes = useMemo(() => {
    if (tab !== 'papers') return 'детальный runtime overview загружается только на вкладке «Бумаги»';
    return overview?.source_notes?.join(' · ') || 'runtime overview по бумаге загружается по запросу';
  }, [overview, tab]);

  return (
    <PageShell
      title="Настройки"
      subtitle="Coordinator-first форма: страница грузится одним bootstrap-запросом и уже внутри показывает разложенные по сущностям настройки и runtime."
      actions={
        <>
          <RetryButton label="Обновить" onClick={reloadAll} />
          <button onClick={async () => { await syncSchedule.mutateAsync(); qc.invalidateQueries({ queryKey: ['ui'] }); }} className="rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-200">Синхронизировать расписание</button>
          <button onClick={async () => { await startBot.mutateAsync(currentMode as any); qc.invalidateQueries({ queryKey: ['ui'] }); }} disabled={startBot.isPending || isRunning} className={`rounded-lg px-3 py-2 text-sm font-medium text-white ${isRunning ? 'bg-emerald-900/70' : 'bg-emerald-600 hover:bg-emerald-500'} disabled:opacity-60`}>{startBot.isPending ? 'Запуск…' : isRunning ? 'Запущен' : 'Запустить'}</button>
          <button onClick={async () => { await stopBot.mutateAsync(); qc.invalidateQueries({ queryKey: ['ui'] }); }} disabled={stopBot.isPending || !isRunning} className={`rounded-lg px-3 py-2 text-sm font-medium text-white ${!isRunning ? 'bg-rose-900/70' : 'bg-rose-600 hover:bg-rose-500'} disabled:opacity-60`}>{stopBot.isPending ? 'Остановка…' : !isRunning ? 'Остановлен' : 'Остановить'}</button>
          <button onClick={async () => { if (form) { await saveMutation.mutateAsync(form); qc.invalidateQueries({ queryKey: ['ui'] }); } }} disabled={!form || saveMutation.isPending} className="rounded-lg bg-blue-700 px-3 py-2 text-sm font-medium text-white disabled:opacity-60">{saveMutation.isPending ? 'Сохранение…' : 'Сохранить'}</button>
        </>
      }
    >
      <div className="flex flex-wrap gap-2">
        {TABS.map(([key, label]) => (
          <button key={key} onClick={() => setTab(key)} className={`rounded-xl border px-4 py-2 text-sm ${tab === key ? 'border-blue-500/40 bg-blue-500/10 text-blue-300' : 'border-gray-700 bg-gray-950 text-gray-200'}`}>{label}</button>
        ))}
      </div>

      <QueryBlock isLoading={page.isLoading && !page.data} isError={page.isError && !page.data} errorMessage="Не удалось загрузить bootstrap настройки" onRetry={reloadAll}>
        <PresetsPanel currentSettings={form} currentWatchlist={watchlist.map((item) => item.instrument_id)} onRefresh={reloadAll} />
        {tab === 'overview' ? (
          <div className="space-y-4">
            <div className="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
              <Surface title="Runtime и рынок" description="То, что backend и worker реально видят сейчас.">
                <div className="space-y-2">
                  <ValueRow label="Статус бота" value={(<StatusChip tone={isRunning ? 'good' : 'warn'}>{isRunning ? 'Запущен' : 'Остановлен'}</StatusChip>)} />
                  <ValueRow label="Режим" value={(<StatusChip tone="blue">{fmtMode(currentMode)}</StatusChip>)} />
                  <ValueRow label="Воркер" value={(<StatusChip tone={workerStatus?.ok ? 'good' : 'warn'}>{String(workerStatus?.ok ? (workerStatus?.phase || 'ok') : 'Нет heartbeat')}</StatusChip>)} />
                  <ValueRow label="PID" value={workerStatus?.pid ?? '—'} />
                  <ValueRow label="Торговый день" value={schedule?.trading_day ?? '—'} />
                  <ValueRow label="Источник расписания" value={schedule?.warning ? `${schedule?.source || 'static'} · fallback` : (schedule?.source ?? '—')} />
                  <ValueRow label="Следующее открытие" value={fmtDateTime(schedule?.next_open)} />
                  <ValueRow label="Открыт ли рынок" value={fmtBool(schedule?.is_open, 'Да', 'Нет')} />
                  <ValueRow label="Runtime notes" value={sourceNotes} />
                </div>
              </Surface>
              <Surface title="Контуры управления" description="Автополитика, governor, ML и Telegram статус.">
                <div className="space-y-3">
                  <JsonCard title="AI runtime" state={runtimeBlockValue({ isLoading: false, isError: false }, aiRuntime)} />
                  <JsonCard title="ML runtime" state={runtimeBlockValue({ isLoading: false, isError: false }, mlRuntime)} />
                  <JsonCard title="Защитный контур" state={runtimeBlockValue({ isLoading: false, isError: false }, autoPolicyRuntime)} />
                  <JsonCard title="Telegram" state={runtimeBlockValue({ isLoading: false, isError: false }, telegramRuntime)} />
                </div>
              </Surface>
            </div>
            <Surface title="Профилирование worker pipeline" description="Видно, где бот тратит время на анализ и какой кейс был самым медленным.">
              <WorkerAnalysisInspector workerStatus={workerStatus} />
            </Surface>
          </div>
        ) : null}

        {tab === 'trading' ? (
          <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
            <Surface title="Торговый движок" description="Базовые параметры принятия решения и режима работы.">
              <div className="grid gap-4 md:grid-cols-2">
                <SelectField label="Режим торговли" value={textValue(form?.trade_mode ?? 'auto_paper')} onChange={(value) => patch({ trade_mode: value as RiskSettings['trade_mode'] })} options={[['review', 'Ручное ревью'], ['auto_paper', 'Paper'], ['auto_live', 'Live']]} />
                <SelectField label="Профиль риска" value={textValue(form?.risk_profile ?? 'balanced')} onChange={(value) => patch({ risk_profile: value as RiskSettings['risk_profile'] })} options={[['conservative', 'Conservative'], ['balanced', 'Balanced'], ['aggressive', 'Aggressive']]} />
                <TextField label="Стратегии" value={textValue(form?.strategy_name)} onChange={(value) => patch({ strategy_name: value })} />
                <TextField label="Higher timeframe" value={textValue(form?.higher_timeframe)} onChange={(value) => patch({ higher_timeframe: value })} />
                <NumberField label="Decision threshold" value={form?.decision_threshold} onChange={(value) => patch({ decision_threshold: value })} />
                <NumberField label="RR min" value={form?.rr_min} onChange={(value) => patch({ rr_min: value })} step={0.1} />
                <NumberField label="RR target" value={form?.rr_target} onChange={(value) => patch({ rr_target: value })} step={0.1} />
                <NumberField label="Signal reentry cooldown, sec" value={form?.signal_reentry_cooldown_sec} onChange={(value) => patch({ signal_reentry_cooldown_sec: value })} />
                <NumberField label="Worker bootstrap limit" value={form?.worker_bootstrap_limit} onChange={(value) => patch({ worker_bootstrap_limit: value })} />
                <NumberField label="Paper balance" value={form?.account_balance} onChange={(value) => patch({ account_balance: value })} step={1000} />
                <SelectField label="Торговая сессия" value={textValue(form?.trading_session ?? 'all')} onChange={(value) => patch({ trading_session: value as RiskSettings['trading_session'] })} options={[['all', 'All'], ['main', 'Main'], ['main_only', 'Main only'], ['evening', 'Evening']]} />
                <TextField label="Биржа для расписания" value={textValue(form?.trading_schedule_exchange || 'MOEX')} onChange={(value) => patch({ trading_schedule_exchange: value })} />
              </div>
              <div className="mt-4">
                <ToggleField label="Использовать брокерское расписание" checked={Boolean(form?.use_broker_trading_schedule)} onChange={(checked) => patch({ use_broker_trading_schedule: checked })} />
              </div>
            </Surface>
            <Surface title="Справка по рынку" description="Расписание и сессии из backend.">
              <div className="space-y-2">
                <ValueRow label="Текущий день" value={schedule?.trading_day ?? '—'} />
                <ValueRow label="Рабочий день" value={(<StatusChip tone={schedule?.is_trading_day ? 'good' : 'warn'}>{fmtBool(schedule?.is_trading_day, 'Да', 'Нет')}</StatusChip>)} />
                <ValueRow label="Сессия" value={`${fmtDateTime(schedule?.current_session_start)} → ${fmtDateTime(schedule?.current_session_end)}`} />
                <ValueRow label="Следующее открытие" value={fmtDateTime(schedule?.next_open)} />
                <ValueRow label="Источник" value={schedule?.warning ? `${schedule?.source || 'static'} fallback` : (schedule?.source ?? '—')} />
                <ValueRow label="Техническая заметка" value={schedule?.warning || '—'} />
              </div>
            </Surface>
          </div>
        ) : null}

        {tab === 'risk' ? (
          <div className="grid gap-4 xl:grid-cols-2">
            <Surface title="Основные лимиты риска" description="Глобальные guardrails счёта.">
              <div className="grid gap-4 md:grid-cols-2">
                <NumberField label="Risk per trade, %" value={form?.risk_per_trade_pct} onChange={(value) => patch({ risk_per_trade_pct: value })} step={0.05} />
                <NumberField label="Daily loss limit, %" value={form?.daily_loss_limit_pct} onChange={(value) => patch({ daily_loss_limit_pct: value })} step={0.1} />
                <NumberField label="Max concurrent positions" value={form?.max_concurrent_positions} onChange={(value) => patch({ max_concurrent_positions: value })} />
                <NumberField label="Max trades per day" value={form?.max_trades_per_day} onChange={(value) => patch({ max_trades_per_day: value })} />
                <NumberField label="Max position notional, %" value={form?.max_position_notional_pct_balance} onChange={(value) => patch({ max_position_notional_pct_balance: value })} step={0.5} />
                <NumberField label="Max total exposure, %" value={form?.max_total_exposure_pct_balance} onChange={(value) => patch({ max_total_exposure_pct_balance: value })} step={0.5} />
              </div>
            </Surface>
            <Surface title="Runtime protective status" description="Чтобы было ясно, это реальные прочерки или просто ещё не загрузилось.">
              <div className="space-y-3">
                <JsonCard title="Auto policy runtime" state={runtimeBlockValue({ isLoading: false, isError: false }, autoPolicyRuntime)} />
                <JsonCard title="Pipeline counters" state={runtimeBlockValue({ isLoading: false, isError: false }, pipelineCounters)} />
              </div>
            </Surface>
          </div>
        ) : null}

        {tab === 'ai' ? (
          <div className="grid gap-4 xl:grid-cols-2">
            <Surface title="AI-настройки" description="Гибкие настройки AI отдельно от остального движка.">
              <div className="grid gap-4 md:grid-cols-2">
                <SelectField label="Режим AI" value={textValue(form?.ai_mode ?? 'off')} onChange={(value) => patch({ ai_mode: value as RiskSettings['ai_mode'] })} options={[['off', 'Off'], ['advisory', 'Advisory'], ['override', 'Override'], ['required', 'Required']]} />
                <NumberField label="Мин. уверенность AI, %" value={form?.ai_min_confidence} onChange={(value) => patch({ ai_min_confidence: value })} step={1} />
                <TextField label="Основной AI provider" value={textValue(form?.ai_primary_provider)} onChange={(value) => patch({ ai_primary_provider: value })} />
                <TextField label="Fallback providers" value={textValue(form?.ai_fallback_providers)} onChange={(value) => patch({ ai_fallback_providers: value })} />
              </div>
            </Surface>
            <Surface title="AI runtime" description="То, что backend реально знает про AI сейчас.">
              <JsonCard title="AI runtime payload" state={runtimeBlockValue({ isLoading: false, isError: false }, aiRuntime)} />
            </Surface>
          </div>
        ) : null}

        {tab === 'telegram' ? (
          <div className="grid gap-4 xl:grid-cols-2">
            <Surface title="Telegram-уведомления" description="Статус канала и базовые токены задаются через раздел токенов.">
              <div className="grid gap-4 md:grid-cols-2">
                <TextField
                  label="Telegram bot token"
                  name="telegram_bot_token"
                  placeholder="Telegram bot token"
                  testId="telegram-bot-token"
                  value={textValue(form?.telegram_bot_token)}
                  onChange={(value) => patch({ telegram_bot_token: value })}
                />
                <TextField
                  label="Telegram chat id"
                  name="telegram_chat_id"
                  placeholder="Telegram chat id"
                  testId="telegram-chat-id"
                  value={textValue(form?.telegram_chat_id)}
                  onChange={(value) => patch({ telegram_chat_id: value })}
                />
              </div>
              <div className="mt-6 space-y-4">
                <div className="text-sm font-semibold text-gray-200">События для уведомлений</div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {[
                    { id: 'signal_created', label: '📡 Новый сигнал' },
                    { id: 'trade_executed', label: '✅ Сделка открыта' },
                    { id: 'sl_hit', label: '🛑 Стоп-лосс' },
                    { id: 'tp_hit', label: '🎯 Тейк-профит' },
                    { id: 'daily_loss_limit_reached', label: '⚠️ Дневной лимит потерь' },
                  ].map((event) => {
                    const currentEvents = (form?.notification_events || '').split(',').filter(Boolean);
                    const checked = currentEvents.includes(event.id);
                    return (
                      <label key={event.id} className="flex items-center space-x-2 cursor-pointer text-sm text-gray-300">
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={() => {
                            const newEvents = checked
                              ? currentEvents.filter((e) => e !== event.id)
                              : [...currentEvents, event.id];
                            patch({ notification_events: newEvents.join(',') });
                          }}
                          className="rounded border-gray-600 bg-gray-800 text-sky-500 focus:ring-sky-500 focus:ring-offset-gray-900"
                        />
                        <span>{event.label}</span>
                      </label>
                    );
                  })}
                </div>
                <div className="pt-4">
                  <div className="text-sm font-semibold text-gray-200 mb-2">Тест отправки</div>
                  <button
                    onClick={() => testTelegram.mutate(undefined)}
                    disabled={testTelegram.isPending}
                    className="inline-flex items-center px-4 py-2 rounded-lg bg-sky-700 hover:bg-sky-600 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium text-sm transition-colors"
                  >
                    {testTelegram.isPending ? 'Отправка...' : 'Отправить тестовое сообщение'}
                  </button>
                  {testTelegram.isSuccess && (
                    <div className="mt-2 text-sm text-emerald-400">✅ Тестовое сообщение отправлено</div>
                  )}
                  {testTelegram.isError && (
                    <div className="mt-2 text-sm text-rose-400">❌ {testTelegram.error instanceof Error ? testTelegram.error.message : 'Ошибка отправки'}</div>
                  )}
                </div>
              </div>
            </Surface>
            <Surface title="Telegram runtime" description="Подтверждение, что backend видит Telegram сущность.">
              <JsonCard title="Telegram payload" state={runtimeBlockValue({ isLoading: false, isError: false }, telegramRuntime)} />
            </Surface>
          </div>
        ) : null}

        {tab === 'automation' ? (
          <div className="grid gap-4 xl:grid-cols-2">
            <Surface title="Автоматика" description="Governor, allocator, ML и symbol recalibration.">
              <div className="grid gap-4 md:grid-cols-2">
                <ToggleField label="Auto degrade" checked={Boolean(form?.auto_degrade_enabled)} onChange={(checked) => patch({ auto_degrade_enabled: checked })} />
                <ToggleField label="Capital allocator" checked={Boolean((form as any)?.capital_allocator_enabled)} onChange={(checked) => patch({ capital_allocator_enabled: checked } as Partial<RiskSettings>)} />
                <ToggleField label="Adaptive exit" checked={Boolean((form as any)?.adaptive_exit_enabled)} onChange={(checked) => patch({ adaptive_exit_enabled: checked } as Partial<RiskSettings>)} />
                <ToggleField label="ML enabled" checked={Boolean(form?.ml_enabled)} onChange={(checked) => patch({ ml_enabled: checked })} />
                <ToggleField label="ML retrain" checked={Boolean(form?.ml_retrain_enabled)} onChange={(checked) => patch({ ml_retrain_enabled: checked })} />
                <ToggleField label="Symbol recalibration" checked={Boolean(form?.symbol_recalibration_enabled)} onChange={(checked) => patch({ symbol_recalibration_enabled: checked })} />
                <NumberField label="Governor lookback, days" value={form?.performance_governor_lookback_days} onChange={(value) => patch({ performance_governor_lookback_days: value })} />
                <NumberField label="ML lookback, days" value={form?.ml_lookback_days} onChange={(value) => patch({ ml_lookback_days: value })} />
                <NumberField label="ML retrain interval, h" value={form?.ml_retrain_interval_hours} onChange={(value) => patch({ ml_retrain_interval_hours: value })} />
                <NumberField label="ML retrain hour (MSK)" value={form?.ml_retrain_hour_msk} onChange={(value) => patch({ ml_retrain_hour_msk: value })} />
              </div>
            </Surface>
            <Surface title="Runtime защитного контура / ML" description="Здесь не прочерки, а явное состояние или текст 'данных нет'.">
              <div className="space-y-3">
                <JsonCard title="Auto policy" state={runtimeBlockValue({ isLoading: false, isError: false }, autoPolicyRuntime)} />
                <JsonCard title="ML runtime" state={runtimeBlockValue({ isLoading: false, isError: false }, mlRuntime)} />
              </div>
            </Surface>
          </div>
        ) : null}

        {tab === 'papers' ? (
          <PapersRuntimePanel
            selectedInstrument={selectedInstrument}
            setSelectedInstrument={setSelectedInstrument}
            watchlist={watchlist}
          />
        ) : null}
      </QueryBlock>
    </PageShell>
  );
}


function PapersRuntimePanel({
  selectedInstrument,
  setSelectedInstrument,
  watchlist,
}: {
  selectedInstrument: string;
  setSelectedInstrument: (value: string) => void;
  watchlist: Array<{ instrument_id: string; ticker: string; name: string }>;
}) {
  const overviewQuery = useRuntimeOverview(selectedInstrument, Boolean(selectedInstrument));
  const profileQuery = useSymbolProfileView(selectedInstrument, Boolean(selectedInstrument));
  const eventRegimeQuery = useEventRegimeView(selectedInstrument, Boolean(selectedInstrument));

  const overview = overviewQuery.data;
  const profilePayload = profileQuery.data;
  const latestEventRegime = (eventRegimeQuery.data?.items || [])[0] ?? null;

  const effectivePlan = overview?.effective_plan ?? profilePayload?.current_plan ?? null;
  const symbolProfile = overview?.symbol_profile ?? profilePayload?.profile ?? null;
  const diagnostics = overview?.diagnostics ?? profilePayload?.diagnostics ?? null;
  const eventRegime = overview?.event_regime ?? latestEventRegime ?? null;

  const effectivePlanState = runtimeBlockValue(overviewQuery, effectivePlan);
  const symbolProfileState = symbolProfile
    ? runtimeBlockValue({ isLoading: false, isError: false }, symbolProfile)
    : runtimeBlockValue(profileQuery, symbolProfile);
  const diagnosticsState = diagnostics
    ? runtimeBlockValue({ isLoading: false, isError: false }, diagnostics)
    : runtimeBlockValue(profileQuery, diagnostics);
  const eventRegimeState = eventRegime
    ? runtimeBlockValue({ isLoading: false, isError: false }, eventRegime)
    : runtimeBlockValue(eventRegimeQuery, eventRegime);

  return (
    <div className="grid gap-4 xl:grid-cols-[0.95fr_1.05fr]">
      <Surface title="Watchlist и поиск" description="Управление бумагами и выбор бумаги для runtime overview.">
        <div className="space-y-4">
          <SelectField
            label="Выбранная бумага"
            value={selectedInstrument}
            onChange={(value) => setSelectedInstrument(value)}
            options={watchlist.map((item) => [item.instrument_id, `${item.ticker} — ${item.name}`])}
          />
          <div className="rounded-xl border border-gray-800 bg-gray-950/60 p-3 text-sm text-gray-300">
            {watchlist.length ? watchlist.map((item) => item.ticker).join(', ') : 'Watchlist пуст'}
          </div>
        </div>
      </Surface>
      <Surface title="Runtime overview по бумаге" description="Effective plan, profile, diagnostics, regime и заметки по источникам.">
        <div className="space-y-3">
          <JsonCard title="Effective plan" state={effectivePlanState} />
          <JsonCard title="Symbol profile" state={symbolProfileState} />
          <JsonCard title="Diagnostics" state={diagnosticsState} />
          <JsonCard title="Event regime" state={eventRegimeState} />
        </div>
      </Surface>
    </div>
  );
}

function JsonCard({ title, state }: { title: string; state: RuntimeCardState }) {
  const text = state.status === 'loading'
    ? 'загрузка'
    : state.status === 'error'
      ? (state.value ? jsonText(state.value) : 'не загрузилось')
      : state.status === 'empty'
        ? 'данных нет'
        : jsonText(state.value);
  const tone = state.status === 'loading' ? 'warn' : state.status === 'error' ? 'warn' : state.status === 'empty' ? 'default' : state.status === 'idle' ? 'default' : 'blue';
  const label = state.status === 'loading' ? 'загрузка' : state.status === 'error' ? 'ошибка' : state.status === 'empty' ? 'данных нет' : state.status === 'idle' ? 'idle' : 'загружено';
  return (
    <div className="rounded-xl border border-gray-800 bg-gray-950/70 p-4">
      <div className="mb-2 flex items-center justify-between gap-3">
        <div className="font-medium text-white">{title}</div>
        <StatusChip tone={tone as any}>{label}</StatusChip>
      </div>
      <pre className="max-h-56 overflow-auto whitespace-pre-wrap break-words text-xs text-gray-300">{text}</pre>
    </div>
  );
}
