import { useMemo, useState } from 'react';
import { PageShell, QueryBlock, RetryButton, SimpleTable, StatusChip, Surface } from '../core/PageBlocks';
import { fmtDateTime, fmtMoney, fmtNumber, fmtPercent } from '../core/format';
import { useUiRuntime, useUiSignals } from '../core/uiQueries';
import type { Signal } from '../../types';

function decisionTone(value?: string | null) {
  if (value === 'TAKE') return 'good';
  if (value === 'REJECT') return 'bad';
  if (value === 'SKIP') return 'warn';
  return 'default';
}

function statusTone(value?: string | null) {
  if (value === 'executed' || value === 'approved') return 'good';
  if (value === 'execution_error' || value === 'rejected') return 'bad';
  if (value === 'pending_review') return 'warn';
  return 'default';
}

function describePendingState(signal: Signal) {
  if (signal.status !== 'pending_review') return null;
  const ts = Number(signal.updated_ts ?? signal.created_ts ?? signal.ts ?? 0);
  if (!ts) return { state: 'pending', label: 'pending_review' };
  const ageSec = Math.max(0, Math.floor((Date.now() - ts) / 1000));
  if (ageSec < 60) return { state: 'in_flight', label: `in flight · ${ageSec}s` };
  return { state: 'stale', label: `stale · ${ageSec}s` };
}

function describeDecisionSource(signal: Signal) {
  const deDecision = String(signal.meta?.decision?.decision || '').toUpperCase();
  const aiDecision = String(signal.meta?.ai_decision?.decision || '').toUpperCase();
  const finalDecision = String(signal.final_decision || '').toUpperCase();
  const aiMode = signal.ai_mode_used || 'off';
  if (signal.status === 'pending_review' && !finalDecision) return 'Сигнал создан, финализация ещё идёт';
  if (!signal.ai_influenced || aiMode === 'off') return `DE only: ${deDecision || finalDecision || '—'}`;
  if (aiDecision && aiDecision === finalDecision && aiDecision !== deDecision) return `AI pushed final: ${aiDecision}`;
  if (aiDecision && deDecision && aiDecision !== deDecision) return `DE ${deDecision} / AI ${aiDecision} → FINAL ${finalDecision || '—'}`;
  return `AI ${signal.ai_influence || 'active'} / FINAL ${finalDecision || '—'}`;
}

function describeRejectReason(signal: Signal) {
  const fastPath = signal.meta?.ai_fast_path || {};
  if (fastPath?.reason) return { mode: 'fast_path', text: String(fastPath.reason) };
  const reasons = Array.isArray(signal.meta?.decision?.reasons) ? signal.meta?.decision?.reasons : [];
  const blocker = reasons.find((reason) => String(reason?.severity || '').toLowerCase() === 'block');
  const preferred = blocker || reasons[0];
  if (preferred?.msg) return { mode: 'decision', text: String(preferred.msg) };
  if (signal.reason) return { mode: 'decision', text: signal.reason };
  return { mode: 'none', text: '—' };
}

function describeGuardrail(signal: Signal) {
  const policy = signal.meta?.auto_policy || {};
  const governor = signal.meta?.performance_governor || {};
  const reasons = [
    ...(Array.isArray(policy?.reasons) ? policy.reasons : []),
    ...(Array.isArray(governor?.reasons) ? governor.reasons : []),
  ].filter(Boolean);
  if (governor?.suppressed) {
    return { tone: 'bad' as const, badge: 'governor', text: `Governor block: ${reasons.join('; ') || 'weak slice suppressed'}` };
  }
  if (policy?.block_new_entries || String(policy?.state || '').toLowerCase() === 'frozen') {
    return { tone: 'warn' as const, badge: String(policy?.state || 'frozen'), text: `${String(policy?.state || 'frozen')}: ${reasons.join('; ') || 'new entries blocked'}` };
  }
  if (policy?.state === 'degraded') {
    return { tone: 'warn' as const, badge: 'degraded', text: `Degraded: ${reasons.join('; ') || 'risk reduced'}` };
  }
  if (policy?.state && policy.state !== 'active') {
    return { tone: 'blue' as const, badge: String(policy.state), text: `${policy.state}: ${reasons.join('; ') || 'policy active with restrictions'}` };
  }
  return { tone: 'default' as const, badge: '—', text: '—' };
}

function describeAi(signal: Signal) {
  const fastPath = signal.meta?.ai_fast_path || {};
  if (fastPath?.applied) {
    return { tone: 'blue' as const, line1: 'skipped fast-path', line2: fastPath.reason || 'deterministic reject' };
  }
  if (signal.ai_influence === 'affected decision') {
    return { tone: 'good' as const, line1: signal.ai_influence, line2: signal.meta?.ai_decision?.provider || signal.ai_mode_used || '—' };
  }
  if (signal.ai_influence === 'advisory only') {
    return { tone: 'warn' as const, line1: signal.ai_influence, line2: signal.meta?.ai_decision?.provider || signal.ai_mode_used || '—' };
  }
  return {
    tone: 'default' as const,
    line1: signal.ai_influence || 'off',
    line2: signal.meta?.ai_decision?.provider || signal.ai_mode_used || '—',
  };
}

function describeMl(signal: Signal) {
  const ml = signal.meta?.ml_overlay || {};
  if (!Object.keys(ml).length) return 'данных нет';
  const target = typeof ml?.target_probability === 'number' ? fmtPercent(ml.target_probability * 100) : '—';
  const fill = typeof ml?.fill_probability === 'number' ? fmtPercent(ml.fill_probability * 100) : '—';
  const reason = ml?.reason || 'runtime';
  return `target ${target} / fill ${fill} · ${reason}`;
}

function deriveMlProgress(runtime: any) {
  const ml = runtime?.ml_runtime || {};
  const minSamples = Number(ml?.min_training_samples || 0);
  const recentRuns = Array.isArray(ml?.recent_runs) ? ml.recent_runs : [];
  const latestFor = (target: string) => recentRuns.find((run: any) => run?.target === target) || null;
  const build = (target: string) => {
    const run = latestFor(target) || {};
    const rows = Number(run?.train_rows || 0);
    return {
      rows,
      remaining: Math.max(0, minSamples - rows),
      status: String(run?.status || ml?.active_models?.[target]?.status || 'missing'),
    };
  };
  return {
    minSamples,
    tradeOutcome: build('trade_outcome'),
    takeFill: build('take_fill'),
  };
}

export default function SignalsPage() {
  const [status, setStatus] = useState<string>('');
  const page = useUiSignals(status || undefined, 40);
  const runtime = useUiRuntime();
  const summary = page.data?.summary || {};
  const items = useMemo(() => page.data?.items ?? [], [page.data?.items]);
  const mlProgress = deriveMlProgress(runtime.data);

  const derived = useMemo(() => {
    let aiSkipped = 0;
    let stalePending = 0;
    let frozen = 0;
    for (const signal of items) {
      if (signal.meta?.ai_fast_path?.applied) aiSkipped += 1;
      if (describePendingState(signal)?.state === 'stale') stalePending += 1;
      const guardrail = describeGuardrail(signal);
      if (guardrail.badge === 'frozen' || guardrail.badge === 'governor') frozen += 1;
    }
    return { aiSkipped, stalePending, frozen };
  }, [items]);

  return (
    <PageShell
      title="Сигналы"
      subtitle="Страница живёт на одном /ui/signals, без каскада доп. запросов."
      actions={
        <>
          <select value={status} onChange={(e) => setStatus(e.target.value)} className="rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-sm text-white">
            <option value="">Все статусы</option>
            <option value="pending_review">pending_review</option>
            <option value="approved">approved</option>
            <option value="rejected">rejected</option>
            <option value="executed">executed</option>
            <option value="execution_error">execution_error</option>
            <option value="expired">expired</option>
            <option value="skipped">skipped</option>
          </select>
          <RetryButton onClick={() => { page.refetch(); runtime.refetch(); }} />
        </>
      }
    >
      <div className="grid gap-4 xl:grid-cols-6">
        <Surface title="Показано"><div className="text-2xl font-semibold text-white">{fmtNumber(summary.visible_count ?? items.length, 0)}</div></Surface>
        <Surface title="Всего в БД"><div className="text-2xl font-semibold text-white">{fmtNumber(summary.total ?? 0, 0)}</div></Surface>
        <Surface title="TAKE"><div className="text-2xl font-semibold text-emerald-300">{fmtNumber(summary.take ?? 0, 0)}</div></Surface>
        <Surface title="AI повлиял"><div className="text-2xl font-semibold text-violet-300">{fmtNumber(summary.ai_affected ?? 0, 0)}</div></Surface>
        <Surface title="AI skipped"><div className="text-2xl font-semibold text-blue-300">{fmtNumber(derived.aiSkipped, 0)}</div></Surface>
        <Surface title="Stale pending"><div className="text-2xl font-semibold text-amber-300">{fmtNumber(derived.stalePending, 0)}</div></Surface>
        <Surface title="Frozen / governor"><div className="text-2xl font-semibold text-rose-300">{fmtNumber(derived.frozen, 0)}</div></Surface>
        <Surface title="ML слой"><div className="text-2xl font-semibold text-sky-300">{fmtNumber(summary.ml_seen ?? 0, 0)}</div></Surface>
        <Surface title="ML trade_outcome">
          <div className="text-xl font-semibold text-white">{fmtNumber(mlProgress.tradeOutcome.rows, 0)} / {fmtNumber(mlProgress.minSamples, 0)}</div>
          <div className="mt-1 text-xs text-gray-400">осталось {fmtNumber(mlProgress.tradeOutcome.remaining, 0)} · {mlProgress.tradeOutcome.status}</div>
        </Surface>
        <Surface title="ML take_fill">
          <div className="text-xl font-semibold text-white">{fmtNumber(mlProgress.takeFill.rows, 0)} / {fmtNumber(mlProgress.minSamples, 0)}</div>
          <div className="mt-1 text-xs text-gray-400">осталось {fmtNumber(mlProgress.takeFill.remaining, 0)} · {mlProgress.takeFill.status}</div>
        </Surface>
        <Surface title="Последний сигнал"><div className="text-sm font-medium text-white">{fmtDateTime((summary as any).latest_signal_ts)}</div></Surface>
      </div>

      <Surface title="Лента сигналов" description="Данные из coordinator endpoint, разложенные по decision source, AI, ML и guardrails.">
        <QueryBlock isLoading={page.isLoading && !page.data} isError={page.isError && !page.data} errorMessage="Не удалось загрузить сигналы" onRetry={() => page.refetch()}>
          <SimpleTable
            columns={['Создан', 'Инструмент', 'Статус', 'Final', 'Источник решения', 'Причина', 'AI', 'ML', 'Guardrail', 'Цена / RR', 'Стратегия']}
            rows={items.map((signal) => {
              const aiInfo = describeAi(signal);
              const pendingState = describePendingState(signal);
              const rejectReason = describeRejectReason(signal);
              const guardrail = describeGuardrail(signal);
              return [
                <div className="space-y-1 text-xs text-gray-300"><div>{fmtDateTime((signal as any).created_ts ?? signal.ts)}</div><div className="text-gray-500">свеча: {fmtDateTime(signal.ts)}</div></div>,
                signal.instrument_id,
                <div className="space-y-1 text-xs text-gray-300">
                  <StatusChip tone={statusTone(signal.status)}>{signal.status}</StatusChip>
                  {pendingState ? <StatusChip tone={pendingState.state === 'stale' ? 'bad' : 'blue'}>{pendingState.label}</StatusChip> : null}
                </div>,
                <StatusChip tone={decisionTone(signal.final_decision)}>{signal.final_decision ?? '—'}</StatusChip>,
                <div className="max-w-[18rem] text-xs text-gray-300">{describeDecisionSource(signal)}</div>,
                <div className="max-w-[20rem] space-y-1 text-xs text-rose-100">
                  {rejectReason.mode === 'fast_path' ? <StatusChip tone="blue">fast-path</StatusChip> : null}
                  <div>{rejectReason.text}</div>
                </div>,
                <div className="max-w-[16rem] space-y-1 text-xs text-gray-300">
                  <StatusChip tone={aiInfo.tone}>{aiInfo.line1}</StatusChip>
                  <div className="text-gray-500">{aiInfo.line2}</div>
                </div>,
                <div className="max-w-[16rem] text-xs text-gray-300">{describeMl(signal)}</div>,
                <div className="max-w-[18rem] space-y-1 text-xs text-amber-200">
                  {guardrail.badge !== '—' ? <StatusChip tone={guardrail.tone}>{guardrail.badge}</StatusChip> : null}
                  <div>{guardrail.text}</div>
                </div>,
                <div className="space-y-1 text-xs text-gray-300"><div>{fmtNumber(signal.entry)} / RR {fmtNumber(signal.r)}</div><div className="text-gray-500">SL {fmtNumber(signal.sl)} · TP {fmtNumber(signal.tp)}</div>{signal.economic_summary ? <div className="text-gray-500">after costs {fmtMoney(signal.economic_summary.expected_profit_after_costs_rub)}</div> : null}</div>,
                <div className="space-y-1 text-xs text-gray-300"><div>{signal.strategy_name ?? '—'}</div><div className="text-gray-500">{signal.analysis_timeframe ?? '—'} / {signal.execution_timeframe ?? '—'}</div></div>,
              ];
            })}
            empty="Сигналов пока нет"
          />
        </QueryBlock>
      </Surface>
    </PageShell>
  );
}
