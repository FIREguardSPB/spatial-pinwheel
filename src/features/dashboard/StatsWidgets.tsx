import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '../../services/api';
import { useActiveOrders } from './hooks';
import { PnLWidget, DrawdownWidget, EquityCurveChart } from './PnLWidgets';
import clsx from 'clsx';
import { TrendingUp, TrendingDown } from 'lucide-react';
import type { BusinessMetrics } from '../../types';

const useBusinessMetrics = () => useQuery({
  queryKey: ['business-metrics-mini'],
  queryFn: async () => {
    try {
      const { data } = await apiClient.get('/metrics?days=7');
      return data as BusinessMetrics;
    } catch {
      return { trades_count: 0, win_rate: 0, profit_factor: 0, expectancy_per_trade: 0, max_drawdown_pct: 0 } as BusinessMetrics;
    }
  },
  refetchInterval: 30_000,
  retry: 1,
  placeholderData: (prev) => prev,
});

export const StatsWidgets: React.FC = () => {
  const { data: activeOrders } = useActiveOrders();
  const { data: metrics } = useBusinessMetrics();

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
          <span className="text-2xl font-bold font-mono">{activeOrders?.length ?? 0}</span>
          <span className="text-xs text-gray-500 ml-2">Live</span>
        </div>
        {metrics && (
          <div className="text-xs text-gray-500 mt-1">Только NEW / PENDING / PARTIALLY_FILLED</div>
        )}
      </div>

      {/* Trades Today */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 flex flex-col justify-between">
        <span className="text-gray-500 text-xs uppercase font-bold tracking-wider">Trades Today</span>
        <div className="flex items-center mt-2">
          {(metrics?.trades_count ?? 0) > 0
            ? <TrendingUp className="w-5 h-5 text-green-500 mr-2" />
            : <TrendingDown className="w-5 h-5 text-gray-600 mr-2" />}
          <span className="text-2xl font-bold font-mono">{metrics?.trades_count ?? 0}</span>
        </div>
        <div className={clsx('text-xs mt-1', (metrics?.win_rate ?? 0) >= 50 ? 'text-emerald-500' : 'text-red-400')}>
          WR {(metrics?.win_rate ?? 0).toFixed(0)}% · PF {(metrics?.profit_factor ?? 0).toFixed(2)}
        </div>
        <div className="text-[11px] text-gray-500 mt-1">
          Exp {(metrics?.expectancy_per_trade ?? 0).toFixed(0)} ₽ · MDD {(metrics?.max_drawdown_pct ?? 0).toFixed(1)}%
        </div>
      </div>
    </div>
  );
};
