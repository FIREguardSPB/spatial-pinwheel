import { Component, type ErrorInfo, type ReactNode } from 'react';
import { AlertTriangle, Home, RefreshCw } from 'lucide-react';

interface Props {
  children?: ReactNode;
  sectionName?: string;
  resetKey?: string;
}

interface State {
  hasError: boolean;
  error?: Error;
  detailsOpen: boolean;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    detailsOpen: false,
  };

  public static getDerivedStateFromError(error: Error): Partial<State> {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Uncaught error:', error, errorInfo);
  }

  public componentDidUpdate(prevProps: Props) {
    if (this.state.hasError && prevProps.resetKey !== this.props.resetKey) {
      this.handleReset();
    }
  }

  private handleReset = () => {
    this.setState({ hasError: false, error: undefined, detailsOpen: false });
  };

  public render() {
    if (!this.state.hasError) return this.props.children;

    const sectionName = this.props.sectionName ?? 'интерфейсе';
    return (
      <div className="min-h-[60vh] w-full flex items-center justify-center p-6">
        <div className="max-w-xl w-full rounded-2xl border border-red-500/20 bg-gray-900 p-6 shadow-2xl space-y-4">
          <div className="flex items-start gap-3">
            <div className="rounded-full bg-red-500/10 p-3 text-red-400">
              <AlertTriangle className="h-5 w-5" />
            </div>
            <div className="space-y-1">
              <h1 className="text-xl font-semibold text-white">Не удалось отрисовать экран</h1>
              <p className="text-sm text-gray-400">
                Произошла ошибка в разделе «{sectionName}». Торговый backend и фоновые процессы могут продолжать работать,
                но этот экран нужно перезагрузить отдельно.
              </p>
            </div>
          </div>
          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={this.handleReset}
              className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-400"
            >
              <RefreshCw className="h-4 w-4" /> Повторить экран
            </button>
            <button
              type="button"
              onClick={() => {
                window.location.href = '/';
              }}
              className="inline-flex items-center gap-2 rounded-lg border border-gray-700 bg-gray-800 px-4 py-2 text-sm font-medium text-gray-200 hover:bg-gray-700 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-400"
            >
              <Home className="h-4 w-4" /> На дашборд
            </button>
            <button
              type="button"
              onClick={() => this.setState((prev) => ({ detailsOpen: !prev.detailsOpen }))}
              className="inline-flex items-center gap-2 rounded-lg border border-gray-700 px-4 py-2 text-sm font-medium text-gray-300 hover:bg-gray-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-400"
            >
              {this.state.detailsOpen ? 'Скрыть детали' : 'Показать детали'}
            </button>
          </div>
          {this.state.detailsOpen ? (
            <pre className="max-h-64 overflow-auto rounded-xl border border-gray-800 bg-black/50 p-4 text-xs text-gray-300 whitespace-pre-wrap break-words">
              {this.state.error?.stack || this.state.error?.message || 'Нет деталей'}
            </pre>
          ) : null}
        </div>
      </div>
    );
  }
}
