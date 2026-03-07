import React from 'react';
import clsx from 'clsx';
import { Brain, ChevronDown, ChevronUp, AlertTriangle } from 'lucide-react';

interface AIDecision {
    provider?: string;
    decision?: string;   // TAKE | SKIP | REJECT
    confidence?: number; // 0-100
    reasoning?: string;
    key_factors?: string[];
}

interface AIDecisionCardProps {
    aiDecision?: AIDecision;
    deDecision?: string;
    finalDecision?: string;
    expanded?: boolean;
    onToggle?: () => void;
}

const DECISION_STYLES: Record<string, { pill: string; dot: string; label: string }> = {
    TAKE:   { pill: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30', dot: 'bg-emerald-400', label: 'TAKE' },
    SKIP:   { pill: 'bg-gray-600/20 text-gray-400 border-gray-600/30',          dot: 'bg-gray-400',    label: 'SKIP' },
    REJECT: { pill: 'bg-red-500/20 text-red-400 border-red-500/30',             dot: 'bg-red-400',     label: 'REJECT' },
};

const PROVIDER_LABELS: Record<string, string> = {
    claude: 'Claude',
    ollama: 'Ollama',
    openai: 'GPT-4o',
    skip:   '—',
};

// Compact badge shown inside the signals table row
export const AIBadgeCell: React.FC<{
    aiDecision?: AIDecision;
    deDecision?: string;
    finalDecision?: string;
    onToggle?: () => void;
    expanded?: boolean;
}> = ({ aiDecision, deDecision, finalDecision, onToggle, expanded }) => {
    if (!aiDecision?.decision) {
        return <span className="text-gray-700 text-xs font-mono">—</span>;
    }

    const style = DECISION_STYLES[aiDecision.decision] ?? DECISION_STYLES.SKIP;
    const hasConflict = deDecision && finalDecision &&
        deDecision !== finalDecision;

    return (
        <div className="flex items-center gap-1.5">
            <button
                onClick={onToggle}
                className={clsx(
                    'inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs border font-medium transition-all',
                    style.pill,
                    onToggle && 'cursor-pointer hover:opacity-80'
                )}
            >
                <span className={clsx('w-1.5 h-1.5 rounded-full', style.dot)} />
                {style.label}
                {aiDecision.confidence != null && (
                    <span className="opacity-60">·{aiDecision.confidence}%</span>
                )}
                {onToggle && (expanded
                    ? <ChevronUp className="w-3 h-3" />
                    : <ChevronDown className="w-3 h-3" />
                )}
            </button>

            {hasConflict && (
                <span
                    title={`DE: ${deDecision} → AI override: ${finalDecision}`}
                    className="inline-flex items-center gap-1 px-1.5 py-0.5 bg-yellow-500/20 text-yellow-400 border border-yellow-500/30 rounded text-xs"
                >
                    <AlertTriangle className="w-3 h-3" />
                    conflict
                </span>
            )}
        </div>
    );
};

// Expanded detail card shown in the expandable row
export const AIDecisionCard: React.FC<AIDecisionCardProps> = ({
    aiDecision,
    deDecision,
    finalDecision,
}) => {
    if (!aiDecision) return null;

    const style = DECISION_STYLES[aiDecision.decision ?? 'SKIP'] ?? DECISION_STYLES.SKIP;
    const providerLabel = PROVIDER_LABELS[aiDecision.provider ?? ''] ?? aiDecision.provider ?? '?';

    return (
        <div className="bg-gray-900 border border-gray-700 rounded-xl p-4 space-y-4">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <Brain className="w-4 h-4 text-blue-400" />
                    <span className="font-semibold text-gray-200 text-sm">AI Анализ</span>
                    <span className="text-xs text-gray-500">via {providerLabel}</span>
                </div>
                <div className="flex items-center gap-3">
                    {deDecision && (
                        <div className="text-xs text-gray-500">
                            DE: <span className={clsx('font-bold',
                                deDecision === 'TAKE' ? 'text-emerald-400' :
                                deDecision === 'REJECT' ? 'text-red-400' : 'text-gray-400')}>
                                {deDecision}
                            </span>
                        </div>
                    )}
                    <span className={clsx('px-2 py-0.5 rounded-full text-xs border font-bold', style.pill)}>
                        AI: {style.label}
                        {aiDecision.confidence != null && ` · ${aiDecision.confidence}%`}
                    </span>
                </div>
            </div>

            {/* Confidence bar */}
            {aiDecision.confidence != null && (
                <div>
                    <div className="flex justify-between text-xs text-gray-500 mb-1">
                        <span>Уверенность</span>
                        <span>{aiDecision.confidence}%</span>
                    </div>
                    <div className="h-1.5 bg-gray-800 rounded-full overflow-hidden">
                        <div
                            className={clsx('h-full rounded-full transition-all',
                                aiDecision.confidence >= 70 ? 'bg-emerald-500' :
                                aiDecision.confidence >= 50 ? 'bg-yellow-500' : 'bg-red-500')}
                            style={{ width: `${aiDecision.confidence}%` }}
                        />
                    </div>
                </div>
            )}

            {/* Reasoning */}
            {aiDecision.reasoning && (
                <div>
                    <div className="text-xs text-gray-500 uppercase tracking-wider mb-1.5">Обоснование</div>
                    <p className="text-sm text-gray-300 leading-relaxed bg-gray-800/50 rounded-lg p-3">
                        {aiDecision.reasoning}
                    </p>
                </div>
            )}

            {/* Key factors */}
            {aiDecision.key_factors?.length ? (
                <div>
                    <div className="text-xs text-gray-500 uppercase tracking-wider mb-2">Ключевые факторы</div>
                    <ul className="space-y-1.5">
                        {aiDecision.key_factors.map((f, i) => (
                            <li key={i} className="flex items-start gap-2 text-sm text-gray-300">
                                <span className="mt-1 w-1.5 h-1.5 rounded-full bg-blue-400 shrink-0" />
                                {f}
                            </li>
                        ))}
                    </ul>
                </div>
            ) : null}
        </div>
    );
};
