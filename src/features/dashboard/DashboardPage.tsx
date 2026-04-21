import { useEffect, useMemo, useState } from 'react';
import { Play, Square } from 'lucide-react';
import { PageShell, QueryBlock, RetryButton, StatGrid, StatusChip, Surface, ValueRow } from '../core/PageBlocks';
import { fmtBool, fmtDateTime, fmtMode, fmtMoney, fmtNumber } from '../core/format';
import { useStartBot, useStopBot } from '../core/queries';
import { useUiDashboard } from '../core/uiQueries';
import { ChartContainer } from './ChartContainer';
import { useAppStore } from '../../store';
import { SimpleAreaChart } from '../../components/charts/SimpleAreaChart';
import { useQueryClient } from '@tanstack/react-query';
import { WorkerAnalysisInspector } from '../system/WorkerAnalysisInspector';

const TIMEFRAMES = ['1m', '5m', '15m', '1h'];

function connectionTone(value?: string) {
  return value === 'connected' ? 'good' : 'warn';
}

export default function DashboardPage() {
  const selectedInstrument = useAppStore((s) => s.selectedInstrument);
  const setSelectedInstrument = useAppStore((s) => s.setSelectedInstrument);
  const selectedTimeframe = useAppStore((s) => s.selectedTimeframe);
  const setSelectedTimeframe = useAppStore((s) => s.setSelectedTimeframe);
  const candles = useAppStore((s) => s.candles);
  const page = useUiDashboard(selectedInstrument, selectedTimeframe);
  const startBot = useStartBot();
  const stopBot = useStopBot();
  const qc = useQueryClient();

  const runtime = page.data?.runtime;
  const botStatus = runtime?.bot_status;
  const workerStatus = runtime?.worker_status;
  const schedule = runtime?.schedule;
  const watchlist = useMemo(() => runtime?.watchlist ?? [], [runtime?.watchlist]);
  const summary = page.data?.account_summary;
  const history = page.data?.account_history;
  const signals = page.data?.signals?.items ?? [];
  const positions = page.data?.positions?.items ?? [];
  const orders = page.data?.orders?.items ?? [];
  const chartCandles = candles[`${selectedInstrument}-${selectedTimeframe}`] ?? [];
  const latestChartCandleTs = chartCandles.length ? Number(chartCandles[chartCandles.length - 1]?.time ?? 0) * 1000 : null;
  const latestCoordinatorCandleTs = page.data?.latest_candle?.instrument_id === selectedInstrument && page.data?.latest_candle?.timeframe === selectedTimeframe && page.data?.latest_candle?.latest_ts
    ? Number(page.data.latest_candle.latest_ts) * 1000
    : null;
  const latestCandleTs = latestChartCandleTs ?? latestCoordinatorCandleTs;
  const [nowTs, setNowTs] = useState(0);
  const candleAgeMinutes = latestCandleTs && nowTs ? Math.max(0, Math.floor((nowTs - latestCandleTs) / 60000)) : null;
  const sessionIsOpen = Boolean(schedule?.is_open);
  const isTradingDay = Boolean(schedule?.is_trading_day);
  const staleThresholdMinutes = selectedTimeframe === '1m' ? 3 : selectedTimeframe === '5m' ? 12 : selectedTimeframe === '15m' ? 35 : 180;
  const candleStale = candleAgeMinutes !== null && sessionIsOpen && isTradingDay && candleAgeMinutes >= staleThresholdMinutes;

  useEffect(() => {
    if (!latestCandleTs) {
      setNowTs(0);
      return;
    }
    const refresh = () => setNowTs(Date.now());
    refresh();
    const timer = window.setInterval(refresh, 60_000);
    return () => window.clearInterval(timer);
  }, [latestCandleTs]);

  useEffect(() => {
    if (!watchlist.length) return;
    if (!watchlist.some((item) => item.instrument_id === selectedInstrument)) {
      setSelectedInstrument(watchlist[0].instrument_id);
    }
  }, [watchlist, selectedInstrument, setSelectedInstrument]);

  const mode = botStatus?.mode ?? runtime?.settings?.trade_mode ?? 'review';
  const isRunning = Boolean(botStatus?.is_running);
  const startDisabled = startBot.isPending || isRunning;
  const stopDisabled = stopBot.isPending || !isRunning;

  const stats = useMemo(() => ([
    { label: 'Режим', value: fmtMode(mode), hint: isRunning ? 'Бот запущен' : 'Бот остановлен' },
    { label: 'Баланс', value: fmtMoney(summary?.balance), hint: 'Текущий баланс' },
    { label: 'Открытый PnL', value: fmtMoney(summary?.open_pnl), tone: Number(summary?.open_pnl ?? 0) >= 0 ? 'good' as const : 'bad' as const },
    { label: 'PnL за день', value: fmtMoney(summary?.day_pnl), tone: Number(summary?.day_pnl ?? 0) >= 0 ? 'good' as const : 'bad' as const },
  ]), [mode, isRunning, summary]);

  const refetchAll = () => {
    qc.invalidateQueries({ queryKey: ['ui'] });
    page.refetch();
  };

  return (
    <PageShell
      title="Дашборд"
      subtitle="Новый coordinator-shell: один bootstrap-запрос на страницу, отдельная загрузка только для графика свечей."
      actions={
        <>
          <button
            onClick={async () => { await startBot.mutateAsync(mode as any); qc.invalidateQueries({ queryKey: ['ui'] }); }}
            disabled={startDisabled}
            className={`inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-white ${isRunning ? 'bg-emerald-900/70 ring-1 ring-emerald-500/40' : 'bg-emerald-600 hover:bg-emerald-500'} disabled:cursor-not-allowed disabled:opacity-60`}
          >
            <Play className="h-4 w-4" /> {startBot.isPending ? 'Запуск…' : isRunning ? 'Запущен' : 'Запустить'}
          </button>
          <button
            onClick={async () => { await stopBot.mutateAsync(); qc.invalidateQueries({ queryKey: ['ui'] }); }}
            disabled={stopDisabled}
            className={`inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-white ${!isRunning ? 'bg-rose-900/70 ring-1 ring-rose-500/30' : 'bg-rose-600 hover:bg-rose-500'} disabled:cursor-not-allowed disabled:opacity-60`}
          >
            <Square className="h-4 w-4" /> {stopBot.isPending ? 'Остановка…' : !isRunning ? 'Остановлен' : 'Остановить'}
          </button>
          <RetryButton label="Обновить всё" onClick={refetchAll} />
        </>
      }
    >
      <StatGrid items={stats} />

      <div className="grid gap-4 xl:grid-cols-[1.3fr_0.7fr]">
        <Surface
          title="График инструмента"
          description="Свечи, сигналы и активная позиция по выбранной бумаге."
          right={
            <div className="flex flex-wrap gap-2">
              <select value={selectedInstrument} onChange={(e) => setSelectedInstrument(e.target.value)} className="rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-sm text-white">
                {watchlist.map((item) => <option key={item.instrument_id} value={item.instrument_id}>{item.ticker}</option>)}
              </select>
              <select value={selectedTimeframe} onChange={(e) => setSelectedTimeframe(e.target.value)} className="rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-sm text-white">
                {TIMEFRAMES.map((tf) => <option key={tf} value={tf}>{tf}</option>)}
              </select>
            </div>
          }
          className="min-h-[420px]"
        >
          <QueryBlock
            isLoading={page.isLoading && !page.data}
            isError={page.isError && !page.data}
            errorMessage="Не удалось загрузить данные дашборда"
            onRetry={refetchAll}
          >
            {watchlist.length > 0 ? (
              <>
                <div className={`mb-3 text-xs ${candleStale ? 'text-amber-300' : 'text-gray-400'}`}>Последняя свеча: {fmtDateTime(latestCandleTs)}{selectedInstrument ? ` · ${selectedInstrument}` : ''}{selectedTimeframe ? ` · ${selectedTimeframe}` : ''}{candleAgeMinutes !== null ? ` · возраст ${candleAgeMinutes} мин` : ''}{candleStale ? ' · данные устарели' : ''}</div>
                <div className="h-[340px]">
                  <ChartContainer signals={signals} positions={positions} />
                </div>
              </>
            ) : (
              <div className="rounded-xl border border-dashed border-gray-700 px-4 py-12 text-center text-sm text-gray-400">Добавь бумаги в watchlist, чтобы появился график.</div>
            )}
          </QueryBlock>
        </Surface>

        <Surface title="Кривая счёта" description="Баланс и equity за последние 7 дней.">
          <QueryBlock isLoading={page.isLoading && !page.data} isError={page.isError && !page.data} errorMessage="Не удалось загрузить историю счёта" onRetry={refetchAll}>
            <SimpleAreaChart
              data={(history?.points ?? []).map((point) => ({ label: point.ts, equity: point.equity }))}
              xKey="label"
              yKey="equity"
              height={320}
              formatValue={(value) => fmtMoney(value)}
              formatLabel={(label) => fmtDateTime(typeof label === 'number' ? label * 1000 : label as any)}
              emptyLabel="Недостаточно точек для графика"
            />
          </QueryBlock>
        </Surface>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <Surface title="Runtime" description="Состояние бота, воркера и сессии рынка из одного coordinator payload.">
          <QueryBlock isLoading={page.isLoading && !page.data} isError={page.isError && !page.data} errorMessage="Не удалось загрузить runtime" onRetry={refetchAll}>
            <div className="space-y-2">
              <ValueRow label="Статус бота" value={(<StatusChip tone={isRunning ? 'good' : 'warn'}>{isRunning ? 'Запущен' : 'Остановлен'}</StatusChip>)} />
              <ValueRow label="Режим" value={(<StatusChip tone="blue">{fmtMode(mode)}</StatusChip>)} />
              <ValueRow label="Воркер" value={(<StatusChip tone={workerStatus?.ok ? 'good' : 'warn'}>{String(workerStatus?.ok ? (workerStatus?.phase || 'ok') : 'Нет heartbeat')}</StatusChip>)} />
              <ValueRow label="PID воркера" value={workerStatus?.pid ?? '—'} />
              <ValueRow label="Торговый день" value={schedule?.trading_day ?? botStatus?.session?.trading_day ?? '—'} />
              <ValueRow label="Рынок" value={schedule?.exchange ?? botStatus?.session?.market ?? 'MOEX'} />
              <ValueRow label="Открыт ли рынок" value={fmtBool(schedule?.is_open ?? botStatus?.session?.is_open, 'Да', 'Нет')} />
              <ValueRow label="Текущая сессия" value={`${fmtDateTime(schedule?.current_session_start ?? botStatus?.session?.current_session_start)} → ${fmtDateTime(schedule?.current_session_end ?? botStatus?.session?.current_session_end)}`} />
              <ValueRow label="Следующее открытие" value={fmtDateTime(schedule?.next_open ?? botStatus?.session?.next_open)} />
              <ValueRow label="Источник расписания" value={schedule?.source_note ? `${schedule?.source} · ${schedule?.source_note}` : (schedule?.source ?? '—')} />
              <ValueRow label="Market data" value={(<StatusChip tone={connectionTone(botStatus?.connection?.market_data)}>{botStatus?.connection?.market_data ?? 'unknown'}</StatusChip>)} />
              <ValueRow label="Broker" value={(<StatusChip tone={connectionTone(botStatus?.connection?.broker)}>{botStatus?.connection?.broker ?? 'unknown'}</StatusChip>)} />
            </div>
            {botStatus?.warnings?.length ? (
              <div className="mt-4 rounded-xl border border-amber-500/20 bg-amber-500/10 p-3 text-sm text-amber-100">
                <div className="font-medium">Предупреждения</div>
                <ul className="mt-2 list-disc space-y-1 pl-5">
                  {botStatus.warnings.map((warning) => <li key={warning}>{warning}</li>)}
                </ul>
              </div>
            ) : null}
          </QueryBlock>
        </Surface>

        <Surface title="Счёт и активность" description="Ключевые показатели, позиции, ордера и сигналы в одном месте.">
          <QueryBlock isLoading={page.isLoading && !page.data} isError={page.isError && !page.data} errorMessage="Не удалось загрузить счёт" onRetry={refetchAll}>
            <div className="space-y-2">
              <ValueRow label="Equity" value={fmtMoney(summary?.equity)} />
              <ValueRow label="Открытых позиций" value={fmtNumber(positions.length, 0)} />
              <ValueRow label="Активных ордеров" value={fmtNumber(orders.length, 0)} />
              <ValueRow label="Сигналов в ленте" value={fmtNumber(signals.length, 0)} />
              <ValueRow label="Watchlist" value={watchlist.map((item) => item.ticker).join(', ') || '—'} />
            </div>
          </QueryBlock>
        </Surface>
      </div>

      <Surface title="Профилирование worker pipeline" description="Живые timings по последнему meaningful анализу: видно, где бот реально тратит время.">
        <QueryBlock isLoading={page.isLoading && !page.data} isError={page.isError && !page.data} errorMessage="Не удалось загрузить telemetry воркера" onRetry={refetchAll}>
          <WorkerAnalysisInspector workerStatus={workerStatus} />
        </QueryBlock>
      </Surface>
    </PageShell>
  );
}
