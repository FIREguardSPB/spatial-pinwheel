import { useQuery } from '@tanstack/react-query';
import { apiClient } from '../../services/api';
import type { Position, Order } from '../../types';
import { QUERY_KEYS, API_ENDPOINTS } from '../../constants';

const ACTIVE_ORDER_STATUSES = new Set(['NEW', 'PENDING', 'PARTIALLY_FILLED', 'SUBMITTED', 'WORKING']);

export const isActiveOrder = (order: { status?: string | null } | Pick<Order, 'status'> | null | undefined) => {
    const status = String(order?.status || '').toUpperCase();
    return ACTIVE_ORDER_STATUSES.has(status);
};


export const usePositions = () => {
    return useQuery({
        queryKey: [QUERY_KEYS.POSITIONS],
        queryFn: async () => {
            try {
                const res = await apiClient.get<{ items: Position[] }>(API_ENDPOINTS.POSITIONS);
                return res.data.items || [];
            } catch {
                return [];
            }
        },
        initialData: [],
        placeholderData: (prev) => prev ?? [],
        retry: false,
    });
};

export const useOrders = () => {
    return useQuery({
        queryKey: [QUERY_KEYS.ORDERS],
        queryFn: async () => {
            try {
                const res = await apiClient.get<{ items: Order[] }>(API_ENDPOINTS.ORDERS);
                return res.data.items || [];
            } catch {
                return [];
            }
        },
        initialData: [],
        placeholderData: (prev) => prev ?? [],
        retry: false,
    });
};

export const useActiveOrders = () => {
    return useQuery({
        queryKey: [QUERY_KEYS.ORDERS, 'active'],
        queryFn: async () => {
            try {
                const res = await apiClient.get<{ items: Order[] }>(`${API_ENDPOINTS.ORDERS}?active_only=true`);
                return (res.data.items || []).filter(isActiveOrder);
            } catch {
                return [];
            }
        },
        initialData: [],
        placeholderData: (prev) => prev ?? [],
        retry: false,
    });
};

export const useDailyStats = () => {
    return useQuery({
        queryKey: [QUERY_KEYS.DAILY_STATS],
        queryFn: async () => {
            try {
                const { data } = await apiClient.get('/account/daily-stats');
                return { pnl: data.day_pnl ?? 0, tradesCount: data.trades_count ?? 0, maxDrawdown: 0 };
            } catch {
                return { pnl: 0, tradesCount: 0, maxDrawdown: 0 };
            }
        },
        refetchInterval: 30_000,
        placeholderData: (prev) => prev ?? { pnl: 0, tradesCount: 0, maxDrawdown: 0 },
    });
}
