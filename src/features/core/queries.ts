import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../../services/api';
import type { BotStatus, Order, Position, RiskSettings, Signal, Trade, TradingScheduleSnapshot } from '../../types';

export type WorkerStatus = {
  running?: boolean;
  pid?: number | null;
  last_heartbeat_ts?: number | null;
  last_cycle_ts?: number | null;
  cycle_interval_sec?: number | null;
  status?: string | null;
  message?: string | null;
  [key: string]: unknown;
};

export type WatchlistItem = {
  instrument_id: string;
  ticker: string;
  name: string;
  exchange?: string;
  is_active?: boolean;
  added_ts?: number;
};

export type InstrumentSearchItem = {
  instrument_id: string;
  ticker: string;
  name: string;
  exchange?: string;
  type?: string;
};

export type DecisionLogItem = {
  id: string;
  ts: number;
  type: string;
  message: string;
  payload?: unknown;
};

export type AccountSummary = {
  mode?: string;
  balance?: number;
  equity?: number;
  open_pnl?: number;
  day_pnl?: number;
  total_pnl?: number;
  open_positions?: number;
  max_drawdown_pct?: number;
  degraded?: boolean;
  broker_info?: { name?: string; type?: string; status?: string };
};

export type AccountHistoryPoint = { ts: number; balance: number; equity: number; day_pnl: number };
export type AccountHistory = { period_days: number; points: AccountHistoryPoint[] };
export type AccountDailyStats = {
  trades_count?: number;
  wins_count?: number;
  losses_count?: number;
  open_positions?: number;
  pnl_total?: number;
  pnl_avg?: number;
  pnl_best?: number;
  pnl_worst?: number;
  win_rate?: number;
  profit_factor?: number | null;
};

export type HealthPayload = {
  status?: string;
  version?: string;
  server_time_utc?: string;
  server_time_msk?: string;
  timezone?: string;
  components?: Record<string, unknown>;
};

export const CORE_KEYS = {
  health: ['core', 'health'] as const,
  botStatus: ['core', 'bot-status'] as const,
  state: ['core', 'state'] as const,
  worker: ['core', 'worker-status'] as const,
  settings: ['core', 'settings'] as const,
  schedule: ['core', 'trading-schedule'] as const,
  watchlist: ['core', 'watchlist'] as const,
  positions: ['core', 'positions'] as const,
  orders: ['core', 'orders'] as const,
  signals: ['core', 'signals'] as const,
  trades: ['core', 'trades'] as const,
  decisionLog: ['core', 'decision-log'] as const,
  accountSummary: ['core', 'account-summary'] as const,
  accountHistory: (days: number) => ['core', 'account-history', days] as const,
  accountDailyStats: ['core', 'account-daily-stats'] as const,
  searchInstruments: (query: string) => ['core', 'instrument-search', query] as const,
};

async function getJson<T>(url: string, params?: Record<string, unknown>): Promise<T> {
  const { data } = await apiClient.get<T>(url, { params });
  return data;
}

async function listItems<T>(url: string, params?: Record<string, unknown>): Promise<T[]> {
  const data = await getJson<{ items?: T[] }>(url, params);
  return Array.isArray(data?.items) ? data.items : [];
}

export function useHealth() {
  return useQuery({
    queryKey: CORE_KEYS.health,
    queryFn: () => getJson<HealthPayload>('/health'),
    retry: false,
    staleTime: 30_000,
    refetchInterval: 30_000,
  });
}

export function useBotStatus() {
  return useQuery({
    queryKey: CORE_KEYS.botStatus,
    queryFn: () => getJson<BotStatus>('/bot/status'),
    retry: false,
    staleTime: 5_000,
    refetchInterval: 10_000,
  });
}

export function useStateSummary() {
  return useQuery({
    queryKey: CORE_KEYS.state,
    queryFn: () => getJson<BotStatus & { degraded?: boolean; error?: unknown }>('/state'),
    retry: false,
    staleTime: 5_000,
    refetchInterval: 10_000,
  });
}

export function useWorkerStatus() {
  return useQuery({
    queryKey: CORE_KEYS.worker,
    queryFn: () => getJson<WorkerStatus>('/worker/status'),
    retry: false,
    staleTime: 5_000,
    refetchInterval: 10_000,
  });
}

export function useSettings() {
  return useQuery({
    queryKey: CORE_KEYS.settings,
    queryFn: () => getJson<RiskSettings>('/settings'),
    retry: false,
    staleTime: 10_000,
  });
}

export function useTradingSchedule() {
  return useQuery({
    queryKey: CORE_KEYS.schedule,
    queryFn: () => getJson<TradingScheduleSnapshot>('/settings/trading-schedule'),
    retry: false,
    staleTime: 60_000,
    refetchInterval: 60_000,
  });
}

export function useWatchlist() {
  return useQuery({
    queryKey: CORE_KEYS.watchlist,
    queryFn: () => listItems<WatchlistItem>('/watchlist'),
    retry: false,
    staleTime: 15_000,
  });
}

export function usePositions() {
  return useQuery({
    queryKey: CORE_KEYS.positions,
    queryFn: () => listItems<Position>('/state/positions'),
    retry: false,
    staleTime: 5_000,
    refetchInterval: 10_000,
  });
}

export function useOrders(activeOnly = false) {
  return useQuery({
    queryKey: [...CORE_KEYS.orders, activeOnly ? 'active' : 'all'],
    queryFn: () => listItems<Order>('/state/orders', { active_only: activeOnly }),
    retry: false,
    staleTime: 5_000,
    refetchInterval: 10_000,
  });
}

export function useSignals(status?: string, limit = 50) {
  return useQuery({
    queryKey: [...CORE_KEYS.signals, status ?? 'all', limit],
    queryFn: () => listItems<Signal>('/signals', { status, limit }),
    retry: false,
    staleTime: 5_000,
    refetchInterval: 10_000,
  });
}

export function useTrades() {
  return useQuery({
    queryKey: CORE_KEYS.trades,
    queryFn: () => listItems<Trade>('/state/trades'),
    retry: false,
    staleTime: 5_000,
    refetchInterval: 10_000,
  });
}

export function useDecisionLog(limit = 200) {
  return useQuery({
    queryKey: [...CORE_KEYS.decisionLog, limit],
    queryFn: () => listItems<DecisionLogItem>('/decision-log', { limit }),
    retry: false,
    staleTime: 5_000,
    refetchInterval: 10_000,
  });
}

export function useAccountSummary() {
  return useQuery({
    queryKey: CORE_KEYS.accountSummary,
    queryFn: () => getJson<AccountSummary>('/account/summary'),
    retry: false,
    staleTime: 10_000,
    refetchInterval: 15_000,
  });
}

export function useAccountHistory(days = 30) {
  return useQuery({
    queryKey: CORE_KEYS.accountHistory(days),
    queryFn: () => getJson<AccountHistory>('/account/history', { period_days: days }),
    retry: false,
    staleTime: 30_000,
  });
}

export function useAccountDailyStats() {
  return useQuery({
    queryKey: CORE_KEYS.accountDailyStats,
    queryFn: () => getJson<AccountDailyStats>('/account/daily-stats'),
    retry: false,
    staleTime: 10_000,
    refetchInterval: 15_000,
  });
}

export function useInstrumentSearch(query: string) {
  return useQuery({
    queryKey: CORE_KEYS.searchInstruments(query),
    queryFn: async () => {
      const data = await getJson<{ items?: InstrumentSearchItem[] }>('/instruments/search', { q: query, limit: 20 });
      return Array.isArray(data?.items) ? data.items : [];
    },
    enabled: query.trim().length >= 1,
    retry: false,
    staleTime: 60_000,
  });
}

export function useUpdateSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: RiskSettings) => {
      const { data } = await apiClient.put<RiskSettings>('/settings', payload);
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: CORE_KEYS.settings });
      qc.invalidateQueries({ queryKey: CORE_KEYS.botStatus });
      qc.invalidateQueries({ queryKey: CORE_KEYS.state });
      qc.invalidateQueries({ queryKey: CORE_KEYS.schedule });
    },
  });
}

export function useSyncTradingSchedule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { data } = await apiClient.post('/settings/trading-schedule/sync');
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: CORE_KEYS.schedule });
      qc.invalidateQueries({ queryKey: CORE_KEYS.botStatus });
      qc.invalidateQueries({ queryKey: CORE_KEYS.state });
    },
  });
}

export function useStartBot() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (mode: BotStatus['mode']) => {
      const { data } = await apiClient.post<BotStatus>('/bot/start', { mode });
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: CORE_KEYS.botStatus });
      qc.invalidateQueries({ queryKey: CORE_KEYS.state });
      qc.invalidateQueries({ queryKey: CORE_KEYS.settings });
    },
  });
}

export function useStopBot() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const { data } = await apiClient.post<BotStatus>('/bot/stop');
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: CORE_KEYS.botStatus });
      qc.invalidateQueries({ queryKey: CORE_KEYS.state });
      qc.invalidateQueries({ queryKey: CORE_KEYS.settings });
    },
  });
}

export function useAddWatchlist() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: { instrument_id: string; ticker: string; name: string; exchange?: string }) => {
      const { data } = await apiClient.post('/watchlist', payload);
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: CORE_KEYS.watchlist });
    },
  });
}

export function useRemoveWatchlist() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (instrumentId: string) => {
      const { data } = await apiClient.delete(`/watchlist/${encodeURIComponent(instrumentId)}`);
      return data;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: CORE_KEYS.watchlist });
    },
  });
}
