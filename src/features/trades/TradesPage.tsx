import { PageShell, QueryBlock, RetryButton, SimpleTable, StatusChip, StatGrid, Surface } from '../core/PageBlocks';
import { fmtDateTime, fmtMoney, fmtNumber } from '../core/format';
import { useTradeStats, useUiTrades } from '../core/uiQueries';

export default function TradesPage() {
  const page = useUiTrades(50);
  const stats = useTradeStats();
  const items = page.data?.items ?? [];
  const instruments = new Set(items.map((trade) => trade.instrument_id).filter(Boolean));
  const totalQty = items.reduce((acc, trade) => acc + Number(trade.qty || 0), 0);
  const latestTradeTs = items[0]?.ts ?? null;

  return (
    <PageShell
      title="Сделки"
      subtitle="Исполнения из одного /ui/trades."
      actions={<RetryButton onClick={() => page.refetch()} />}
    >
      <StatGrid
        items={[
          { label: 'Показано', value: fmtNumber(items.length, 0) },
          { label: 'Всего закрытых', value: fmtNumber(stats.data?.total_trades ?? page.data?.total ?? 0, 0) },
          { label: 'Инструментов', value: fmtNumber(instruments.size, 0) },
          { label: 'Суммарный qty', value: fmtNumber(totalQty, 0) },
          { label: 'Общий PnL', value: fmtMoney(stats.data?.total_pnl) },
          { label: 'Win rate', value: `${fmtNumber(stats.data?.win_rate ?? 0, 1)}%` },
          { label: 'Profit factor', value: stats.data?.profit_factor == null ? '—' : fmtNumber(stats.data?.profit_factor, 2) },
          { label: 'Последнее закрытие', value: fmtDateTime(latestTradeTs as any) },
          { label: 'Статус API', value: <StatusChip tone={page.isError || stats.isError ? 'bad' : 'good'}>{page.isError || stats.isError ? 'Ошибка' : 'OK'}</StatusChip> },
        ]}
      />

      <Surface title="Исполнения">
        <QueryBlock isLoading={page.isLoading && !page.data} isError={page.isError && !page.data} errorMessage="Не удалось загрузить сделки" onRetry={() => { page.refetch(); stats.refetch(); }}>
          <SimpleTable
            columns={['Закрыта', 'Инструмент', 'Сторона', 'Entry → Exit', 'Qty', 'PnL', 'Fees', 'Причина', 'Длительность', 'Стратегия']}
            rows={items.map((trade) => [
              <div className="space-y-1 text-xs text-gray-300"><div>{fmtDateTime(trade.ts)}</div><div className="text-gray-500">open: {fmtDateTime(trade.opened_ts as any)}</div></div>,
              trade.instrument_id,
              trade.side,
              <div className="space-y-1 text-xs text-gray-300"><div>{fmtNumber(trade.entry_price ?? trade.price)} → {fmtNumber(trade.close_price ?? trade.price)}</div><div className="text-gray-500">signal: {trade.signal_id || '—'}</div></div>,
              fmtNumber(trade.qty, 0),
              <span className={Number(trade.realized_pnl || 0) >= 0 ? 'text-emerald-300' : 'text-rose-300'}>{fmtMoney(trade.realized_pnl)}</span>,
              fmtMoney(trade.fees_est),
              trade.close_reason || '—',
              trade.duration_sec ? `${fmtNumber(trade.duration_sec, 0)}s` : '—',
              <div className="space-y-1 text-xs text-gray-300"><div>{trade.strategy || '—'}</div><div className="text-gray-500">AI {trade.ai_decision || '—'} / {trade.ai_mode_used || '—'}</div></div>,
            ])}
            empty="Закрытых сделок пока нет"
          />
        </QueryBlock>
      </Surface>
    </PageShell>
  );
}
