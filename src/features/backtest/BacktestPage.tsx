import { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { PageShell, RetryButton, SimpleTable, Surface } from '../core/PageBlocks';
import { apiClient } from '../../services/api';
import { useWatchlist } from '../core/queries';
import { fmtMoney, fmtNumber } from '../core/format';

export default function BacktestPage() {
  const watchlist = useWatchlist();
  const [instrumentId, setInstrumentId] = useState('TQBR:SBER');
  const [strategy, setStrategy] = useState('breakout');
  const [timeframe, setTimeframe] = useState('1m');

  const strategies = useQuery({
    queryKey: ['backtest', 'strategies'],
    queryFn: async () => {
      const { data } = await apiClient.get<{ strategies?: string[] }>('/backtest/strategies');
      return Array.isArray(data?.strategies) ? data.strategies : [];
    },
    retry: false,
    staleTime: 60_000,
  });

  const runBacktest = useMutation({
    mutationFn: async () => {
      const { data } = await apiClient.post('/backtest', {
        instrument_id: instrumentId,
        strategy,
        timeframe,
        history_limit: 500,
        initial_balance: 100000,
        risk_pct: 1,
        commission_pct: 0.03,
        use_decision_engine: false,
      });
      return data as any;
    },
  });

  return (
    <PageShell title="Бэктест" subtitle="Упрощённый экран: один запуск, один результат, без перегруженного UI." actions={<RetryButton onClick={() => strategies.refetch()} />}>
      <div className="grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
        <Surface title="Параметры">
          <div className="grid gap-4 md:grid-cols-2">
            <label className="space-y-2 text-sm md:col-span-2">
              <span className="text-gray-300">Инструмент</span>
              <select value={instrumentId} onChange={(e) => setInstrumentId(e.target.value)} className="w-full rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-white">
                {(watchlist.data ?? []).map((item) => <option key={item.instrument_id} value={item.instrument_id}>{item.ticker} — {item.name}</option>)}
                {!watchlist.data?.length ? <option value="TQBR:SBER">TQBR:SBER</option> : null}
              </select>
            </label>
            <label className="space-y-2 text-sm">
              <span className="text-gray-300">Стратегия</span>
              <select value={strategy} onChange={(e) => setStrategy(e.target.value)} className="w-full rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-white">
                {(strategies.data ?? ['breakout']).map((item) => <option key={item} value={item}>{item}</option>)}
              </select>
            </label>
            <label className="space-y-2 text-sm">
              <span className="text-gray-300">Таймфрейм</span>
              <select value={timeframe} onChange={(e) => setTimeframe(e.target.value)} className="w-full rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-white">
                {['1m', '5m', '15m', '1h', '4h', '1d'].map((item) => <option key={item} value={item}>{item}</option>)}
              </select>
            </label>
            <button onClick={() => runBacktest.mutate(undefined)} disabled={runBacktest.isPending} className="rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-50 md:col-span-2">Запустить бэктест</button>
          </div>
        </Surface>

        <Surface title="Результат">
          {!runBacktest.data && !runBacktest.isPending && !runBacktest.isError ? <div className="text-sm text-gray-400">Ещё не запускался.</div> : null}
          {runBacktest.isPending ? <div className="text-sm text-gray-400">Запуск…</div> : null}
          {runBacktest.isError ? <div className="rounded-xl border border-rose-500/20 bg-rose-500/10 p-4 text-sm text-rose-200">Бэктест завершился ошибкой.</div> : null}
          {runBacktest.data ? (
            <div className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                <Card label="Return" value={`${fmtNumber(runBacktest.data.total_return_pct)}%`} />
                <Card label="Max DD" value={`${fmtNumber(runBacktest.data.max_drawdown_pct)}%`} />
                <Card label="PF" value={fmtNumber(runBacktest.data.profit_factor)} />
                <Card label="Trades" value={fmtNumber(runBacktest.data.total_trades, 0)} />
              </div>
              <SimpleTable
                columns={['Entry', 'Exit', 'Side', 'PnL']}
                rows={(runBacktest.data.trades ?? []).slice(-20).reverse().map((trade: any) => [
                  fmtNumber(trade.entry_price),
                  fmtNumber(trade.exit_price),
                  trade.side,
                  fmtMoney(trade.pnl_rub),
                ])}
                empty="Сделок нет"
              />
            </div>
          ) : null}
        </Surface>
      </div>
    </PageShell>
  );
}

function Card({ label, value }: { label: string; value: string }) {
  return <div className="rounded-xl border border-gray-800 bg-gray-950/60 p-4"><div className="text-xs text-gray-500">{label}</div><div className="mt-2 text-xl font-semibold text-white">{value}</div></div>;
}
