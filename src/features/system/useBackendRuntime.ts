import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiClient } from '../../services/api';
import { useAppStore } from '../../store';

type HealthResponse = {
  status?: string;
  server_time_utc?: string;
  server_time_msk?: string;
  components?: {
    broker?: {
      provider?: string;
      sandbox?: boolean;
      status?: string;
      execution_mode?: string;
    };
  };
};

function deriveSourceLabel(health?: HealthResponse, isUiDemoMode?: boolean): { label: string; isMockMode: boolean; provider: string; sandbox: boolean } {
  if (isUiDemoMode) {
    return { label: 'UI DEMO', isMockMode: true, provider: 'mock', sandbox: false };
  }

  const broker = health?.components?.broker;
  const provider = (broker?.provider ?? 'unknown').toLowerCase();
  const sandbox = Boolean(broker?.sandbox);

  if (provider === 'tbank') return { label: sandbox ? 'TBANK SANDBOX' : 'TBANK LIVE', isMockMode: false, provider, sandbox };
  if (provider === 'paper') return { label: 'PAPER', isMockMode: false, provider, sandbox };
  return { label: 'API', isMockMode: false, provider, sandbox };
}

export function useBackendRuntime() {
  const isUiDemoMode = useAppStore((s) => s.isUiDemoMode);
  const setBackendSource = useAppStore((s) => s.setBackendSource);
  const setBackendHealth = useAppStore((s) => s.setBackendHealth);

  const query = useQuery({
    queryKey: ['backend-runtime-health'],
    queryFn: async () => {
      const { data } = await apiClient.get<HealthResponse>('/health');
      return data;
    },
    retry: false,
    refetchInterval: 30_000,
    staleTime: 15_000,
    enabled: !isUiDemoMode,
  });

  useEffect(() => {
    const runtime = deriveSourceLabel(query.data, isUiDemoMode);
    if (isUiDemoMode) {
      setBackendHealth('ok', null);
    } else if (query.isError) {
      setBackendHealth('degraded', 'Health endpoint недоступен, UI работает в degraded mode');
    } else if (query.data?.status === 'degraded') {
      setBackendHealth('degraded', 'Backend reported degraded status');
    } else if (query.data) {
      setBackendHealth('ok', null);
    }

    setBackendSource({
      sourceLabel: runtime.label,
      brokerProvider: runtime.provider,
      brokerSandbox: runtime.sandbox,
      isMockMode: runtime.isMockMode,
    });
  }, [query.data, query.isError, isUiDemoMode, setBackendSource, setBackendHealth]);

  return query;
}
