import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../../services/api';
import type { RiskSettings, BotStatus } from '../../types';
import { QUERY_KEYS, API_ENDPOINTS } from '../../constants';
import { useAppStore } from '../../store';

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
            mode: 'paper',
            is_paper: true,
            active_instrument_id: '',
            connection: { market_data: 'disconnected', broker: 'disconnected' }
        } as BotStatus,
        refetchInterval: connectionStatus !== 'connected' ? 10000 : false
    });
};

export const useBotControl = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (action: 'start' | 'stop') => {
            // POST /bot/start or /bot/stop
            const res = await apiClient.post(API_ENDPOINTS.BOT_ACTION + '/' + action);
            return res.data;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: [QUERY_KEYS.BOT_STATUS] });
        }
    });
};

export const useSettings = () => {
    return useQuery({
        queryKey: [QUERY_KEYS.SETTINGS],
        queryFn: async () => {
            try {
                const res = await apiClient.get<RiskSettings>(API_ENDPOINTS.SETTINGS);
                return res.data;
            } catch {
                // Mock defaults matches new contract structure
                return {
                    risk_profile: 'balanced',
                    risk_per_trade_pct: 1.0,
                    daily_loss_limit_pct: 2.0,
                    max_concurrent_positions: 3,
                    preset: 'Balanced' // Note: Contract uses lowercase 'balanced' in risk_profile, but UI might want Title Case. keeping aligned for now.
                } as unknown as RiskSettings;
            }
        }
    });
};

export const useUpdateSettings = () => {
    const queryClient = useQueryClient();
    return useMutation({
        mutationFn: async (settings: Partial<RiskSettings>) => {
            const res = await apiClient.put(API_ENDPOINTS.SETTINGS, settings); // PUT according to contract
            return res.data;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: [QUERY_KEYS.SETTINGS] });
        }
    });
};
