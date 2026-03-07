import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '../../services/api';
import { AreaChart, Area, ResponsiveContainer, Tooltip } from 'recharts';
import clsx from 'clsx';
import { TrendingUp, TrendingDown, Activity, DollarSign, ArrowRight } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

// ─── Types ────────────────────────────────────────────────────────────────
interface DailyStats {
    day_pnl: number; trades_count: number; win_rate: number;
    best_trade: number; worst_trade: number; open_positions: number;
}
interface HistoryPoint { ts: number; equity: number; day_pnl: number; }
interface Position {
    instrument_id: string; side: string; qty: number;
    avg_price: number; unrealized_pnl?: number;
}
interface AccountSummary {
    balance: number; equity: number; total_pnl: number;
    day_pnl: number; open_positions: number;
}

// ─── Hooks ────────────────────────────────────────────────────────────────
const useDailyStatsReal = () => useQuery({
    queryKey: ['daily-stats-real'],
    queryFn: async () => {
        const { data } = await apiClient.get('/account/daily-stats');
        return data as DailyStats;
    },
    refetchInterval: 30_000,
    retry: false,
});

const useEquityMini = () => useQuery({
    queryKey: ['equity-mini'],
    queryFn: async () => {
        const { data } = await apiClient.get('/account/history?period_days=7');
        return (data.points ?? []) as HistoryPoint[];
    },
    refetchInterval: 300_000,
    retry: false,
});

const useOpenPositions = () => useQuery({
    queryKey: ['open-positions'],
    queryFn: async () => {
        const { data } = await apiClient.get('/state/positions');
        return (data.items ?? []) as Position[];
    },
    refetchInterval: 15_000,
    retry: false,
});

const useAccountSummary = () => useQuery({
    queryKey: ['account-summary-mini'],
    queryFn: async () => {
        const { data } = await apiClient.get('/account/summary');
        return data as AccountSummary;
    },
    refetchInterval: 30_000,
    retry: false,
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
    const dd = summary?.max_drawdown_pct ?? 0; // NOTE: summary doesn't have this yet, fallback 0

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
                    <ResponsiveContainer width="100%" height={48}>
                        <AreaChart data={chartData} margin={{ top: 2, right: 0, bottom: 2, left: 0 }}>
                            <defs>
                                <linearGradient id="sparkGrad" x1="0" y1="0" x2="0" y2="1">
                                    <stop offset="5%"  stopColor={isUp ? '#10b981' : '#ef4444'} stopOpacity={0.3} />
                                    <stop offset="95%" stopColor={isUp ? '#10b981' : '#ef4444'} stopOpacity={0.02} />
                                </linearGradient>
                            </defs>
                            <Tooltip
                                content={({ active, payload }) =>
                                    active && payload?.length ? (
                                        <div className="bg-gray-800 text-xs px-2 py-1 rounded border border-gray-700">
                                            {payload[0].value?.toLocaleString('ru-RU', { maximumFractionDigits: 0 })} ₽
                                        </div>
                                    ) : null
                                }
                            />
                            <Area type="monotone" dataKey="v" stroke={isUp ? '#10b981' : '#ef4444'}
                                strokeWidth={1.5} fill="url(#sparkGrad)" dot={false} />
                        </AreaChart>
                    </ResponsiveContainer>
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
                        <div key={p.instrument_id} className="px-4 py-3 hover:bg-gray-800/40 transition-colors">
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
                                <span>Qty: {p.qty} · Avg: {p.avg_price?.toFixed(2)}</span>
                            </div>
                        </div>
                    );
                })}
            </div>
        </div>
    );
};
