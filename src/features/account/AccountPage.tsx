import React from 'react';
import { Skeleton, EmptyState } from '../../components/ui/UIComponents';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../../services/api';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { format } from 'date-fns';
import { ru } from 'date-fns/locale';
import clsx from 'clsx';
import { toast } from 'sonner';
import { HelpLabel } from '../../components/help/HelpSystem';
import {
    Wallet, TrendingUp, BarChart2, Clock, Landmark, PiggyBank,
    PlusCircle, RefreshCcw, Link2, ArrowLeftRight, ShieldCheck
} from 'lucide-react';

interface AccountSummary {
    mode: string;
    balance: number;
    equity: number;
    open_pnl: number;
    day_pnl: number;
    total_pnl: number;
    open_positions: number;
    max_drawdown_pct: number;
    broker_info: { name: string; type: string; status: string };
}
interface HistoryPoint { ts: number; balance: number; equity: number; day_pnl: number; }
interface DailyStats {
    day_pnl: number;
    trades_count: number;
    win_rate: number;
    best_trade: number;
    worst_trade: number;
    open_positions: number;
}
interface BrokerAccountItem {
    id: string;
    name: string;
    type: string;
    status: string;
    access_level: string;
    currency: string;
    is_selected: boolean;
    raw?: Record<string, unknown>;
}
interface BrokerAccountAdminData {
    available: boolean;
    provider: string;
    sandbox: boolean;
    live_trading_enabled?: boolean;
    selected_account_id: string;
    broker_accounts: BrokerAccountItem[];
    bank_accounts: BrokerAccountItem[];
    message?: string;
}

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
const useBrokerAdmin = () => useQuery({
    queryKey: ['tbank-account-admin'],
    queryFn: async () => { const { data } = await apiClient.get('/account/tbank/accounts'); return data as BrokerAccountAdminData; },
    refetchInterval: 30_000,
});

const fmt = (v: number, d = 2) => v.toLocaleString('ru-RU', { minimumFractionDigits: d, maximumFractionDigits: d });
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

function SmallAccountCard({
    title,
    subtitle,
    accent,
    selected,
    onSelect,
    actionLabel = 'Сделать активным',
}: {
    title: string;
    subtitle: string;
    accent?: React.ReactNode;
    selected?: boolean;
    onSelect?: () => void;
    actionLabel?: string;
}) {
    return (
        <div className={clsx(
            'rounded-xl border p-4 space-y-3',
            selected ? 'border-blue-500/40 bg-blue-500/10' : 'border-gray-800 bg-gray-900',
        )}>
            <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                    <div className="font-medium text-gray-100 break-all">{title}</div>
                    <div className="text-xs text-gray-500 mt-1">{subtitle}</div>
                </div>
                {accent}
            </div>
            <div className="flex items-center gap-2">
                {selected ? (
                    <span className="inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-medium bg-emerald-500/15 text-emerald-300 border border-emerald-500/20">
                        <ShieldCheck className="w-3.5 h-3.5" /> Активный
                    </span>
                ) : onSelect ? (
                    <button
                        type="button"
                        onClick={onSelect}
                        className="px-3 py-1.5 rounded-lg text-xs font-medium bg-gray-800 hover:bg-gray-700 text-gray-200 transition-colors"
                    >
                        {actionLabel}
                    </button>
                ) : null}
            </div>
        </div>
    );
}

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

export default function AccountPage() {
    const queryClient = useQueryClient();
    const { data: summary, isLoading } = useSummary();
    const { data: daily } = useDailyStats();
    const [histDays, setHistDays] = React.useState(30);
    const { data: historyFull = [] } = useHistory(histDays);
    const { data: brokerAdmin, isFetching: brokerRefreshing } = useBrokerAdmin();

    const [sandboxAccountName, setSandboxAccountName] = React.useState('');
    const [sandboxPayAccountId, setSandboxPayAccountId] = React.useState('');
    const [sandboxPayAmount, setSandboxPayAmount] = React.useState('100000');

    const [realFromBankId, setRealFromBankId] = React.useState('');
    const [realToBrokerId, setRealToBrokerId] = React.useState('');
    const [realPayAmount, setRealPayAmount] = React.useState('10000');

    const [transferFromBrokerId, setTransferFromBrokerId] = React.useState('');
    const [transferToBrokerId, setTransferToBrokerId] = React.useState('');
    const [transferAmount, setTransferAmount] = React.useState('10000');

    React.useEffect(() => {
        if (!brokerAdmin) return;
        if (!sandboxPayAccountId) {
            const selectedSandbox = brokerAdmin.broker_accounts.find(a => a.is_selected) ?? brokerAdmin.broker_accounts[0];
            if (selectedSandbox?.id) setSandboxPayAccountId(selectedSandbox.id);
        }
        if (!realFromBankId && brokerAdmin.bank_accounts[0]?.id) setRealFromBankId(brokerAdmin.bank_accounts[0].id);
        if (!realToBrokerId) {
            const selectedBroker = brokerAdmin.broker_accounts.find(a => a.is_selected) ?? brokerAdmin.broker_accounts[0];
            if (selectedBroker?.id) setRealToBrokerId(selectedBroker.id);
        }
        if (!transferFromBrokerId && brokerAdmin.broker_accounts[0]?.id) setTransferFromBrokerId(brokerAdmin.broker_accounts[0].id);
        if (!transferToBrokerId && brokerAdmin.broker_accounts[1]?.id) setTransferToBrokerId(brokerAdmin.broker_accounts[1].id);
    }, [brokerAdmin, sandboxPayAccountId, realFromBankId, realToBrokerId, transferFromBrokerId, transferToBrokerId]);

    const invalidateAdmin = React.useCallback(async () => {
        await Promise.all([
            queryClient.invalidateQueries({ queryKey: ['tbank-account-admin'] }),
            queryClient.invalidateQueries({ queryKey: ['account-summary'] }),
        ]);
    }, [queryClient]);

    const selectAccountMutation = useMutation({
        mutationFn: async (accountId: string) => {
            const { data } = await apiClient.post('/account/tbank/select-account', { account_id: accountId });
            return data;
        },
        onSuccess: async () => {
            toast.success('Активный T-Bank счёт обновлён');
            await invalidateAdmin();
        },
    });

    const openSandboxMutation = useMutation({
        mutationFn: async () => {
            const { data } = await apiClient.post('/account/tbank/sandbox/open-account', {
                name: sandboxAccountName.trim() || undefined,
                activate: true,
            });
            return data;
        },
        onSuccess: async (data) => {
            toast.success(`Sandbox-счёт создан${data?.created_account_id ? `: ${data.created_account_id}` : ''}`);
            setSandboxAccountName('');
            await invalidateAdmin();
        },
    });

    const sandboxPayMutation = useMutation({
        mutationFn: async () => {
            const { data } = await apiClient.post('/account/tbank/sandbox/pay-in', {
                account_id: sandboxPayAccountId,
                amount: Number(sandboxPayAmount),
                currency: 'RUB',
                activate: true,
            });
            return data;
        },
        onSuccess: async () => {
            toast.success('Sandbox-счёт пополнен');
            await invalidateAdmin();
        },
    });

    const realPayInMutation = useMutation({
        mutationFn: async () => {
            const { data } = await apiClient.post('/account/tbank/pay-in', {
                from_account_id: realFromBankId,
                to_account_id: realToBrokerId,
                amount: Number(realPayAmount),
                currency: 'RUB',
            });
            return data;
        },
        onSuccess: async () => {
            toast.success('Пополнение брокерского счёта отправлено в T-Bank');
            await invalidateAdmin();
        },
    });

    const transferMutation = useMutation({
        mutationFn: async () => {
            const { data } = await apiClient.post('/account/tbank/transfer', {
                from_account_id: transferFromBrokerId,
                to_account_id: transferToBrokerId,
                amount: Number(transferAmount),
                currency: 'RUB',
            });
            return data;
        },
        onSuccess: async () => {
            toast.success('Перевод между брокерскими счетами отправлен');
            await invalidateAdmin();
        },
    });

    const chartData = historyFull.map(p => ({
        date: format(p.ts, 'dd MMM', { locale: ru }),
        equity: p.equity,
        pnl: p.day_pnl,
    }));

    const isTBankMode = summary?.mode === 'tbank';
    const equityColor = (summary?.total_pnl ?? 0) >= 0 ? '#10b981' : '#ef4444';

    if (isLoading) return (
        <div className="p-4 space-y-4 max-w-4xl mx-auto">
            <Skeleton className="h-32 rounded-xl" />
            <Skeleton className="h-48 rounded-xl" />
            <Skeleton className="h-24 rounded-xl" />
        </div>
    );

    const sandboxMode = Boolean(brokerAdmin?.sandbox);
    const brokerAccounts = brokerAdmin?.broker_accounts ?? [];
    const bankAccounts = brokerAdmin?.bank_accounts ?? [];

    return (
        <div className="h-full overflow-y-auto bg-gray-950">
            <div className="max-w-6xl mx-auto p-6 space-y-8">
                <div className="flex items-center justify-between gap-4 flex-wrap">
                    <div>
                        <h1 className="text-2xl font-bold text-gray-100">Мой счёт</h1>
                        <p className="text-sm text-gray-500 mt-1">
                            {summary?.broker_info.name} ·{' '}
                            <span className={clsx('font-medium', isTBankMode ? 'text-green-400' : 'text-yellow-400')}>
                                {isTBankMode ? (sandboxMode ? '🟢 T-Bank Sandbox' : '🟢 T-Bank Live') : '🟡 Виртуальный счёт'}
                            </span>
                        </p>
                    </div>
                    <button
                        type="button"
                        onClick={() => queryClient.invalidateQueries({ queryKey: ['tbank-account-admin'] })}
                        className="inline-flex items-center gap-2 px-4 py-2 bg-gray-800 hover:bg-gray-700 text-gray-100 rounded-lg text-sm font-medium transition-colors border border-gray-700"
                    >
                        <RefreshCcw className={clsx('w-4 h-4', brokerRefreshing && 'animate-spin')} /> Обновить счета
                    </button>
                </div>

                {brokerAdmin?.available ? (
                    <div className={clsx(
                        'rounded-xl p-4 text-sm border',
                        sandboxMode ? 'bg-blue-500/10 border-blue-500/20 text-blue-200' : 'bg-yellow-500/10 border-yellow-500/20 text-yellow-100',
                    )}>
                        {sandboxMode ? (
                            <>Sandbox-счета и пополнение доступны прямо из приложения. Создайте песочный счёт, выберите его активным и пополните тестовыми рублями перед запуском auto_live в sandbox.</>
                        ) : (
                            <>Для реальных счетов из UI доступны: выбор активного брокерского счёта, пополнение брокерского счёта с банковского и перевод между брокерскими счетами. Для денежных операций T-Bank может требовать токен с правами на переводы.</>
                        )}
                    </div>
                ) : (
                    <EmptyState
                        title="T-Bank ещё не настроен"
                        description={brokerAdmin?.message || 'Добавьте TBANK_TOKEN и, при необходимости, включите TBANK_SANDBOX=true.'}
                    />
                )}

                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <MetricCard label="Баланс" value={`${fmt(summary?.balance ?? 0)} ₽`} icon={Wallet} />
                    <MetricCard
                        label="Equity"
                        value={`${fmt(summary?.equity ?? 0)} ₽`}
                        sub={`Открытые: ${fmtPnl(summary?.open_pnl ?? 0)}`}
                        color={(summary?.equity ?? 0) >= (summary?.balance ?? 0) ? 'text-emerald-400' : 'text-red-400'}
                    />
                    <MetricCard label="P&L сегодня" value={fmtPnl(summary?.day_pnl ?? 0)} icon={TrendingUp} color={pnlClr(summary?.day_pnl ?? 0)} />
                    <MetricCard label="P&L всего" value={fmtPnl(summary?.total_pnl ?? 0)} color={pnlClr(summary?.total_pnl ?? 0)} />
                </div>

                {brokerAdmin?.available && (
                    <div className="grid xl:grid-cols-[1.4fr_1fr] gap-6">
                        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 space-y-5">
                            <div className="flex items-center gap-2 text-gray-100 font-semibold">
                                <Landmark className="w-4 h-4 text-blue-400" />
                                <HelpLabel label={sandboxMode ? 'T-Bank sandbox-счета' : 'T-Bank реальные счета'} helpId={sandboxMode ? 'tbank_sandbox_account' : 'tbank_real_topup'} />
                            </div>

                            {sandboxMode && (
                                <div className="rounded-xl border border-gray-800 bg-gray-950/60 p-4 space-y-3">
                                    <div className="flex items-center gap-2 text-sm font-medium text-gray-100">
                                        <PlusCircle className="w-4 h-4 text-emerald-400" /> Создать sandbox-счёт
                                    </div>
                                    <div className="grid md:grid-cols-[1fr_auto] gap-3">
                                        <input
                                            value={sandboxAccountName}
                                            onChange={(e) => setSandboxAccountName(e.target.value)}
                                            className="w-full rounded-lg bg-gray-900 border border-gray-800 px-3 py-2 text-sm text-gray-100"
                                            placeholder="Например: Sandbox MOEX 1"
                                        />
                                        <button
                                            type="button"
                                            onClick={() => openSandboxMutation.mutate()}
                                            disabled={openSandboxMutation.isPending}
                                            className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-sm font-medium"
                                        >
                                            Создать и сделать активным
                                        </button>
                                    </div>
                                    <div className="text-xs text-gray-500">После создания счёт сразу можно выбрать активным для торговли и пополнения.</div>
                                </div>
                            )}

                            <div className="grid md:grid-cols-2 gap-3">
                                {brokerAccounts.length > 0 ? brokerAccounts.map((account) => (
                                    <SmallAccountCard
                                        key={account.id}
                                        title={account.name}
                                        subtitle={`ID: ${account.id} · ${account.status} · ${account.type}`}
                                        selected={account.is_selected}
                                        accent={<span className="text-[10px] uppercase tracking-wider text-gray-500">{account.access_level}</span>}
                                        onSelect={account.is_selected ? undefined : () => selectAccountMutation.mutate(account.id)}
                                    />
                                )) : (
                                    <div className="text-sm text-gray-500">Счета пока не найдены.</div>
                                )}
                            </div>
                        </div>

                        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 space-y-5">
                            {sandboxMode ? (
                                <>
                                    <div className="flex items-center gap-2 text-gray-100 font-semibold">
                                        <PiggyBank className="w-4 h-4 text-emerald-400" />
                                        <HelpLabel label="Пополнение sandbox-счёта" helpId="tbank_sandbox_topup" />
                                    </div>
                                    <div className="space-y-3">
                                        <select
                                            value={sandboxPayAccountId}
                                            onChange={(e) => setSandboxPayAccountId(e.target.value)}
                                            className="w-full rounded-lg bg-gray-950 border border-gray-800 px-3 py-2 text-sm text-gray-100"
                                        >
                                            <option value="">Выберите sandbox-счёт</option>
                                            {brokerAccounts.map(account => (
                                                <option key={account.id} value={account.id}>{account.name} · {account.id}</option>
                                            ))}
                                        </select>
                                        <input
                                            type="number"
                                            min={1}
                                            step={1000}
                                            value={sandboxPayAmount}
                                            onChange={(e) => setSandboxPayAmount(e.target.value)}
                                            className="w-full rounded-lg bg-gray-950 border border-gray-800 px-3 py-2 text-sm text-gray-100"
                                            placeholder="Сумма в RUB"
                                        />
                                        <button
                                            type="button"
                                            onClick={() => sandboxPayMutation.mutate()}
                                            disabled={sandboxPayMutation.isPending || !sandboxPayAccountId || Number(sandboxPayAmount) <= 0}
                                            className="w-full px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white text-sm font-medium"
                                        >
                                            Пополнить sandbox-счёт
                                        </button>
                                    </div>
                                </>
                            ) : (
                                <>
                                    <div className="space-y-5">
                                        <div>
                                            <div className="flex items-center gap-2 text-gray-100 font-semibold mb-3">
                                                <PiggyBank className="w-4 h-4 text-yellow-400" />
                                                <HelpLabel label="Пополнение брокерского счёта" helpId="tbank_real_topup" />
                                            </div>
                                            <div className="space-y-3">
                                                <select value={realFromBankId} onChange={(e) => setRealFromBankId(e.target.value)} className="w-full rounded-lg bg-gray-950 border border-gray-800 px-3 py-2 text-sm text-gray-100">
                                                    <option value="">С какого банковского счёта</option>
                                                    {bankAccounts.map(account => <option key={account.id} value={account.id}>{account.name} · {account.id}</option>)}
                                                </select>
                                                <select value={realToBrokerId} onChange={(e) => setRealToBrokerId(e.target.value)} className="w-full rounded-lg bg-gray-950 border border-gray-800 px-3 py-2 text-sm text-gray-100">
                                                    <option value="">На какой брокерский счёт</option>
                                                    {brokerAccounts.map(account => <option key={account.id} value={account.id}>{account.name} · {account.id}</option>)}
                                                </select>
                                                <input type="number" min={1} step={1000} value={realPayAmount} onChange={(e) => setRealPayAmount(e.target.value)} className="w-full rounded-lg bg-gray-950 border border-gray-800 px-3 py-2 text-sm text-gray-100" placeholder="Сумма в RUB" />
                                                <button
                                                    type="button"
                                                    onClick={() => realPayInMutation.mutate()}
                                                    disabled={realPayInMutation.isPending || !realFromBankId || !realToBrokerId || Number(realPayAmount) <= 0}
                                                    className="w-full px-4 py-2 rounded-lg bg-yellow-500 hover:bg-yellow-400 disabled:opacity-50 text-black text-sm font-semibold"
                                                >
                                                    Пополнить брокерский счёт
                                                </button>
                                            </div>
                                        </div>

                                        <div>
                                            <div className="flex items-center gap-2 text-gray-100 font-semibold mb-3">
                                                <ArrowLeftRight className="w-4 h-4 text-blue-400" />
                                                <HelpLabel label="Перевод между брокерскими счетами" helpId="tbank_broker_transfer" />
                                            </div>
                                            <div className="space-y-3">
                                                <select value={transferFromBrokerId} onChange={(e) => setTransferFromBrokerId(e.target.value)} className="w-full rounded-lg bg-gray-950 border border-gray-800 px-3 py-2 text-sm text-gray-100">
                                                    <option value="">Со счёта</option>
                                                    {brokerAccounts.map(account => <option key={account.id} value={account.id}>{account.name} · {account.id}</option>)}
                                                </select>
                                                <select value={transferToBrokerId} onChange={(e) => setTransferToBrokerId(e.target.value)} className="w-full rounded-lg bg-gray-950 border border-gray-800 px-3 py-2 text-sm text-gray-100">
                                                    <option value="">На счёт</option>
                                                    {brokerAccounts.map(account => <option key={account.id} value={account.id}>{account.name} · {account.id}</option>)}
                                                </select>
                                                <input type="number" min={1} step={1000} value={transferAmount} onChange={(e) => setTransferAmount(e.target.value)} className="w-full rounded-lg bg-gray-950 border border-gray-800 px-3 py-2 text-sm text-gray-100" placeholder="Сумма в RUB" />
                                                <button
                                                    type="button"
                                                    onClick={() => transferMutation.mutate()}
                                                    disabled={transferMutation.isPending || !transferFromBrokerId || !transferToBrokerId || transferFromBrokerId === transferToBrokerId || Number(transferAmount) <= 0}
                                                    className="w-full px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white text-sm font-medium"
                                                >
                                                    Перевести между брокерскими счетами
                                                </button>
                                            </div>
                                        </div>
                                    </div>
                                </>
                            )}

                            {!sandboxMode && bankAccounts.length > 0 && (
                                <div className="rounded-xl border border-gray-800 bg-gray-950/60 p-4">
                                    <div className="text-xs uppercase tracking-widest text-gray-500 font-semibold mb-3 inline-flex items-center gap-2">
                                        <Link2 className="w-3.5 h-3.5" /> Доступные банковские счета
                                    </div>
                                    <div className="space-y-2">
                                        {bankAccounts.map(account => (
                                            <div key={account.id} className="text-sm text-gray-300 border border-gray-800 rounded-lg px-3 py-2 bg-gray-900/70">
                                                <div className="font-medium">{account.name}</div>
                                                <div className="text-xs text-gray-500 mt-1 break-all">{account.id}</div>
                                            </div>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                )}

                <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
                    <div className="flex items-center justify-between mb-4">
                        <h2 className="font-semibold text-gray-200">Equity Curve</h2>
                        <div className="flex gap-2">
                            {[7, 14, 30, 90].map(d => (
                                <button
                                    key={d}
                                    onClick={() => setHistDays(d)}
                                    className={clsx('px-3 py-1 text-xs rounded font-medium transition-colors',
                                        histDays === d ? 'bg-blue-600 text-white' : 'bg-gray-800 text-gray-400 hover:text-gray-200')}
                                >
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
                                        <stop offset="5%" stopColor={equityColor} stopOpacity={0.3} />
                                        <stop offset="95%" stopColor={equityColor} stopOpacity={0.02} />
                                    </linearGradient>
                                </defs>
                                <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                                <XAxis dataKey="date" tick={{ fill: '#6b7280', fontSize: 11 }} />
                                <YAxis tick={{ fill: '#6b7280', fontSize: 11 }} width={70} tickFormatter={v => `${(v / 1000).toFixed(0)}k`} />
                                <Tooltip content={<CustomTooltip />} />
                                <Area type="monotone" dataKey="equity" stroke={equityColor} strokeWidth={2} fill="url(#equityGrad)" dot={false} />
                            </AreaChart>
                        </ResponsiveContainer>
                    )}
                </div>

                <div className="grid md:grid-cols-2 gap-6">
                    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 space-y-4">
                        <h2 className="font-semibold text-gray-200 flex items-center gap-2">
                            <Clock className="w-4 h-4 text-gray-500" /> Сегодня
                        </h2>
                        <div className="grid grid-cols-2 gap-3">
                            <div>
                                <div className="text-xs text-gray-500">P&L</div>
                                <div className={clsx('text-xl font-bold font-mono', pnlClr(daily?.day_pnl ?? 0))}>{fmtPnl(daily?.day_pnl ?? 0)}</div>
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
                                <div className="text-lg font-bold text-emerald-400">{daily?.best_trade ? fmtPnl(daily.best_trade) : '—'}</div>
                            </div>
                            <div>
                                <div className="text-xs text-gray-500">Худшая</div>
                                <div className="text-lg font-bold text-red-400">{daily?.worst_trade ? fmtPnl(daily.worst_trade) : '—'}</div>
                            </div>
                        </div>
                    </div>

                    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 space-y-4">
                        <h2 className="font-semibold text-gray-200 flex items-center gap-2">
                            <BarChart2 className="w-4 h-4 text-gray-500" /> За всё время
                        </h2>
                        <div className="grid grid-cols-2 gap-3">
                            <div>
                                <div className="text-xs text-gray-500">Total P&L</div>
                                <div className={clsx('text-xl font-bold font-mono', pnlClr(summary?.total_pnl ?? 0))}>{fmtPnl(summary?.total_pnl ?? 0)}</div>
                            </div>
                            <div>
                                <div className="text-xs text-gray-500">Max Drawdown</div>
                                <div className="text-xl font-bold text-red-400">{(summary?.max_drawdown_pct ?? 0).toFixed(2)}%</div>
                            </div>
                            <div>
                                <div className="text-xs text-gray-500">Открытых позиций</div>
                                <div className="text-xl font-bold text-blue-400">{summary?.open_positions ?? 0}</div>
                            </div>
                            <div>
                                <div className="text-xs text-gray-500">Контур брокера</div>
                                <div className={clsx('text-xl font-bold', isTBankMode ? 'text-green-400' : 'text-yellow-400')}>
                                    {isTBankMode ? (sandboxMode ? 'Sandbox' : 'Live') : 'Paper'}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
