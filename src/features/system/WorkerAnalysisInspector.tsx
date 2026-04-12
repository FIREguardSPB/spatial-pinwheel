import type { WorkerStatus } from '../core/queries';
import { fmtDateTime, fmtNumber } from '../core/format';

const TIMING_LABELS: Record<string, string> = {
  total_ms: 'Total',
  prepare_context_ms: 'Prepare context',
  risk_and_sizing_ms: 'Risk + sizing',
  persist_signal_ms: 'Persist signal',
  decision_flow_total_ms: 'Decision flow',
  'decision_flow_ms.de_and_internet_ms': 'DE + internet',
  'decision_flow_ms.event_regime_ms': 'Event regime',
  'decision_flow_ms.geometry_rescue_ms': 'Geometry rescue',
  'decision_flow_ms.performance_governor_ms': 'Governor',
  'decision_flow_ms.ml_overlay_ms': 'ML overlay',
  'decision_flow_ms.freshness_ms': 'Freshness',
  'decision_flow_ms.ai_ms': 'AI',
  'decision_flow_ms.finalize_ms': 'Finalize',
  publish_notify_total_ms: 'Publish + notify',
  'publish_notify_ms.sse_publish_ms': 'SSE publish',
  'publish_notify_ms.telegram_notify_ms': 'Telegram notify',
  execute_signal_total_ms: 'Execute signal',
};

const TIMING_ORDER = [
  'total_ms',
  'prepare_context_ms',
  'risk_and_sizing_ms',
  'persist_signal_ms',
  'decision_flow_total_ms',
  'decision_flow_ms.de_and_internet_ms',
  'decision_flow_ms.event_regime_ms',
  'decision_flow_ms.geometry_rescue_ms',
  'decision_flow_ms.performance_governor_ms',
  'decision_flow_ms.ml_overlay_ms',
  'decision_flow_ms.freshness_ms',
  'decision_flow_ms.ai_ms',
  'decision_flow_ms.finalize_ms',
  'publish_notify_total_ms',
  'publish_notify_ms.sse_publish_ms',
  'publish_notify_ms.telegram_notify_ms',
  'execute_signal_total_ms',
];

function fmtMs(value: unknown) {
  if (typeof value !== 'number' || Number.isNaN(value)) return '—';
  return `${fmtNumber(value, value >= 100 ? 0 : 2)} ms`;
}

function normalizeTimings(source: unknown): Array<[string, number]> {
  if (!source || typeof source !== 'object') return [];
  const dict = source as Record<string, unknown>;
  const seen = new Set<string>();
  const rows: Array<[string, number]> = [];

  for (const key of TIMING_ORDER) {
    const value = dict[key];
    if (typeof value === 'number' && !Number.isNaN(value)) {
      rows.push([key, value]);
      seen.add(key);
    }
  }

  Object.entries(dict)
    .filter(([key, value]) => !seen.has(key) && typeof value === 'number' && !Number.isNaN(value))
    .sort(([a], [b]) => a.localeCompare(b))
    .forEach(([key, value]) => rows.push([key, value as number]));

  return rows;
}

function labelForTiming(key: string) {
  return TIMING_LABELS[key] ?? key;
}

function AnalysisResultCard({
  title,
  result,
}: {
  title: string;
  result: Record<string, any> | null | undefined;
}) {
  const timings = normalizeTimings(result?.timings_ms);
  return (
    <div className="rounded-xl border border-gray-800 bg-gray-950 p-4">
      <div className="text-sm font-semibold text-gray-100">{title}</div>
      {result ? (
        <>
          <div className="mt-3 grid gap-2 text-sm text-gray-300 md:grid-cols-2 xl:grid-cols-3">
            <div>Тикер: <span className="font-mono text-gray-100">{result.ticker ?? '—'}</span></div>
            <div>Outcome: <span className="font-mono text-gray-100">{result.outcome ?? '—'}</span></div>
            <div>Decision: <span className="font-mono text-gray-100">{result.final_decision ?? '—'}</span></div>
            <div>Status: <span className="font-mono text-gray-100">{result.status ?? '—'}</span></div>
            <div>Signal ID: <span className="font-mono text-gray-100">{result.signal_id ?? '—'}</span></div>
            <div>Total: <span className="font-mono text-emerald-200">{fmtMs((result.timings_ms || {}).total_ms)}</span></div>
          </div>
          {timings.length ? (
            <div className="mt-4 grid gap-2 md:grid-cols-2 xl:grid-cols-3">
              {timings.slice(0, 9).map(([key, value]) => (
                <div key={key} className="rounded-lg border border-gray-800 bg-gray-900/70 px-3 py-2 text-sm text-gray-300">
                  <div className="text-[11px] uppercase tracking-wide text-gray-500">{labelForTiming(key)}</div>
                  <div className="mt-1 font-mono text-gray-100">{fmtMs(value)}</div>
                </div>
              ))}
            </div>
          ) : (
            <div className="mt-3 text-sm text-gray-500">Подробных timings ещё нет.</div>
          )}
        </>
      ) : (
        <div className="mt-3 text-sm text-gray-500">Пока нет данных.</div>
      )}
    </div>
  );
}

export function WorkerAnalysisInspector({ workerStatus }: { workerStatus?: WorkerStatus | null }) {
  const stats = (workerStatus?.last_analysis_stats ?? {}) as Record<string, any>;
  const avgTimings = normalizeTimings(stats.timing_avg_ms);
  const slowest = (stats.slowest_analysis ?? null) as Record<string, any> | null;
  const lastResult = (stats.last_analysis_result ?? null) as Record<string, any> | null;

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-gray-800 bg-gray-950 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="text-sm font-semibold text-gray-100">Worker pipeline timings</div>
            <div className="mt-1 text-sm text-gray-400">Последний осмысленный замер анализа и разбор, где именно тратится время.</div>
          </div>
          <div className="text-xs text-gray-500">Обновлено: {fmtDateTime(workerStatus?.updated_ts as string | number | null | undefined)}</div>
        </div>

        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-5">
          <div className="rounded-lg border border-gray-800 bg-gray-900/70 px-3 py-2">
            <div className="text-[11px] uppercase tracking-wide text-gray-500">Processed</div>
            <div className="mt-1 font-mono text-lg text-gray-100">{fmtNumber(stats.processed, 0)}</div>
          </div>
          <div className="rounded-lg border border-gray-800 bg-gray-900/70 px-3 py-2">
            <div className="text-[11px] uppercase tracking-wide text-gray-500">Takes</div>
            <div className="mt-1 font-mono text-lg text-gray-100">{fmtNumber(stats.takes, 0)}</div>
          </div>
          <div className="rounded-lg border border-gray-800 bg-gray-900/70 px-3 py-2">
            <div className="text-[11px] uppercase tracking-wide text-gray-500">Skipped</div>
            <div className="mt-1 font-mono text-lg text-gray-100">{fmtNumber(stats.skipped, 0)}</div>
          </div>
          <div className="rounded-lg border border-gray-800 bg-gray-900/70 px-3 py-2">
            <div className="text-[11px] uppercase tracking-wide text-gray-500">Cycle duration</div>
            <div className="mt-1 font-mono text-lg text-emerald-200">{fmtMs(stats.duration_ms)}</div>
          </div>
          <div className="rounded-lg border border-gray-800 bg-gray-900/70 px-3 py-2">
            <div className="text-[11px] uppercase tracking-wide text-gray-500">Timing samples</div>
            <div className="mt-1 font-mono text-lg text-gray-100">{fmtNumber(stats.timing_samples, 0)}</div>
          </div>
        </div>

        {avgTimings.length ? (
          <div className="mt-4 grid gap-2 md:grid-cols-2 xl:grid-cols-3">
            {avgTimings.map(([key, value]) => (
              <div key={key} className="rounded-lg border border-gray-800 bg-gray-900/70 px-3 py-2 text-sm text-gray-300">
                <div className="text-[11px] uppercase tracking-wide text-gray-500">{labelForTiming(key)}</div>
                <div className="mt-1 font-mono text-gray-100">{fmtMs(value)}</div>
              </div>
            ))}
          </div>
        ) : (
          <div className="mt-4 text-sm text-gray-500">Пока нет осмысленного timing breakdown — нужен хотя бы один реальный проход анализа.</div>
        )}
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <AnalysisResultCard title="Самый медленный недавний кейс" result={slowest} />
        <AnalysisResultCard title="Последний анализ" result={lastResult} />
      </div>
    </div>
  );
}
