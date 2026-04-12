import React, { useEffect, useId, useRef } from 'react';
import { AlertTriangle, X, RefreshCw } from 'lucide-react';
import clsx from 'clsx';

function getFocusableElements(container: HTMLElement | null) {
  if (!container) return [] as HTMLElement[];
  return Array.from(
    container.querySelectorAll<HTMLElement>('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'),
  ).filter((el) => !el.hasAttribute('disabled') && el.getAttribute('aria-hidden') !== 'true');
}

function useDialogAccessibility(open: boolean, onClose: () => void) {
  const dialogRef = useRef<HTMLDivElement | null>(null);
  const previouslyFocusedRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return undefined;
    previouslyFocusedRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const dialog = dialogRef.current;
    const focusable = getFocusableElements(dialog);
    const firstFocusable = focusable[0] ?? dialog;
    window.setTimeout(() => firstFocusable?.focus(), 0);

    const handler = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== 'Tab') return;
      const items = getFocusableElements(dialogRef.current);
      if (items.length === 0) {
        event.preventDefault();
        dialogRef.current?.focus();
        return;
      }
      const currentIndex = items.indexOf(document.activeElement as HTMLElement);
      const lastIndex = items.length - 1;
      if (event.shiftKey) {
        if (currentIndex <= 0) {
          event.preventDefault();
          items[lastIndex]?.focus();
        }
        return;
      }
      if (currentIndex === -1 || currentIndex === lastIndex) {
        event.preventDefault();
        items[0]?.focus();
      }
    };

    window.addEventListener('keydown', handler);
    document.body.style.overflow = 'hidden';
    return () => {
      window.removeEventListener('keydown', handler);
      document.body.style.overflow = '';
      previouslyFocusedRef.current?.focus?.();
    };
  }, [open, onClose]);

  return dialogRef;
}

interface ConfirmModalProps {
  title: string;
  description?: string;
  message?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: 'danger' | 'warning' | 'default';
  onConfirm: () => void;
  onCancel: () => void;
}

export const ConfirmModal: React.FC<ConfirmModalProps> = ({
  title,
  description,
  message,
  confirmLabel = 'Подтвердить',
  cancelLabel = 'Отмена',
  variant = 'default',
  onConfirm,
  onCancel,
}) => {
  const dialogRef = useDialogAccessibility(true, onCancel);
  const titleId = useId();
  const descriptionId = useId();
  const cancelButtonRef = useRef<HTMLButtonElement | null>(null);
  const bodyText = description ?? message;

  useEffect(() => {
    cancelButtonRef.current?.focus();
  }, []);

  const confirmStyle = {
    danger: 'bg-red-600 hover:bg-red-500 text-white focus-visible:outline-red-400',
    warning: 'bg-yellow-600 hover:bg-yellow-500 text-white focus-visible:outline-yellow-400',
    default: 'bg-blue-600 hover:bg-blue-500 text-white focus-visible:outline-blue-400',
  }[variant];

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onCancel();
      }}
    >
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        aria-describedby={bodyText ? descriptionId : undefined}
        tabIndex={-1}
        className="bg-gray-900 border border-gray-700 rounded-2xl shadow-2xl max-w-sm w-full p-6 outline-none"
      >
        <div className="flex items-start justify-between mb-3 gap-3">
          <div className="flex items-center gap-3 min-w-0">
            <div className={clsx('w-9 h-9 rounded-full flex items-center justify-center shrink-0', variant === 'danger' ? 'bg-red-500/20' : variant === 'warning' ? 'bg-yellow-500/20' : 'bg-blue-500/20')}>
              <AlertTriangle className={clsx('w-4 h-4', variant === 'danger' ? 'text-red-400' : variant === 'warning' ? 'text-yellow-400' : 'text-blue-400')} />
            </div>
            <div className="min-w-0">
              <h2 id={titleId} className="text-base font-bold text-gray-100">{title}</h2>
              {bodyText ? <p id={descriptionId} className="text-sm text-gray-400 mt-1">{bodyText}</p> : null}
            </div>
          </div>
          <button
            type="button"
            onClick={onCancel}
            aria-label="Закрыть диалог"
            className="text-gray-500 hover:text-gray-200 transition-colors p-1 rounded-lg hover:bg-gray-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-400"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="flex gap-3 justify-end mt-5">
          <button
            ref={cancelButtonRef}
            type="button"
            onClick={onCancel}
            className="px-4 py-2 bg-gray-800 hover:bg-gray-700 border border-gray-600 text-gray-300 rounded-lg text-sm font-medium transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-400"
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className={clsx('px-4 py-2 rounded-lg text-sm font-medium transition-colors focus-visible:outline focus-visible:outline-2', confirmStyle)}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
};

export const Skeleton: React.FC<{ className?: string; style?: React.CSSProperties }> = ({ className, style }) => (
  <div className={clsx('bg-gray-800 rounded animate-pulse', className)} style={style} aria-hidden="true" />
);

export const StatsWidgetsSkeleton: React.FC = () => (
  <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-3" aria-hidden="true">
    {Array.from({ length: 5 }).map((_, i) => (
      <div key={i} className="bg-gray-900 border border-gray-800 rounded-lg p-4 space-y-3">
        <Skeleton className="h-3 w-20" />
        <Skeleton className="h-7 w-28" />
        <Skeleton className="h-2 w-16" />
      </div>
    ))}
  </div>
);

export const SignalsTableSkeleton: React.FC = () => (
  <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden" aria-hidden="true">
    <div className="bg-gray-800 h-10" />
    {Array.from({ length: 5 }).map((_, i) => (
      <div key={i} className="flex items-center gap-4 px-6 py-4 border-b border-gray-800">
        <Skeleton className="h-4 w-16" />
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-6 w-14 rounded-full" />
        <Skeleton className="h-4 w-32" />
        <Skeleton className="h-4 w-16" />
        <Skeleton className="h-4 w-20" />
        <Skeleton className="h-4 w-20" />
        <Skeleton className="h-4 w-12" />
        <div className="ml-auto flex gap-2">
          <Skeleton className="h-7 w-7 rounded" />
          <Skeleton className="h-7 w-7 rounded" />
        </div>
      </div>
    ))}
  </div>
);

const activityWidths = ['52%', '68%', '74%', '61%', '83%', '58%'];

export const ActivityLogSkeleton: React.FC = () => (
  <div className="space-y-1 p-4" aria-hidden="true">
    {activityWidths.map((width, i) => (
      <div key={i} className="flex items-center gap-3 py-2">
        <Skeleton className="w-2 h-2 rounded-full shrink-0" />
        <Skeleton className="h-3 w-16" />
        <Skeleton className="h-3 flex-1" style={{ width }} />
      </div>
    ))}
  </div>
);

interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  message?: string;
  action?: { label: string; onClick: () => void };
}

export const EmptyState: React.FC<EmptyStateProps> = ({ icon, title, description, message, action }) => {
  const bodyText = description ?? message;
  return (
    <div className="flex flex-col items-center justify-center py-16 px-6 text-center">
      {icon && <div className="mb-4 text-gray-700">{icon}</div>}
      <h3 className="text-gray-300 font-medium mb-2">{title}</h3>
      {bodyText && <p className="text-gray-500 text-sm max-w-xs leading-relaxed mb-4">{bodyText}</p>}
      {action && (
        <button onClick={action.onClick} className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-sm font-medium transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-400">
          {action.label}
        </button>
      )}
    </div>
  );
};

interface ErrorStateProps {
  message?: string;
  onRetry?: () => void;
}

export const ErrorState: React.FC<ErrorStateProps> = ({
  message = 'Не удалось загрузить данные',
  onRetry,
}) => (
  <div className="flex flex-col items-center justify-center py-12 px-6 text-center" role="status" aria-live="polite">
    <div className="w-12 h-12 rounded-full bg-red-500/10 flex items-center justify-center mb-4">
      <AlertTriangle className="w-6 h-6 text-red-400" />
    </div>
    <p className="text-gray-300 font-medium mb-1">{message}</p>
    <p className="text-gray-500 text-sm mb-4">Проверьте подключение к серверу или повторите запрос.</p>
    {onRetry && (
      <button onClick={onRetry} className="flex items-center gap-2 px-4 py-2 bg-gray-800 hover:bg-gray-700 border border-gray-600 text-gray-300 rounded-lg text-sm font-medium transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-400">
        <RefreshCw className="w-3.5 h-3.5" /> Повторить
      </button>
    )}
  </div>
);

export const TradeModeChip: React.FC<{ mode?: string; onClick?: () => void }> = ({ mode, onClick }) => {
  const normalized = mode === 'paper' ? 'auto_paper' : mode === 'live' ? 'auto_live' : (mode ?? 'review');
  const config = {
    review: { label: '👁 Ручное ревью', cls: 'bg-blue-500/10 text-blue-400 border-blue-500/20' },
    auto_paper: { label: '📄 Авто Paper', cls: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20' },
    auto_live: { label: '💸 Авто Live', cls: 'bg-red-500/10 text-red-400 border-red-500/20' },
  }[normalized] ?? { label: '— Режим', cls: 'bg-gray-800 text-gray-500 border-gray-700' };

  return (
    <button
      type="button"
      onClick={onClick}
      className={clsx('inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium border transition-colors hover:opacity-80 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-400', config.cls)}
      title="Нажмите, чтобы открыть настройки режима торговли"
    >
      {config.label}
    </button>
  );
};

export const WelcomeBanner: React.FC<{ onDismiss: () => void }> = ({ onDismiss }) => (
  <div className="bg-gradient-to-r from-blue-600/20 to-purple-600/10 border border-blue-500/20 rounded-xl p-4 mb-4 relative" role="region" aria-label="Быстрый старт">
    <button onClick={onDismiss} className="absolute top-3 right-3 text-gray-500 hover:text-gray-300 transition-colors rounded-lg p-1 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-400" aria-label="Скрыть быстрый старт">
      <X className="w-4 h-4" />
    </button>
    <h3 className="font-bold text-blue-300 mb-2">👋 Добро пожаловать в BotPanel!</h3>
    <div className="flex flex-wrap items-center gap-3 text-sm text-gray-400">
      <span className="flex items-center gap-1.5"><span className="text-blue-400 font-bold">1.</span> Настройте инструменты</span>
      <span className="text-gray-600" aria-hidden="true">→</span>
      <span className="flex items-center gap-1.5"><span className="text-blue-400 font-bold">2.</span> Запустите бота</span>
      <span className="text-gray-600" aria-hidden="true">→</span>
      <span className="flex items-center gap-1.5"><span className="text-blue-400 font-bold">3.</span> Ожидайте сигналы</span>
    </div>
  </div>
);
