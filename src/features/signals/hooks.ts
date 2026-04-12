import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiClient } from '../../services/api';
import type { Signal, SignalStatus } from '../../types';
import { QUERY_KEYS, API_ENDPOINTS } from '../../constants';
import { useAppStore } from '../../store';

type UseSignalsOptions = {
  enabled?: boolean;
  limit?: number;
  refetchInterval?: number | false;
};

export const useSignals = (status?: SignalStatus, options: UseSignalsOptions = {}) => {
  const { connectionStatus } = useAppStore();
  const { enabled = true, limit = 20, refetchInterval } = options;
  return useQuery({
    queryKey: [QUERY_KEYS.SIGNALS, status, limit],
    queryFn: async () => {
      const params = status ? { status, limit } : { limit };
      try {
        const res = await apiClient.get<{ items: Signal[] }>(API_ENDPOINTS.SIGNALS, { params });
        return res.data.items || [];
      } catch {
        return [];
      }
    },
    enabled,
    staleTime: 15 * 1000,
    placeholderData: (prev) => prev,
    refetchInterval: refetchInterval ?? (connectionStatus !== 'connected' ? 15000 : 30000),
    retry: 1,
  });
};

export const useSignalAction = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ id, action, comment }: { id: string, action: 'approve' | 'reject', comment?: string }) => {
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
