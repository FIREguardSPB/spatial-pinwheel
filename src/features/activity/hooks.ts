import { useQuery } from '@tanstack/react-query';
import { apiClient } from '../../services/api';
import type { DecisionLog } from '../../types';
import { QUERY_KEYS, API_ENDPOINTS } from '../../constants';

export const useDecisionLog = () => {
  return useQuery({
    queryKey: [QUERY_KEYS.DECISION_LOG],
    queryFn: async () => {
      // Mock Data 
      const mockLogs: DecisionLog[] = Array.from({ length: 20 }).map((_, i) => ({
        id: 'log-' + i,
        ts: Date.now() - i * 1000 * 60 * 5,
        type: i % 3 === 0 ? 'signal_created' : 'risk_check',
        message: i % 3 === 0 ? 'Signal created for SBER' : 'Risk check passed'
      }));

      try {
        const res = await apiClient.get<{ items: DecisionLog[] }>(API_ENDPOINTS.DECISION_LOG + '?limit=50');
        return res.data.items || [];
      } catch {
        return mockLogs;
      }
    }
  });
};
