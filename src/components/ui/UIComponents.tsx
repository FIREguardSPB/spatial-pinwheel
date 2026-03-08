import React, { useEffect } from 'react';
import { AlertTriangle, X, RefreshCw } from 'lucide-react';
import clsx from 'clsx';

interface ConfirmModalProps {
  title: string;
  description?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: 'danger' | 'warning' | 'default';
  onConfirm: () => void;
  onCancel: () => void;
}

export const ConfirmModal: React.FC<ConfirmModalProps> = ({
  title,
  description,
  confirmLabel = 'Подтвердить',
  cancelLabel = 'Отмена',
  variant = 'default',
  onConfirm,
  onCancel,
}) => {
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onCancel();
    };
    window.addEventListener('keydown', h);
    return () => window.removeEventListener('keydown', h);
  }, [onCancel]);

  const confirmStyle = {
    danger: 'bg-red-600 hover:bg-red-500 text-white',
    warning: 'bg-yellow-600 hover:bg-yellow-500 text-white',
    default: 'bg-blue-600 hover:bg-blue-500 text-white',
  }[variant];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4" onClick={(e) => { if (e.target === e.currentTarget) onCancel(); }}>
      <div className="bg-gray-900 border border-gray-700 rounded-2xl shadow-2xl max-w-sm w-full p-6">
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-3">
            <div className={clsx('w-9 h-9 rounded-full flex items-center justify-center shrink-0', variant === 'danger' ? 'bg-red-500/20' : variant === 'warning' ? 'bg-yellow-500/20' : 'bg-blue-500/20')}>
              <AlertTriangle className={clsx('w-4 h-4', variant === 'danger' ? 'text-red-400' : variant === 'warning' ? 'text-yellow-400' : 'text-blue-400')} />
            </div>
            <h2 className="text-base font-bold text-gray-100">{title}</h2>
          </div>
          <button onClick={onCancel} className="text-gray-500 hover:text-gray-200 transition-colors p-1">
            <X className="w-4 h-4" />
          </button>
        </div>
        {description && <p className="text-sm text-gray-400 mb-5 pl-12">{description}</p>}
        <div className="flex gap-3 justify-end">
          <button onClick={onCancel} className="px-4 py-2 bg-gray-800 hover:bg-gray-700 border border-gray-600 text-gray-300 rounded-lg text-sm font-medium transition-colors">
            {cancelLabel}
          </button>
          <button onClick={onConfirm} className={clsx('px-4 py-2 rounded-lg text-sm font-medium transition-colors', confirmStyle)}>
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
};

export const Skeleton: React.FC<{ className?: string; style?: React.CSSProperties }> = ({ className, style }) => (
  <div className={clsx('bg-gray-800 rounded animate-pulse', className)} style={style} />
);

export const StatsWidgetsSkeleton: React.FC = () => (
  <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-3">
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
  <div className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
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

export const ActivityLogSkeleton: React.FC = () => (
  <div className="space-y-1 p-4">
    {Array.from({ length: 6 }).map((_, i) => (
      <div key={i} className="flex items-center gap-3 py-2">
        <Skeleton className="w-2 h-2 rounded-full shrink-0" />
        <Skeleton className="h-3 w-16" />
        <Skeleton className="h-3 flex-1" style={{ width: `${50 + Math.random() * 40}%` }} />
      </div>
    ))}
  </div>
);

interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  action?: { label: string; onClick: () => void };
}

export const EmptyState: React.FC<EmptyStateProps> = ({ icon, title, description, action }) => (
  <div className="flex flex-col items-center justify-center py-16 px-6 text-center">
    {icon && <div className="mb-4 text-gray-700">{icon}</div>}
    <h3 className="text-gray-400 font-medium mb-2">{title}</h3>
    {description && <p className="text-gray-600 text-sm max-w-xs leading-relaxed mb-4">{description}</p>}
    {action && (
      <button onClick={action.onClick} className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-sm font-medium transition-colors">
        {action.label}
      </button>
    )}
  </div>
);

interface ErrorStateProps {
  message?: string;
  onRetry?: () => void;
}

export const ErrorState: React.FC<ErrorStateProps> = ({
  message = 'Не удалось загрузить данные',
  onRetry,
}) => (
  <div className="flex flex-col items-center justify-center py-12 px-6 text-center">
    <div className="w-12 h-12 rounded-full bg-red-500/10 flex items-center justify-center mb-4">
      <AlertTriangle className="w-6 h-6 text-red-400" />
    </div>
    <p className="text-gray-400 font-medium mb-1">{message}</p>
    <p className="text-gray-600 text-sm mb-4">Проверьте подключение к серверу</p>
    {onRetry && (
      <button onClick={onRetry} className="flex items-center gap-2 px-4 py-2 bg-gray-800 hover:bg-gray-700 border border-gray-600 text-gray-300 rounded-lg text-sm font-medium transition-colors">
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
    <button onClick={onClick} className={clsx('inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium border transition-colors hover:opacity-80', config.cls)} title="Нажмите, чтобы открыть настройки режима торговли">
      {config.label}
    </button>
  );
};

export const WelcomeBanner: React.FC<{ onDismiss: () => void }> = ({ onDismiss }) => (
  <div className="bg-gradient-to-r from-blue-600/20 to-purple-600/10 border border-blue-500/20 rounded-xl p-4 mb-4 relative">
    <button onClick={onDismiss} className="absolute top-3 right-3 text-gray-500 hover:text-gray-300 transition-colors">
      <X className="w-4 h-4" />
    </button>
    <h3 className="font-bold text-blue-300 mb-2">👋 Добро пожаловать в BotPanel!</h3>
    <div className="flex items-center gap-6 text-sm text-gray-400">
      <span className="flex items-center gap-1.5"><span className="text-blue-400 font-bold">1.</span> Настройте инструменты</span>
      <span className="text-gray-600">→</span>
      <span className="flex items-center gap-1.5"><span className="text-blue-400 font-bold">2.</span> Запустите бота</span>
      <span className="text-gray-600">→</span>
      <span className="flex items-center gap-1.5"><span className="text-blue-400 font-bold">3.</span> Ожидайте сигналы</span>
    </div>
  </div>
);
