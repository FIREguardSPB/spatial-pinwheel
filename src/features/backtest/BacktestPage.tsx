import React, { useState } from 'react';
import { Skeleton, EmptyState } from '../../components/ui/UIComponents';
import { useMutation } from '@tanstack/react-query';
import { apiClient } from '../../services/api';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import clsx from 'clsx';
import { Play, TrendingUp, TrendingDown, BarChart2, AlertCircle } from 'lucide-react';

interface BacktestResult {
  instrument_id: string; strategy_name: string;
  from_ts: number; to_ts: number;
  initial_balance: number; final_balance: number;
  total_return_pct: number; max_drawdown_pct: number;
  sharpe_ratio: number | null; win_rate: number;
  profit_factor: number | null; total_trades: number;
  avg_trade_pct: number;
  equity_curve: { ts: number; equity: number }[];
  trades: { side: string; entry: number; close: number; pnl: number; pnl_pct: number; close_reason: string; bars_held: number }[];
}

// Generate simple synthetic candles for demo
function genCandles(n = 300) {
  let price = 250.0; const candles = [];
  for (let i = 0; i < n; i++) {
    const change = (Math.random() - 0.495) * 2;
    const open = price, close = price + change;
    candles.push({ time: 1700000000 + i * 60, open, high: Math.max(open, close) + Math.random() * 0.5, low: Math.min(open, close) - Math.random() * 0.5, close, volume: 500 + Math.random() * 1000 });
    price = close;
  }
  return candles;
}

export default function BacktestPage() {
  const [strategy,  setStrategy]  = useState('breakout');
  const [instrument, setInstrument] = useState('TQBR:SBER');
  const [balance,   setBalance]   = useState('100000');
  const [riskPct,   setRiskPct]   = useState('1.0');
  const [result,    setResult]    = useState<BacktestResult | null>(null);

  const runMut = useMutation({
    mutationFn: async () => {
      const candles = genCandles(300);
      const { data } = await apiClient.post('/backtest', {
        instrument_id: instrument,
        strategy,
        candles,
        initial_balance: parseFloat(balance) || 100_000,
        risk_pct: parseFloat(riskPct) || 1.0,
        use_decision_engine: false,
      });
      return data as BacktestResult;
    },
    onSuccess: data => setResult(data),
  });

  const isProfit = (result?.total_return_pct ?? 0) >= 0;
  const equityColor = isProfit ? '#10b981' : '#ef4444';

  const chartData = result?.equity_curve.map(p => ({
    ts:     new Date(p.ts).toLocaleDateString('ru-RU', { month: 'short', day: 'numeric' }),
    equity: p.equity,
  })) ?? [];

  return (
    <div className="h-full overflow-y-auto bg-gray-950">
      <div className="max-w-5xl mx-auto p-6 space-y-6">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold text-gray-100">Бэктест</h1>
          <p className="text-sm text-gray-500 mt-1">Walk-forward симуляция стратегии на синтетических данных</p>
        </div>

        {/* Config panel */}
        <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
          <h2 className="font-semibold text-gray-200 mb-4">Параметры</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Стратегия</label>
              <select value={strategy} onChange={e => setStrategy(e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 outline-none focus:border-blue-500">
                <option value="breakout">Breakout</option>
                <option value="mean_reversion">Mean Reversion</option>
                <option value="vwap_bounce">VWAP Bounce</option>
              </select>
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Инструмент</label>
              <input value={instrument} onChange={e => setInstrument(e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 outline-none focus:border-blue-500" />
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Начальный баланс ₽</label>
              <input type="number" value={balance} onChange={e => setBalance(e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 outline-none focus:border-blue-500" />
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Риск на сделку %</label>
              <input type="number" step="0.1" value={riskPct} onChange={e => setRiskPct(e.target.value)}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 outline-none focus:border-blue-500" />
            </div>
          </div>
          <div className="flex items-center gap-4 mt-4">
            <button onClick={() => runMut.mutate()}
              disabled={runMut.isPending}
              className="flex items-center gap-2 px-6 py-2.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white rounded-lg font-medium transition-colors">
              {runMut.isPending
                ? <><span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" /> Вычисляется...</>
                : <><Play className="w-4 h-4" /> Запустить</>}
            </button>
            {runMut.isError && (
              <div className="flex items-center gap-2 text-red-400 text-sm">
                <AlertCircle className="w-4 h-4" /> Ошибка — проверьте подключение к API
              </div>
            )}
          </div>
          <p className="text-xs text-gray-600 mt-2">
            ℹ️ В демо-режиме используются 300 синтетических свечей. Для реального бэктеста подключите API.
          </p>
        </div>

        {runMut.isPending && (
                <div className="space-y-3">
                    <Skeleton className="h-16 rounded-xl" />
                    <Skeleton className="h-64 rounded-xl" />
                    <Skeleton className="h-32 rounded-xl" />
                </div>
            )}
            {result && (
          <>
            {/* Metrics */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {[
                { label: 'Доходность',    value: `${result.total_return_pct > 0 ? '+' : ''}${result.total_return_pct.toFixed(2)}%`, color: isProfit ? 'text-emerald-400' : 'text-red-400' },
                { label: 'Макс. просадка', value: `-${result.max_drawdown_pct.toFixed(2)}%`, color: 'text-red-400' },
                { label: 'Win Rate',       value: `${result.win_rate.toFixed(1)}%`,           color: result.win_rate >= 50 ? 'text-emerald-400' : 'text-yellow-400' },
                { label: 'Profit Factor',  value: result.profit_factor?.toFixed(2) ?? '—',    color: (result.profit_factor ?? 0) >= 1.5 ? 'text-emerald-400' : 'text-yellow-400' },
                { label: 'Sharpe',         value: result.sharpe_ratio?.toFixed(3) ?? '—',     color: (result.sharpe_ratio ?? 0) >= 1 ? 'text-emerald-400' : 'text-gray-400' },
                { label: 'Сделок',         value: String(result.total_trades),                color: 'text-gray-200' },
                { label: 'Средняя сделка', value: `${result.avg_trade_pct > 0 ? '+' : ''}${result.avg_trade_pct.toFixed(3)}%`, color: result.avg_trade_pct >= 0 ? 'text-emerald-400' : 'text-red-400' },
                { label: 'Итоговый баланс', value: `${result.final_balance.toLocaleString('ru-RU', { maximumFractionDigits: 0 })} ₽`, color: 'text-gray-100' },
              ].map(({ label, value, color }) => (
                <div key={label} className="bg-gray-900 border border-gray-800 rounded-xl p-4">
                  <div className="text-xs text-gray-500 uppercase tracking-wider mb-2">{label}</div>
                  <div className={clsx('text-xl font-bold font-mono', color)}>{value}</div>
                </div>
              ))}
            </div>

            {/* Equity Curve */}
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-5">
              <h2 className="font-semibold text-gray-200 mb-4">Equity Curve</h2>
              <ResponsiveContainer width="100%" height={240}>
                <AreaChart data={chartData} margin={{ top: 5, right: 5, bottom: 5, left: 10 }}>
                  <defs>
                    <linearGradient id="btGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor={equityColor} stopOpacity={0.3} />
                      <stop offset="95%" stopColor={equityColor} stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
                  <XAxis dataKey="ts" tick={{ fill: '#6b7280', fontSize: 10 }} interval="preserveStartEnd" />
                  <YAxis tick={{ fill: '#6b7280', fontSize: 10 }} width={80}
                    tickFormatter={v => `${(v / 1000).toFixed(0)}k`} />
                  <Tooltip formatter={(v: number) => [`${v.toLocaleString('ru-RU', { maximumFractionDigits: 0 })} ₽`, 'Equity']}
                    contentStyle={{ background: '#1f2937', border: '1px solid #374151', borderRadius: 8, fontSize: 12 }} />
                  <Area type="monotone" dataKey="equity" stroke={equityColor} strokeWidth={2} fill="url(#btGrad)" dot={false} />
                </AreaChart>
              </ResponsiveContainer>
            </div>

            {/* Trades table */}
            {result.trades.length > 0 && (
              <div className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
                <div className="px-5 py-3 border-b border-gray-800 font-semibold text-gray-200">
                  Список сделок ({result.trades.length})
                </div>
                <div className="overflow-x-auto max-h-72">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-800 text-gray-400 text-xs uppercase sticky top-0">
                      <tr>
                        {['#', 'Side', 'Вход', 'Выход', 'P&L', 'P&L %', 'Свечей', 'Причина'].map(h => (
                          <th key={h} className="px-4 py-2 text-left">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-800">
                      {result.trades.map((t, i) => (
                        <tr key={i} className="hover:bg-gray-800/40">
                          <td className="px-4 py-2 text-gray-600 font-mono text-xs">{i + 1}</td>
                          <td className="px-4 py-2">
                            <span className={clsx('px-1.5 py-0.5 rounded text-xs font-bold', t.side === 'BUY' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400')}>{t.side}</span>
                          </td>
                          <td className="px-4 py-2 font-mono text-gray-300">{t.entry.toFixed(2)}</td>
                          <td className="px-4 py-2 font-mono text-gray-300">{t.close.toFixed(2)}</td>
                          <td className={clsx('px-4 py-2 font-bold font-mono', t.pnl >= 0 ? 'text-emerald-400' : 'text-red-400')}>
                            {t.pnl >= 0 ? '+' : ''}{t.pnl.toFixed(2)}
                          </td>
                          <td className={clsx('px-4 py-2 font-mono text-xs', t.pnl_pct >= 0 ? 'text-emerald-400' : 'text-red-400')}>
                            {t.pnl_pct >= 0 ? '+' : ''}{t.pnl_pct.toFixed(3)}%
                          </td>
                          <td className="px-4 py-2 text-gray-500 font-mono text-xs">{t.bars_held}</td>
                          <td className="px-4 py-2 text-gray-600 text-xs">{t.close_reason}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
