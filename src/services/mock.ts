import { EVENTS } from '../constants';
import type { Signal, BotStatus, Candle } from '../types';

type Dispatcher = (type: string, payload: any) => void;

class ScenarioGenerator {
    private basePrice = 270.0;
    private cycleDuration = 15 * 60; // 15 min cycle in seconds

    // Deterministic price based on time (Cycle)
    getPriceAt(timestamp: number): number {
        const t = (timestamp / 1000) % this.cycleDuration;
        const progress = t / this.cycleDuration;

        // Sine wave for cycle
        const sine = Math.sin(progress * Math.PI * 2);

        // Add some "trend" depending on part of cycle
        const trend = (progress < 0.5) ? progress * 10 : (1 - progress) * 10;

        // Noise (pseudo-random based on time to be deterministic-ish but looks random)
        const noise = Math.sin(t * 0.5) * 0.5 + Math.cos(t * 1.3) * 0.3;

        return this.basePrice + (sine * 5) + trend + noise;
    }
}

export class MockStreamService {
    private timer: any;
    private dispatcher: Dispatcher;
    private generator: ScenarioGenerator;
    private currentCandle: Candle | null = null;

    constructor(dispatcher: Dispatcher) {
        this.dispatcher = dispatcher;
        this.generator = new ScenarioGenerator();
    }

    start() {
        console.log('[Mock] Starting Cyclic Demo Mode (15min loop)');

        // 1. Initial State
        this.emitStatus();

        // 2. Start Loop (1s ticks)
        this.timer = setInterval(() => {
            this.tick();
        }, 1000);
    }

    stop() {
        if (this.timer) clearInterval(this.timer);
    }

    private tick() {
        const now = Date.now();
        const price = this.generator.getPriceAt(now);

        // 1. Manage Candle Logic
        const frameSize = 60 * 1000; // 1m candles for MVP
        const currentFrameStart = Math.floor(now / frameSize) * frameSize;

        if (!this.currentCandle || this.currentCandle.time !== currentFrameStart) {
            // New Bar
            this.currentCandle = {
                time: currentFrameStart / 1000, // Unix Seconds for Chart
                open: price,
                high: price,
                low: price,
                close: price,
                volume: 0
            };
        } else {
            // Update Bar
            this.currentCandle.close = price;
            this.currentCandle.high = Math.max(this.currentCandle.high, price);
            this.currentCandle.low = Math.min(this.currentCandle.low, price);
            this.currentCandle.volume += Math.floor(Math.random() * 10);
        }

        // Emit Kline (Live Update)
        this.dispatcher(EVENTS.KLINE, {
            type: EVENTS.KLINE,
            ts: now,
            data: {
                instrument_id: 'TQBR:SBER',
                tf: '1m',
                candle: this.currentCandle
            }
        });

        // 2. Periodic Signals (deterministic based on time)
        const secondOfCycle = Math.floor((now / 1000) % (15 * 60));

        // Emit signal at minute 2 and minute 8 of the cycle
        if (secondOfCycle === 120 || secondOfCycle === 480) {
            this.emitSignal(now);
        }

        // 3. Status Heartbeat (every 5s)
        if (now % 5000 < 1000) {
            this.emitStatus();
        }
    }

    private emitSignal(now: number) {
        const signal: Signal = {
            id: `mock-${now}`,
            instrument_id: 'TQBR:SBER',
            ts: now / 1000,
            side: Math.random() > 0.5 ? 'BUY' : 'SELL',
            entry: this.generator.getPriceAt(now),
            sl: this.generator.getPriceAt(now) * 0.99,
            tp: this.generator.getPriceAt(now) * 1.02,
            size: 10,
            r: 2.0,
            reason: 'Cyclic demo signal',
            status: 'pending_review',
            meta: { strategy: 'cyclic_demo' }
        };

        this.dispatcher(EVENTS.SIGNAL_CREATED, {
            type: EVENTS.SIGNAL_CREATED,
            ts: now,
            data: { signal }
        });
    }

    private emitStatus() {
        const status: BotStatus = {
            is_running: true,
            mode: 'paper',
            is_paper: true,
            active_instrument_id: 'TQBR:SBER',
            connection: { market_data: 'connected', broker: 'connected' }
        };
        this.dispatcher(EVENTS.BOT_STATUS, {
            type: EVENTS.BOT_STATUS,
            ts: Date.now(),
            data: status
        });
    }
}
