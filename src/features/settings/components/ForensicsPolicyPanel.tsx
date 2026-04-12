import clsx from 'clsx';
import type { RiskSettings, RuntimeOverview } from '../../../types';

type Props = {
  hidden: boolean;
  runtimeOverview: RuntimeOverview | undefined;
  isExporting: boolean;
  onExport: () => void;
  formState: RiskSettings;
  patch: (patch: Partial<RiskSettings>) => void;
};

function NumberControl({ label, value, onChange, step = '1' }: { label: string; value: number | undefined; onChange: (next: number) => void; step?: string }) {
  return (
    <label className="block">
      <div className="mb-1 text-xs text-gray-400">{label}</div>
      <input
        type="number"
        step={step}
        value={value ?? 0}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full rounded-xl border border-gray-800 bg-gray-950 px-3 py-2 text-sm text-gray-100 outline-none focus:border-blue-500"
      />
    </label>
  );
}

export function ForensicsPolicyPanel({ hidden, runtimeOverview, isExporting, onExport, formState, patch }: Props) {
  if (hidden) return null;
  const policy = runtimeOverview?.auto_policy ?? null;
  const state = policy?.state ?? 'unknown';
  return (
    <section id="forensics-policy" className="rounded-2xl border border-gray-800 bg-gray-900/70 p-5 space-y-4">
      <div>
        <h2 className="text-lg font-semibold text-gray-100">Forensic export и automatic degrade/freeze policy</h2>
        <p className="mt-1 text-sm text-gray-400">Экспортирует единый forensic-пакет для расследований и показывает, не перевела ли система себя в деградированный или замороженный режим.</p>
      </div>
      <div className="grid grid-cols-1 xl:grid-cols-[1.2fr,0.8fr] gap-4">
        <div className="rounded-xl border border-gray-800 bg-gray-950 p-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="text-sm font-semibold text-gray-100">Состояние auto-policy</div>
              <div className="mt-1 text-sm text-gray-400">Последние данные берутся из бизнес-метрик и бумажного аудита за lookback-окно.</div>
            </div>
            <span className={clsx('rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-wide border', state === 'normal' ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200' : state === 'degraded' ? 'border-yellow-500/30 bg-yellow-500/10 text-yellow-200' : state === 'frozen' ? 'border-red-500/30 bg-red-500/10 text-red-200' : 'border-gray-700 bg-gray-900 text-gray-300')}>
              {state}
            </span>
          </div>
          <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
            <div className="rounded-lg border border-gray-800 bg-gray-900 p-3"><div className="text-gray-500">Lookback</div><div className="mt-1 font-mono text-gray-100">{policy?.lookback_days ?? '—'}d</div></div>
            <div className="rounded-lg border border-gray-800 bg-gray-900 p-3"><div className="text-gray-500">PF</div><div className="mt-1 font-mono text-gray-100">{policy?.metrics?.profit_factor ?? '—'}</div></div>
            <div className="rounded-lg border border-gray-800 bg-gray-900 p-3"><div className="text-gray-500">Expectancy</div><div className="mt-1 font-mono text-gray-100">{policy?.metrics?.expectancy_per_trade ?? '—'}</div></div>
            <div className="rounded-lg border border-gray-800 bg-gray-900 p-3"><div className="text-gray-500">Exec errors</div><div className="mt-1 font-mono text-gray-100">{policy?.metrics?.execution_error_count ?? '—'}</div></div>
          </div>
          <div className="mt-4 text-sm text-gray-400">Причины:</div>
          <ul className="mt-2 list-disc pl-5 space-y-1 text-sm text-gray-300">
            {(policy?.reasons ?? ['данные ещё не получены']).map((reason) => <li key={reason}>{reason}</li>)}
          </ul>
          <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
            <div className="rounded-lg border border-gray-800 bg-gray-900 p-3"><div className="text-gray-500">Risk override</div><div className="mt-1 font-mono text-gray-100">{policy?.risk_multiplier_override ?? '—'}</div></div>
            <div className="rounded-lg border border-gray-800 bg-gray-900 p-3"><div className="text-gray-500">Threshold penalty</div><div className="mt-1 font-mono text-gray-100">{policy?.threshold_penalty ?? '—'}</div></div>
            <div className="rounded-lg border border-gray-800 bg-gray-900 p-3"><div className="text-gray-500">Новые входы</div><div className="mt-1 font-mono text-gray-100">{policy?.block_new_entries ? 'blocked' : 'allowed'}</div></div>
          </div>
        </div>
        <div className="rounded-xl border border-gray-800 bg-gray-950 p-4 flex flex-col justify-between">
          <div>
            <div className="text-sm font-semibold text-gray-100">Единый forensic export</div>
            <div className="mt-2 text-sm text-gray-400">Скачивает единый zip с сигналами, сделками, decision log, trace-связями, effective plan, paper audit, validation и активными настройками.</div>
            <div className="mt-4 flex flex-wrap gap-2 text-xs text-gray-300">
              {['signals', 'trades', 'orders', 'decision_log', 'trace_links', 'paper_audit', 'validation', 'effective_symbol_plans', 'settings'].map((item) => (
                <span key={item} className="rounded-full border border-blue-500/20 bg-blue-500/10 px-2.5 py-1">{item}</span>
              ))}
            </div>
          </div>
          <button
            type="button"
            onClick={onExport}
            disabled={isExporting}
            className="mt-5 rounded-xl border border-blue-500/30 bg-blue-600/10 px-4 py-3 text-sm font-semibold text-blue-100 transition-colors hover:bg-blue-600/20 disabled:opacity-60"
          >
            {isExporting ? 'Готовлю экспорт…' : 'Скачать forensic export'}
          </button>
        </div>
      </div>

      <div className="rounded-xl border border-gray-800 bg-gray-950 p-4">
        <div className="text-sm font-semibold text-gray-100">Настройки automatic degrade/freeze policy</div>
        <div className="mt-2 grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
          <label className="flex items-center gap-2 rounded-xl border border-gray-800 bg-gray-900 px-3 py-2 text-sm text-gray-200">
            <input type="checkbox" checked={!!formState.auto_degrade_enabled} onChange={(e) => patch({ auto_degrade_enabled: e.target.checked })} />
            Auto degrade
          </label>
          <label className="flex items-center gap-2 rounded-xl border border-gray-800 bg-gray-900 px-3 py-2 text-sm text-gray-200">
            <input type="checkbox" checked={!!formState.auto_freeze_enabled} onChange={(e) => patch({ auto_freeze_enabled: e.target.checked })} />
            Auto freeze
          </label>
          <label className="flex items-center gap-2 rounded-xl border border-gray-800 bg-gray-900 px-3 py-2 text-sm text-gray-200">
            <input type="checkbox" checked={!!formState.auto_freeze_new_entries} onChange={(e) => patch({ auto_freeze_new_entries: e.target.checked })} />
            Freeze блокирует новые входы
          </label>
          <NumberControl label="Lookback days" value={formState.auto_policy_lookback_days} onChange={(v) => patch({ auto_policy_lookback_days: v })} />
          <NumberControl label="Degrade exec errors" value={formState.auto_degrade_max_execution_errors} onChange={(v) => patch({ auto_degrade_max_execution_errors: v })} />
          <NumberControl label="Freeze exec errors" value={formState.auto_freeze_max_execution_errors} onChange={(v) => patch({ auto_freeze_max_execution_errors: v })} />
          <NumberControl label="Degrade PF" step="0.01" value={formState.auto_degrade_min_profit_factor} onChange={(v) => patch({ auto_degrade_min_profit_factor: v })} />
          <NumberControl label="Freeze PF" step="0.01" value={formState.auto_freeze_min_profit_factor} onChange={(v) => patch({ auto_freeze_min_profit_factor: v })} />
          <NumberControl label="Degrade expectancy" step="0.01" value={formState.auto_degrade_min_expectancy} onChange={(v) => patch({ auto_degrade_min_expectancy: v })} />
          <NumberControl label="Freeze expectancy" step="0.01" value={formState.auto_freeze_min_expectancy} onChange={(v) => patch({ auto_freeze_min_expectancy: v })} />
          <NumberControl label="Degrade MDD %" step="0.1" value={formState.auto_degrade_drawdown_pct} onChange={(v) => patch({ auto_degrade_drawdown_pct: v })} />
          <NumberControl label="Freeze MDD %" step="0.1" value={formState.auto_freeze_drawdown_pct} onChange={(v) => patch({ auto_freeze_drawdown_pct: v })} />
          <NumberControl label="Degrade risk x" step="0.01" value={formState.auto_degrade_risk_multiplier} onChange={(v) => patch({ auto_degrade_risk_multiplier: v })} />
          <NumberControl label="Threshold penalty" value={formState.auto_degrade_threshold_penalty} onChange={(v) => patch({ auto_degrade_threshold_penalty: v })} />
        </div>
        <div className="mt-3 text-xs text-gray-500">Это глобальный аварийный контур. Его смысл не в “улучшить edge магией”, а в том, чтобы система сама деградировала или замораживала новые входы, когда paper-run объективно ухудшился.</div>
      </div>
    </section>
  );
}
