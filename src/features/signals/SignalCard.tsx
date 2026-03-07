import React from 'react';
import { Check, X, Clock } from 'lucide-react';
import clsx from 'clsx';
import { toast } from 'sonner';

interface SignalCardProps {
  signal: any;
  onAction: (id: string, action: 'approve' | 'reject') => void;
  isPending: boolean;
  processingId: string | null;
}

const StatusRu: Record<string, string> = {
  pending_review: 'Ожидает',
  approved:       'Одобрен',
  rejected:       'Отклонён',
  executed:       'Исполнен',
  expired:        'Истёк',
};

export const SignalCard: React.FC<SignalCardProps> = ({ signal, onAction, isPending, processingId }) => {
  const isProcessing = processingId === signal.id;
  const score = signal.meta?.decision?.score;
  const isPos = signal.side === 'BUY';

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="font-bold text-gray-100 text-lg">{signal.instrument_id}</span>
          <span className={clsx('px-2 py-0.5 rounded font-bold text-sm',
            isPos ? 'bg-blue-500/20 text-blue-300' : 'bg-orange-500/20 text-orange-300')}>
            {isPos ? 'ПОКУПКА' : 'ПРОДАЖА'}
          </span>
        </div>
        {score != null && (
          <span className={clsx('text-xs font-bold px-2 py-0.5 rounded-full border',
            score >= 70 ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
              : score >= 50 ? 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20'
              : 'bg-gray-800 text-gray-500 border-gray-700')}>
            {score}
          </span>
        )}
      </div>

      {/* Prices */}
      <div className="grid grid-cols-3 gap-2 text-sm">
        <div className="bg-gray-800 rounded-lg p-2 text-center">
          <div className="text-gray-500 text-xs mb-0.5">Вход</div>
          <div className="font-mono font-bold text-gray-200">{signal.entry?.toFixed(2)}</div>
        </div>
        <div className="bg-red-950/30 rounded-lg p-2 text-center">
          <div className="text-red-400/70 text-xs mb-0.5">SL</div>
          <div className="font-mono font-bold text-red-400">{signal.sl?.toFixed(2)}</div>
        </div>
        <div className="bg-emerald-950/30 rounded-lg p-2 text-center">
          <div className="text-emerald-400/70 text-xs mb-0.5">TP</div>
          <div className="font-mono font-bold text-emerald-400">{signal.tp?.toFixed(2)}</div>
        </div>
      </div>

      {/* R/R + Status */}
      <div className="flex items-center justify-between text-xs text-gray-500">
        <span>R/R: <span className="font-mono text-gray-300">{signal.r?.toFixed(2)}</span></span>
        <span className={clsx('font-medium',
          signal.status === 'pending_review' ? 'text-yellow-400' :
          signal.status === 'approved'       ? 'text-green-400'  :
          signal.status === 'rejected'       ? 'text-red-400'    : 'text-blue-400')}>
          {StatusRu[signal.status] ?? signal.status}
        </span>
      </div>

      {/* Actions */}
      {signal.status === 'pending_review' && (
        <div className="grid grid-cols-2 gap-2">
          <button
            onClick={() => onAction(signal.id, 'reject')}
            disabled={isPending || isProcessing}
            className="flex items-center justify-center gap-2 py-3 bg-red-600/20 hover:bg-red-600/40 text-red-400 border border-red-500/20 rounded-xl font-medium text-sm transition-colors disabled:opacity-50">
            <X className="w-4 h-4" /> Отклонить
          </button>
          <button
            onClick={() => onAction(signal.id, 'approve')}
            disabled={isPending || isProcessing}
            className="flex items-center justify-center gap-2 py-3 bg-emerald-600/20 hover:bg-emerald-600/40 text-emerald-400 border border-emerald-500/20 rounded-xl font-medium text-sm transition-colors disabled:opacity-50">
            <Check className="w-4 h-4" /> Одобрить
          </button>
        </div>
      )}
      {isProcessing && (
        <div className="text-center text-xs text-blue-400 animate-pulse py-1">Синхронизация...</div>
      )}
    </div>
  );
};
