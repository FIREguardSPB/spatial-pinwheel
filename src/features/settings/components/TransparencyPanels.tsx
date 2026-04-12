import type { ReactNode } from 'react';
import clsx from 'clsx';
import type { RuntimeOverview } from '../../../types';

type WatchlistItem = { instrument_id: string; ticker: string };

type Props = {
  hiddenTransparency: boolean;
  hiddenAdaptivePlan: boolean;
  runtimeOverview: RuntimeOverview | undefined;
  telegramStatus: RuntimeOverview['telegram'] | null;
  inspectedInstrument: string;
  setInspectedInstrument: (value: string) => void;
  watchlist: WatchlistItem[];
  profileSnapshot: Record<string, any> | null;
  effectivePlan: Record<string, any> | null;
  diagnosticsSnapshot: Record<string, any> | null;
  isRuntimeOverviewFetching: boolean;
};

function SectionShell({ id, title, description, hidden, children }: { id: string; title: string; description: string; hidden?: boolean; children: ReactNode }) {
  if (hidden) return null;
  return (
    <section id={id} className="rounded-2xl border border-gray-800 bg-gray-900/70 p-5 space-y-4">
      <div>
        <h2 className="text-lg font-semibold text-gray-100">{title}</h2>
        <p className="mt-1 text-sm text-gray-400">{description}</p>
      </div>
      {children}
    </section>
  );
}

export function TransparencyPanels({
  hiddenTransparency,
  hiddenAdaptivePlan,
  runtimeOverview,
  telegramStatus,
  inspectedInstrument,
  setInspectedInstrument,
  watchlist,
  profileSnapshot,
  effectivePlan,
  diagnosticsSnapshot,
  isRuntimeOverviewFetching,
}: Props) {
  return (
    <>
      <SectionShell
        hidden={hiddenTransparency}
        id="system-transparency"
        title="Прозрачность системы"
        description="Здесь видно, какие настройки являются глобальными рамками, а какие параметры бот рассчитывает сам по бумаге и режиму рынка."
      >
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
          {(runtimeOverview?.hierarchy ?? []).map((layer) => (
            <div key={layer.scope} className="rounded-xl border border-gray-800 bg-gray-950 p-4">
              <div className="flex items-center justify-between gap-2">
                <div className="font-semibold text-gray-100">{layer.title}</div>
                <span className={clsx('rounded-full px-2 py-0.5 text-[10px] uppercase tracking-wide border', layer.recommended_to_change === true ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200' : layer.recommended_to_change === 'careful' ? 'border-yellow-500/30 bg-yellow-500/10 text-yellow-200' : 'border-violet-500/30 bg-violet-500/10 text-violet-200')}>
                  {layer.recommended_to_change === true ? 'можно менять' : layer.recommended_to_change === 'careful' ? 'осторожно' : 'auto'}
                </span>
              </div>
              <div className="mt-2 text-sm text-gray-400">{layer.description}</div>
              <div className="mt-3 flex flex-wrap gap-2">
                {layer.fields.map((field) => (
                  <span key={field} className="rounded-full border border-gray-800 bg-gray-900 px-2.5 py-1 text-[11px] text-gray-300">{field}</span>
                ))}
              </div>
            </div>
          ))}
        </div>
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-4 mt-4">
          <div className="rounded-xl border border-gray-800 bg-gray-950 p-4">
            <div className="text-sm font-semibold text-gray-100">Что реально можно крутить вручную</div>
            <div className="mt-3 flex flex-wrap gap-2">
              {(runtimeOverview?.safe_manual_fields ?? []).map((field) => (
                <span key={field} className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-1 text-[11px] text-emerald-200">{field}</span>
              ))}
            </div>
          </div>
          <div className="rounded-xl border border-gray-800 bg-gray-950 p-4">
            <div className="text-sm font-semibold text-gray-100">Поля, которые лучше не трогать без уверенности</div>
            <div className="mt-3 flex flex-wrap gap-2">
              {(runtimeOverview?.caution_fields ?? []).map((field) => (
                <span key={field} className="rounded-full border border-yellow-500/30 bg-yellow-500/10 px-2.5 py-1 text-[11px] text-yellow-200">{field}</span>
              ))}
            </div>
          </div>
          <div className="rounded-xl border border-gray-800 bg-gray-950 p-4">
            <div className="text-sm font-semibold text-gray-100">Эти параметры бот считает сам</div>
            <div className="mt-3 flex flex-wrap gap-2">
              {(runtimeOverview?.auto_owned_fields ?? []).map((field) => (
                <span key={field} className="rounded-full border border-violet-500/30 bg-violet-500/10 px-2.5 py-1 text-[11px] text-violet-200">{field}</span>
              ))}
            </div>
          </div>
        </div>
        <div className="grid grid-cols-1 xl:grid-cols-3 gap-4 mt-4">
          <div className="rounded-xl border border-gray-800 bg-gray-950 p-4">
            <div className="text-sm font-semibold text-gray-100">Worker</div>
            <div className="mt-2 text-sm text-gray-400">Фаза: <span className="text-gray-200 font-mono">{runtimeOverview?.worker?.phase ?? '—'}</span></div>
            <div className="mt-1 text-sm text-gray-400">Инструментов в работе: <span className="text-gray-200 font-mono">{runtimeOverview?.worker?.current_instrument_count ?? 0}</span></div>
            <div className="mt-1 text-sm text-gray-400">Последний TAKE: <span className="text-gray-200 font-mono">{runtimeOverview?.worker?.last_take_instrument ?? '—'}</span></div>
          </div>
          <div className="rounded-xl border border-gray-800 bg-gray-950 p-4">
            <div className="text-sm font-semibold text-gray-100">AI / LM</div>
            <div className="mt-2 text-sm text-gray-400">Режим: <span className="text-gray-200 font-mono">{runtimeOverview?.ai_runtime?.ai_mode ?? 'off'}</span></div>
            <div className="mt-1 text-sm text-gray-400">Участвует в решении: <span className="text-gray-200 font-mono">{runtimeOverview?.ai_runtime?.participates_in_decision ? 'да' : 'нет'}</span></div>
            <div className="mt-1 text-sm text-gray-400">Primary: <span className="text-gray-200 font-mono">{runtimeOverview?.ai_runtime?.primary_provider ?? '—'}</span></div>
            <div className="mt-1 text-sm text-gray-400">Последний вызов: <span className="text-gray-200 font-mono">{runtimeOverview?.ai_runtime?.last_decision ? `${runtimeOverview.ai_runtime.last_decision.instrument_id} / ${runtimeOverview.ai_runtime.last_decision.provider}` : 'ещё не было'}</span></div>
          </div>
          <div className="rounded-xl border border-gray-800 bg-gray-950 p-4">
            <div className="text-sm font-semibold text-gray-100">Telegram</div>
            <div className="mt-2 text-sm text-gray-400">Конфигурация: <span className="text-gray-200 font-mono">{telegramStatus?.configured ? 'готово' : 'неполная'}</span></div>
            <div className="mt-1 text-sm text-gray-400">Bot token: <span className="text-gray-200 font-mono">{telegramStatus?.bot_token_present ? 'есть' : 'нет'}</span></div>
            <div className="mt-1 text-sm text-gray-400">Chat id: <span className="text-gray-200 font-mono">{telegramStatus?.chat_id_present ? 'есть' : 'нет'}</span></div>
            <div className="mt-2 flex flex-wrap gap-2">
              {(telegramStatus?.enabled_events ?? []).map((event) => (
                <span key={event} className="rounded-full border border-sky-500/30 bg-sky-500/10 px-2.5 py-1 text-[11px] text-sky-200">{event}</span>
              ))}
            </div>
          </div>
        </div>
      </SectionShell>

      <SectionShell
        hidden={hiddenAdaptivePlan}
        id="adaptive-plan"
        title="Инспектор адаптивного плана по бумаге"
        description="Показывает, какие эффективные параметры сейчас реально активны по выбранной бумаге. Именно этот план должен участвовать в расчёте, а не только общие глобальные настройки."
      >
        <div className="grid grid-cols-1 xl:grid-cols-[280px,1fr] gap-4">
          <div className="space-y-4">
            <div>
              <div className="mb-2 text-sm font-medium text-gray-300">Бумага для инспекции</div>
              <select value={inspectedInstrument} onChange={(e) => setInspectedInstrument(e.target.value)} className="w-full rounded-xl border border-gray-800 bg-gray-950 px-3 py-2.5 text-sm text-gray-100 outline-none focus:border-blue-500">
                {watchlist.map((item) => (
                  <option key={item.instrument_id} value={item.instrument_id}>{item.ticker} · {item.instrument_id}</option>
                ))}
              </select>
            </div>
            <div className="rounded-xl border border-gray-800 bg-gray-950 p-4 text-sm text-gray-400">
              <div>Профиль: <span className="font-mono text-gray-200">{profileSnapshot?.source ?? '—'}</span></div>
              <div className="mt-1">Autotune: <span className="font-mono text-gray-200">{profileSnapshot?.autotune ? 'on' : 'off'}</span></div>
              <div className="mt-1">Best hours: <span className="font-mono text-gray-200">{(profileSnapshot?.best_hours_json ?? []).join(', ') || '—'}</span></div>
              <div className="mt-1">Blocked hours: <span className="font-mono text-gray-200">{(profileSnapshot?.blocked_hours_json ?? []).join(', ') || '—'}</span></div>
              <div className="mt-3 text-xs text-gray-500">{isRuntimeOverviewFetching ? 'Обновляю effective plan…' : (runtimeOverview?.source_notes ?? []).join(' · ') || 'Effective plan ещё не рассчитан.'}</div>
            </div>
          </div>
          <div className="space-y-4">
            <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3">
              {[
                ['Стратегия', effectivePlan?.strategy_name ?? '—'],
                ['Режим', effectivePlan?.regime ?? '—'],
                ['Threshold', effectivePlan?.decision_threshold ?? '—'],
                ['TF', effectivePlan ? `${effectivePlan.analysis_timeframe ?? '1m'} → ${effectivePlan.execution_timeframe ?? effectivePlan.analysis_timeframe ?? '1m'}` : '—'],
                ['Hold bars', effectivePlan?.hold_bars ?? '—'],
                ['Re-entry', effectivePlan?.reentry_cooldown_sec ? `${effectivePlan.reentry_cooldown_sec}s` : '—'],
                ['Risk x', effectivePlan?.risk_multiplier ?? '—'],
              ].map(([label, value]) => (
                <div key={label} className="rounded-xl border border-gray-800 bg-gray-950 p-4">
                  <div className="text-xs uppercase tracking-wide text-gray-500">{label}</div>
                  <div className="mt-2 text-lg font-semibold text-gray-100">{String(value)}</div>
                </div>
              ))}
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="rounded-xl border border-gray-800 bg-gray-950 p-4">
                <div className="text-sm font-semibold text-gray-100">Из чего сложился итоговый план</div>
                <div className="mt-3 space-y-2 text-sm text-gray-400">
                  <div>Global threshold: <span className="font-mono text-gray-200">{runtimeOverview?.global_defaults?.base_engine_defaults?.decision_threshold ?? '—'}</span></div>
                  <div>Profile offset: <span className="font-mono text-gray-200">{profileSnapshot?.decision_threshold_offset ?? 0}</span></div>
                  <div>Итоговый threshold: <span className="font-mono text-emerald-200">{effectivePlan?.decision_threshold ?? '—'}</span></div>
                  <div>Global hold bars: <span className="font-mono text-gray-200">{runtimeOverview?.global_defaults?.base_engine_defaults?.time_stop_bars ?? '—'}</span></div>
                  <div>Profile hold base: <span className="font-mono text-gray-200">{profileSnapshot?.hold_bars_base ?? '—'}</span></div>
                  <div>Итоговый hold bars: <span className="font-mono text-emerald-200">{effectivePlan?.hold_bars ?? '—'}</span></div>
                  <div>Global re-entry: <span className="font-mono text-gray-200">{runtimeOverview?.global_defaults?.base_engine_defaults?.signal_reentry_cooldown_sec ?? '—'}</span></div>
                  <div>Итоговый re-entry: <span className="font-mono text-emerald-200">{effectivePlan?.reentry_cooldown_sec ?? '—'}</span></div>
                </div>
              </div>
              <div className="rounded-xl border border-gray-800 bg-gray-950 p-4">
                <div className="text-sm font-semibold text-gray-100">Диагностика бумаги и режима</div>
                <div className="mt-3 space-y-2 text-sm text-gray-400">
                  <div>Sample size: <span className="font-mono text-gray-200">{effectivePlan?.sample_size ?? profileSnapshot?.sample_size ?? '—'}</span></div>
                  <div>Recent win rate: <span className="font-mono text-gray-200">{effectivePlan?.recent_win_rate ?? profileSnapshot?.last_win_rate ?? '—'}</span></div>
                  <div>Recent avg bars: <span className="font-mono text-gray-200">{effectivePlan?.recent_avg_bars ?? '—'}</span></div>
                  <div>Event regime: <span className="font-mono text-gray-200">{runtimeOverview?.event_regime ? `${runtimeOverview.event_regime.regime} / ${runtimeOverview.event_regime.action}` : 'нет'}</span></div>
                  <div>Diagnostics regime: <span className="font-mono text-gray-200">{diagnosticsSnapshot?.regime ?? diagnosticsSnapshot?.summary?.regime ?? '—'}</span></div>
                  <div>Notes:</div>
                  <ul className="list-disc pl-5 space-y-1 text-xs text-gray-500">
                    {(effectivePlan?.notes ?? []).map((note: string) => <li key={note}>{note}</li>)}
                  </ul>
                </div>
              </div>
            </div>
          </div>
        </div>
      </SectionShell>
    </>
  );
}
