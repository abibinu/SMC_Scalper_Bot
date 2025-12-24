import pandas as pd
import MetaTrader5 as mt5

def get_ohlc_data(symbol, timeframe, count=100):
    """Fetches OHLC data from MT5 and returns it as a Pandas DataFrame."""
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    return df

def detect_mss_and_sl(df):
    """
    Detects a Market Structure Shift (MSS) and returns the shift type and the stop loss level.
    """
    # Identify swing points (a simple n=1 implementation)
    df['swing_high'] = (df['high'] > df['high'].shift(1)) & (df['high'] > df['high'].shift(-1))
    df['swing_low'] = (df['low'] < df['low'].shift(1)) & (df['low'] < df['low'].shift(-1))

    # We look at the most recently completed candle, which is at index -2
    last_candle = df.iloc[-2]
    
    # Find the most recent swing points prior to the last candle
    swing_highs = df[df['swing_high']].iloc[:-2]
    swing_lows = df[df['swing_low']].iloc[:-2]

    if swing_highs.empty or swing_lows.empty:
        return None, None

    last_swing_high = swing_highs.iloc[-1]
    last_swing_low = swing_lows.iloc[-1]

    # Check for MSS
    bullish_mss = last_candle['close'] > last_swing_high['high']
    bearish_mss = last_candle['close'] < last_swing_low['low']

    if bullish_mss:
        # Stop loss is placed at the low of the candle that caused the shift
        return "bullish", last_candle['low']
    elif bearish_mss:
        # Stop loss is placed at the high of the candle that caused the shift
        return "bearish", last_candle['high']
    
    return None, None

def find_fvg(df):
    """
    Identifies the most recent Fair Value Gap (FVG) and returns its high and low.
    Looks at the last 3 completed candles.
    """
    # We look at the pattern in the 3 most recently completed candles (indices -4, -3, -2)
    candle_1 = df.iloc[-4]
    candle_2 = df.iloc[-3]
    candle_3 = df.iloc[-2]

    # Bullish FVG: The low of candle 3 is higher than the high of candle 1
    if candle_3['low'] > candle_1['high']:
        return {"high": candle_3['low'], "low": candle_1['high'], "type": "bullish"}

    # Bearish FVG: The high of candle 3 is lower than the low of candle 1
    if candle_3['high'] < candle_1['low']:
        return {"high": candle_1['low'], "low": candle_3['high'], "type": "bearish"}
        
    return None

def find_order_block(df, mss_type, lookback=20):
    """
    Identifies the Order Block (OB) based on the MSS direction.
    
    An Order Block is the last opposing candle before a strong move:
    - Bullish OB: Last bearish candle before bullish MSS (where institutions bought)
    - Bearish OB: Last bullish candle before bearish MSS (where institutions sold)
    
    Args:
        df: DataFrame with OHLC data
        mss_type: "bullish" or "bearish"
        lookback: Number of candles to look back for OB (default: 20)
    
    Returns:
        Dictionary with OB zone details or None
    """
    if mss_type is None:
        return None
    
    # Look at recent candles (exclude the last one which is incomplete)
    recent_candles = df.iloc[-lookback-1:-1]
    
    if mss_type == "bullish":
        # Find the last bearish candle (close < open) before the bullish move
        bearish_candles = recent_candles[recent_candles['close'] < recent_candles['open']]
        
        if bearish_candles.empty:
            return None
        
        # The most recent bearish candle is the Bullish Order Block
        ob_candle = bearish_candles.iloc[-1]
        
        return {
            "type": "bullish",
            "high": ob_candle['high'],
            "low": ob_candle['low'],
            "open": ob_candle['open'],
            "close": ob_candle['close'],
            "time": ob_candle['time'],
            "body_high": max(ob_candle['open'], ob_candle['close']),
            "body_low": min(ob_candle['open'], ob_candle['close'])
        }
    
    elif mss_type == "bearish":
        # Find the last bullish candle (close > open) before the bearish move
        bullish_candles = recent_candles[recent_candles['close'] > recent_candles['open']]
        
        if bullish_candles.empty:
            return None
        
        # The most recent bullish candle is the Bearish Order Block
        ob_candle = bullish_candles.iloc[-1]
        
        return {
            "type": "bearish",
            "high": ob_candle['high'],
            "low": ob_candle['low'],
            "open": ob_candle['open'],
            "close": ob_candle['close'],
            "time": ob_candle['time'],
            "body_high": max(ob_candle['open'], ob_candle['close']),
            "body_low": min(ob_candle['open'], ob_candle['close'])
        }
    
    return None

def check_confluence(order_block, fvg, min_overlap_pct=30):
    """
    Checks if FVG and Order Block have confluence (overlap).
    
    Args:
        order_block: OB dictionary with high/low
        fvg: FVG dictionary with high/low
        min_overlap_pct: Minimum overlap percentage required (default: 30%)
    
    Returns:
        Dictionary with confluence details or None
    """
    if order_block is None or fvg is None:
        return None
    
    if order_block['type'] != fvg['type']:
        return None
    
    # Calculate overlap between OB and FVG zones
    overlap_high = min(order_block['high'], fvg['high'])
    overlap_low = max(order_block['low'], fvg['low'])
    
    # Check if there's actual overlap
    if overlap_low >= overlap_high:
        return None
    
    overlap_size = overlap_high - overlap_low
    fvg_size = fvg['high'] - fvg['low']
    ob_size = order_block['high'] - order_block['low']
    
    # Calculate overlap as percentage of FVG size
    overlap_pct = (overlap_size / fvg_size) * 100 if fvg_size > 0 else 0
    
    if overlap_pct < min_overlap_pct:
        return None
    
    return {
        "type": order_block['type'],
        "overlap_high": overlap_high,
        "overlap_low": overlap_low,
        "overlap_size": overlap_size,
        "overlap_pct": overlap_pct,
        "ob": order_block,
        "fvg": fvg,
        "quality": "high" if overlap_pct >= 70 else "medium" if overlap_pct >= 50 else "low"
    }

def get_refined_entry(order_block, fvg, confluence):
    """
    Determines the optimal entry price based on OB, FVG, and confluence.
    
    Priority:
    1. If strong confluence (70%+): Use middle of overlap zone
    2. If medium confluence (50-70%): Use FVG edge closest to OB
    3. If weak confluence (30-50%): Use OB body (50% of OB)
    4. No confluence: Use FVG edge (original strategy)
    
    Args:
        order_block: OB dictionary
        fvg: FVG dictionary
        confluence: Confluence dictionary or None
    
    Returns:
        Refined entry price
    """
    if confluence:
        # Strong confluence: Use middle of overlap for best fill probability
        if confluence['quality'] == "high":
            return (confluence['overlap_high'] + confluence['overlap_low']) / 2
        
        # Medium confluence: Use optimal edge
        elif confluence['quality'] == "medium":
            if confluence['type'] == "bullish":
                return confluence['overlap_high']  # Top of overlap for buys
            else:
                return confluence['overlap_low']  # Bottom of overlap for sells
        
        # Weak confluence: Use Order Block body (50% retracement)
        else:
            return (order_block['body_high'] + order_block['body_low']) / 2
    
    # No confluence: Fall back to FVG edge (original strategy)
    if order_block and order_block['type'] == "bullish":
        return order_block['body_low']  # Bottom of OB body for buys
    elif order_block and order_block['type'] == "bearish":
        return order_block['body_high']  # Top of OB body for sells
    
    # Absolute fallback: FVG edge
    if fvg:
        return fvg['high'] if fvg['type'] == "bullish" else fvg['low']
    
    return None

def analyze_setup_quality(mss_type, order_block, fvg, confluence):
    """
    Analyzes the overall quality of the trading setup.
    
    Returns:
        Dictionary with quality score and description
    """
    score = 0
    factors = []
    
    # MSS present (required)
    if mss_type:
        score += 25
        factors.append("✓ MSS detected")
    
    # Order Block present
    if order_block:
        score += 25
        factors.append("✓ Order Block identified")
    
    # FVG present
    if fvg:
        score += 25
        factors.append("✓ FVG present")
    
    # Confluence
    if confluence:
        if confluence['quality'] == "high":
            score += 25
            factors.append("✓ Strong OB+FVG confluence (70%+)")
        elif confluence['quality'] == "medium":
            score += 20
            factors.append("✓ Medium OB+FVG confluence (50-70%)")
        else:
            score += 15
            factors.append("✓ Weak OB+FVG confluence (30-50%)")
    
    # Determine quality rating
    if score >= 90:
        quality = "EXCELLENT"
    elif score >= 75:
        quality = "GOOD"
    elif score >= 60:
        quality = "FAIR"
    else:
        quality = "POOR"
    
    return {
        "score": score,
        "quality": quality,
        "factors": factors
    }