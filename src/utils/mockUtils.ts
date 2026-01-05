import type { Candle } from '../types';

export const generateMockCandles = (count: number = 100, startPrice: number = 50000): Candle[] => {
    const candles: Candle[] = [];
    let currentPrice = startPrice;
    const now = Date.now();
    const timeframeMs = 15 * 60 * 1000; // 15m

    for (let i = count; i > 0; i--) {
        const time = now - i * timeframeMs;
        const volatility = currentPrice * 0.005; // 0.5% volatility
        const change = (Math.random() - 0.5) * volatility;

        const open = currentPrice;
        const close = currentPrice + change;
        const high = Math.max(open, close) + Math.random() * volatility * 0.5;
        const low = Math.min(open, close) - Math.random() * volatility * 0.5;

        candles.push({
            time,
            open,
            high,
            low,
            close,
            volume: Math.floor(Math.random() * 100)
        });

        currentPrice = close;
    }
    return candles;
};

import type { Signal } from '../types';

export const generateMockSignals = (count: number = 10): Signal[] => {
    return Array.from({ length: count }).map((_, i) => ({
        id: crypto.randomUUID(),
        instrument_id: 'TQBR:SBER',
        ts: Date.now() - i * 3600000,
        side: Math.random() > 0.5 ? 'BUY' : 'SELL',
        entry: 270.0 + Math.random() * 5,
        sl: 265.0,
        tp: 280.0,
        size: 10,
        r: 2.0,
        reason: 'Mock Strategy Signal',
        status: i === 0 ? 'pending_review' : 'executed',
        meta: { strategy: 'breakout_v1' }
    }));
};
