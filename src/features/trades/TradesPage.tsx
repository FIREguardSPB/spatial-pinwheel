import React, { useState, useMemo } from 'react';
import { Skeleton, EmptyState } from '../../components/ui/UIComponents';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '../../services/api';
import { format } from 'date-fns';
import clsx from 'clsx';
import {
    TrendingUp, TrendingDown, Download, Filter,
    ChevronUp, ChevronDown, BarChart2, Award, Minus
} from 'lucide-react';

// ── API types ──────────────────────────────────────────────────────────────
interface Trade {
    id: string; ts: number; instrument_id: string; side: string;
    entry_price: number; close_price: number; qty: number;
    realized_pnl: number; close_reason: string; duration_sec: number;
    strategy: string; ai_decision: string; ai_confidence?: number; de_score?: number;
}
interface TradeStats {
    total_trades: number; win_rate: number; total_pnl: number;
    avg_trade_pnl: number; best_trade: number; worst_trade: number;
    profit_factor?: number; avg_duration_sec: number;
}

// ── Hooks ──────────────────────────────────────────────────────────────────
function useTrades(filters: Record<string, string | number>) {
    return useQuery({
        queryKey: ['trades', filters],
        queryFn: async () => {
            const params = new URLSearchParams();
            Object.entries(filters).forEach(([k, v]) => v && params.set(k, String(v)));
            const { data } = await apiClient.get(`/trades?${params}`);
            return data as { items: Trade[]; total: number };
        },
        refetchInterval: 30_000,
    });
}
function useTradeStats() {
    return useQuery({
        queryKey: ['trade-stats'],
        queryFn: async () => {
            const { data } = await apiClient.get('/trades/stats');
            return data as TradeStats;
        },
        refetchInterval: 60_000,
    });
}

// ── Helpers ────────────────────────────────────────────────────────────────
const pnlColor = (v: number) => v > 0 ? 'text-emerald-400' : v < 0 ? 'text-red-400' : 'text-gray-400';
const fmtPnl   = (v: number) => `${v > 0 ? '+' : ''}${v.toFixed(2)} ₽`;
const fmtDur   = (s: number) => s < 60 ? `${s}s` : `${Math.round(s / 60)}m`;

function StatCard({ label, value, sub, icon: Icon, color = 'text-gray-200' }: {
    label: string; value: string; sub?: string; icon?: React.FC<any>; color?: string;
}) {
    return (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
            <div className="flex items-center justify-between mb-1">
                <span className="text-xs text-gray-500 uppercase tracking-wider font-semibold">{label}</span>
                {Icon && <Icon className="w-4 h-4 text-gray-600" />}
            </div>
            <div className={clsx('text-2xl font-bold font-mono', color)}>{value}</div>
            {sub && <div className="text-xs text-gray-600 mt-1">{sub}</div>}
        </div>
    );
}

function AIBadge({ decision, confidence }: { decision: string; confidence?: number }) {
    if (!decision) return <span className="text-gray-600 text-xs">—</span>;
    const colors: Record<string, string> = {
        TAKE:   'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
        SKIP:   'bg-gray-600/20 text-gray-400 border-gray-600/30',
        REJECT: 'bg-red-500/20 text-red-400 border-red-500/30',
    };
    return (
        <span className={clsx('inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs border font-medium',
            colors[decision] ?? 'bg-gray-800 text-gray-400 border-gray-700')}>
            {decision}
            {confidence != null && <span className="opacity-60">·{confidence}%</span>}
        </span>
    );
}

// ── Main component ─────────────────────────────────────────────────────────
export default function TradesPage() {
    const [filters, setFilters] = useState<Record<string, string>>({
        limit: '100', sort_by: 'ts', sort_dir: 'desc'
    });
    const [sortBy, setSortBy]     = useState('ts');
    const [sortDir, setSortDir]   = useState<'asc' | 'desc'>('desc');
    const [expanded, setExpanded] = useState<string | null>(null);

    const { data, isLoading } = useTrades({ ...filters, sort_by: sortBy, sort_dir: sortDir });
    const { data: stats }     = useTradeStats();
    const trades = data?.items ?? [];

    const handleSort = (col: string) => {
        if (sortBy === col) setSortDir(d => d === 'desc' ? 'asc' : 'desc');
        else { setSortBy(col); setSortDir('desc'); }
    };

    const handleExport = () => {
        window.open(`${import.meta.env.VITE_API_URL || '/api/v1'}/trades/export`, '_blank');
    };

    const SortIcon = ({ col }: { col: string }) => sortBy === col
        ? (sortDir === 'desc' ? <ChevronDown className="w-3 h-3" /> : <ChevronUp className="w-3 h-3" />)
        : <Minus className="w-3 h-3 opacity-30" />;

    return (
        <div className="h-full flex flex-col bg-gray-950 overflow-hidden">
            {/* Header */}
            <div className="border-b border-gray-800 px-6 py-4 shrink-0">
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-xl font-bold text-gray-100">Журнал сделок</h1>
                        <p className="text-sm text-gray-500 mt-0.5">История исполненных позиций</p>
                    </div>
                    <button
                        onClick={handleExport}
                        className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-sm font-medium transition-colors"
                    >
                        <Download className="w-4 h-4" /> Экспорт CSV
                    </button>
                </div>
            </div>

            <div className="flex-1 overflow-y-auto p-6 space-y-6">
                {/* Stats Row */}
                <div className="grid grid-cols-2 md:grid-cols-4 xl:grid-cols-7 gap-3">
                    <StatCard label="Сделок" value={String(stats?.total_trades ?? '—')} icon={BarChart2} />
                    <StatCard label="Win Rate" value={stats ? `${stats.win_rate.toFixed(1)}%` : '—'} icon={TrendingUp} color={stats && stats.win_rate >= 50 ? 'text-emerald-400' : 'text-red-400'} />
                    <StatCard label="Total P&L" value={stats ? fmtPnl(stats.total_pnl) : '—'} color={pnlColor(stats?.total_pnl ?? 0)} />
                    <StatCard label="Avg Trade" value={stats ? fmtPnl(stats.avg_trade_pnl) : '—'} color={pnlColor(stats?.avg_trade_pnl ?? 0)} />
                    <StatCard label="Best" value={stats ? fmtPnl(stats.best_trade) : '—'} icon={Award} color="text-emerald-400" />
                    <StatCard label="Worst" value={stats ? fmtPnl(stats.worst_trade) : '—'} color="text-red-400" />
                    <StatCard label="Profit Factor" value={stats?.profit_factor != null ? stats.profit_factor.toFixed(2) : '—'} color={stats && (stats.profit_factor ?? 0) >= 1.5 ? 'text-emerald-400' : 'text-yellow-400'} />
                </div>

                {/* Filters */}
                <div className="flex items-center gap-3 flex-wrap">
                    <Filter className="w-4 h-4 text-gray-500" />
                    {[
                        { key: 'instrument', placeholder: 'Инструмент...' },
                        { key: 'side',       placeholder: 'Сторона (BUY/SELL)' },
                        { key: 'outcome',    placeholder: 'Исход (profit/loss)' },
                        { key: 'strategy',   placeholder: 'Стратегия...' },
                    ].map(({ key, placeholder }) => (
                        <input
                            key={key}
                            placeholder={placeholder}
                            value={filters[key] ?? ''}
                            onChange={e => setFilters(f => ({ ...f, [key]: e.target.value }))}
                            className="px-3 py-1.5 bg-gray-900 border border-gray-700 rounded-lg text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-blue-500 w-44"
                        />
                    ))}
                    <button
                        onClick={() => setFilters({ limit: '100', sort_by: 'ts', sort_dir: 'desc' })}
                        className="px-3 py-1.5 text-sm text-gray-500 hover:text-gray-300 transition-colors"
                    >
                        Сбросить
                    </button>
                </div>

                {/* Table */}
                <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
                    {isLoading ? (
                        <div className="p-4 space-y-2">
                            {[1,2,3,4,5].map(i => <Skeleton key={i} className="h-10 rounded-lg" />)}
                        </div>
                    ) : trades.length === 0 ? (
                        <EmptyState
                            title="Нет сделок"
                            message="По текущим фильтрам сделок не найдено"
                        />
                    ) : (
                        <table className="w-full text-sm text-left">
                            <thead className="bg-gray-800/80 text-gray-400 text-xs uppercase tracking-wider sticky top-0">
                                <tr>
                                    {[
                                        { key: 'ts', label: 'Время' },
                                        { key: 'instrument_id', label: 'Инструмент' },
                                        { key: 'side', label: 'Side' },
                                        { key: 'entry_price', label: 'Вход' },
                                        { key: 'close_price', label: 'Выход' },
                                        { key: 'qty', label: 'Qty' },
                                        { key: 'realized_pnl', label: 'P&L' },
                                        { key: 'duration_sec', label: 'Длит.' },
                                        { key: null, label: 'Стратегия' },
                                        { key: null, label: 'AI' },
                                        { key: null, label: 'Причина' },
                                    ].map(({ key, label }) => (
                                        <th
                                            key={label}
                                            className={clsx('px-4 py-3', key && 'cursor-pointer hover:text-gray-200 select-none')}
                                            onClick={() => key && handleSort(key)}
                                        >
                                            <span className="flex items-center gap-1">
                                                {label} {key && <SortIcon col={key} />}
                                            </span>
                                        </th>
                                    ))}
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-800">
                                {trades.map(t => (
                                    <React.Fragment key={t.id}>
                                        <tr
                                            className="hover:bg-gray-800/40 transition-colors cursor-pointer"
                                            onClick={() => setExpanded(expanded === t.id ? null : t.id)}
                                        >
                                            <td className="px-4 py-3 font-mono text-gray-400 text-xs">
                                                {format(t.ts, 'dd.MM HH:mm')}
                                            </td>
                                            <td className="px-4 py-3 font-bold text-gray-200">{t.instrument_id}</td>
                                            <td className="px-4 py-3">
                                                <span className={clsx('px-2 py-0.5 rounded text-xs font-bold',
                                                    t.side === 'BUY' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400')}>
                                                    {t.side}
                                                </span>
                                            </td>
                                            <td className="px-4 py-3 font-mono text-gray-300">{t.entry_price.toFixed(2)}</td>
                                            <td className="px-4 py-3 font-mono text-gray-300">{t.close_price.toFixed(2)}</td>
                                            <td className="px-4 py-3 font-mono text-gray-400">{t.qty}</td>
                                            <td className={clsx('px-4 py-3 font-bold font-mono', pnlColor(t.realized_pnl))}>
                                                {fmtPnl(t.realized_pnl)}
                                            </td>
                                            <td className="px-4 py-3 text-gray-500 font-mono text-xs">{fmtDur(t.duration_sec)}</td>
                                            <td className="px-4 py-3 text-gray-500 text-xs">{t.strategy}</td>
                                            <td className="px-4 py-3"><AIBadge decision={t.ai_decision} confidence={t.ai_confidence} /></td>
                                            <td className="px-4 py-3 text-gray-600 text-xs">{t.close_reason}</td>
                                        </tr>
                                        {expanded === t.id && (
                                            <tr className="bg-gray-800/30">
                                                <td colSpan={11} className="px-6 py-4">
                                                    <div className="grid grid-cols-3 gap-4 text-xs text-gray-400">
                                                        <div><span className="text-gray-600">ID:</span> <span className="font-mono">{t.id}</span></div>
                                                        <div><span className="text-gray-600">DE Score:</span> {t.de_score ?? '—'}</div>
                                                        <div><span className="text-gray-600">AI Confidence:</span> {t.ai_confidence != null ? `${t.ai_confidence}%` : '—'}</div>
                                                    </div>
                                                </td>
                                            </tr>
                                        )}
                                    </React.Fragment>
                                ))}
                            </tbody>
                        </table>
                    )}
                </div>
                {data && <div className="text-xs text-gray-600 text-right">Всего: {data.total} сделок</div>}
            </div>
        </div>
    );
}
