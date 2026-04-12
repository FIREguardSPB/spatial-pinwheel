import { ServerCrash } from 'lucide-react';
import { useAppStore } from '../store';

export function RuntimeStatusBanner() {
  const { lastApiError } = useAppStore();

  if (!lastApiError) {
    return null;
  }

  return (
    <div className="border-b border-yellow-500/20 bg-yellow-500/10 px-4 py-3 text-sm text-yellow-100">
      <div className="flex items-start gap-3">
        <ServerCrash className="mt-0.5 h-4 w-4 shrink-0 text-yellow-300" />
        <div className="min-w-0">
          <div className="font-medium">Последняя ошибка API</div>
          <div className="mt-1 break-words text-yellow-50/90">{lastApiError.message}</div>
          <div className="mt-1 text-xs text-yellow-100/70">
            {lastApiError.path ? `path: ${lastApiError.path}` : 'path: —'}
            {lastApiError.requestId ? ` · req:${lastApiError.requestId}` : ''}
            {lastApiError.statusCode ? ` · HTTP ${lastApiError.statusCode}` : ''}
          </div>
        </div>
      </div>
    </div>
  );
}
