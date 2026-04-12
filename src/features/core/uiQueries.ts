import { useQuery } from '@tanstack/react-query';
import { apiClient } from '../../services/api';
import type { BotStatus, DecisionLog, Order, Position, RiskSettings, Signal, Trade, TradingScheduleSnapshot } from '../../types';
import type { AccountDailyStats, AccountHistory, AccountSummary, WorkerStatus, WatchlistItem } from './queries';

export type RuntimeOverviewPayload = {
  instrument_id?: string | null;
  effective_plan?: Record<string, unknown> | null;
  symbol_profile?: Record<string, unknown> | null;
  diagnostics?: Record<string, unknown> | null;
  event_regime?: Record<string, unknown> | null;
  hierarchy?: Array<{ title: string; scope: string; recommended_to_change: boolean | string; description: string; fields: string[] }>;
  global_defaults?: Record<string, unknown>;
  ai_runtime?: Record<string, unknown> | null;
  telegram?: Record<string, unknown> | null;
  auto_policy?: Record<string, unknown> | null;
  ml_runtime?: Record<string, unknown> | null;
  pipeline_counters?: Record<string, unknown> | null;
  source_notes?: string[];
};

export type SymbolProfileViewPayload = {
  profile?: Record<string, unknown> | null;
  current_plan?: Record<string, unknown> | null;
  diagnostics?: Record<string, unknown> | null;
};

export type EventRegimeViewPayload = {
  items?: Array<Record<string, unknown>>;
};

export type UiRuntimePayload = {
  bot_status: BotStatus;
  worker_status: WorkerStatus;
  settings: RiskSettings;
  schedule: TradingScheduleSnapshot;
  watchlist: WatchlistItem[];
  runtime_overview?: RuntimeOverviewPayload | null;
  ai_runtime?: Record<string, unknown> | null;
  telegram?: Record<string, unknown> | null;
  auto_policy?: Record<string, unknown> | null;
  ml_runtime?: Record<string, unknown> | null;
  pipeline_counters?: Record<string, unknown> | null;
};

export type UiDashboardPayload = {
  runtime: UiRuntimePayload;
  account_summary: AccountSummary;
  account_history: AccountHistory;
  positions: { items: Position[]; degraded?: boolean; error?: unknown };
  orders: { items: Order[]; degraded?: boolean; error?: unknown };
  signals: { items: Signal[]; next_cursor?: string | null };
  signals_summary: Record<string, number>;
  latest_candle?: { instrument_id?: string | null; latest_ts?: number | null; timeframe?: string | null };
  requested_instrument_id?: string | null;
  requested_timeframe?: string | null;
  generated_ts?: number | null;
};

export type UiSignalsPayload = {
  items: Signal[];
  next_cursor?: string | null;
  summary: Record<string, number>;
  status_counts?: Record<string, number>;
};

export type UiActivityPayload = {
  items: DecisionLog[];
  next_cursor?: string | null;
};

export type UiTradesPayload = {
  items: Trade[];
  total?: number;
  limit?: number;
  offset?: number;
  summary?: Record<string, number>;
};

export type TradeStatsPayload = {
  total_trades: number;
  win_rate: number;
  total_pnl: number;
  avg_trade_pnl: number;
  best_trade: number;
  worst_trade: number;
  wins_count: number;
  losses_count: number;
  profit_factor: number | null;
  avg_duration_sec: number;
};

export type UiAccountPayload = {
  summary: AccountSummary;
  history: AccountHistory & { meta?: { points_count?: number; latest_ts?: number | null; flat_equity?: boolean; note?: string | null } };
  daily_stats: AccountDailyStats;
};

async function getUi<T>(url: string, params?: Record<string, unknown>): Promise<T> {
  const { data } = await apiClient.get<T>(url, { params });
  return data;
}

export function useUiRuntime() {
  return useQuery({
    queryKey: ['ui', 'runtime'],
    queryFn: () => getUi<UiRuntimePayload>('/ui/runtime'),
    staleTime: 15_000,
    refetchInterval: (query) => {
      const status = (query.state.data as UiRuntimePayload | undefined)?.auto_policy?.status;
      return status === 'loading' ? 7_500 : 20_000;
    },
    refetchOnWindowFocus: false,
    refetchOnMount: false,
    placeholderData: undefined,
    retry: false,
  });
}

export function useUiDashboard(instrumentId?: string | null, timeframe: string = '1m') {
  return useQuery({
    queryKey: ['ui', 'dashboard', instrumentId || 'all', timeframe],
    queryFn: () => getUi<UiDashboardPayload>('/ui/dashboard', { history_days: 7, signals_limit: 40, instrument_id: instrumentId || undefined, timeframe }),
    staleTime: 15_000,
    refetchInterval: 20_000,
    refetchOnWindowFocus: false,
    refetchOnMount: false,
    placeholderData: undefined,
    retry: false,
  });
}

export function useUiSettings() {
  return useQuery({
    queryKey: ['ui', 'settings'],
    queryFn: () => getUi<{ runtime: UiRuntimePayload }>('/ui/settings'),
    staleTime: 20_000,
    refetchInterval: (query) => {
      const status = (query.state.data as { runtime?: UiRuntimePayload } | undefined)?.runtime?.auto_policy?.status;
      return status === 'loading' ? 7_500 : 45_000;
    },
    refetchOnWindowFocus: false,
    refetchOnMount: false,
    placeholderData: undefined,
    retry: false,
  });
}


export function useRuntimeOverview(instrumentId?: string | null, enabled = true) {
  return useQuery({
    queryKey: ['settings', 'runtime-overview', instrumentId || 'none'],
    queryFn: () => getUi<RuntimeOverviewPayload>('/settings/runtime-overview', instrumentId ? { instrument_id: instrumentId, include_globals: false } : { include_globals: false }),
    staleTime: 30_000,
    enabled,
    refetchOnWindowFocus: true,
    refetchOnMount: 'always',
    placeholderData: undefined,
    retry: false,
  });
}

export function useSymbolProfileView(instrumentId?: string | null, enabled = true) {
  return useQuery({
    queryKey: ['symbol-profile', instrumentId || 'none'],
    queryFn: () => getUi<SymbolProfileViewPayload>(`/symbol-profiles/${encodeURIComponent(instrumentId || '')}`),
    staleTime: 30_000,
    enabled: enabled && Boolean(instrumentId),
    refetchOnWindowFocus: true,
    refetchOnMount: 'always',
    placeholderData: undefined,
    retry: false,
  });
}

export function useEventRegimeView(instrumentId?: string | null, enabled = true) {
  return useQuery({
    queryKey: ['event-regime', instrumentId || 'none'],
    queryFn: () => getUi<EventRegimeViewPayload>('/event-regimes', instrumentId ? { instrument_id: instrumentId, limit: 1 } : { limit: 1 }),
    staleTime: 30_000,
    enabled: enabled && Boolean(instrumentId),
    refetchOnWindowFocus: true,
    refetchOnMount: 'always',
    placeholderData: undefined,
    retry: false,
  });
}

export function useUiSignals(status?: string, limit = 40) {
  return useQuery({
    queryKey: ['ui', 'signals', status || 'all', limit],
    queryFn: () => getUi<UiSignalsPayload>('/ui/signals', { status: status || undefined, limit }),
    staleTime: 15_000,
    refetchInterval: 20_000,
    refetchOnWindowFocus: false,
    refetchOnMount: false,
    placeholderData: undefined,
    retry: false,
  });
}

export function useUiActivity(limit = 200) {
  return useQuery({
    queryKey: ['ui', 'activity', limit],
    queryFn: () => getUi<UiActivityPayload>('/ui/activity', { limit }),
    staleTime: 15_000,
    refetchInterval: 20_000,
    refetchOnWindowFocus: false,
    refetchOnMount: false,
    placeholderData: undefined,
    retry: false,
  });
}

export function useUiTrades(limit = 50) {
  return useQuery({
    queryKey: ['ui', 'trades', limit],
    queryFn: async () => {
      const { data } = await apiClient.get<UiTradesPayload>('/ui/trades');
      const items = Array.isArray(data.items) ? data.items.slice(0, limit) : [];
      return {
        ...data,
        items,
        total: Number(data.total ?? data.summary?.total ?? items.length),
        limit,
        offset: 0,
      } satisfies UiTradesPayload;
    },
    staleTime: 15_000,
    refetchInterval: 20_000,
    refetchOnWindowFocus: false,
    refetchOnMount: false,
    placeholderData: undefined,
    retry: false,
  });
}

export function useTradeStats() {
  return useQuery({
    queryKey: ['trades', 'stats'],
    queryFn: async () => {
      const { data } = await apiClient.get<TradeStatsPayload>('/trades/stats');
      return data;
    },
    staleTime: 15_000,
    refetchInterval: 20_000,
    refetchOnWindowFocus: false,
    refetchOnMount: false,
    placeholderData: undefined,
    retry: false,
  });
}

export function useUiAccount(historyDays = 30) {
  return useQuery({
    queryKey: ['ui', 'account', historyDays],
    queryFn: () => getUi<UiAccountPayload>('/ui/account', { history_days: historyDays }),
    staleTime: 20_000,
    refetchInterval: 25_000,
    refetchOnWindowFocus: false,
    refetchOnMount: false,
    placeholderData: undefined,
    retry: false,
  });
}
