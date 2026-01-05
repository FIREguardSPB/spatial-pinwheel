import { useEffect, useRef } from 'react';
import { createChart, CandlestickSeries, createSeriesMarkers, type IChartApi, type CandlestickData, type Time } from 'lightweight-charts';
import { useQuery } from '@tanstack/react-query';
import { useAppStore } from '../../store';
import { apiClient } from '../../services/api';
import { streamService } from '../../services/stream';
import type { Candle, Signal } from '../../types';
import { COLORS, EVENTS, QUERY_KEYS, API_ENDPOINTS } from '../../constants';
import { generateMockCandles } from '../../utils/mockUtils';

interface ChartContainerProps {
    signals?: Signal[];
}

export const ChartContainer: React.FC<ChartContainerProps> = ({ signals = [] }) => {
    const chartContainerRef = useRef<HTMLDivElement>(null);
    const chartRef = useRef<IChartApi | null>(null);
    const candleSeriesRef = useRef<any>(null);
    const markersPluginRef = useRef<any>(null);
    const activeLinesRef = useRef<any[]>([]);

    const { selectedInstrument, selectedTimeframe, candles, addCandle } = useAppStore();

    // 1. Fetch Historical Data
    const historicalCandles = candles[`${selectedInstrument}-${selectedTimeframe}`] || [];

    // Logic to fetch if empty?
    const { refetch: fetchHistory, isFetching: isHistoryLoading } = useQuery({
        queryKey: ['candles', selectedInstrument, selectedTimeframe],
        queryFn: async () => {
            // UI Demo Mode Bypass (Strict Client-Side)
            if (useAppStore.getState().isUiDemoMode) {
                console.log('[Chart] Generating Mock History (UI Demo Mode)');
                const mocks = generateMockCandles(150); // 150 bars
                // Fix timestamps to standard seconds for library
                return mocks.map(m => ({ ...m, time: m.time / 1000 }));
            }

            // Normal API fetch (even if Backend is MOCK, it serves via API)
            const res = await apiClient.get<any[]>(`${API_ENDPOINTS.CANDLES}/${selectedInstrument}`, {
                params: { tf: selectedTimeframe }
            });
            return res.data || [];
        },
        enabled: false
    });

    const isLoading = isHistoryLoading;

    // 1b. Fetch Positions
    const { data: positions } = useQuery({
        queryKey: [QUERY_KEYS.POSITIONS],
        queryFn: async () => {
            const res = await apiClient.get<{ items: any[] }>(API_ENDPOINTS.POSITIONS);
            return res.data.items || [];
        },
        initialData: []
    });

    // 2. Initialize Chart
    useEffect(() => {
        if (!chartContainerRef.current) return;

        // Cleanup any existing chart (Strict Mode safety)
        chartContainerRef.current.innerHTML = '';

        const chart = createChart(chartContainerRef.current, {
            layout: {
                background: { type: 'solid' as any, color: COLORS.CHART_BG },
                textColor: COLORS.CHART_TEXT,
            },
            grid: {
                vertLines: { color: COLORS.CHART_GRID },
                horzLines: { color: COLORS.CHART_GRID },
            },
            localization: {
                locale: 'ru-RU',
            },
            width: chartContainerRef.current.clientWidth,
            height: chartContainerRef.current.clientHeight,
            timeScale: {
                timeVisible: true,
                secondsVisible: false,
                tickMarkFormatter: (time: number) => {
                    const date = new Date(time * 1000);
                    return date.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
                }
            },
        }) as any;

        const candleSeries = chart.addSeries(CandlestickSeries, {
            upColor: COLORS.CANDLE_UP,
            downColor: COLORS.CANDLE_DOWN,
            borderVisible: false,
            wickUpColor: COLORS.CANDLE_UP,
            wickDownColor: COLORS.CANDLE_DOWN,
        });

        chartRef.current = chart;
        candleSeriesRef.current = candleSeries;

        // Initialize Markers Plugin (v5)
        try {
            markersPluginRef.current = createSeriesMarkers(candleSeries);
        } catch (e) {
            console.error('Failed to create markers plugin', e);
        }

        const handleResize = () => {
            if (chartContainerRef.current) {
                chart.applyOptions({ width: chartContainerRef.current.clientWidth });
            }
        };

        window.addEventListener('resize', handleResize);

        return () => {
            window.removeEventListener('resize', handleResize);
            chart.remove();
        };
    }, []);

    useEffect(() => {
        // If no data in store for this TF, fetch it
        if (historicalCandles.length === 0) {
            fetchHistory().then(res => {
                if (res.data) {
                    res.data.forEach((c: any) => addCandle(selectedInstrument, selectedTimeframe, c));
                }
            });
        }
    }, [selectedInstrument, selectedTimeframe]);


    // 3. Set Data (from Store)
    useEffect(() => {
        if (candleSeriesRef.current) {
            const data = historicalCandles.map(c => ({
                time: c.time as Time, // Backend sends Unix Seconds
                open: c.open,
                high: c.high,
                low: c.low,
                close: c.close,
            }));
            candleSeriesRef.current.setData(data as CandlestickData<Time>[]);
        }
    }, [historicalCandles, selectedTimeframe]); // Re-run when candles change OR TF changes

    // 4. Realtime Updates
    useEffect(() => {
        const handleKline = (payload: any) => {
            // Payload: { type: 'kline', ts: ..., data: { instrument_id, tf, candle: {...} } }
            if (payload?.data?.candle && candleSeriesRef.current) {
                const c = payload.data.candle;
                const tf = payload.data.tf || '1m'; // Default 1m if missing

                // Always update store
                addCandle(payload.data.instrument_id, tf, c);

                // Only update Chart if matches current view
                if (payload.data.instrument_id === selectedInstrument && tf === selectedTimeframe) {
                    // SAFEGUARD: Prevent update() if time is older than last bar (causes crash)
                    // Backend now returns Unix Seconds (Standardized)
                    const newTime = c.time;
                    const lastCandle = historicalCandles[historicalCandles.length - 1];
                    const lastTime = lastCandle ? lastCandle.time : 0;

                    if (newTime >= lastTime) {
                        console.log('[Chart] Updating candle', c);
                        candleSeriesRef.current.update({
                            time: newTime as Time,
                            open: c.open,
                            high: c.high,
                            low: c.low,
                            close: c.close,
                        } as CandlestickData<Time>);
                    }
                }
            }
        };

        const unsubscribe = streamService.on(EVENTS.KLINE, handleKline);
        return () => unsubscribe();
    }, [selectedInstrument, selectedTimeframe]);

    // 5. Signals Overlay
    useEffect(() => {
        if (!candleSeriesRef.current) return;

        // Filter signals using instrument_id
        const activeSignals = signals.filter(s => s.instrument_id === selectedInstrument);

        const markers = activeSignals.map(sig => ({
            time: sig.ts as Time, // API now returns Seconds
            position: (sig.side === 'BUY' ? 'belowBar' : 'aboveBar') as any, // BUY/SELL now
            color: sig.side === 'BUY' ? COLORS.LONG : COLORS.SHORT,
            shape: (sig.side === 'BUY' ? 'arrowUp' : 'arrowDown') as any,
            text: sig.side,
        }));

        if (markersPluginRef.current) {
            markersPluginRef.current.setMarkers(markers);
        }
    }, [signals, selectedInstrument]);

    // 6. Active Position Lines
    useEffect(() => {
        if (!candleSeriesRef.current || !positions) return;

        activeLinesRef.current.forEach(line => {
            try { candleSeriesRef.current.removePriceLine(line); } catch (e) { }
        });
        activeLinesRef.current = [];

        const position = positions.find(p => p.instrument_id === selectedInstrument);

        if (position) {
            // Entry
            activeLinesRef.current.push(candleSeriesRef.current.createPriceLine({
                price: position.avg_price || position.entry, // Contract says avg_price
                color: COLORS.ENTRY,
                lineWidth: 2,
                lineStyle: 0,
                axisLabelVisible: true,
                title: 'ENTRY',
            }));

            if (position.sl) {
                activeLinesRef.current.push(candleSeriesRef.current.createPriceLine({
                    price: position.sl,
                    color: COLORS.SL,
                    lineWidth: 1,
                    lineStyle: 2,
                    axisLabelVisible: true,
                    title: 'SL',
                }));
            }

            if (position.tp) {
                activeLinesRef.current.push(candleSeriesRef.current.createPriceLine({
                    price: position.tp,
                    color: COLORS.TP,
                    lineWidth: 1,
                    lineStyle: 2,
                    axisLabelVisible: true,
                    title: 'TP',
                }));
            }
        }
    }, [positions, selectedInstrument]);

    return (
        <div className="w-full h-full relative" ref={chartContainerRef}>
            {isLoading && <div className="absolute inset-0 flex items-center justify-center text-gray-500">Loading Data...</div>}
        </div>
    );
};
