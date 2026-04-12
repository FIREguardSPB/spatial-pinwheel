import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../../services/api';
import type { AIRuntimeDiagnostics, BotStatus, RiskSettings, RuntimeOverview, TradingScheduleSnapshot } from '../../types';
import { API_ENDPOINTS, QUERY_KEYS } from '../../constants';
import { useAppStore } from '../../store';

const defaultSettings: RiskSettings = {
  risk_profile: 'balanced',
  risk_per_trade_pct: 0.25,
  daily_loss_limit_pct: 1.5,
  max_concurrent_positions: 4,
  max_trades_per_day: 120,
  fees_bps: 3,
  slippage_bps: 5,
  max_position_notional_pct_balance: 10,
  max_total_exposure_pct_balance: 35,
  signal_reentry_cooldown_sec: 30,
  rr_target: 1.4,
  time_stop_bars: 12,
  close_before_session_end_minutes: 5,
  cooldown_after_losses: { losses: 2, minutes: 30 },
  atr_stop_hard_min: 0.6,
  atr_stop_hard_max: 2.5,
  atr_stop_soft_min: 0.8,
  atr_stop_soft_max: 2.5,
  rr_min: 1.5,
  decision_threshold: 70,
  w_regime: 20,
  w_volatility: 15,
  w_momentum: 15,
  w_levels: 20,
  w_costs: 15,
  w_liquidity: 5,
  w_volume: 10,
  strategy_name: 'breakout,mean_reversion',
  ai_mode: 'advisory',
  ai_min_confidence: 55,
  ai_primary_provider: 'deepseek',
  ai_fallback_providers: 'deepseek,ollama,skip',
  ollama_url: 'http://localhost:11434',
  ai_override_policy: 'promote_only',
  min_sl_distance_pct: 0.08,
  min_profit_after_costs_multiplier: 1.25,
  min_trade_value_rub: 10,
  min_instrument_price_rub: 0.001,
  min_tick_floor_rub: 0,
  commission_dominance_warn_ratio: 0.3,
  volatility_sl_floor_multiplier: 0,
  sl_cost_floor_multiplier: 0,
  no_trade_opening_minutes: 10,
  higher_timeframe: '15m',
  trading_session: 'all',
  use_broker_trading_schedule: true,
  trading_schedule_exchange: '',
  correlation_threshold: 0.8,
  max_correlated_positions: 2,
  telegram_bot_token: '',
  telegram_chat_id: '',
  notification_events: 'signal_created,trade_executed,sl_hit,tp_hit',
  account_balance: 100000,
  trade_mode: 'auto_paper',
  bot_enabled: false,
  strong_signal_score_threshold: 80,
  strong_signal_position_bonus: 2,
  partial_close_threshold: 80,
  partial_close_ratio: 0.5,
  min_position_age_for_partial_close: 180,
  adaptive_exit_partial_cooldown_sec: 180,
  adaptive_exit_max_partial_closes: 2,
  signal_freshness_enabled: true,
  signal_freshness_grace_bars: 1.0,
  signal_freshness_penalty_per_bar: 6,
  signal_freshness_max_bars: 3.0,
  pm_risk_throttle_enabled: true,
  pm_drawdown_soft_limit_pct: 1.5,
  pm_drawdown_hard_limit_pct: 3.0,
  pm_loss_streak_soft_limit: 2,
  pm_loss_streak_hard_limit: 4,
  pm_min_risk_multiplier: 0.35,
  auto_degrade_enabled: true,
  auto_freeze_enabled: true,
  auto_policy_lookback_days: 14,
  auto_degrade_max_execution_errors: 4,
  auto_freeze_max_execution_errors: 10,
  auto_degrade_min_profit_factor: 0.95,
  auto_freeze_min_profit_factor: 0.70,
  auto_degrade_min_expectancy: -50,
  auto_freeze_min_expectancy: -250,
  auto_degrade_drawdown_pct: 2.5,
  auto_freeze_drawdown_pct: 5.0,
  auto_degrade_risk_multiplier: 0.55,
  auto_degrade_threshold_penalty: 8,
  auto_freeze_new_entries: true,
  performance_governor_enabled: true,
  performance_governor_lookback_days: 45,
  performance_governor_min_closed_trades: 3,
  performance_governor_strict_whitelist: true,
  performance_governor_auto_suppress: true,
  performance_governor_max_execution_error_rate: 0.35,
  performance_governor_min_take_fill_rate: 0.2,
  performance_governor_pass_risk_multiplier: 1.2,
  performance_governor_fail_risk_multiplier: 0.6,
  performance_governor_threshold_bonus: 6,
  performance_governor_threshold_penalty: 10,
  performance_governor_execution_priority_boost: 1.2,
  performance_governor_execution_priority_penalty: 0.7,
  performance_governor_allocator_boost: 1.15,
  performance_governor_allocator_penalty: 0.8,
  ml_enabled: true,
  ml_retrain_enabled: true,
  ml_lookback_days: 120,
  ml_min_training_samples: 80,
  ml_retrain_interval_hours: 24,
  ml_retrain_hour_msk: 4,
  ml_take_probability_threshold: 0.55,
  ml_fill_probability_threshold: 0.45,
  ml_risk_boost_threshold: 0.65,
  ml_risk_cut_threshold: 0.45,
  ml_pass_risk_multiplier: 1.15,
  ml_fail_risk_multiplier: 0.75,
  ml_threshold_bonus: 4,
  ml_threshold_penalty: 8,
  ml_execution_priority_boost: 1.15,
  ml_execution_priority_penalty: 0.8,
  ml_allocator_boost: 1.1,
  ml_allocator_penalty: 0.85,
  ml_allow_take_veto: true,
  worker_bootstrap_limit: 10,
  capital_allocator_min_edge_improvement: 0.18,
  capital_allocator_max_position_concentration_pct: 18,
  capital_allocator_age_decay_per_hour: 0.08,
  symbol_recalibration_enabled: true,
  symbol_recalibration_hour_msk: 4,
  symbol_recalibration_train_limit: 6,
  symbol_recalibration_lookback_days: 180,
};


const FALLBACK_BOT_STATUS: BotStatus = {
  is_running: false,
  mode: 'auto_paper',
  is_paper: true,
  active_instrument_id: 'TQBR:SBER',
  connection: { market_data: 'disconnected', broker: 'disconnected' },
  session: {
    market: 'MOEX',
    timezone: 'Europe/Moscow',
    trading_day: 'unknown',
    source: 'static',
    is_open: null,
    current_session_start: null,
    current_session_end: null,
    next_open: null,
  },
  warnings: ['status unavailable'],
  timezone: 'Europe/Moscow',
  capabilities: {
    manual_review: true,
    auto_paper: true,
    auto_live: true,
  },
};

const FALLBACK_TRADING_SCHEDULE: TradingScheduleSnapshot = {
  source: 'static',
  exchange: 'MOEX',
  trading_day: 'unknown',
  is_trading_day: null,
  is_open: null,
  current_session_start: '2026-01-01T06:50:00+03:00',
  current_session_end: '2026-01-01T23:50:00+03:00',
  next_open: null,
  timezone: 'Europe/Moscow',
  error: 'schedule fallback active',
};

export const useBotStatus = () => {
  const { connectionStatus } = useAppStore();
  return useQuery({
    queryKey: [QUERY_KEYS.BOT_STATUS],
    queryFn: async () => {
      try {
        const res = await apiClient.get<BotStatus>(API_ENDPOINTS.BOT_STATUS);
        return { ...FALLBACK_BOT_STATUS, ...res.data };
      } catch {
        return FALLBACK_BOT_STATUS;
      }
    },
    retry: false,
    initialData: FALLBACK_BOT_STATUS,
    placeholderData: (prev) => prev ?? FALLBACK_BOT_STATUS,
    staleTime: 0,
    refetchOnMount: 'always',
    refetchOnWindowFocus: true,
    refetchInterval: connectionStatus !== 'connected' ? 10000 : 15000,
  });
};

export const useBotControl = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ action, mode }: { action: 'start' | 'stop'; mode?: BotStatus['mode'] }) => {
      const res = await apiClient.post(`${API_ENDPOINTS.BOT_ACTION}/${action}`, action === 'start' ? { mode } : undefined);
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [QUERY_KEYS.BOT_STATUS] });
      queryClient.invalidateQueries({ queryKey: ['settings-mini'] });
      queryClient.invalidateQueries({ queryKey: ['bot-status-mini'] });
      queryClient.invalidateQueries({ queryKey: [QUERY_KEYS.SETTINGS] });
      queryClient.invalidateQueries({ queryKey: ['trading-schedule'] });
    },
  });
};

export const useSettings = () => {
  return useQuery({
    queryKey: [QUERY_KEYS.SETTINGS],
    queryFn: async () => {
      try {
        const res = await apiClient.get<RiskSettings>(API_ENDPOINTS.SETTINGS);
        return { ...defaultSettings, ...res.data };
      } catch {
        return { ...defaultSettings };
      }
    },
    staleTime: 0,
    retry: false,
    initialData: { ...defaultSettings },
    placeholderData: (prev) => prev ?? { ...defaultSettings },
  });
};

export const useUpdateSettings = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (settings: RiskSettings) => {
      const res = await apiClient.put(API_ENDPOINTS.SETTINGS, settings);
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [QUERY_KEYS.SETTINGS] });
      queryClient.invalidateQueries({ queryKey: [QUERY_KEYS.BOT_STATUS] });
      queryClient.invalidateQueries({ queryKey: ['settings-mini'] });
      queryClient.invalidateQueries({ queryKey: ['bot-status-mini'] });
      queryClient.invalidateQueries({ queryKey: ['trading-schedule'] });
    },
  });
};

export const useTradingSchedule = (enabled = true) => {
  return useQuery({
    queryKey: ['trading-schedule'],
    enabled,
    queryFn: async () => {
      try {
        const res = await apiClient.get<TradingScheduleSnapshot>('/settings/trading-schedule');
        return { ...FALLBACK_TRADING_SCHEDULE, ...res.data };
      } catch {
        return FALLBACK_TRADING_SCHEDULE;
      }
    },
    retry: false,
    initialData: FALLBACK_TRADING_SCHEDULE,
    refetchInterval: 60_000,
    placeholderData: (prev) => prev ?? FALLBACK_TRADING_SCHEDULE,
  });
};

export const useSyncTradingSchedule = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      const res = await apiClient.post<TradingScheduleSnapshot>('/settings/trading-schedule/sync');
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['trading-schedule'] });
      queryClient.invalidateQueries({ queryKey: [QUERY_KEYS.BOT_STATUS] });
    },
  });
};

export { defaultSettings };


export const useAIRuntimeDiagnostics = () => {
  return useQuery({
    queryKey: ['ai-runtime'],
    queryFn: async () => {
      try {
        const res = await apiClient.get<AIRuntimeDiagnostics>('/ai/runtime');
        return res.data;
      } catch {
        return {
          enabled: false,
          participates_in_decision: false,
          ai_mode: 'advisory',
          min_confidence: 0,
          override_policy: 'promote_only',
          primary_provider: 'deepseek',
          fallback_providers: [],
          provider_chain: [],
          provider_availability: {},
          recent_count: 0,
          last_decision: null,
        } as AIRuntimeDiagnostics;
      }
    },
    retry: false,
    refetchInterval: 15000,
    placeholderData: (prev) => prev,
  });
};


export const useRuntimeOverview = (instrumentId?: string | null) => {
  return useQuery({
    queryKey: ['runtime-overview', instrumentId || 'none'],
    queryFn: async () => {
      const suffix = instrumentId ? `?instrument_id=${encodeURIComponent(instrumentId)}` : '';
      try {
        const res = await apiClient.get<RuntimeOverview>(`/settings/runtime-overview${suffix}`);
        return res.data;
      } catch {
        return { effective_plan: null, symbol_profile: null, diagnostics: null, telegram: null } as RuntimeOverview;
      }
    },
    staleTime: 15_000,
    retry: false,
    initialData: { effective_plan: null, symbol_profile: null, diagnostics: null, telegram: null } as RuntimeOverview,
    refetchInterval: 20_000,
    placeholderData: (prev) => prev ?? ({ effective_plan: null, symbol_profile: null, diagnostics: null, telegram: null } as RuntimeOverview),
  });
};

export const useTestTelegram = () => {
  return useMutation({
    mutationFn: async () => {
      const res = await apiClient.post('/settings/telegram/test-send', {});
      if (!res.data?.ok) {
        throw new Error(res.data?.message || 'Не удалось отправить тестовое сообщение в Telegram');
      }
      return res.data;
    },
  });
};
