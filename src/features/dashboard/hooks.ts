import { useQuery } from '@tanstack/react-query';
import { apiClient } from '../../services/api';
import type { Position, Order } from '../../types';
import { QUERY_KEYS, API_ENDPOINTS } from '../../constants';

export const usePositions = () => {
    return useQuery({
        queryKey: [QUERY_KEYS.POSITIONS],
        queryFn: async () => {
            const { isMockMode } = await import('../../store').then(m => m.useAppStore.getState());
            if (isMockMode) {
                return [{
                    instrument_id: 'TQBR:SBER',
                    side: 'BUY',
                    qty: 10,
                    avg_price: 274.50,
                    sl: 270.00,
                    tp: 280.00,
                    opened_ts: Date.now()
                }] as Position[];
            }

            const res = await apiClient.get<{ items: Position[] }>(API_ENDPOINTS.POSITIONS);
            return res.data.items || []; // Contract says { items: [] }
        },
        initialData: [],
    });
};

export const useOrders = () => {
    return useQuery({
        queryKey: [QUERY_KEYS.ORDERS],
        queryFn: async () => {
            const { isMockMode } = await import('../../store').then(m => m.useAppStore.getState());
            if (isMockMode) {
                return [{
                    order_id: 'ord_mock_1',
                    instrument_id: 'TQBR:SBER',
                    side: 'BUY',
                    price: 274.50,
                    qty: 10,
                    filled: 10,
                    status: 'FILLED',
                    ts: Date.now()
                }] as unknown as Order[];
            }

            const res = await apiClient.get<{ items: Order[] }>(API_ENDPOINTS.ORDERS);
            return res.data.items || [];
        },
        initialData: [],
    });
};

export const useDailyStats = () => {
    return useQuery({
        queryKey: [QUERY_KEYS.DAILY_STATS],
        queryFn: async () => {
            return {
                pnl: 125.50,
                tradesCount: 4,
                maxDrawdown: -50.0,
            };
        }
    });
}
