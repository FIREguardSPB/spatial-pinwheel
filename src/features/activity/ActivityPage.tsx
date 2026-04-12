import { PageShell, QueryBlock, RetryButton, SimpleTable, Surface } from '../core/PageBlocks';
import { fmtDateTime } from '../core/format';
import { useUiActivity } from '../core/uiQueries';

export default function ActivityPage() {
  const page = useUiActivity(200);

  return (
    <PageShell
      title="Журнал событий"
      subtitle="Decision log из одного /ui/activity без фона из вспомогательных запросов."
      actions={<RetryButton onClick={() => page.refetch()} />}
    >
      <Surface title="Последние события" description="Coordinator endpoint для decision-log.">
        <QueryBlock isLoading={page.isLoading && !page.data} isError={page.isError && !page.data} errorMessage="Не удалось загрузить журнал" onRetry={() => page.refetch()}>
          <SimpleTable
            columns={['Время', 'Тип', 'Сообщение']}
            rows={(page.data?.items ?? []).map((item) => [
              fmtDateTime(item.ts),
              item.type,
              <div className="max-w-[720px] whitespace-pre-wrap break-words">{item.message}</div>,
            ])}
            empty="Журнал пуст"
          />
        </QueryBlock>
      </Surface>
    </PageShell>
  );
}
