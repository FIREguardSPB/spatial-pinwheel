import { useEffect, useMemo, useRef, useState } from 'react';
import {
  CandlestickSeries,
  ColorType,
  createChart,
  createSeriesMarkers,
  type CandlestickData,
  type IChartApi,
  type IPriceLine,
  type ISeriesApi,
  type SeriesMarkerPosition,
  type SeriesMarkerShape,
  type Time,
} from 'lightweight-charts';
import { apiClient } from '../../services/api';
import { streamService } from '../../services/stream';
import { useAppStore } from '../../store';
import type { Signal } from '../../types';
import { API_ENDPOINTS, COLORS, EVENTS } from '../../constants';
import { formatTimeMsk } from '../../utils/time';

interface CandleData {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

interface PositionLike {
  instrument_id: string;
  avg_price?: number;
  entry?: number;
  sl?: number;
  tp?: number;
}

type StreamEventHandler = (payload: any) => void;

function normalizeTs(value: unknown): number {
  const raw = Number(value || 0);
  if (!Number.isFinite(raw) || raw <= 0) return 0;
  return raw > 10_000_000_000 ? Math.floor(raw / 1000) : Math.floor(raw);
}

function normalizeCandles(candles: CandleData[]): CandleData[] {
  const map = new Map<number, CandleData>();
  for (const candle of candles || []) {
    const time = normalizeTs(candle?.time);
    if (!time) continue;
    map.set(time, {
      time,
      open: Number(candle.open),
      high: Number(candle.high),
      low: Number(candle.low),
      close: Number(candle.close),
      volume: Number(candle.volume || 0),
    });
  }
  return Array.from(map.values()).sort((a, b) => a.time - b.time);
}

interface ChartContainerProps {
  signals?: Signal[];
  positions?: PositionLike[];
}

export const ChartContainer: React.FC<ChartContainerProps> = ({ signals = [], positions = [] }) => {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const markersPluginRef = useRef<any>(null);
  const activeLinesRef = useRef<IPriceLine[]>([]);
  const fetchSeqRef = useRef(0);
  const fetchAbortRef = useRef<AbortController | null>(null);
  const activeKeyRef = useRef('');
  const lastCandleTimeRef = useRef(0);

  const { selectedInstrument, selectedTimeframe, candles, addCandle, mergeCandles } = useAppStore();
  const historicalCandles = useMemo(
    () => normalizeCandles((candles[`${selectedInstrument}-${selectedTimeframe}`] || []) as CandleData[]),
    [candles, selectedInstrument, selectedTimeframe],
  );

  const [isHistoryLoading, setIsHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState<string | null>(null);

  useEffect(() => {
    lastCandleTimeRef.current = historicalCandles.length ? historicalCandles[historicalCandles.length - 1].time : 0;
  }, [historicalCandles]);

  useEffect(() => {
    if (!chartContainerRef.current) return;

    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: COLORS.CHART_BG },
        textColor: COLORS.CHART_TEXT,
      },
      grid: {
        vertLines: { color: COLORS.CHART_GRID },
        horzLines: { color: COLORS.CHART_GRID },
      },
      localization: {
        locale: 'ru-RU',
        timeFormatter: (time: number) => formatTimeMsk(time, {
          day: '2-digit',
          month: '2-digit',
          hour: '2-digit',
          minute: '2-digit',
        }),
      },
      width: chartContainerRef.current.clientWidth,
      height: chartContainerRef.current.clientHeight,
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
        tickMarkFormatter: (time: number) => formatTimeMsk(time, { hour: '2-digit', minute: '2-digit' }),
      },
    });

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: COLORS.CANDLE_UP,
      downColor: COLORS.CANDLE_DOWN,
      borderVisible: false,
      wickUpColor: COLORS.CANDLE_UP,
      wickDownColor: COLORS.CANDLE_DOWN,
    });

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;
    markersPluginRef.current = createSeriesMarkers(candleSeries);

    const handleResize = () => {
      if (chartContainerRef.current) {
        chart.applyOptions({ width: chartContainerRef.current.clientWidth, height: chartContainerRef.current.clientHeight });
      }
    };

    window.addEventListener('resize', handleResize);
    return () => {
      window.removeEventListener('resize', handleResize);
      fetchAbortRef.current?.abort();
      fetchAbortRef.current = null;
      try {
        chart.remove();
      } catch {
        // noop
      }
      if (chartRef.current === chart) {
        chartRef.current = null;
        candleSeriesRef.current = null;
        markersPluginRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    if (!candleSeriesRef.current) return;
    candleSeriesRef.current.setData(
      historicalCandles.map((c) => ({
        time: c.time as Time,
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
      })) as CandlestickData<Time>[],
    );
    if (historicalCandles.length) {
      chartRef.current?.timeScale().fitContent();
    }
  }, [historicalCandles]);

  useEffect(() => {
    const nextKey = `${selectedInstrument}-${selectedTimeframe}`;
    if (activeKeyRef.current && activeKeyRef.current !== nextKey) {
      fetchAbortRef.current?.abort();
      fetchAbortRef.current = null;
      candleSeriesRef.current?.setData([] as CandlestickData<Time>[]);
      lastCandleTimeRef.current = 0;
      setHistoryError(null);
    }
    activeKeyRef.current = nextKey;
  }, [selectedInstrument, selectedTimeframe]);

  useEffect(() => {
    if (!selectedInstrument) {
      setHistoryError(null);
      setIsHistoryLoading(false);
      return;
    }

    let disposed = false;

    const fetchCandles = async (showLoading = false) => {
      const currentRequestId = ++fetchSeqRef.current;
      if (showLoading) {
        setIsHistoryLoading(true);
      }
      setHistoryError(null);

      try {
        const res = await apiClient.get<CandleData[]>(`${API_ENDPOINTS.CANDLES}/${selectedInstrument}`, {
          params: { tf: selectedTimeframe },
          timeout: 8_000,
        });
        if (disposed || currentRequestId !== fetchSeqRef.current) return;
        mergeCandles(selectedInstrument, selectedTimeframe, normalizeCandles(res.data || []));
      } catch (error: any) {
        if (disposed || currentRequestId !== fetchSeqRef.current) return;
        if (error?.code === 'ERR_CANCELED' || String(error?.name || '') === 'CanceledError') {
          return;
        }
        setHistoryError(error?.message || 'Не удалось загрузить свечи');
      } finally {
        if (!disposed && currentRequestId === fetchSeqRef.current) {
          setIsHistoryLoading(false);
        }
      }
    };

    void fetchCandles(true);

    const handleVisible = () => {
      if (document.visibilityState === 'visible') {
        void fetchCandles(false);
      }
    };
    const handleFocus = () => {
      void fetchCandles(false);
    };

    document.addEventListener('visibilitychange', handleVisible);
    window.addEventListener('focus', handleFocus);
    const intervalId = window.setInterval(() => {
      void fetchCandles(false);
    }, 15_000);

    return () => {
      disposed = true;
      document.removeEventListener('visibilitychange', handleVisible);
      window.removeEventListener('focus', handleFocus);
      window.clearInterval(intervalId);
    };
  }, [mergeCandles, selectedInstrument, selectedTimeframe]);

  useEffect(() => {
    const handleKline: StreamEventHandler = (payload) => {
      const data = payload?.data;
      const candle = data?.candle;
      const instrumentId = data?.instrument_id;
      const tf = data?.tf || '1m';
      if (!candle || !instrumentId) return;

      const normalized = {
        ...candle,
        time: normalizeTs(candle.time),
      };
      if (!normalized.time) return;

      addCandle(instrumentId, tf, normalized);

      if (instrumentId !== selectedInstrument || tf !== selectedTimeframe || !candleSeriesRef.current) {
        return;
      }

      const lastTime = lastCandleTimeRef.current || 0;
      if (normalized.time < lastTime) {
        return;
      }
      lastCandleTimeRef.current = normalized.time;
      candleSeriesRef.current.update({
        time: normalized.time as Time,
        open: Number(normalized.open),
        high: Number(normalized.high),
        low: Number(normalized.low),
        close: Number(normalized.close),
      } as CandlestickData<Time>);
    };

    const unsubscribe = streamService.on(EVENTS.KLINE, handleKline);
    return () => unsubscribe();
  }, [addCandle, selectedInstrument, selectedTimeframe]);

  useEffect(() => {
    if (!candleSeriesRef.current) return;
    const activeSignals = signals.filter((signal) => signal.instrument_id === selectedInstrument);
    const markers = activeSignals.map((sig) => ({
      time: normalizeTs((sig as any).created_ts ?? sig.ts) as Time,
      position: (sig.side === 'BUY' ? 'belowBar' : 'aboveBar') as SeriesMarkerPosition,
      color: sig.side === 'BUY' ? COLORS.LONG : COLORS.SHORT,
      shape: (sig.side === 'BUY' ? 'arrowUp' : 'arrowDown') as SeriesMarkerShape,
      text: sig.side,
    }));
    markersPluginRef.current?.setMarkers(markers as any);
  }, [signals, selectedInstrument]);

  useEffect(() => {
    if (!candleSeriesRef.current) return;
    activeLinesRef.current.forEach((line) => {
      try {
        candleSeriesRef.current?.removePriceLine(line);
      } catch {
        // noop
      }
    });
    activeLinesRef.current = [];

    const position = positions.find((p) => p.instrument_id === selectedInstrument);
    if (!position) return;

    const entryPrice = Number(position.avg_price ?? position.entry ?? 0);
    if (entryPrice > 0) {
      activeLinesRef.current.push(candleSeriesRef.current.createPriceLine({
        price: entryPrice,
        color: COLORS.ENTRY,
        lineWidth: 2,
        lineStyle: 0,
        axisLabelVisible: true,
        title: 'ENTRY',
      }));
    }
    if (position.sl) {
      activeLinesRef.current.push(candleSeriesRef.current.createPriceLine({
        price: Number(position.sl),
        color: COLORS.SL,
        lineWidth: 1,
        lineStyle: 2,
        axisLabelVisible: true,
        title: 'SL',
      }));
    }
    if (position.tp) {
      activeLinesRef.current.push(candleSeriesRef.current.createPriceLine({
        price: Number(position.tp),
        color: COLORS.TP,
        lineWidth: 1,
        lineStyle: 2,
        axisLabelVisible: true,
        title: 'TP',
      }));
    }
  }, [positions, selectedInstrument]);

  const isLoading = isHistoryLoading && historicalCandles.length === 0;

  return (
    <div className="relative h-full w-full" ref={chartContainerRef}>
      {isLoading && <div className="absolute inset-0 flex items-center justify-center text-gray-500">Загрузка свечей…</div>}
      {!isLoading && historyError && historicalCandles.length === 0 && (
        <div className="absolute inset-0 flex items-center justify-center px-6 text-center text-sm text-gray-500">
          {historyError}
        </div>
      )}
    </div>
  );
};
