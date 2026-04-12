import { useQuery } from "@tanstack/react-query";
import { apiClient } from "../../services/api";
import { API_ENDPOINTS } from "../../constants";
import type { WorkerStatus } from "../../types";

export function useWorkerStatus() {
  return useQuery({
    queryKey: ["worker_status"],
    queryFn: async () => {
      const { data } = await apiClient.get<WorkerStatus>(API_ENDPOINTS.WORKER_STATUS);
      return data;
    },
    refetchInterval: 5000,
    retry: 1,
  });
}
