import React, { useState } from 'react';
import { useSignals, useSignalAction } from './hooks';
import { format } from 'date-fns';
import clsx from 'clsx';
import { Check, X, Clock, AlertTriangle } from 'lucide-react';
import { toast } from 'sonner';
import { SignalsTableSkeleton, EmptyState, ErrorState } from '../../components/ui/UIComponents';
import { AIBadgeCell, AIDecisionCard } from './AIDecisionCard';
import { COLORS } from '../../constants';
import { formatPercent, formatPrice } from '../../utils/formatPrice';

const canManualApprove = (signal: any) => {
    const finalDecision = signal?.meta?.final_decision ?? signal?.meta?.decision?.decision;
    return signal?.status === 'pending_review' && (!finalDecision || finalDecision === 'TAKE');
};

const getEconomicSummary = (signal: any) => signal?.economic_summary ?? signal?.meta?.decision?.metrics ?? {};

const economicFlagsLabel: Record<string, string> = {
    MICRO_LEVELS_WARNING: 'микро-уровни',
    COMMISSION_DOMINANCE_WARNING: 'комиссии доминируют',
    LOW_PRICE_WARNING: 'дешёвая бумага',
};

const strategySourceLabel: Record<string, string> = {
    global: 'global / глобально',
    symbol: 'symbol / профиль бумаги',
    regime: 'regime / режим рынка',
    unknown: 'unknown / неясно',
};

const aiInfluenceLabel: Record<string, string> = {
    off: 'rules only / без ИИ',
    'advisory only': 'advisory only / только комментарий',
    'affected decision': 'affected decision / ИИ повлиял',
    unknown: 'unknown / неясно',
};

const rejectPriorityLabel: Record<string, string> = {
    economics: 'economics / экономика',
    risk: 'risk / риск',
    ai: 'ai / ИИ',
    'strategy mismatch': 'strategy mismatch / конфликт стратегии',
    other: 'other / прочее',
};

const pillTone = (value: string | null | undefined) => {
    switch (value) {
        case 'global':
            return 'border-slate-600 bg-slate-800 text-slate-200';
        case 'symbol':
            return 'border-fuchsia-500/30 bg-fuchsia-500/10 text-fuchsia-300';
        case 'regime':
            return 'border-cyan-500/30 bg-cyan-500/10 text-cyan-300';
        case 'affected decision':
            return 'border-purple-500/30 bg-purple-500/10 text-purple-300';
        case 'advisory only':
            return 'border-blue-500/30 bg-blue-500/10 text-blue-300';
        case 'economics':
            return 'border-yellow-500/30 bg-yellow-500/10 text-yellow-300';
        case 'risk':
            return 'border-orange-500/30 bg-orange-500/10 text-orange-300';
        case 'ai':
            return 'border-purple-500/30 bg-purple-500/10 text-purple-300';
        case 'strategy mismatch':
            return 'border-red-500/30 bg-red-500/10 text-red-300';
        default:
            return 'border-gray-700 bg-gray-800 text-gray-400';
    }
};


export const SignalsTable: React.FC = () => {
    const { data: signals, isLoading, isError } = useSignals();
    const { mutate: performAction, isPending: isActionPending } = useSignalAction();
    const [processingId, setProcessingId] = useState<string | null>(null);
    const [expandedAI, setExpandedAI] = useState<string | null>(null);

    const handleAction = (id: string, action: 'approve' | 'reject') => {
        setProcessingId(id);
        performAction({ id, action }, {
            onSuccess: () => toast.success(action === 'approve' ? '✅ Сигнал одобрен' : '❌ Сигнал отклонён'),
            onError:   () => toast.error('Ошибка выполнения действия'),
            onSettled: () => setProcessingId(null),
        });
    };

    if (isLoading) return <SignalsTableSkeleton />;
    if (isError) return <ErrorState message="Не удалось загрузить сигналы" onRetry={() => window.location.reload()} />;

    return (
        <div className="h-full overflow-y-auto overflow-x-auto bg-gray-900 border border-gray-800 rounded-lg shadow-inner">
            <table className="w-full text-sm text-left">
                <thead className="bg-gray-800 text-gray-400 uppercase text-xs font-bold tracking-wider sticky top-0 z-10">
                    <tr>
                        <th className="px-6 py-3">Time</th>
                        <th className="px-6 py-3">Instrument</th>
                        <th className="px-6 py-3">Side</th>
                        <th className="px-6 py-3">Signal</th>
                        <th className="px-6 py-3">Decision</th>
                        <th className="px-6 py-3">Score</th>
                        <th className="px-6 py-3">Price</th>
                        <th className="px-6 py-3">SL / TP</th>
                        <th className="px-6 py-3">Economics</th>
                        <th className="px-6 py-3">Size</th>
                        <th className="px-6 py-3">Status</th>
                        <th className="px-6 py-3">AI</th>
                        <th className="px-6 py-3 text-right">Actions</th>
                    </tr>
                </thead>
                <tbody className="divide-y divide-gray-800">
                    {signals?.map((signal) => {
                        const decisionData = signal.meta?.decision;
                        const score = decisionData?.score;
                        const decision = decisionData?.decision;
                        const reasons = decisionData?.reasons || [];
                        const econ = getEconomicSummary(signal);
                        const econFlags = (econ.economic_warning_flags || []) as string[];
                        const geometry = signal.meta?.geometry_optimizer as any;

                        return (
                            <React.Fragment key={signal.id}>
                            <tr className="hover:bg-gray-800/50 transition-colors">
                                <td className="px-6 py-4 font-mono text-gray-400">
                                    {format(signal.ts * (signal.ts > 10000000000 ? 1 : 1000), 'HH:mm:ss')}
                                    <br />
                                    <span className="text-xs text-gray-600">{format(signal.ts * (signal.ts > 10000000000 ? 1 : 1000), 'dd MMM')}</span>
                                </td>
                                <td className="px-6 py-4 font-bold text-gray-200">{signal.instrument_id}</td>
                                <td className="px-6 py-4">
                                    <span className={clsx('px-2 py-1 rounded text-xs font-bold', signal.side === 'BUY' ? 'bg-blue-500/10 text-blue-400' : 'bg-orange-500/10 text-orange-400')}>
                                        {signal.side}
                                    </span>
                                </td>
                                <td className="px-6 py-4 text-xs">
                                    <div className="font-mono text-gray-200">{signal.strategy_name || signal.meta?.strategy_name || signal.meta?.strategy || 'Unknown'}</div>
                                    <div className="mt-1 flex flex-wrap items-center gap-1">
                                      <span className={clsx('inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-wide', pillTone(signal.strategy_source))}>
                                          source: {strategySourceLabel[signal.strategy_source || 'unknown'] || (signal.strategy_source || 'unknown')}
                                      </span>
                                      {(signal.analysis_timeframe || signal.execution_timeframe) && (
                                        <span className="inline-flex items-center gap-1 rounded-full border border-cyan-500/20 bg-cyan-500/10 px-2 py-0.5 text-[10px] uppercase tracking-wide text-cyan-200">
                                          tf: {signal.analysis_timeframe || '1m'} → {signal.execution_timeframe || signal.analysis_timeframe || '1m'}
                                        </span>
                                      )}
                                    </div>
                                </td>
                                <td className="px-6 py-4">
                                    <div className="space-y-1">
                                        {decision ? (
                                            <span className={clsx('inline-flex px-2 py-1 rounded text-xs font-bold border', decision === 'TAKE' ? 'bg-green-500/10 text-green-400 border-green-500/30' : decision === 'SKIP' ? 'bg-gray-500/10 text-gray-400 border-gray-500/30' : 'bg-red-500/10 text-red-400 border-red-500/30')}>
                                                {decision}
                                            </span>
                                        ) : <span className="text-gray-600">-</span>}
                                        {signal.reject_reason_priority && decision !== 'TAKE' && (
                                            <span className={clsx('inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-wide', pillTone(signal.reject_reason_priority))}>
                                                priority: {rejectPriorityLabel[signal.reject_reason_priority] || signal.reject_reason_priority}
                                            </span>
                                        )}
                                    </div>
                                </td>
                                <td className="px-6 py-4">
                                    {score !== undefined ? (
                                        <div className="flex flex-col">
                                            <span className={clsx('font-bold', score >= 70 ? 'text-green-400' : score >= 50 ? 'text-yellow-400' : 'text-red-400')}>
                                                {score}/100
                                            </span>
                                            {reasons.length > 0 && (
                                                <div className="group relative">
                                                    <button
                                                        type="button"
                                                        className="text-[10px] text-gray-500 underline decoration-dotted cursor-help rounded focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-400"
                                                        aria-label={`Показать ${reasons.length} причин расчёта сигнала`}
                                                        title={reasons.map((r: any) => r.msg).join(' • ')}
                                                    >
                                                        {reasons.length} reasons
                                                    </button>
                                                    <div className="hidden group-hover:block group-focus-within:block absolute z-50 left-0 top-full mt-1 w-72 p-2 bg-gray-900 border border-gray-700 rounded shadow-xl text-xs">
                                                        {reasons.slice(0, 6).map((r: any, idx: number) => (
                                                            <div key={idx} className={clsx('mb-1 last:mb-0', r.severity === 'block' ? 'text-red-400 font-bold' : r.severity === 'warn' ? 'text-yellow-400' : 'text-gray-400')}>
                                                                • {r.msg}
                                                            </div>
                                                        ))}
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                    ) : <span className="text-gray-600">-</span>}
                                </td>
                                <td className="px-6 py-4 font-mono">
                                    <div>{formatPrice(signal.entry)}</div>
                                    {econ.entry_price_rub != null && Number(econ.entry_price_rub) < 10 && (
                                        <div className="text-[10px] text-yellow-400">4 знака для low-price</div>
                                    )}
                                </td>
                                <td className="px-6 py-4 font-mono text-xs">
                                    <div className="text-red-400">SL: {formatPrice(signal.sl)}</div>
                                    <div className="text-emerald-400">TP: {formatPrice(signal.tp)}</div>
                                    <div className="mt-1 text-gray-500">{formatPercent(econ.sl_distance_pct, 3)} / {formatPercent(econ.tp_distance_pct, 3)}</div>
                                    {geometry?.applied && (
                                        <div className="mt-2 rounded-lg border border-cyan-500/20 bg-cyan-500/10 px-2 py-1 text-[10px] text-cyan-200">
                                            <div className="font-semibold">Adaptive geometry: {geometry.phase}</div>
                                            <div>{geometry.action}</div>
                                            {(geometry.original_sl || geometry.original_tp) && (
                                                <div className="mt-1 text-cyan-100/80">orig SL/TP: {formatPrice(geometry.original_sl)} / {formatPrice(geometry.original_tp)}</div>
                                            )}
                                            {Array.isArray(geometry.notes) && geometry.notes.length > 0 && (
                                                <div className="mt-1">{geometry.notes.slice(0, 2).join(' • ')}</div>
                                            )}
                                            {geometry.suggested_timeframe && (
                                                <div className="mt-1 text-cyan-100/80">HTF hint: {geometry.suggested_timeframe}</div>
                                            )}
                                            {(signal.analysis_timeframe || signal.confirmation_timeframe) && (
                                                <div className="mt-1 text-cyan-100/80">analysis/execution: {signal.analysis_timeframe || '1m'} → {signal.execution_timeframe || signal.analysis_timeframe || '1m'}{signal.confirmation_timeframe ? ` | confirm ${signal.confirmation_timeframe}` : ''}</div>
                                            )}
                                        </div>
                                    )}
                                </td>
                                <td className="px-6 py-4 text-xs text-gray-300">
                                    <div>Cost: {econ.round_trip_cost_rub != null ? `${formatPrice(econ.round_trip_cost_rub)} ₽` : '—'}</div>
                                    <div>Min profit: {econ.min_required_profit_rub != null ? `${formatPrice(econ.min_required_profit_rub)} ₽` : '—'}</div>
                                    <div className={clsx('mt-1', econ.expected_profit_after_costs_rub != null && Number(econ.expected_profit_after_costs_rub) > 0 ? 'text-emerald-400' : 'text-red-400')}>
                                        After costs: {econ.expected_profit_after_costs_rub != null ? `${formatPrice(econ.expected_profit_after_costs_rub)} ₽` : '—'}
                                    </div>
                                    {econFlags.length > 0 && (
                                        <div className="mt-2 rounded-lg border border-yellow-500/20 bg-yellow-500/10 px-2 py-1 text-[10px] text-yellow-200">
                                            <div className="inline-flex items-center gap-1 font-semibold"><AlertTriangle className="w-3 h-3" /> Риск</div>
                                            <div>{econFlags.map((flag) => economicFlagsLabel[flag] || flag).join(', ')}</div>
                                        </div>
                                    )}
                                </td>
                                <td className="px-6 py-4 font-mono">{signal.size}</td>
                                <td className="px-6 py-4"><StatusBadge status={signal.status} /></td>
                                <td className="px-6 py-4">
                                    <div className="space-y-1">
                                        <span className={clsx('inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-wide', signal.ai_influenced ? (signal.ai_mode_used === 'required' || signal.ai_mode_used === 'override' ? 'border-purple-500/30 bg-purple-500/10 text-purple-300' : 'border-blue-500/30 bg-blue-500/10 text-blue-300') : 'border-gray-700 bg-gray-800 text-gray-500')}>
                                            {signal.ai_influenced ? (signal.ai_mode_used === 'required' || signal.ai_mode_used === 'override' ? '🤖 ai decision' : '🧠 ai advice') : 'manual rules'}
                                        </span>
                                        <span className={clsx('inline-flex max-w-[11rem] items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-wide', pillTone(signal.ai_influence))}>
                                            {aiInfluenceLabel[signal.ai_influence || 'unknown'] || (signal.ai_influence || 'unknown')}
                                        </span>
                                        <AIBadgeCell
                                            aiDecision={signal.meta?.ai_decision}
                                            deDecision={(signal.meta?.decision as any)?.decision}
                                            finalDecision={signal.meta?.final_decision}
                                            expanded={expandedAI === signal.id}
                                            onToggle={() => setExpandedAI(expandedAI === signal.id ? null : signal.id)}
                                        />
                                    </div>
                                </td>
                                <td className="px-6 py-4 text-right">
                                    {canManualApprove(signal) && (
                                        <div className="flex justify-end gap-2">
                                            <button onClick={() => handleAction(signal.id, 'approve')} disabled={isActionPending} className="p-1 rounded bg-green-600 hover:bg-green-500 text-white transition-colors disabled:opacity-50" title="Одобрить">
                                                <Check className="w-4 h-4" />
                                            </button>
                                            <button onClick={() => handleAction(signal.id, 'reject')} disabled={isActionPending} className="p-1 rounded bg-red-600 hover:bg-red-500 text-white transition-colors disabled:opacity-50" title="Отклонить">
                                                <X className="w-4 h-4" />
                                            </button>
                                        </div>
                                    )}
                                    {processingId === signal.id && <span className="text-xs text-blue-400 animate-pulse">Syncing...</span>}
                                </td>
                            </tr>
                            {expandedAI === signal.id && signal.meta?.ai_decision && (
                                <tr className="bg-gray-900/30">
                                    <td colSpan={13} className="px-6 py-4">
                                        <AIDecisionCard
                                            aiDecision={signal.meta.ai_decision}
                                            deDecision={(signal.meta?.decision as any)?.decision}
                                            finalDecision={signal.meta?.final_decision}
                                        />
                                    </td>
                                </tr>
                            )}
                            </React.Fragment>
                        );
                    })}
                    {!signals?.length && (
                        <tr>
                            <td colSpan={13} className="p-0">
                                <EmptyState
                                    title="Сигналов нет"
                                    description="Бот ещё не нашёл торговых возможностей. Убедитесь, что бот запущен и торговая сессия активна."
                                />
                            </td>
                        </tr>
                    )}
                </tbody>
            </table>
        </div>
    );
};

const StatusBadge = ({ status }: { status: string }) => {
    switch (status) {
        case 'pending_review':
            return <span className={clsx('flex items-center text-xs font-bold', COLORS.STATUS_PENDING)}><Clock className="w-3 h-3 mr-1" /> REVIEW</span>;
        case 'approved':
            return <span className={clsx('text-xs font-bold', COLORS.STATUS_APPROVED)}>APPROVED</span>;
        case 'rejected':
            return <span className={clsx('text-xs font-bold', COLORS.STATUS_REJECTED)}>REJECTED</span>;
        case 'executed':
            return <span className={clsx('text-xs font-bold', COLORS.STATUS_EXECUTED)}>EXECUTED</span>;
        default:
            return <span className="text-gray-500 text-xs">{status}</span>;
    }
};
