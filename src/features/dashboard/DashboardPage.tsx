import { ChartContainer } from './ChartContainer';
import { TradeModeChip } from '../../components/ui/UIComponents';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '../../services/api';
import { useNavigate } from 'react-router-dom';
import { Play, Square } from 'lucide-react';
import { InstrumentSelector } from './InstrumentSelector';
import { StatsWidgets } from './StatsWidgets';
import { OpenPositionsPanel } from './PnLWidgets';
import { useSignals } from '../signals/hooks';

export default function DashboardPage() {
  const { data: signals }  = useSignals();
  const navigate           = useNavigate();
  const { data: botStatus } = useQuery({
    queryKey: ['bot-status-mini'],
    queryFn: async () => { const { data } = await apiClient.get('/state'); return data; },
    refetchInterval: 10_000, retry: false,
  });
  const { data: settings } = useQuery({
    queryKey: ['settings-mini'],
    queryFn: async () => { const { data } = await apiClient.get('/settings'); return data; },
    staleTime: 60_000, retry: false,
  });

  return (
    <div className="h-full flex flex-col bg-gray-950 overflow-hidden">
      {/* Header */}
      <div className="h-14 border-b border-gray-800 flex items-center px-4 gap-3 bg-gray-950 shrink-0">
        <InstrumentSelector />
        <div className="ml-auto flex items-center gap-2">
          <TradeModeChip mode={settings?.trade_mode} onClick={() => navigate('/settings')} />
          {botStatus !== undefined && (
            <button
              onClick={() => navigate('/settings')}
              title={botStatus?.is_running ? 'Бот работает (нажмите для управления)' : 'Бот остановлен (нажмите для запуска)'}
              className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
                botStatus?.is_running
                  ? 'bg-green-500/10 border-green-500/30 text-green-400 hover:bg-green-500/20'
                  : 'bg-gray-800 border-gray-700 text-gray-500 hover:border-gray-500'
              }`}>
              {botStatus?.is_running ? <><span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />Работает</> : <><Square className="w-3 h-3" />Остановлен</>}
            </button>
          )}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 flex min-h-0">
        {/* Main: stats + chart */}
        <div className="flex-1 flex flex-col p-3 min-w-0">
          <StatsWidgets />
          <div className="flex-1 bg-gray-900 border border-gray-800 rounded-lg overflow-hidden shadow-inner">
            <ChartContainer signals={signals} />
          </div>
        </div>

        {/* Right sidebar: open positions */}
        <div className="hidden xl:flex flex-col w-64 p-3 pl-0">
          <OpenPositionsPanel />
        </div>
      </div>
    </div>
  );
}
