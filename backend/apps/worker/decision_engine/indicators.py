from decimal import Decimal
from typing import List, Optional
import math

def to_float(d: Decimal) -> float:
    return float(d)

def calc_ema(values: List[float], period: int) -> Optional[float]:
    """
    Calculate Exponential Moving Average.
    Formula: EMA_today = (Value_today * (k)) + (EMA_yesterday * (1-k))
    where k = 2 / (N + 1)
    """
    if len(values) < period:
        return None
    
    k = 2 / (period + 1)
    
    # Simple MA as initial EMA
    ema = sum(values[:period]) / period
    
    for val in values[period:]:
        ema = (val * k) + (ema * (1 - k))
        
    return round(ema, 6)

def calc_rsi(values: List[float], period: int = 14) -> Optional[float]:
    """
    Calculate RSI (Relative Strength Index).
    """
    if len(values) < period + 1:
        return None

    deltas = [values[i+1] - values[i] for i in range(len(values)-1)]
    
    gains = [d if d > 0 else 0 for d in deltas]
    losses = [-d if d < 0 else 0 for d in deltas]

    # Initial Avg Gain/Loss
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    # Smoothed calc
    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    return round(rsi, 6)

def calc_atr(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> Optional[float]:
    """
    Calculate ATR (Average True Range).
    TR = Max(High-Low, Abs(High-ClosePrev), Abs(Low-ClosePrev))
    """
    if len(closes) < period + 1:
        return None
        
    tr_values = []
    # First TR is High - Low
    tr_values.append(highs[0] - lows[0])
    
    for i in range(1, len(closes)):
        h = highs[i]
        l = lows[i]
        c_prev = closes[i-1]
        
        tr = max(h - l, abs(h - c_prev), abs(l - c_prev))
        tr_values.append(tr)
        
    # Initial ATR (SMA of TR)
    if len(tr_values) < period:
        return None
        
    atr = sum(tr_values[:period]) / period
    
    # Smoothed ATR: (Previous ATR * (n-1) + Current TR) / n
    for i in range(period, len(tr_values)):
        atr = (atr * (period - 1) + tr_values[i]) / period
        
    return round(atr, 6)

def calc_macd(values: List[float], fast_period: int = 12, slow_period: int = 26, signal_period: int = 9) -> Optional[tuple[float, float, float]]:
    """
    Calculate MACD (Line, Signal, Histogram).
    Returns: (macd_line, signal_line, histogram)
    """
    if len(values) < slow_period + signal_period:
        return None
        
    # 1. Calc Fast EMA
    # We need full series for accurate EMA alignment
    ema_fast_series = []
    k_fast = 2 / (fast_period + 1)
    
    # Simple MA init
    ema_fast_curr = sum(values[:fast_period]) / fast_period
    ema_fast_series.append(ema_fast_curr) # This corresponds to index [fast_period-1]
    
    # Calc EMA Fast for rest
    for val in values[fast_period:]:
        ema_fast_curr = (val * k_fast) + (ema_fast_curr * (1 - k_fast))
        ema_fast_series.append(ema_fast_curr)
        
    # 2. Calc Slow EMA
    ema_slow_series = []
    k_slow = 2 / (slow_period + 1)
    
    ema_slow_curr = sum(values[:slow_period]) / slow_period
    ema_slow_series.append(ema_slow_curr) # Index [slow_period-1]
    
    for val in values[slow_period:]:
        ema_slow_curr = (val * k_slow) + (ema_slow_curr * (1 - k_slow))
        ema_slow_series.append(ema_slow_curr)
        
    # 3. MACD Line = Fast - Slow
    # Align series: Slow starts at slow_period-1. Fast needs to be sliced to match.
    # Fast length > Slow length. 
    # Alignment Index: slow_start_idx = slow_period - 1
    # fast_series corresponding start: (slow_period - 1) - (fast_period - 1) offset from beginning of fast_series
    
    # Simpler approach: Calculate full EMAs just for the needed tail? 
    # No, EMA needs history.
    
    # Re-calc properly aligned:
    # We need MACD line values to calculate Signal EMA.
    
    macd_line_values = []
    
    # Calculate alignment offset
    # ema_fast_series[0] is at index fast_period-1 of original values
    # ema_slow_series[0] is at index slow_period-1 of original values
    
    offset = (slow_period - 1) - (fast_period - 1)
    
    # Iterate through slow series and subtract corresponding fast
    for i in range(len(ema_slow_series)):
        fast_idx = i + offset
        if fast_idx < len(ema_fast_series):
            macd_val = ema_fast_series[fast_idx] - ema_slow_series[i]
            macd_line_values.append(macd_val)
            
    # 4. Signal Line = EMA(MACD Line, 9)
    if len(macd_line_values) < signal_period:
        return None
        
    k_signal = 2 / (signal_period + 1)
    signal_curr = sum(macd_line_values[:signal_period]) / signal_period
    
    # Calc rest of signal line
    # We really only care about the latest values
    for val in macd_line_values[signal_period:]:
        signal_curr = (val * k_signal) + (signal_curr * (1 - k_signal))
        
    # Final values
    final_fast = ema_fast_series[-1]
    final_slow = ema_slow_series[-1]
    final_macd_line = final_fast - final_slow
    final_signal_line = signal_curr
    final_hist = final_macd_line - final_signal_line
    
    return (round(final_macd_line, 6), round(final_signal_line, 6), round(final_hist, 6))
