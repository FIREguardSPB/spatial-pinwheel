import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowDownToLine, ArrowUpFromLine, Bot, Brain, ChevronDown, ChevronUp, Loader2 } from 'lucide-react';
import clsx from 'clsx';
import { isActiveOrder } from './hooks';
import { apiClient } from '../../services/api';
import { useAppStore } from '../../store';
import { API_ENDPOINTS, QUERY_KEYS } from '../../constants';
import { formatDateTimeMsk } from '../../utils/time';

interface OrderRow {
  order_id: string;
  instrument_id: string;
  ts: number;
  side: 'BUY' | 'SELL';
  type: 'MARKET' | 'LIMIT' | 'STOP';
  price?: number;
  qty: number;
  filled_qty: number;
  status: 'NEW' | 'PENDING' | 'PARTIALLY_FILLED' | 'SUBMITTED' | 'WORKING' | 'FILLED' | 'CANCELLED' | 'REJECTED';
  related_signal_id?: string | null;
  ai_influenced?: boolean;
  ai_mode_used?: string | null;
}

const COLLAPSE_STORAGE_KEY = 'spatial.manual-order-panel.collapsed';

export function ManualOrderPanel({ tradeMode }: { tradeMode?: string | null }) {
  const queryClient = useQueryClient();
  const { selectedInstrument, selectedTimeframe, candles } = useAppStore();
  const [side, setSide] = useState<'BUY' | 'SELL'>('BUY');
  const [orderType, setOrderType] = useState<'MARKET' | 'LIMIT'>('MARKET');
  const [qty, setQty] = useState('1');
  const [limitPrice, setLimitPrice] = useState('');
  const [collapsed, setCollapsed] = useState(false);
  const [expandedOrderId, setExpandedOrderId] = useState<string | null>(null);

  useEffect(() => {
    try {
      setCollapsed(window.localStorage.getItem(COLLAPSE_STORAGE_KEY) === '1');
    } catch {
      setCollapsed(false);
    }
  }, []);

  const toggleCollapsed = () => {
    setCollapsed((prev) => {
      const next = !prev;
      try {
        window.localStorage.setItem(COLLAPSE_STORAGE_KEY, next ? '1' : '0');
      } catch {
        // ignore storage failures
      }
      return next;
    });
  };

  const candleKey = `${selectedInstrument}-${selectedTimeframe}`;
  const lastCandle = useMemo(() => {
    const rows = candles[candleKey] || [];
    return rows[rows.length - 1] || null;
  }, [candles, candleKey]);

  const { data: settings } = useQuery({
    queryKey: [QUERY_KEYS.SETTINGS],
    queryFn: async () => { try { return (await apiClient.get('/settings')).data; } catch { return { trade_mode: 'auto_paper' }; } },
    staleTime: 30_000,
    retry: false,
    placeholderData: (prev) => prev,
    enabled: !tradeMode,
  });
  const { data: botStatus } = useQuery({
    queryKey: [QUERY_KEYS.BOT_STATUS],
    queryFn: async () => { try { return (await apiClient.get('/state')).data; } catch { return { mode: 'auto_paper', is_running: false }; } },
    refetchInterval: 10_000,
    retry: false,
    placeholderData: (prev) => prev,
    enabled: !tradeMode,
  });

  const { data: orders = [] } = useQuery({
    queryKey: [QUERY_KEYS.ORDERS],
    queryFn: async () => {
      try {
        const { data } = await apiClient.get<{ items: OrderRow[] }>(API_ENDPOINTS.ORDERS);
        return data.items || [];
      } catch {
        return [];
      }
    },
    refetchInterval: collapsed ? false : 5000,
    enabled: !collapsed,
    placeholderData: (prev) => prev ?? [],
    retry: false,
  });

  const activeOrders = useMemo(() => orders.filter((order) => isActiveOrder(order)), [orders]);
  const recentOrders = useMemo(() => orders.filter((order) => !isActiveOrder(order)).slice(0, 12), [orders]);

  const submitOrder = useMutation({
    mutationFn: async () => {
      const payload: any = {
        instrument_id: selectedInstrument,
        side,
        qty: Number(qty),
        qty_mode: 'lots',
        reference_price: lastCandle?.close,
      };
      if (orderType === 'LIMIT') {
        payload.price = Number(limitPrice || lastCandle?.close || 0);
        return (await apiClient.post('/orders/limit', payload)).data;
      }
      return (await apiClient.post('/orders/market', payload)).data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [QUERY_KEYS.ORDERS] });
      queryClient.invalidateQueries({ queryKey: [QUERY_KEYS.POSITIONS] });
      queryClient.invalidateQueries({ queryKey: [QUERY_KEYS.TRADES] });
    },
  });

  return (
    <div className="space-y-3">
      <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 space-y-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <div className="text-sm font-semibold text-gray-100">Ручной ордер</div>
            <div className="text-xs text-gray-500">{selectedInstrument} · last {lastCandle ? Number(lastCandle.close).toFixed(2) : '—'}</div>
          </div>
          <div className="flex items-center gap-2">
            <div className="text-[11px] px-2 py-1 rounded-full border border-gray-700 text-gray-400">
              {tradeMode || settings?.trade_mode || botStatus?.mode || 'review'}
            </div>
            <button
              type="button"
              onClick={toggleCollapsed}
              className="inline-flex items-center gap-1 rounded-lg border border-gray-700 px-2 py-1 text-[11px] text-gray-400 hover:border-gray-500 hover:text-gray-200"
              title={collapsed ? 'Развернуть панель ручных ордеров' : 'Свернуть панель ручных ордеров'}
            >
              {collapsed ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronUp className="w-3.5 h-3.5" />}
              {collapsed ? 'Развернуть' : 'Свернуть'}
            </button>
          </div>
        </div>

        {!collapsed && (
          <>
            <div className="grid grid-cols-2 gap-2">
              <button onClick={() => setSide('BUY')} className={clsx('px-3 py-2 rounded-lg text-sm font-medium border', side === 'BUY' ? 'bg-emerald-600/20 border-emerald-500/40 text-emerald-300' : 'bg-gray-800 border-gray-700 text-gray-400')}>
                <ArrowUpFromLine className="w-4 h-4 inline mr-2" />Купить
              </button>
              <button onClick={() => setSide('SELL')} className={clsx('px-3 py-2 rounded-lg text-sm font-medium border', side === 'SELL' ? 'bg-red-600/20 border-red-500/40 text-red-300' : 'bg-gray-800 border-gray-700 text-gray-400')}>
                <ArrowDownToLine className="w-4 h-4 inline mr-2" />Продать
              </button>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <button onClick={() => setOrderType('MARKET')} className={clsx('px-3 py-2 rounded-lg text-sm font-medium border', orderType === 'MARKET' ? 'bg-blue-600/20 border-blue-500/40 text-blue-300' : 'bg-gray-800 border-gray-700 text-gray-400')}>
                Market
              </button>
              <button onClick={() => setOrderType('LIMIT')} className={clsx('px-3 py-2 rounded-lg text-sm font-medium border', orderType === 'LIMIT' ? 'bg-blue-600/20 border-blue-500/40 text-blue-300' : 'bg-gray-800 border-gray-700 text-gray-400')}>
                Limit
              </button>
            </div>

            <div className="space-y-2">
              <label className="block text-xs text-gray-500">Количество (лоты)</label>
              <input value={qty} onChange={e => setQty(e.target.value)} className="w-full bg-gray-950 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100" />
            </div>

            {orderType === 'LIMIT' && (
              <div className="space-y-2">
                <label className="block text-xs text-gray-500">Лимитная цена</label>
                <input value={limitPrice} onChange={e => setLimitPrice(e.target.value)} placeholder={String(lastCandle?.close ?? '')} className="w-full bg-gray-950 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100" />
              </div>
            )}

            <div className="text-[11px] text-gray-500 bg-gray-950 border border-gray-800 rounded-lg p-3 leading-relaxed">
              В paper-режиме рыночный ордер исполняется по текущей цене с графика. Если текущая сборка умеет прямой T-Bank execution,
              бэкенд отправит ордер брокеру автоматически.
            </div>

            <button
              onClick={() => submitOrder.mutate(undefined)}
              disabled={submitOrder.isPending || !qty || Number(qty) <= 0 || (orderType === 'LIMIT' && !Number(limitPrice || 0))}
              className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-medium"
            >
              {submitOrder.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
              Отправить ордер
            </button>
          </>
        )}
      </div>

      <div className="bg-gray-900 border border-gray-800 rounded-xl p-4 space-y-4">
        <div className="flex items-center justify-between gap-2">
          <div className="text-sm font-semibold text-gray-100">Ордера</div>
          {collapsed && <div className="text-[11px] text-gray-500">Панель формы свёрнута, список ордеров остаётся доступен</div>}
        </div>

        <div className="rounded-lg border border-gray-800 bg-gray-950/60 p-3">
          <div className="flex items-center justify-between gap-2">
            <div className="text-sm font-medium text-gray-200">Активные ордера</div>
            <div className="text-[11px] text-gray-500">Только NEW / PENDING / PARTIALLY_FILLED</div>
          </div>
          <div className="mt-3 space-y-2 max-h-48 overflow-auto pr-1">
            {activeOrders.length === 0 && <div className="text-xs text-gray-500">Сейчас активных ордеров нет.</div>}
            {activeOrders.map(order => (
              <button
                type="button"
                key={order.order_id}
                onClick={() => setExpandedOrderId((prev) => (prev === order.order_id ? null : order.order_id))}
                className="w-full rounded-lg border border-gray-800 bg-black/20 px-3 py-2 text-left"
              >
                <div className="flex items-center justify-between gap-2">
                  <div>
                    <div className="text-sm font-medium text-gray-200">{order.instrument_id}</div>
                    <div className="text-[11px] text-gray-500">{order.side} · {order.type} · qty {order.qty}</div>
                  </div>
                  <div className="text-right">
                    <div className="text-xs text-yellow-300">{order.status}</div>
                    <div className="text-[11px] text-gray-600">{order.price ? Number(order.price).toFixed(2) : 'market'}</div>
                  </div>
                </div>
                <div className="mt-2 flex items-center gap-2 text-[11px] text-gray-500">
                  {order.ai_influenced ? (
                    <span className="inline-flex items-center gap-1 rounded-full border border-purple-500/30 bg-purple-500/10 px-2 py-0.5 text-purple-300"><Bot className="w-3 h-3" /> {order.ai_mode_used || 'ai'}</span>
                  ) : (
                    <span className="inline-flex items-center gap-1 rounded-full border border-gray-700 bg-gray-800 px-2 py-0.5 text-gray-400"><Brain className="w-3 h-3" /> rules engine</span>
                  )}
                  <span className="text-[11px] text-gray-600">{expandedOrderId === order.order_id ? 'Скрыть детали' : 'Показать детали'}</span>
                </div>
                {expandedOrderId === order.order_id ? (
                  <div className="mt-3 grid grid-cols-2 gap-2 rounded-lg border border-gray-800 bg-black/20 p-3 text-[11px] text-gray-400">
                    <div><span className="text-gray-600">Order ID:</span> <span className="font-mono">{order.order_id}</span></div>
                    <div><span className="text-gray-600">Время:</span> {formatDateTimeMsk(order.ts)}</div>
                    <div><span className="text-gray-600">Filled qty:</span> {order.filled_qty}</div>
                    <div><span className="text-gray-600">Цена:</span> {order.price ? Number(order.price).toFixed(4) : 'market'}</div>
                    <div><span className="text-gray-600">Signal:</span> <span className="font-mono">{order.related_signal_id || '—'}</span></div>
                  </div>
                ) : null}
              </button>
            ))}
          </div>
        </div>

        <div className="rounded-lg border border-gray-800 bg-gray-950/60 p-3">
          <div className="flex items-center justify-between gap-2">
            <div className="text-sm font-medium text-gray-200">Последние завершённые ордера</div>
            <div className="text-[11px] text-gray-500">FILLED / CANCELED / REJECTED</div>
          </div>
          <div className="mt-3 space-y-2 max-h-48 overflow-auto pr-1">
            {recentOrders.length === 0 && <div className="text-xs text-gray-500">История ордеров пока пуста.</div>}
            {recentOrders.map(order => (
              <button
                type="button"
                key={order.order_id}
                onClick={() => setExpandedOrderId((prev) => (prev === order.order_id ? null : order.order_id))}
                className="w-full rounded-lg border border-gray-800 bg-black/20 px-3 py-2 text-left"
              >
                <div className="flex items-center justify-between gap-2">
                  <div>
                    <div className="text-sm font-medium text-gray-200">{order.instrument_id}</div>
                    <div className="text-[11px] text-gray-500">{order.side} · {order.type} · qty {order.qty}</div>
                  </div>
                  <div className="text-right">
                    <div className="text-xs text-gray-400">{order.status}</div>
                    <div className="text-[11px] text-gray-600">{order.price ? Number(order.price).toFixed(2) : 'market'}</div>
                  </div>
                </div>
                <div className="mt-2 flex items-center gap-2 text-[11px] text-gray-500">
                  {order.ai_influenced ? (
                    <span className="inline-flex items-center gap-1 rounded-full border border-purple-500/30 bg-purple-500/10 px-2 py-0.5 text-purple-300"><Bot className="w-3 h-3" /> {order.ai_mode_used || 'ai'}</span>
                  ) : (
                    <span className="inline-flex items-center gap-1 rounded-full border border-gray-700 bg-gray-800 px-2 py-0.5 text-gray-400"><Brain className="w-3 h-3" /> rules engine</span>
                  )}
                  <span className="text-[11px] text-gray-600">{expandedOrderId === order.order_id ? 'Скрыть детали' : 'Показать детали'}</span>
                </div>
                {expandedOrderId === order.order_id ? (
                  <div className="mt-3 grid grid-cols-2 gap-2 rounded-lg border border-gray-800 bg-black/20 p-3 text-[11px] text-gray-400">
                    <div><span className="text-gray-600">Order ID:</span> <span className="font-mono">{order.order_id}</span></div>
                    <div><span className="text-gray-600">Время:</span> {formatDateTimeMsk(order.ts)}</div>
                    <div><span className="text-gray-600">Filled qty:</span> {order.filled_qty}</div>
                    <div><span className="text-gray-600">Цена:</span> {order.price ? Number(order.price).toFixed(4) : 'market'}</div>
                    <div><span className="text-gray-600">Signal:</span> <span className="font-mono">{order.related_signal_id || '—'}</span></div>
                  </div>
                ) : null}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
