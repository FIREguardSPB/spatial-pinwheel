import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../../services/api';
import type { BotStatus, RiskSettings } from '../../types';
import { API_ENDPOINTS, QUERY_KEYS } from '../../constants';
import { useAppStore } from '../../store';

const defaultSettings: RiskSettings = {
  risk_profile: 'balanced',
  risk_per_trade_pct: 1,
  daily_loss_limit_pct: 2,
  max_concurrent_positions: 2,
  max_trades_per_day: 8,
  rr_target: 1.5,
  time_stop_bars: 6,
  close_before_session_end_minutes: 10,
  cooldown_after_losses: { losses: 2, minutes: 60 },
  atr_stop_hard_min: 0.6,
  atr_stop_hard_max: 2.5,
  atr_stop_soft_min: 0.8,
  atr_stop_soft_max: 2,
  rr_min: 1.5,
  decision_threshold: 70,
  w_regime: 20,
  w_volatility: 15,
  w_momentum: 15,
  w_levels: 20,
  w_costs: 15,
  w_liquidity: 5,
  w_volume: 10,
  strategy_name: 'breakout',
  ai_mode: 'off',
  ai_min_confidence: 70,
  ai_primary_provider: 'claude',
  ai_fallback_providers: 'ollama,skip',
  ollama_url: 'http://localhost:11434',
  no_trade_opening_minutes: 10,
  higher_timeframe: '15m',
  correlation_threshold: 0.8,
  max_correlated_positions: 2,
  telegram_bot_token: '',
  telegram_chat_id: '',
  notification_events: 'signal_created,trade_executed,sl_hit,tp_hit',
  account_balance: 100000,
  trade_mode: 'review',
  bot_enabled: false,
};

export const useBotStatus = () => {
  const { connectionStatus } = useAppStore();
  return useQuery({
    queryKey: [QUERY_KEYS.BOT_STATUS],
    queryFn: async () => {
      const res = await apiClient.get<BotStatus>(API_ENDPOINTS.BOT_STATUS);
      return res.data;
    },
    initialData: {
      is_running: false,
      mode: 'review',
      is_paper: true,
      active_instrument_id: '',
      connection: { market_data: 'disconnected', broker: 'disconnected' },
      warnings: [],
      capabilities: { manual_review: true, auto_paper: true, auto_live: true },
    } as BotStatus,
    refetchInterval: connectionStatus !== 'connected' ? 10000 : false,
  });
};

export const useBotControl = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (action: 'start' | 'stop') => {
      const res = await apiClient.post(`${API_ENDPOINTS.BOT_ACTION}/${action}`);
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [QUERY_KEYS.BOT_STATUS] });
      queryClient.invalidateQueries({ queryKey: ['bot-status-mini'] });
      queryClient.invalidateQueries({ queryKey: [QUERY_KEYS.SETTINGS] });
    },
  });
};

export const useSettings = () => {
  return useQuery({
    queryKey: [QUERY_KEYS.SETTINGS],
    queryFn: async () => {
      const res = await apiClient.get<RiskSettings>(API_ENDPOINTS.SETTINGS);
      return { ...defaultSettings, ...res.data };
    },
    initialData: defaultSettings,
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
    },
  });
};
