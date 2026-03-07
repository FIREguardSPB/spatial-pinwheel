import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '../../services/api';
import { usePositions, useOrders } from './hooks';
import { PnLWidget, DrawdownWidget, EquityCurveChart } from './PnLWidgets';
import clsx from 'clsx';
import { TrendingUp, TrendingDown, Activity } from 'lucide-react';

// Real daily stats from P6-11 account API
const useRealDailyStats = () => useQuery({
  queryKey: ['daily-stats-real'],
  queryFn: async () => {
    const { data } = await apiClient.get('/account/daily-stats');
    return data as { day_pnl: number; trades_count: number; win_rate: number; open_positions: number; best_trade: number; worst_trade: number };
  },
  refetchInterval: 30_000,
  retry: false,
  // Fallback mock while API not connected
  placeholderData: { day_pnl: 0, trades_count: 0, win_rate: 0, open_positions: 0, best_trade: 0, worst_trade: 0 },
});

export const StatsWidgets: React.FC = () => {
  const { data: positions } = usePositions();
  const { data: orders }    = useOrders();
  const { data: stats }     = useRealDailyStats();

  return (
    <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-3">
      {/* P&L Day — real from API */}
      <PnLWidget />

      {/* Open Positions + drawdown */}
      <DrawdownWidget />

      {/* Equity sparkline */}
      <EquityCurveChart />

      {/* Active Orders */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 flex flex-col justify-between">
        <span className="text-gray-500 text-xs uppercase font-bold tracking-wider">Active Orders</span>
        <div className="flex items-center mt-2">
          <span className="text-2xl font-bold font-mono">{orders?.length ?? 0}</span>
          <span className="text-xs text-gray-500 ml-2">Pending</span>
        </div>
      </div>

      {/* Trades Today */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 flex flex-col justify-between">
        <span className="text-gray-500 text-xs uppercase font-bold tracking-wider">Trades Today</span>
        <div className="flex items-center mt-2">
          {(stats?.trades_count ?? 0) > 0
            ? <TrendingUp className="w-5 h-5 text-green-500 mr-2" />
            : <TrendingDown className="w-5 h-5 text-gray-600 mr-2" />}
          <span className="text-2xl font-bold font-mono">{stats?.trades_count ?? 0}</span>
        </div>
        {stats && stats.win_rate > 0 && (
          <div className={clsx('text-xs mt-1', stats.win_rate >= 50 ? 'text-emerald-500' : 'text-red-400')}>
            WR {stats.win_rate.toFixed(0)}%
          </div>
        )}
      </div>
    </div>
  );
};
