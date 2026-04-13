export type Side = 'BUY' | 'SELL';
export type SignalStatus = 'pending_review' | 'approved' | 'rejected' | 'executed' | 'expired' | 'execution_error' | 'skipped';
export type BotMode = 'review' | 'auto_paper' | 'auto_live' | 'paper' | 'live';

export interface Instrument {
    instrument_id: string;
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
    time: number;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
}

export interface SignalDecisionReason {
    code: string;
    severity: 'info' | 'warn' | 'block';
    msg: string;
}

export interface EconomicSummary {
    entry_price_rub?: number;
    position_qty?: number;
    position_value_rub?: number;
    sl_distance_rub?: number;
    sl_distance_pct?: number;
    tp_distance_rub?: number;
    tp_distance_pct?: number;
    round_trip_cost_rub?: number;
    round_trip_cost_pct?: number;
    min_required_sl_pct?: number;
    min_required_sl_rub?: number;
    min_required_profit_pct?: number;
    min_required_profit_rub?: number;
    expected_profit_after_costs_rub?: number;
    breakeven_move_pct?: number;
    commission_dominance_ratio?: number | null;
    economic_warning_flags?: string[];
    economic_filter_valid?: boolean;
}

export interface Signal {
    id: string;
    instrument_id: string;
    ts: number;
    created_ts?: number | null;
    updated_ts?: number | null;
    side: Side;
    entry: number;
    sl: number;
    tp: number;
    size: number;
    r: number;
    reason: string;
    status: SignalStatus;
    economic_summary?: EconomicSummary | null;
    strategy_name?: string | null;
    final_decision?: 'TAKE' | 'SKIP' | 'REJECT' | null;
    analysis_timeframe?: string | null;
    execution_timeframe?: string | null;
    confirmation_timeframe?: string | null;
    strategy_source?: 'global' | 'symbol' | 'regime' | 'unknown' | null;
    ai_influence?: 'off' | 'advisory only' | 'affected decision' | 'unknown' | null;
    reject_reason_priority?: 'economics' | 'risk' | 'ai' | 'strategy mismatch' | 'other' | null;
    geometry_optimized?: boolean | null;
    geometry_phase?: string | null;
    geometry_action?: string | null;
    geometry_source?: string | null;
    meta?: Record<string, any> & {
        decision?: {
            decision: 'TAKE' | 'SKIP' | 'REJECT';
            score: number;
            reasons: SignalDecisionReason[];
        };
        final_decision?: 'TAKE' | 'SKIP' | 'REJECT';
        ai_decision?: {
            provider: string;
            decision: 'TAKE' | 'SKIP' | 'REJECT';
            confidence: number;
            reasoning?: string;
            key_factors?: string[];
        };
    };
    comment?: string;
    ai_influenced?: boolean;
    ai_mode_used?: string | null;
    ai_decision_id?: string | null;
}

export interface Position {
    instrument_id: string;
    strategy?: string | null;
    trace_id?: string | null;
    side: Side;
    qty: number;
    opened_qty?: number;
    avg_price: number;
    unrealized_pnl: number;
    realized_pnl: number;
    sl?: number;
    tp?: number;
    opened_signal_id?: string | null;
    opened_order_id?: string | null;
    closed_order_id?: string | null;
    entry_fee_est?: number | null;
    exit_fee_est?: number | null;
    total_fees_est?: number | null;
    opened_ts: number;
    updated_ts?: number | null;
}

export interface Order {
    order_id: string;
    strategy?: string | null;
    trace_id?: string | null;
    instrument_id: string;
    ts: number;
    side: Side;
    type: 'MARKET' | 'LIMIT' | 'STOP';
    price: number;
    qty: number;
    filled_qty: number;
    status: 'NEW' | 'PARTIALLY_FILLED' | 'FILLED' | 'CANCELLED' | 'REJECTED';
    related_signal_id?: string | null;
    ai_influenced?: boolean;
    ai_mode_used?: string | null;
}

export interface Trade {
    trade_id?: string;
    id?: string;
    source?: string | null;
    signal_id?: string | null;
    strategy?: string | null;
    trace_id?: string | null;
    instrument_id: string;
    ts: number;
    opened_ts?: number | null;
    side: Side;
    price?: number;
    entry_price?: number | null;
    close_price?: number | null;
    qty: number;
    order_id?: string;
    opened_order_id?: string | null;
    closed_order_id?: string | null;
    realized_pnl?: number | null;
    fees_est?: number | null;
    close_reason?: string | null;
    duration_sec?: number | null;
    ai_decision?: string | null;
    ai_confidence?: number | null;
    ai_influenced?: boolean | null;
    ai_mode_used?: string | null;
}

export interface DecisionLog {
    id: string;
    ts: number;
    type: string;
    message: string;
    payload?: any;
}

export interface TradingScheduleSnapshot {
    source?: 'broker' | 'static' | string;
    exchange?: string;
    trading_day?: string;
    is_trading_day?: boolean | null;
    is_open?: boolean | null;
    current_session_start?: string | null;
    current_session_end?: string | null;
    next_open?: string | null;
    error?: string | null;
    warning?: string | null;
    source_note?: string | null;
    fetched_at?: string | number | null;
    timezone?: string | null;
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
        source?: string;
        is_open?: boolean | null;
        current_session_start?: string | null;
        current_session_end?: string | null;
        next_open?: string | null;
    };
    warnings?: string[];
    server_time_utc?: string;
    server_time_msk?: string;
    timezone?: string;
    capabilities?: {
        manual_review: boolean;
        auto_paper: boolean;
        auto_live: boolean;
    };
}

export interface RiskSettings {
    id?: number;
    updated_ts?: number;
    is_active?: boolean;
    risk_profile: 'conservative' | 'balanced' | 'aggressive';
    risk_per_trade_pct: number;
    daily_loss_limit_pct: number;
    max_concurrent_positions: number;
    max_trades_per_day?: number;
    fees_bps?: number;
    slippage_bps?: number;
    max_position_notional_pct_balance?: number;
    max_total_exposure_pct_balance?: number;
    signal_reentry_cooldown_sec?: number;
    cooldown_after_losses?: { losses: number; minutes: number };
    rr_target?: number;
    time_stop_bars?: number;
    close_before_session_end_minutes?: number;
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
    ai_primary_provider?: string;
    ai_fallback_providers?: string;
    ollama_url?: string;
    ai_override_policy?: 'promote_only' | 'two_way';
    min_sl_distance_pct?: number;
    min_profit_after_costs_multiplier?: number;
    min_trade_value_rub?: number;
    min_instrument_price_rub?: number;
    min_tick_floor_rub?: number;
    commission_dominance_warn_ratio?: number;
    volatility_sl_floor_multiplier?: number;
    sl_cost_floor_multiplier?: number;
    no_trade_opening_minutes?: number;
    higher_timeframe?: string;
    trading_session?: 'morning' | 'main' | 'main_only' | 'evening' | 'all';
    use_broker_trading_schedule?: boolean;
    trading_schedule_exchange?: string;
    correlation_threshold?: number;
    max_correlated_positions?: number;
    telegram_bot_token?: string;
    telegram_chat_id?: string;
    notification_events?: string;
    account_balance?: number;
    trade_mode?: 'review' | 'auto_paper' | 'auto_live';
    bot_enabled?: boolean;
    strong_signal_score_threshold?: number;
    strong_signal_position_bonus?: number;
    partial_close_threshold?: number;
    partial_close_ratio?: number;
    min_position_age_for_partial_close?: number;
    adaptive_exit_partial_cooldown_sec?: number;
    adaptive_exit_max_partial_closes?: number;
    signal_freshness_enabled?: boolean;
    signal_freshness_grace_bars?: number;
    signal_freshness_penalty_per_bar?: number;
    signal_freshness_max_bars?: number;
    pm_risk_throttle_enabled?: boolean;
    pm_drawdown_soft_limit_pct?: number;
    pm_drawdown_hard_limit_pct?: number;
    pm_loss_streak_soft_limit?: number;
    pm_loss_streak_hard_limit?: number;
    pm_min_risk_multiplier?: number;
    auto_degrade_enabled?: boolean;
    auto_freeze_enabled?: boolean;
    auto_policy_lookback_days?: number;
    auto_degrade_max_execution_errors?: number;
    auto_freeze_max_execution_errors?: number;
    auto_degrade_min_profit_factor?: number;
    auto_freeze_min_profit_factor?: number;
    auto_degrade_min_expectancy?: number;
    auto_freeze_min_expectancy?: number;
    auto_degrade_drawdown_pct?: number;
    auto_freeze_drawdown_pct?: number;
    auto_degrade_risk_multiplier?: number;
    auto_degrade_threshold_penalty?: number;
    auto_freeze_new_entries?: boolean;
    performance_governor_enabled?: boolean;
    performance_governor_lookback_days?: number;
    performance_governor_min_closed_trades?: number;
    performance_governor_strict_whitelist?: boolean;
    performance_governor_auto_suppress?: boolean;
    performance_governor_max_execution_error_rate?: number;
    performance_governor_min_take_fill_rate?: number;
    performance_governor_pass_risk_multiplier?: number;
    performance_governor_fail_risk_multiplier?: number;
    performance_governor_threshold_bonus?: number;
    performance_governor_threshold_penalty?: number;
    performance_governor_execution_priority_boost?: number;
    performance_governor_execution_priority_penalty?: number;
    performance_governor_allocator_boost?: number;
    performance_governor_allocator_penalty?: number;
    ml_enabled?: boolean;
    ml_retrain_enabled?: boolean;
    ml_lookback_days?: number;
    ml_min_training_samples?: number;
    ml_retrain_interval_hours?: number;
    ml_retrain_hour_msk?: number;
    ml_take_probability_threshold?: number;
    ml_fill_probability_threshold?: number;
    ml_risk_boost_threshold?: number;
    ml_risk_cut_threshold?: number;
    ml_pass_risk_multiplier?: number;
    ml_fail_risk_multiplier?: number;
    ml_threshold_bonus?: number;
    ml_threshold_penalty?: number;
    ml_execution_priority_boost?: number;
    ml_execution_priority_penalty?: number;
    ml_allocator_boost?: number;
    ml_allocator_penalty?: number;
    ml_allow_take_veto?: boolean;
    worker_bootstrap_limit?: number;
    capital_allocator_min_edge_improvement?: number;
    capital_allocator_max_position_concentration_pct?: number;
    capital_allocator_age_decay_per_hour?: number;
    portfolio_optimizer_enabled?: boolean;
    portfolio_optimizer_lookback_bars?: number;
    portfolio_optimizer_min_history_bars?: number;
    portfolio_optimizer_max_pair_corr?: number;
    portfolio_optimizer_regime_risk_off_multiplier?: number;
    portfolio_optimizer_target_weight_buffer_pct?: number;
    symbol_recalibration_enabled?: boolean;
    symbol_recalibration_hour_msk?: number;
    symbol_recalibration_train_limit?: number;
    symbol_recalibration_lookback_days?: number;
}

export interface SettingsPreset {
    id: string;
    name: string;
    description?: string;
    settings_json: Record<string, any>;
    created_at: number;
    updated_at: number;
    is_system: boolean;
}

export interface SettingsPresetListResponse {
    items: SettingsPreset[];
}

export interface SettingsPresetMutationResponse {
    preset: SettingsPreset;
    created?: boolean | null;
}

export interface SettingsPresetApplyResponse {
    ok: boolean;
    preset: SettingsPreset;
    applied: {
        changed_keys: string[];
        diff_summary: string[];
        changed_count?: number;
        watchlist?: { added: string[]; removed: string[]; kept: string[] };
        applied_settings_updated_ts?: number;
    };
}


export interface BusinessMetrics {
    total_pnl: number;
    daily_pnl: number;
    win_rate: number;
    profit_factor: number | null;
    signals_count: number;
    takes_count: number;
    trades_count: number;
    raw_fills_count: number;
    conversion_rate: number;
    avg_holding_time_sec: number;
    avg_profit_per_trade: number;
    avg_loss_per_trade: number;
    expectancy_per_trade?: number;
    max_drawdown_pct?: number;
    wins_count?: number;
    losses_count?: number;
    best_trade: number;
    worst_trade: number;
    execution_error_count?: number;
    adaptive_partial_closes_count?: number;
    capital_reallocations_count?: number;
    avg_reallocation_ratio?: number;
    avg_mfe_pct?: number;
    avg_mae_pct?: number;
    avg_realized_to_mfe_capture_ratio?: number;
    portfolio_optimizer_adjustments_count?: number;
    avg_optimizer_risk_multiplier?: number;
    freshness_penalties_count?: number;
    stale_signal_blocks_count?: number;
    portfolio_concentration_pct?: number;
    recalibration_runs_count?: number;
    recalibration_symbols_trained?: number;
    last_recalibration_ts?: number | null;
    exit_reason_breakdown?: Record<string, number>;
    avg_portfolio_risk_multiplier?: number;
    throttle_hits_count?: number;
    strategy_breakdown: Array<{ strategy: string; trades: number; pnl: number }>;
    instrument_breakdown: Array<{ instrument_id: string; trades: number; pnl: number }>;
    pnl_curve: Array<{ ts: number; pnl: number }>;
    equity_curve: Array<{ ts: number; equity: number }>;
}



export interface TradingQualityAudit {
    period_days: number;
    summary: {
        status: 'pass' | 'partial' | 'fail' | 'insufficient_data' | string;
        signals_count: number;
        takes_count: number;
        approved_count: number;
        executed_signals_count: number;
        closed_signals_count: number;
        execution_error_count: number;
        risk_rejected_count: number;
        pending_count: number;
        filtered_out_count: number;
        conversion_rate: number;
        take_fill_rate: number;
        close_rate: number;
        orphan_fills_count: number;
    };
    funnel: Array<{ stage: string; count: number; share_pct: number }>;
    allocator: {
        status: 'pass' | 'partial' | 'fail' | 'insufficient_data' | string;
        capital_reallocations_count: number;
        avg_reallocation_ratio: number;
        avg_edge_improvement: number;
        avg_portfolio_pressure: number;
        avg_allocator_score: number;
        reason_breakdown: Record<string, number>;
        recent_rows: Array<Record<string, any>>;
    };
    exit_capture: {
        status: 'pass' | 'partial' | 'fail' | 'insufficient_data' | string;
        closed_trades_count: number;
        excellent_or_good_share_pct: number;
        weak_or_poor_share_pct: number;
        avg_tp_capture_ratio: number;
        avg_mfe_capture_ratio: number;
        avg_missed_tp_value_rub: number;
        avg_missed_mfe_value_rub: number;
        time_decay_share_pct: number;
        late_failure_share_pct: number;
        recent_rows: Array<Record<string, any>>;
    };
    conversion_audit: {
        status: 'pass' | 'partial' | 'fail' | 'insufficient_data' | string;
        bottlenecks: Array<{ bucket: string; count: number }>;
        recent_signal_journeys: Array<{
            signal_id: string;
            instrument_id: string;
            strategy: string;
            status: string;
            final_decision: string;
            stage: string;
            created_ts: number;
            reason?: string | null;
            fills_count: number;
            closed_count: number;
            realized_pnl: number;
            trace_id?: string | null;
        }>;
        strategy_rows: Array<Record<string, any>>;
        instrument_rows: Array<Record<string, any>>;
        orphan_fills: Array<Record<string, any>>;
    };
    recommendations: string[];
}

export interface PerformanceLayerAudit {
    period_days: number;
    post_trade_attribution: {
        status: 'pass' | 'partial' | 'fail' | 'insufficient_data' | string;
        closed_trades_count: number;
        strategy_rows: Array<Record<string, any>>;
        regime_rows: Array<Record<string, any>>;
        strategy_regime_rows: Array<Record<string, any>>;
        session_rows: Array<Record<string, any>>;
        best_slice?: Record<string, any> | null;
        worst_slice?: Record<string, any> | null;
    };
    walk_forward: {
        status: 'pass' | 'partial' | 'fail' | 'insufficient_data' | string;
        timeframe: string;
        history_limit: number;
        folds: number;
        active_strategies: string[];
        candidate_instruments: string[];
        considered_instruments_count: number;
        scored_instruments_count: number;
        pass_rate_pct: number;
        avg_oos_score: number;
        avg_oos_profit_factor: number;
        instrument_rows: Array<Record<string, any>>;
        strategy_rows: Array<Record<string, any>>;
    };
    regime_sliced_audit: {
        status: 'pass' | 'partial' | 'fail' | 'insufficient_data' | string;
        regime_rows: Array<Record<string, any>>;
        session_rows: Array<Record<string, any>>;
        dominant_draggers: Array<Record<string, any>>;
        dominant_winners: Array<Record<string, any>>;
    };
    recommendations: string[];
}


export interface PerformanceGovernorAudit {
    period_days: number;
    summary: {
        status: 'pass' | 'partial' | 'fail' | 'insufficient_data' | string;
        signals_count: number;
        closed_trades_count: number;
        validated_slices_count: number;
        suppressed_slices_count: number;
    };
    settings: {
        enabled: boolean;
        lookback_days: number;
        min_closed_trades: number;
        strict_whitelist: boolean;
        auto_suppress: boolean;
    };
    slice_rows: Array<Record<string, any>>;
    strategy_rows: Array<Record<string, any>>;
    regime_rows: Array<Record<string, any>>;
    whitelist_by_regime: Record<string, string[]>;
    suppressed_slices: Array<Record<string, any>>;
    boosted_slices: Array<Record<string, any>>;
    recommendations: string[];
}

export interface LiveValidationChecklistItem {
    key: string;
    label: string;
    status: 'pass' | 'partial' | 'fail' | 'insufficient_data';
    value: any;
    thresholds: Record<string, any>;
    details?: string;
}

export interface LiveValidationSnapshotItem {
    id: string;
    ts: number;
    source: string;
    days: number;
    weeks: number;
    summary: {
        overall_status: 'pass' | 'partial' | 'fail' | 'insufficient_data';
        passed_items: number;
        partial_items: number;
        failed_items: number;
        insufficient_data_items: number;
        trades_count: number;
        signals_count: number;
        conversion_rate: number;
        period_total_pnl: number;
    };
    failed_keys: string[];
    partial_keys: string[];
    recommendations: string[];
}

export interface LiveTraderValidation {
    summary: {
        days: number;
        weeks: number;
        overall_status: 'pass' | 'partial' | 'fail' | 'insufficient_data';
        passed_items: number;
        partial_items: number;
        failed_items: number;
        insufficient_data_items: number;
        trades_count: number;
        signals_count: number;
        conversion_rate: number;
        period_total_pnl: number;
    };
    checklist: LiveValidationChecklistItem[];
    weekly_rows: Array<{
        week: string;
        pnl: number;
        trades: number;
        wins: number;
        losses: number;
        win_rate: number;
        profit_factor: number | null;
        expectancy_per_trade: number;
    }>;
    weekly_stability: {
        status: 'pass' | 'partial' | 'fail' | 'insufficient_data';
        target_green_weeks: number;
        considered_weeks: number;
        green_weeks: number;
        red_weeks: number;
    };
    regime_rows: Array<{
        regime: string;
        trades: number;
        pnl: number;
        win_rate: number;
        profit_factor: number | null;
        expectancy_per_trade: number;
    }>;
    strategy_rows: Array<{
        strategy: string;
        trades: number;
        pnl: number;
        win_rate: number;
        profit_factor: number | null;
        expectancy_per_trade: number;
    }>;
    paper_audit: {
        summary: Record<string, any>;
        exit_diagnostics: Record<string, any>;
        recommendations: string[];
    };
    metrics_snapshot: {
        profit_factor?: number | null;
        expectancy_per_trade?: number;
        expectancy_r?: number | null;
        max_drawdown_pct?: number;
        win_rate?: number;
        avg_realized_to_mfe_capture_ratio?: number;
        execution_error_count?: number;
        portfolio_concentration_pct?: number;
    };
    recommendations: string[];
}

export interface TBankStats {
    started_ts?: number;
    requests_total: number;
    success_total: number;
    error_total: number;
    requests_by_method: Record<string, number>;
    success_by_method?: Record<string, number>;
    error_by_method?: Record<string, number>;
    recent_requests_60s?: number;
    requests_per_sec?: number;
    last_rate_limit_remaining?: string | null;
    last_rate_limit_reset?: string | null;
    recommendation?: string;
    last_error?: { method?: string; status_code?: number; detail?: string; ts?: number } | null;
}

export interface SSEEvent<T = any> {
    type: string;
    ts: number;
    data: T;
}


export interface AIRuntimeDiagnostics {
    enabled: boolean;
    participates_in_decision?: boolean;
    ai_mode: string;
    min_confidence: number;
    override_policy: string;
    primary_provider: string;
    fallback_providers: string[];
    provider_chain: string[];
    provider_availability: Record<string, boolean>;
    ollama_url?: string;
    recent_count: number;
    last_decision?: {
        ts: number;
        instrument_id: string;
        provider: string;
        ai_decision: string;
        ai_confidence: number;
        final_decision: string;
        actual_outcome: string;
        latency_ms: number;
    } | null;
}


export interface AutoPolicyRuntimeStatus {
    enabled: boolean;
    freeze_enabled: boolean;
    state: string;
    reasons: string[];
    lookback_days: number;
    risk_multiplier_override: number;
    threshold_penalty: number;
    block_new_entries: boolean;
    metrics?: Record<string, any>;
    thresholds?: Record<string, any>;
}

export interface TelegramRuntimeStatus {
    configured: boolean;
    bot_token_present: boolean;
    chat_id_present: boolean;
    enabled_events: string[];
    quiet_hours: number[];
    transport: string;
}

export interface RuntimeOverview {
    instrument_id?: string | null;
    hierarchy: Array<{
        title: string;
        scope: string;
        recommended_to_change: boolean | string;
        description: string;
        fields: string[];
    }>;
    safe_manual_fields: string[];
    caution_fields: string[];
    auto_owned_fields: string[];
    global_defaults: Record<string, Record<string, any>>;
    symbol_profile?: Record<string, any> | null;
    effective_plan?: Record<string, any> | null;
    diagnostics?: Record<string, any> | null;
    event_regime?: Record<string, any> | null;
    source_notes?: string[];
    worker?: Record<string, any> | null;
    ai_runtime?: AIRuntimeDiagnostics | null;
    telegram?: TelegramRuntimeStatus | null;
    auto_policy?: AutoPolicyRuntimeStatus | null;
}
export interface WorkerStatus {
    ok: boolean;
    phase: string;
    message?: string;
    current_instrument_count?: number;
    tickers?: string[];
    unresolved_instruments?: string[];
    updated_ts?: number | null;
    last_error?: {
        where: string;
        message: string;
        ts: number;
    } | null;
    last_take_signal_ts?: number | null;
    last_take_instrument?: string | null;
    last_poll_stats?: Record<string, any>;
    last_analysis_stats?: Record<string, any>;
    tbank_stats?: TBankStats | null;
}


export interface PaperAudit {
    period_days: number;
    summary: {
        trading_days: number;
        green_days: number;
        red_days: number;
        flat_days: number;
        avg_day_pnl: number;
        best_day_pnl: number;
        worst_day_pnl: number;
        throttle_hits_count: number;
        avg_portfolio_risk_multiplier: number;
        freshness_blocks_count: number;
        capital_reallocations_count: number;
        portfolio_optimizer_adjustments_count?: number;
        recalibration_runs_count: number;
    };
    exit_diagnostics: {
        avg_hold_utilization_pct: number;
        avg_tp_capture_ratio: number;
        avg_realized_rr_multiple: number;
        avg_adverse_slippage_bps: number;
        avg_mfe_pct?: number;
        avg_mae_pct?: number;
        avg_mfe_capture_ratio?: number;
        avg_mae_recovery_ratio?: number;
        time_decay_exit_share_pct: number;
        late_failure_share_pct: number;
        fast_realization_share_pct: number;
        close_quality_breakdown: Record<string, number>;
        exit_reason_breakdown: Record<string, number>;
        edge_decay_breakdown: Record<string, number>;
    };
    daily_rows: Array<{
        date: string; pnl: number; trades: number; wins: number; losses: number; tp: number; sl: number;
        time_decay: number; late_failure: number; execution_errors: number; win_rate: number; profit_factor: number | null;
    }>;
    recommendations: string[];
}


export interface MLTrainingRunItem {
    id: string;
    ts: number;
    target: string;
    status: string;
    source: string;
    lookback_days: number;
    train_rows: number;
    validation_rows: number;
    artifact_path?: string | null;
    model_type: string;
    metrics?: Record<string, any>;
    params?: Record<string, any>;
    notes?: string | null;
    is_active?: boolean;
}

export interface MLRuntimeStatus {
    enabled: boolean;
    retrain_enabled: boolean;
    lookback_days: number;
    min_training_samples: number;
    retrain_interval_hours: number;
    retrain_hour_msk: number;
    allow_veto: boolean;
    latest_training_ts?: number | null;
    active_models: {
        trade_outcome?: MLTrainingRunItem | null;
        take_fill?: MLTrainingRunItem | null;
    };
    recent_runs: MLTrainingRunItem[];
}
