import React, { useState } from 'react';
import { useSignals, useSignalAction } from './hooks';
import { format } from 'date-fns';
import clsx from 'clsx';
import { Check, X, Clock } from 'lucide-react';
import { COLORS } from '../../constants';

export const SignalsTable: React.FC = () => {
    const { data: signals, isLoading, isError } = useSignals();

    // Debug logging
    // console.log('SignalsTable render:', { signals, isLoading });

    const { mutate: performAction, isPending: isActionPending } = useSignalAction();
    const [processingId, setProcessingId] = useState<string | null>(null);

    const handleAction = (id: string, action: 'approve' | 'reject') => {
        setProcessingId(id);
        performAction({ id, action }, {
            onSettled: () => setProcessingId(null)
        });
    };

    if (isLoading) return <div className="p-8 text-center text-gray-500">Loading signals...</div>;
    if (isError) return <div className="p-8 text-center text-red-500 font-bold">Failed to load signals. API Disconnected.</div>;

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
                        <th className="px-6 py-3">Size</th>
                        <th className="px-6 py-3">Status</th>
                        <th className="px-6 py-3 text-right">Actions</th>
                    </tr>
                </thead>
                <tbody className="divide-y divide-gray-800">
                    {signals?.map((signal) => {
                        const decisionData = signal.meta?.decision;
                        const score = decisionData?.score;
                        const decision = decisionData?.decision;
                        const reasons = decisionData?.reasons || [];

                        return (
                            <tr key={signal.id} className="hover:bg-gray-800/50 transition-colors">
                                <td className="px-6 py-4 font-mono text-gray-400">
                                    {format(signal.ts * (signal.ts > 10000000000 ? 1 : 1000), 'HH:mm:ss')}
                                    <br />
                                    <span className="text-xs text-gray-600">{format(signal.ts * (signal.ts > 10000000000 ? 1 : 1000), 'dd MMM')}</span>
                                </td>
                                <td className="px-6 py-4 font-bold text-gray-200">{signal.instrument_id}</td>
                                <td className="px-6 py-4">
                                    <span className={clsx("px-2 py-1 rounded text-xs font-bold",
                                        signal.side === 'BUY' ? "bg-blue-500/10 text-blue-400" : "bg-orange-500/10 text-orange-400"
                                    )}>
                                        {signal.side}
                                    </span>
                                </td>
                                <td className="px-6 py-4 text-xs font-mono text-gray-400">
                                    {signal.meta?.strategy || 'Unknown'}
                                </td>
                                <td className="px-6 py-4">
                                    {decision ? (
                                        <span className={clsx("px-2 py-1 rounded text-xs font-bold border",
                                            decision === 'TAKE' ? "bg-green-500/10 text-green-400 border-green-500/30" :
                                                decision === 'SKIP' ? "bg-gray-500/10 text-gray-400 border-gray-500/30" :
                                                    "bg-red-500/10 text-red-400 border-red-500/30"
                                        )}>
                                            {decision}
                                        </span>
                                    ) : <span className="text-gray-600">-</span>}
                                </td>
                                <td className="px-6 py-4">
                                    {score !== undefined ? (
                                        <div className="flex flex-col">
                                            <span className={clsx("font-bold",
                                                score >= 70 ? "text-green-400" :
                                                    score >= 50 ? "text-yellow-400" : "text-red-400"
                                            )}>
                                                {score}/100
                                            </span>
                                            {reasons.length > 0 && (
                                                <div className="group relative">
                                                    <span className="text-[10px] text-gray-500 underline cursor-help">
                                                        {reasons.length} reasons
                                                    </span>
                                                    <div className="hidden group-hover:block absolute z-50 left-0 top-full mt-1 w-64 p-2 bg-gray-900 border border-gray-700 rounded shadow-xl text-xs">
                                                        {reasons.slice(0, 5).map((r: any, idx: number) => (
                                                            <div key={idx} className={clsx("mb-1",
                                                                r.severity === 'block' ? "text-red-400 font-bold" :
                                                                    r.severity === 'warn' ? "text-yellow-400" : "text-gray-400"
                                                            )}>
                                                                • {r.msg}
                                                            </div>
                                                        ))}
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                    ) : <span className="text-gray-600">-</span>}
                                </td>
                                <td className="px-6 py-4 font-mono">{signal.entry.toFixed(2)}</td>
                                <td className="px-6 py-4 font-mono text-xs">
                                    <div className="text-red-400">SL: {signal.sl.toFixed(2)}</div>
                                    <div className="text-green-400">TP: {signal.tp.toFixed(2)}</div>
                                </td>
                                <td className="px-6 py-4 font-mono">{signal.size}</td>
                                <td className="px-6 py-4">
                                    <StatusBadge status={signal.status} />
                                </td>
                                <td className="px-6 py-4 text-right">
                                    {signal.status === 'pending_review' && (
                                        <div className="flex justify-end gap-2">
                                            <button
                                                onClick={() => handleAction(signal.id, 'approve')}
                                                disabled={isActionPending}
                                                className="p-1 rounded bg-green-600 hover:bg-green-500 text-white transition-colors disabled:opacity-50"
                                                title="Approve"
                                            >
                                                <Check className="w-4 h-4" />
                                            </button>
                                            <button
                                                onClick={() => handleAction(signal.id, 'reject')}
                                                disabled={isActionPending}
                                                className="p-1 rounded bg-red-600 hover:bg-red-500 text-white transition-colors disabled:opacity-50"
                                                title="Reject"
                                            >
                                                <X className="w-4 h-4" />
                                            </button>
                                        </div>
                                    )}
                                    {processingId === signal.id && <span className="text-xs text-blue-400 animate-pulse">Syncing...</span>}
                                </td>
                            </tr>
                        );
                    })}
                    {!signals?.length && (
                        <tr>
                            <td colSpan={11} className="px-6 py-8 text-center text-gray-600 italic">
                                No signals in queue
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
            return <span className={clsx("flex items-center text-xs font-bold", COLORS.STATUS_PENDING)}><Clock className="w-3 h-3 mr-1" /> REVIEW</span>;
        case 'approved':
            return <span className={clsx("text-xs font-bold", COLORS.STATUS_APPROVED)}>APPROVED</span>;
        case 'rejected':
            return <span className={clsx("text-xs font-bold", COLORS.STATUS_REJECTED)}>REJECTED</span>;
        case 'executed':
            return <span className={clsx("text-xs font-bold", COLORS.STATUS_EXECUTED)}>EXECUTED</span>;
        default:
            return <span className="text-gray-500 text-xs">{status}</span>;
    }
}
