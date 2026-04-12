import { useQuery } from '@tanstack/react-query';
import { apiClient } from '../../services/api';
import type { DecisionLog } from '../../types';
import { QUERY_KEYS, API_ENDPOINTS } from '../../constants';

export const useDecisionLog = () => {
  return useQuery({
    queryKey: [QUERY_KEYS.DECISION_LOG],
    queryFn: async () => {
      const res = await apiClient.get<{ items: DecisionLog[] }>(API_ENDPOINTS.DECISION_LOG + '?limit=50');
      return res.data.items || [];
    },
    retry: false,
    staleTime: 5_000,
    refetchInterval: 10_000,
  });
};
