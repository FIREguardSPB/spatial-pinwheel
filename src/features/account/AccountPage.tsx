import { PageShell, QueryBlock, RetryButton, SimpleTable, StatusChip, Surface, StatGrid } from '../core/PageBlocks';
import { apiClient } from '../../services/api';
import { fmtDateTime, fmtMoney, fmtNumber, fmtPercent } from '../core/format';
import { useUiAccount } from '../core/uiQueries';

export default function AccountPage() {
  const page = useUiAccount(30);
  const summary = page.data?.summary;
  const history = page.data?.history;
  const daily = page.data?.daily_stats;

  return (
    <PageShell
      title="Счёт"
      subtitle="Сводка счёта из одного /ui/account без каскада из трёх независимых GET."
      actions={<>
        <RetryButton onClick={() => page.refetch()} />
        <button onClick={async () => { await apiClient.post('/account/paper/reset'); page.refetch(); }} className="rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-200">Сбросить paper-счёт</button>
      </>}
    >
      <StatGrid
        items={[
          { label: 'Баланс', value: fmtMoney(summary?.balance) },
          { label: 'Equity', value: fmtMoney(summary?.equity) },
          { label: 'Open PnL', value: fmtMoney(summary?.open_pnl), tone: Number(summary?.open_pnl ?? 0) >= 0 ? 'good' : 'bad' },
          { label: 'Day PnL', value: fmtMoney(summary?.day_pnl), tone: Number(summary?.day_pnl ?? 0) >= 0 ? 'good' : 'bad' },
        ]}
      />

      <div className="grid gap-4 xl:grid-cols-2">
        <Surface title="Сводка счёта">
          <QueryBlock isLoading={page.isLoading && !page.data} isError={page.isError && !page.data} errorMessage="Не удалось загрузить summary" onRetry={() => page.refetch()}>
            <div className="space-y-2">
              <div className="flex items-center justify-between gap-4 border-b border-gray-800 py-2 text-sm"><span className="text-gray-400">Режим</span><span className="text-white">{summary?.mode ?? '—'}</span></div>
              <div className="flex items-center justify-between gap-4 border-b border-gray-800 py-2 text-sm"><span className="text-gray-400">Открытых позиций</span><span className="text-white">{fmtNumber(summary?.open_positions ?? 0, 0)}</span></div>
              <div className="flex items-center justify-between gap-4 border-b border-gray-800 py-2 text-sm"><span className="text-gray-400">Total PnL</span><span className="text-white">{fmtMoney(summary?.total_pnl)}</span></div>
              <div className="flex items-center justify-between gap-4 border-b border-gray-800 py-2 text-sm"><span className="text-gray-400">Макс. просадка</span><span className="text-white">{fmtPercent(summary?.max_drawdown_pct)}</span></div>
              <div className="flex items-center justify-between gap-4 py-2 text-sm"><span className="text-gray-400">Состояние broker_info</span><span className="text-white">{summary?.broker_info?.name ?? '—'} · {summary?.broker_info?.status ?? '—'}</span></div>
            </div>
          </QueryBlock>
        </Surface>

        <Surface title="Статистика дня">
          <QueryBlock isLoading={page.isLoading && !page.data} isError={page.isError && !page.data} errorMessage="Не удалось загрузить daily stats" onRetry={() => page.refetch()}>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-xl border border-gray-800 bg-gray-950/60 p-4"><div className="text-xs text-gray-500">Сделок сегодня</div><div className="mt-2 text-xl font-semibold text-white">{fmtNumber(daily?.trades_count ?? 0, 0)}</div></div>
              <div className="rounded-xl border border-gray-800 bg-gray-950/60 p-4"><div className="text-xs text-gray-500">Win rate</div><div className="mt-2 text-xl font-semibold text-white">{fmtPercent(daily?.win_rate ?? 0)}</div></div>
              <div className="rounded-xl border border-gray-800 bg-gray-950/60 p-4"><div className="text-xs text-gray-500">Profit factor</div><div className="mt-2 text-xl font-semibold text-white">{(daily as any)?.profit_factor ?? '—'}</div></div>
              <div className="rounded-xl border border-gray-800 bg-gray-950/60 p-4"><div className="text-xs text-gray-500">Открытых позиций</div><div className="mt-2 text-xl font-semibold text-white">{fmtNumber(daily?.open_positions ?? 0, 0)}</div></div>
            </div>
          </QueryBlock>
        </Surface>
      </div>

      <Surface title="История equity">
        <QueryBlock isLoading={page.isLoading && !page.data} isError={page.isError && !page.data} errorMessage="Не удалось загрузить history" onRetry={() => page.refetch()}>
          {history?.meta?.flat_equity ? <div className="mb-3 rounded-xl border border-amber-500/20 bg-amber-500/10 p-3 text-sm text-amber-100">{history.meta.note || 'Кривая equity пока плоская: движений по счёту ещё не было.'}</div> : null}
          <SimpleTable
            columns={['Время', 'Баланс', 'Equity', 'Day PnL']}
            rows={(history?.points ?? []).slice(-30).reverse().map((point) => [
              fmtDateTime(point.ts),
              fmtMoney(point.balance),
              fmtMoney(point.equity),
              <span className={Number(point.day_pnl ?? 0) >= 0 ? 'text-emerald-300' : 'text-rose-300'}>{fmtMoney(point.day_pnl)}</span>,
            ])}
            empty="История пуста"
          />
        </QueryBlock>
      </Surface>

      <Surface title="Качество ответа API">
        <div className="grid gap-3 md:grid-cols-3">
          <div className="rounded-xl border border-gray-800 bg-gray-950/60 p-4"><div className="text-xs text-gray-500">/ui/account</div><div className="mt-2"><StatusChip tone={page.isError ? 'bad' : 'good'}>{page.isError ? 'Ошибка' : 'OK'}</StatusChip></div></div>
          <div className="rounded-xl border border-gray-800 bg-gray-950/60 p-4"><div className="text-xs text-gray-500">summary</div><div className="mt-2"><StatusChip tone={summary?.degraded ? 'warn' : 'good'}>{summary?.degraded ? 'degraded' : 'OK'}</StatusChip></div></div>
          <div className="rounded-xl border border-gray-800 bg-gray-950/60 p-4"><div className="text-xs text-gray-500">daily stats</div><div className="mt-2"><StatusChip tone={(daily as any)?.degraded ? 'warn' : 'good'}>{(daily as any)?.degraded ? 'degraded' : 'OK'}</StatusChip></div></div>
        </div>
      </Surface>
    </PageShell>
  );
}
