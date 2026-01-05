export type Side = 'BUY' | 'SELL'; // Contract: BUY/SELL (not LONG/SHORT)
export type SignalStatus = 'pending_review' | 'approved' | 'rejected' | 'executed' | 'expired';
export type BotMode = 'paper' | 'review' | 'live';

export interface Instrument {
    instrument_id: string; // TQBR:SBER
    ticker: string;
    name: string;
    exchange: string;
    currency: string;
    type: string;
    lot: number;
    price_step: number;
    is_tradable: boolean;
}

export interface Candle {
    time: number; // unix ms
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
}

export interface Signal {
    id: string;
    instrument_id: string; // Contract calls it instrument_id
    ts: number;
    side: Side;
    entry: number;
    sl: number;
    tp: number;
    size: number;
    r: number; // API: "r"
    reason: string;
    status: SignalStatus;
    meta?: Record<string, any> & {
        decision?: {
            decision: 'TAKE' | 'SKIP' | 'REJECT';
            score: number;
            reasons: Array<{
                code: string;
                severity: 'info' | 'warn' | 'block';
                msg: string;
            }>;
        }
    };
    comment?: string;
}

export interface Position {
    instrument_id: string;
    side: Side;
    qty: number;
    avg_price: number;
    unrealized_pnl: number;
    realized_pnl: number;
    sl?: number;
    tp?: number;
    opened_ts: number;
}

export interface Order {
    order_id: string;
    instrument_id: string;
    ts: number;
    side: Side;
    type: 'MARKET' | 'LIMIT' | 'STOP';
    price: number;
    qty: number;
    filled_qty: number;
    status: 'NEW' | 'PARTIALLY_FILLED' | 'FILLED' | 'CANCELLED' | 'REJECTED';
}

export interface Trade {
    trade_id: string;
    instrument_id: string;
    ts: number;
    side: Side;
    price: number;
    qty: number;
    order_id: string;
}

export interface DecisionLog {
    id: string;
    ts: number;
    type: string; // signal_created, etc
    message: string;
    payload?: any;
}

export interface BotStatus {
    is_running: boolean;
    mode: BotMode;
    is_paper: boolean;
    active_instrument_id: string;
    connection: {
        market_data: 'connected' | 'disconnected';
        broker: 'connected' | 'disconnected';
    };
    session?: {
        market: string;
        timezone: string;
        trading_day: string;
    };
}

export interface RiskSettings {
    risk_profile: 'conservative' | 'balanced' | 'aggressive';
    risk_per_trade_pct: number;
    daily_loss_limit_pct: number;
    max_concurrent_positions: number;
    max_trades_per_day?: number;
    cooldown_after_losses?: { losses: number, minutes: number };
    rr_target?: number;
    time_stop_bars?: number;
    close_before_session_end_minutes?: number;

    // Strictness / Autotrading
    atr_stop_hard_min?: number;
    atr_stop_hard_max?: number;
    atr_stop_soft_min?: number;
    atr_stop_soft_max?: number;
    rr_min?: number;
    decision_threshold?: number;
    w_regime?: number;
    w_volatility?: number;
    w_momentum?: number;
    w_levels?: number;
    w_costs?: number;
    w_liquidity?: number;
}

// SSE Payload Wrapper
export interface SSEEvent<T = any> {
    type: string;
    ts: number;
    data: T;
}
