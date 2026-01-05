// Application Constants

export const COLORS = {
    // Trading Sides
    LONG: '#3B82F6', // Blue-500
    SHORT: '#F59E0B', // Amber-500

    // Chart Lines
    ENTRY: '#3B82F6',
    TP: '#10B981',    // Green-500
    SL: '#EF4444',    // Red-500

    // Chart Theme
    CHART_BG: '#111827',     // Gray-900
    CHART_TEXT: '#9CA3AF',   // Gray-400
    CHART_GRID: '#1F2937',   // Gray-800
    CANDLE_UP: '#10B981',
    CANDLE_DOWN: '#EF4444',

    // Statuses
    STATUS_APPROVED: 'text-green-500',
    STATUS_REJECTED: 'text-red-500',
    STATUS_EXECUTED: 'text-blue-500',
    STATUS_PENDING: 'text-yellow-500',
} as const;

export const EVENTS = {
    SIGNAL_CREATED: 'signal_created',
    SIGNAL_UPDATED: 'signal_updated',
    POSITIONS_UPDATED: 'positions_updated',
    ORDERS_UPDATED: 'orders_updated',
    TRADE_FILLED: 'trade_filled',
    BOT_STATUS: 'bot_status',
    KLINE: 'kline',
} as const;

export const QUERY_KEYS = {
    SIGNALS: 'signals',
    POSITIONS: 'positions',
    ORDERS: 'orders',
    TRADES: 'trades',
    CANDLES: 'candles',
    BOT_STATUS: 'bot_status',
    SETTINGS: 'settings',
    DECISION_LOG: 'decision_log',
    DAILY_STATS: 'daily_stats',
} as const;

export const API_ENDPOINTS = {
    SIGNALS: '/signals',
    POSITIONS: '/state/positions',
    ORDERS: '/state/orders',
    CANDLES: '/candles',
    BOT_STATUS: '/bot/status',
    BOT_ACTION: '/bot',
    SETTINGS: '/settings', // Changed from RISK_SETTINGS
    DECISION_LOG: '/decision-log',
} as const;
