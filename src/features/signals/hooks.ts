import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../../services/api';
import type { Signal, SignalStatus } from '../../types';
import { QUERY_KEYS, API_ENDPOINTS } from '../../constants';
import { useAppStore } from '../../store';

export const useSignals = (status?: SignalStatus) => {
  const { connectionStatus } = useAppStore();
  return useQuery({
    queryKey: [QUERY_KEYS.SIGNALS, status],
    queryFn: async () => {
      const { isMockMode } = useAppStore.getState();

      if (isMockMode) {
        console.log('[Mock] Generating mock signals');
        const { generateMockSignals } = await import('../../utils/mockUtils');
        return generateMockSignals(5);
      }

      // Real Mode - Fail if API is down
      const params = status ? { status } : {};
      const res = await apiClient.get<{ items: Signal[] }>(API_ENDPOINTS.SIGNALS, { params });
      return res.data.items || [];
    },
    staleTime: 60 * 1000,
    refetchInterval: connectionStatus !== 'connected' ? 10000 : false
  });
};

export const useSignalAction = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ id, action, comment }: { id: string, action: 'approve' | 'reject', comment?: string }) => {
      const { isMockMode } = useAppStore.getState();

      if (isMockMode) {
        console.log(`[Mock] Action ${action} on signal ${id}`);
        await new Promise(r => setTimeout(r, 500)); // Simulate latency
        return { status: 'ok', mocked: true };
      }

      const res = await apiClient.post(API_ENDPOINTS.SIGNALS + '/' + id + '/' + action, { comment });
      return res.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [QUERY_KEYS.SIGNALS] });
      queryClient.invalidateQueries({ queryKey: [QUERY_KEYS.POSITIONS] });
      queryClient.invalidateQueries({ queryKey: [QUERY_KEYS.ORDERS] });
    }
  });
};
