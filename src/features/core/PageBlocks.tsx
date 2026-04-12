import clsx from 'clsx';
import { RefreshCw } from 'lucide-react';
import type { ReactNode } from 'react';
import { ErrorState, Skeleton } from '../../components/ui/UIComponents';

export function PageShell({ title, subtitle, actions, children }: { title: string; subtitle?: string; actions?: ReactNode; children: ReactNode }) {
  return (
    <div className="p-4 md:p-6 space-y-4">
      <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-white">{title}</h1>
          {subtitle ? <p className="mt-1 text-sm text-gray-400">{subtitle}</p> : null}
        </div>
        {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
      </div>
      {children}
    </div>
  );
}

export function Surface({ title, description, right, children, className }: { title: string; description?: string; right?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={clsx('rounded-2xl border border-gray-800 bg-gray-900/80 p-4 shadow-sm', className)}>
      <div className="mb-4 flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <h2 className="text-base font-semibold text-white">{title}</h2>
          {description ? <p className="mt-1 text-sm text-gray-400">{description}</p> : null}
        </div>
        {right ? <div className="flex items-center gap-2">{right}</div> : null}
      </div>
      {children}
    </section>
  );
}

export function StatGrid({ items }: { items: { label: string; value: ReactNode; hint?: string; tone?: 'default' | 'good' | 'bad' }[] }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      {items.map((item) => (
        <div key={item.label} className="rounded-xl border border-gray-800 bg-gray-950/60 p-4">
          <div className="text-xs uppercase tracking-wide text-gray-500">{item.label}</div>
          <div className={clsx('mt-2 text-xl font-semibold', item.tone === 'good' ? 'text-emerald-300' : item.tone === 'bad' ? 'text-rose-300' : 'text-white')}>
            {item.value}
          </div>
          {item.hint ? <div className="mt-1 text-xs text-gray-500">{item.hint}</div> : null}
        </div>
      ))}
    </div>
  );
}

export function ValueRow({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4 py-2 border-b border-gray-800 last:border-b-0">
      <div className="text-sm text-gray-400">{label}</div>
      <div className="text-right text-sm text-white break-words">{value}</div>
    </div>
  );
}

export function QueryBlock({
  isLoading,
  isError,
  errorMessage,
  onRetry,
  skeleton,
  children,
}: {
  isLoading: boolean;
  isError: boolean;
  errorMessage?: string;
  onRetry?: () => void;
  skeleton?: ReactNode;
  children: ReactNode;
}) {
  if (isLoading) {
    return <>{skeleton ?? <div className="space-y-3"><Skeleton className="h-16 w-full" /><Skeleton className="h-16 w-full" /></div>}</>;
  }
  if (isError) {
    return <ErrorState message={errorMessage} onRetry={onRetry} />;
  }
  return <>{children}</>;
}

export function RetryButton({ onClick, label = 'Обновить' }: { onClick: () => void; label?: string }) {
  return (
    <button onClick={onClick} className="inline-flex items-center gap-2 rounded-lg border border-gray-700 bg-gray-800 px-3 py-2 text-sm text-gray-200 hover:bg-gray-700">
      <RefreshCw className="h-4 w-4" />
      {label}
    </button>
  );
}

export function StatusChip({ children, tone = 'default' }: { children: ReactNode; tone?: 'default' | 'good' | 'bad' | 'warn' | 'blue' }) {
  const cls = {
    default: 'border-gray-700 bg-gray-800 text-gray-200',
    good: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300',
    bad: 'border-rose-500/30 bg-rose-500/10 text-rose-300',
    warn: 'border-amber-500/30 bg-amber-500/10 text-amber-300',
    blue: 'border-blue-500/30 bg-blue-500/10 text-blue-300',
  }[tone];
  return <span className={clsx('inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-medium', cls)}>{children}</span>;
}

export function SimpleTable({ columns, rows, empty }: { columns: string[]; rows: ReactNode[][]; empty?: string }) {
  if (rows.length === 0) {
    return <div className="rounded-xl border border-dashed border-gray-700 px-4 py-8 text-center text-sm text-gray-400">{empty ?? 'Нет данных'}</div>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-sm">
        <thead>
          <tr className="border-b border-gray-800 text-left text-gray-400">
            {columns.map((column) => (
              <th key={column} className="px-3 py-2 font-medium">{column}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index} className="border-b border-gray-900 last:border-b-0">
              {row.map((cell, cellIndex) => (
                <td key={cellIndex} className="px-3 py-2 align-top text-gray-200">{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
