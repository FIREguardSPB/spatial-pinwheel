export type Side = 'BUY' | 'SELL';
export type SignalStatus = 'pending_review' | 'approved' | 'rejected' | 'executed' | 'expired';
export type BotMode = 'review' | 'auto_paper' | 'auto_live';

export interface Instrument {
  instrument_id: string;
  ticker: string;
  name: string;
  exchange: string;
  currency?: string;
  type: string;
  lot?: number;
  price_step?: number;
  is_tradable?: boolean;
}

export interface Candle {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface SignalReason {
  code?: string;
  severity: 'info' | 'warn' | 'block';
  msg: string;
}

export interface Signal {
  id: string;
  instrument_id: string;
  ts: number;
  side: Side;
  entry: number;
  sl: number;
  tp: number;
  size: number;
  r: number;
  reason?: string;
  status: SignalStatus;
  meta?: Record<string, any> & {
    strategy?: string;
    final_decision?: 'TAKE' | 'SKIP' | 'REJECT';
    decision?: {
      decision: 'TAKE' | 'SKIP' | 'REJECT';
      score: number;
      reasons: SignalReason[];
    };
    ai_decision?: any;
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
  price?: number;
  qty: number;
  filled_qty: number;
  status: 'NEW' | 'PARTIALLY_FILLED' | 'FILLED' | 'CANCELLED' | 'REJECTED' | string;
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
  type: string;
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
  capabilities?: {
    manual_review: boolean;
    auto_paper: boolean;
    auto_live: boolean;
  };
  warnings?: string[];
}

export interface RiskSettings {
  risk_profile: 'conservative' | 'balanced' | 'aggressive';
  risk_per_trade_pct: number;
  daily_loss_limit_pct: number;
  max_concurrent_positions: number;
  max_trades_per_day: number;
  cooldown_after_losses: { losses: number; minutes: number };
  rr_target: number;
  time_stop_bars: number;
  close_before_session_end_minutes: number;

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
  w_volume?: number;

  strategy_name?: string;

  ai_mode?: 'off' | 'advisory' | 'override' | 'required';
  ai_min_confidence?: number;
  ai_primary_provider?: 'claude' | 'openai' | 'deepseek' | 'ollama' | 'skip' | string;
  ai_fallback_providers?: string;
  ollama_url?: string;

  no_trade_opening_minutes?: number;
  higher_timeframe?: string;
  correlation_threshold?: number;
  max_correlated_positions?: number;

  telegram_bot_token?: string;
  telegram_chat_id?: string;
  notification_events?: string;

  account_balance?: number;
  trade_mode?: BotMode;
  bot_enabled?: boolean;
}

export interface SSEEvent<T = any> {
  type: string;
  ts: number;
  data: T;
}
