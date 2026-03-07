import React from 'react';
import { Skeleton, EmptyState } from '../../components/ui/UIComponents';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '../../services/api';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { format } from 'date-fns';
import { ru } from 'date-fns/locale';
import clsx from 'clsx';
import {
    Wallet, TrendingUp, TrendingDown, Activity,
    ExternalLink, BarChart2, Clock
} from 'lucide-react';

// ── Types ──────────────────────────────────────────────────────────────────
interface AccountSummary {
    mode: string; balance: number; equity: number; open_pnl: number;
    day_pnl: number; total_pnl: number; open_positions: number;
    max_drawdown_pct: number;
    broker_info: { name: string; type: string; status: string };
}
interface HistoryPoint { ts: number; balance: number; equity: number; day_pnl: number; }
interface DailyStats {
    day_pnl: number; trades_count: number; win_rate: number;
    best_trade: number; worst_trade: number; open_positions: number;
}

// ── Hooks ──────────────────────────────────────────────────────────────────
const useSummary = () => useQuery({
    queryKey: ['account-summary'],
    queryFn: async () => { const { data } = await apiClient.get('/account/summary'); return data as AccountSummary; },
    refetchInterval: 30_000,
});
const useHistory = (days = 30) => useQuery({
    queryKey: ['account-history', days],
    queryFn: async () => { const { data } = await apiClient.get(`/account/history?period_days=${days}`); return data.points as HistoryPoint[]; },
    refetchInterval: 300_000,
});
const useDailyStats = () => useQuery({
    queryKey: ['daily-stats'],
    queryFn: async () => { const { data } = await apiClient.get('/account/daily-stats'); return data as DailyStats; },
    refetchInterval: 30_000,
});

// ── Helpers ────────────────────────────────────────────────────────────────
const fmt    = (v: number, d = 2) => v.toLocaleString('ru-RU', { minimumFractionDigits: d, maximumFractionDigits: d });
const pnlClr = (v: number) => v > 0 ? 'text-emerald-400' : v < 0 ? 'text-red-400' : 'text-gray-400';
const fmtPnl = (v: number) => `${v > 0 ? '+' : ''}${fmt(v)} ₽`;

function MetricCard({ label, value, sub, icon: Icon, color = '' }: {
    label: string; value: string; sub?: string; icon?: React.FC<any>; color?: string;
}) {
    return (
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
            <div className="flex items-center justify-between mb-3">
                <span className="text-xs text-gray-500 uppercase tracking-widest font-semibold">{label}</span>
                {Icon && <Icon className="w-4 h-4 text-gray-700" />}
            </div>
            <div className={clsx('text-3xl font-bold font-mono', color || 'text-gray-100')}>{value}</div>
            {sub && <div className="text-xs text-gray-600 mt-2">{sub}</div>}
        </div>
    );
}

// ── Custom Tooltip ─────────────────────────────────────────────────────────
const CustomTooltip = ({ active, payload, label }: any) => {
    if (!active || !payload?.length) return null;
    const equity = payload[0]?.value;
    return (
        <div className="bg-gray-800 border border-gray-700 rounded-lg p-3 text-xs shadow-xl">
            <div className="text-gray-400 mb-1">{label}</div>
            <div className="text-white font-bold">{fmt(equity)} ₽</div>
        </div>
    );
};

// ── Main ───────────────────────────────────────────────────────────────────
export default function AccountPage() {
    const { data: summary, isLoading } = useSummary();
    const { data: history = [] }       = useHistory(30);
    const { data: daily }              = useDailyStats();
    const [histDays, setHistDays]      = React.useState(30);
    const { data: historyFull = [] }   = useHistory(histDays);

    const chartData = historyFull.map(p => ({
        date:   format(p.ts, 'dd MMM', { locale: ru }),
        equity: p.equity,
        pnl:    p.day_pnl,
    }));

    const isLive = summary?.mode === 'tbank';
    const equityColor = (summary?.total_pnl ?? 0) >= 0 ? '#10b981' : '#ef4444';

    if (isLoading) return (
        <div className="p-4 space-y-4 max-w-4xl mx-auto">
            <Skeleton className="h-32 rounded-xl" />
            <Skeleton className="h-48 rounded-xl" />
            <Skeleton className="h-24 rounded-xl" />
        </div>
    );

    return (
        <div className="h-full overflow-y-auto bg-gray-950">
            <div className="max-w-6xl mx-auto p-6 space-y-8">
                {/* Header */}
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-2xl font-bold text-gray-100">Мой счёт</h1>
                        <p className="text-sm text-gray-500 mt-1">
                            {summary?.broker_info.name} ·{' '}
                            <span className={clsx('font-medium', isLive ? 'text-green-400' : 'text-yellow-400')}>
                                {isLive ? '🟢 Live' : '🟡 Виртуальный счёт'}
                            </span>
                        </p>
                    </div>
                    {isLive && (
                        <div className="flex gap-3">
                            <a
                                href="https://www.tbank.ru/invest/"
                                target="_blank" rel="noopener noreferrer"
                                className="flex items-center gap-2 px-4 py-2 bg-yellow-500 hover:bg-yellow-400 text-black rounded-lg text-sm font-bold transition-colors"
                            >
                                <ExternalLink className="w-4 h-4" /> Пополнить в T-Bank
                            </a>
                            <a
                                href="https://www.tbank.ru/invest/"
                                target="_blank" rel="noopener noreferrer"
                                className="flex items-center gap-2 px-4 py-2 bg-gray-800 hover:bg-gray-700 text-gray-200 rounded-lg text-sm font-medium transition-colors border border-gray-700"
                            >
                                <ExternalLink className="w-4 h-4" /> Вывод средств
                            </a>
                        </div>
                    )}
                </div>

                {/* T-Bank notice */}
                {isLive && (
                    <div className="bg-blue-500/10 border border-blue-500/20 rounded-xl p-4 text-sm text-blue-300">
                        💡 Пополнение и вывод средств выполняются через приложение T-Bank Invest.
                        Бот отображает баланс через API брокера и не хранит ваши деньги.
                    </div>
                )}

                {/* Balance cards */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <MetricCard label="Баланс" value={`${fmt(summary?.balance ?? 0)} ₽`} icon={Wallet} />
                    <MetricCard label="Equity" value={`${fmt(summary?.equity ?? 0)} ₽`}
                        sub={`Открытые: ${fmtPnl(summary?.open_pnl ?? 0)}`}
                        color={(summary?.equity ?? 0) >= (summary?.balance ?? 0) ? 'text-emerald-400' : 'text-red-400'} />
                    <MetricCard label="P&L сегодня" value={fmtPnl(summary?.day_pnl ?? 0)} icon={TrendingUp} color={pnlClr(summary?.day_pnl ?? 0)} />
                    <MetricCard label="P&L всего" value={fmtPnl(summary?.total_pnl ?? 0)} color={pnlClr(summary?.total_pnl ?? 0)} />
                </div>

                {/* Equity Curve */}
                <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
                    <div className="flex items-center justify-between mb-4">
                        <h2 className="font-semibold text-gray-200">Equity Curve</h2>
                        <div className="flex gap-2">
                            {[7, 14, 30, 90].map(d => (
                                <button key={d}
                                    onClick={() => setHistDays(d)}
                                    className={clsx('px-3 py-1 text-xs rounded font-medium transition-colors',
                                        histDays === d ? 'bg-blue-600 text-white' : 'bg-gray-800 text-gray-400 hover:text-gray-200')}>
                                    {d}д
                                </button>
                            ))}
                        </div>
                    </div>
                    {chartData.length === 0 ? (
                        <div className="h-48 flex items-center justify-center text-gray-600 text-sm">
                            Нет данных equity curve. Будут появляться по мере торговли.
                        </div>
                    ) : (
                        <ResponsiveContainer width="100%" height={220}>
                            <AreaChart data={chartData} margin={{ top: 5, right: 5, bottom: 5, left: 5 }}>
                                <defs>
                                    <linearGradient id="equityGrad" x1="0" y1="0" x2="0" y2="1">
                                        <stop offset="5%"   stopColor={equityColor} stopOpacity={0.3} />
                                        <stop offset="95%"  stopColor={equityColor} stopOpacity={0.02} />
                                    </linearGradient>
                                </defs>
                                <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                                <XAxis dataKey="date" tick={{ fill: '#6b7280', fontSize: 11 }} />
                                <YAxis tick={{ fill: '#6b7280', fontSize: 11 }} width={70}
                                    tickFormatter={v => `${(v / 1000).toFixed(0)}k`} />
                                <Tooltip content={<CustomTooltip />} />
                                <Area type="monotone" dataKey="equity" stroke={equityColor}
                                    strokeWidth={2} fill="url(#equityGrad)" dot={false} />
                            </AreaChart>
                        </ResponsiveContainer>
                    )}
                </div>

                {/* Today + All-time */}
                <div className="grid md:grid-cols-2 gap-6">
                    {/* Today */}
                    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 space-y-4">
                        <h2 className="font-semibold text-gray-200 flex items-center gap-2">
                            <Clock className="w-4 h-4 text-gray-500" /> Сегодня
                        </h2>
                        <div className="grid grid-cols-2 gap-3">
                            <div>
                                <div className="text-xs text-gray-500">P&L</div>
                                <div className={clsx('text-xl font-bold font-mono', pnlClr(daily?.day_pnl ?? 0))}>
                                    {fmtPnl(daily?.day_pnl ?? 0)}
                                </div>
                            </div>
                            <div>
                                <div className="text-xs text-gray-500">Сделок</div>
                                <div className="text-xl font-bold">{daily?.trades_count ?? 0}</div>
                            </div>
                            <div>
                                <div className="text-xs text-gray-500">Win Rate</div>
                                <div className={clsx('text-xl font-bold', (daily?.win_rate ?? 0) >= 50 ? 'text-emerald-400' : 'text-red-400')}>
                                    {(daily?.win_rate ?? 0).toFixed(1)}%
                                </div>
                            </div>
                            <div>
                                <div className="text-xs text-gray-500">Открытых</div>
                                <div className="text-xl font-bold text-blue-400">{daily?.open_positions ?? 0}</div>
                            </div>
                            <div>
                                <div className="text-xs text-gray-500">Лучшая</div>
                                <div className="text-lg font-bold text-emerald-400">
                                    {daily?.best_trade ? fmtPnl(daily.best_trade) : '—'}
                                </div>
                            </div>
                            <div>
                                <div className="text-xs text-gray-500">Худшая</div>
                                <div className="text-lg font-bold text-red-400">
                                    {daily?.worst_trade ? fmtPnl(daily.worst_trade) : '—'}
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* All-time */}
                    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 space-y-4">
                        <h2 className="font-semibold text-gray-200 flex items-center gap-2">
                            <BarChart2 className="w-4 h-4 text-gray-500" /> За всё время
                        </h2>
                        <div className="grid grid-cols-2 gap-3">
                            <div>
                                <div className="text-xs text-gray-500">Total P&L</div>
                                <div className={clsx('text-xl font-bold font-mono', pnlClr(summary?.total_pnl ?? 0))}>
                                    {fmtPnl(summary?.total_pnl ?? 0)}
                                </div>
                            </div>
                            <div>
                                <div className="text-xs text-gray-500">Max Drawdown</div>
                                <div className="text-xl font-bold text-red-400">
                                    {(summary?.max_drawdown_pct ?? 0).toFixed(2)}%
                                </div>
                            </div>
                            <div>
                                <div className="text-xs text-gray-500">Открытых позиций</div>
                                <div className="text-xl font-bold text-blue-400">{summary?.open_positions ?? 0}</div>
                            </div>
                            <div>
                                <div className="text-xs text-gray-500">Режим</div>
                                <div className={clsx('text-xl font-bold', isLive ? 'text-green-400' : 'text-yellow-400')}>
                                    {isLive ? 'Live' : 'Paper'}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
