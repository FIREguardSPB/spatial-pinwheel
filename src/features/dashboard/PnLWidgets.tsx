import React, { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '../../services/api';
import { SimpleAreaChart } from '../../components/charts/SimpleAreaChart';
import clsx from 'clsx';
import { TrendingUp, TrendingDown, Activity, DollarSign, ArrowRight } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { formatDateTimeMsk } from '../../utils/time';

// ─── Types ────────────────────────────────────────────────────────────────
interface DailyStats {
    day_pnl: number; trades_count: number; win_rate: number;
    best_trade: number; worst_trade: number; open_positions: number;
}
interface HistoryPoint { ts: number; equity: number; day_pnl: number; }
interface Position {
    instrument_id: string; side: string; qty: number; opened_qty?: number;
    avg_price: number; unrealized_pnl?: number; realized_pnl?: number;
    sl?: number | null; tp?: number | null; opened_ts: number;
    opened_signal_id?: string | null; opened_order_id?: string | null;
    total_fees_est?: number | null;
}
interface AccountSummary {
    balance: number;
    equity: number;
    total_pnl: number;
    day_pnl: number;
    open_positions: number;
    max_drawdown_pct?: number;
}

// ─── Hooks ────────────────────────────────────────────────────────────────
const useDailyStatsReal = () => useQuery({
    queryKey: ['daily-stats-real'],
    queryFn: async () => {
        try {
            const { data } = await apiClient.get('/account/daily-stats');
            return data as DailyStats;
        } catch {
            return { day_pnl: 0, trades_count: 0, win_rate: 0, best_trade: 0, worst_trade: 0, open_positions: 0 } as DailyStats;
        }
    },
    refetchInterval: 30_000,
    retry: false,
    initialData: { day_pnl: 0, trades_count: 0, win_rate: 0, best_trade: 0, worst_trade: 0, open_positions: 0 } as DailyStats,
    placeholderData: (prev: DailyStats | undefined) => prev ?? ({ day_pnl: 0, trades_count: 0, win_rate: 0, best_trade: 0, worst_trade: 0, open_positions: 0 } as DailyStats),
});

const useEquityMini = () => useQuery({
    queryKey: ['equity-mini'],
    queryFn: async () => {
        try {
            const { data } = await apiClient.get('/account/history?period_days=7');
            return (data.points ?? []) as HistoryPoint[];
        } catch {
            return [] as HistoryPoint[];
        }
    },
    refetchInterval: 300_000,
    retry: false,
    initialData: [] as HistoryPoint[],
    placeholderData: (prev: HistoryPoint[] | undefined) => prev ?? [],
});

const useOpenPositions = () => useQuery({
    queryKey: ['open-positions'],
    queryFn: async () => {
        try {
            const { data } = await apiClient.get('/state/positions');
            return (data.items ?? []) as Position[];
        } catch {
            return [] as Position[];
        }
    },
    refetchInterval: 15_000,
    retry: false,
    initialData: [] as Position[],
    placeholderData: (prev: Position[] | undefined) => prev ?? [],
});

const useAccountSummary = () => useQuery({
    queryKey: ['account-summary-mini'],
    queryFn: async () => {
        try {
            const { data } = await apiClient.get('/account/summary');
            return data as AccountSummary;
        } catch {
            return { balance: 0, equity: 0, total_pnl: 0, day_pnl: 0, open_positions: 0, max_drawdown_pct: 0 } as AccountSummary;
        }
    },
    refetchInterval: 30_000,
    retry: false,
    initialData: { balance: 0, equity: 0, total_pnl: 0, day_pnl: 0, open_positions: 0, max_drawdown_pct: 0 } as AccountSummary,
    placeholderData: (prev: AccountSummary | undefined) => prev ?? ({ balance: 0, equity: 0, total_pnl: 0, day_pnl: 0, open_positions: 0, max_drawdown_pct: 0 } as AccountSummary),
});

// ─── PnLWidget ────────────────────────────────────────────────────────────
export const PnLWidget: React.FC = () => {
    const { data: stats } = useDailyStatsReal();
    const { data: summary } = useAccountSummary();
    const navigate = useNavigate();
    const pnl = stats?.day_pnl ?? 0;
    const isPos = pnl >= 0;

    return (
        <div
            className="bg-gray-900 border border-gray-800 rounded-lg p-4 flex flex-col justify-between cursor-pointer hover:border-gray-600 transition-colors"
            onClick={() => navigate('/account')}
        >
            <div className="flex items-center justify-between">
                <span className="text-gray-500 text-xs uppercase font-bold tracking-wider">Day P&L</span>
                <ArrowRight className="w-3.5 h-3.5 text-gray-700" />
            </div>
            <div className="flex items-center mt-2">
                <DollarSign className="w-5 h-5 text-gray-400 mr-1 shrink-0" />
                <span className={clsx('text-2xl font-bold font-mono', isPos ? 'text-emerald-400' : 'text-red-400')}>
                    {pnl > 0 ? '+' : ''}{pnl.toFixed(2)} ₽
                </span>
            </div>
            {summary && (
                <div className="mt-2 text-xs text-gray-600">
                    Equity: {summary.equity.toLocaleString('ru-RU', { maximumFractionDigits: 0 })} ₽
                </div>
            )}
        </div>
    );
};

// ─── DrawdownWidget ───────────────────────────────────────────────────────
export const DrawdownWidget: React.FC = () => {
    const { data: summary } = useAccountSummary();
    return (
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 flex flex-col justify-between">
            <span className="text-gray-500 text-xs uppercase font-bold tracking-wider">Open Pos</span>
            <div className="flex items-center mt-2">
                <Activity className="w-5 h-5 text-blue-500 mr-2 shrink-0" />
                <span className="text-2xl font-bold font-mono">{summary?.open_positions ?? 0}</span>
            </div>
            <div className="mt-2 text-xs text-gray-600">
                Open P&L: {((summary?.equity ?? 0) - (summary?.balance ?? 0)).toFixed(2)} ₽
            </div>
        </div>
    );
};

// ─── EquityCurveChart (mini sparkline) ───────────────────────────────────
export const EquityCurveChart: React.FC = () => {
    const { data: points = [] } = useEquityMini();
    const { data: stats } = useDailyStatsReal();

    const chartData = points.slice(-30).map(p => ({ v: p.equity }));
    const isUp = points.length >= 2
        ? points[points.length - 1]?.equity >= points[0]?.equity
        : true;

    return (
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 flex flex-col justify-between">
            <span className="text-gray-500 text-xs uppercase font-bold tracking-wider">Equity (7d)</span>
            <div className="flex-1 min-h-0 mt-2" style={{ height: 48 }}>
                {chartData.length >= 2 ? (
                    <SimpleAreaChart
                        data={chartData}
                        xKey="v"
                        yKey="v"
                        height={48}
                        color={isUp ? '#10b981' : '#ef4444'}
                        emptyLabel="нет данных"
                        formatValue={(value) => value.toLocaleString('ru-RU', { maximumFractionDigits: 0 }) + ' ₽'}
                        formatLabel={() => 'Equity'}
                        showGrid={false}
                    />
                ) : (
                    <div className="h-12 flex items-center justify-center text-gray-700 text-xs">нет данных</div>
                )}
            </div>
            <div className="flex items-center mt-1">
                {isUp
                    ? <TrendingUp className="w-3.5 h-3.5 text-emerald-400 mr-1" />
                    : <TrendingDown className="w-3.5 h-3.5 text-red-400 mr-1" />}
                <span className={clsx('text-xs font-medium', isUp ? 'text-emerald-400' : 'text-red-400')}>
                    {stats?.win_rate != null ? `WR ${stats.win_rate.toFixed(0)}%` : '—'}
                </span>
            </div>
        </div>
    );
};

// ─── OpenPositionsPanel (right sidebar) ──────────────────────────────────
export const OpenPositionsPanel: React.FC = () => {
    const { data: positions = [] } = useOpenPositions();
    const [expandedId, setExpandedId] = useState<string | null>(null);

    if (positions.length === 0) return (
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 h-full flex items-center justify-center">
            <span className="text-gray-600 text-sm">Нет открытых позиций</span>
        </div>
    );

    return (
        <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden h-full flex flex-col">
            <div className="px-4 py-3 border-b border-gray-800">
                <span className="text-xs text-gray-500 uppercase font-bold tracking-wider">Открытые позиции</span>
            </div>
            <div className="flex-1 overflow-y-auto divide-y divide-gray-800">
                {positions.map(p => {
                    const upnl = p.unrealized_pnl ?? 0;
                    return (
                        <button
                            type="button"
                            key={p.instrument_id}
                            onClick={() => setExpandedId((prev) => (prev === p.instrument_id ? null : p.instrument_id))}
                            className="w-full px-4 py-3 text-left hover:bg-gray-800/40 transition-colors"
                        >
                            <div className="flex items-center justify-between">
                                <div>
                                    <span className="font-bold text-gray-200 text-sm">{p.instrument_id}</span>
                                    <span className={clsx('ml-2 text-xs font-medium px-1.5 py-0.5 rounded',
                                        p.side === 'BUY' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400')}>
                                        {p.side}
                                    </span>
                                </div>
                                <span className={clsx('text-sm font-bold font-mono', upnl >= 0 ? 'text-emerald-400' : 'text-red-400')}>
                                    {upnl > 0 ? '+' : ''}{upnl.toFixed(2)} ₽
                                </span>
                            </div>
                            <div className="flex items-center justify-between mt-1 text-xs text-gray-600">
                                <span>Qty: {p.qty} · Avg: {(p.avg_price ?? 0).toFixed(2)}</span>
                                <span>{expandedId === p.instrument_id ? 'Скрыть детали' : 'Показать детали'}</span>
                            </div>
                            {expandedId === p.instrument_id ? (
                                <div className="mt-3 grid grid-cols-2 gap-2 rounded-lg border border-gray-800 bg-gray-950/80 p-3 text-[11px] text-gray-400">
                                    <div><span className="text-gray-600">Открыта:</span> {formatDateTimeMsk(p.opened_ts)}</div>
                                    <div><span className="text-gray-600">SL:</span> {p.sl != null ? p.sl.toFixed(2) : '—'}</div>
                                    <div><span className="text-gray-600">TP:</span> {p.tp != null ? p.tp.toFixed(2) : '—'}</div>
                                    <div><span className="text-gray-600">Opened qty:</span> {p.opened_qty ?? p.qty}</div>
                                    <div><span className="text-gray-600">Signal:</span> <span className="font-mono">{p.opened_signal_id || '—'}</span></div>
                                    <div><span className="text-gray-600">Order:</span> <span className="font-mono">{p.opened_order_id || '—'}</span></div>
                                    <div><span className="text-gray-600">Fees est:</span> {(p.total_fees_est ?? 0).toFixed(2)} ₽</div>
                                    <div><span className="text-gray-600">Realized:</span> {p.realized_pnl?.toFixed(2) ?? '0.00'} ₽</div>
                                </div>
                            ) : null}
                        </button>
                    );
                })}
            </div>
        </div>
    );
};
