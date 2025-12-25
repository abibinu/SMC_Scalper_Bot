import pandas as pd
import MetaTrader5 as mt5

def get_ohlc_data(symbol, timeframe, count=100):
    """Fetches OHLC data from MT5 and returns it as a Pandas DataFrame."""
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
    df = pd.DataFrame(rates)
    df['time'] = pd.to_datetime(df['time'], unit='s')
    return df

def calculate_atr(symbol, period=14, timeframe=mt5.TIMEFRAME_H1):
    """
    Calculate Average True Range for volatility filtering.
    Uses H1 timeframe for more stable ATR calculation.
    
    Args:
        symbol: Trading symbol
        period: ATR period (default: 14)
        timeframe: Timeframe for ATR calculation (default: H1)
    
    Returns:
        ATR value as float
    """
    # Fetch more data from H1 timeframe for better ATR calculation
    df = get_ohlc_data(symbol, timeframe, count=period * 3)
    
    if len(df) < period:
        return 0.0
    
    high = df['high']
    low = df['low']
    close = df['close']
    
    # Calculate True Range
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    # Calculate ATR using exponential moving average
    atr = tr.ewm(span=period, adjust=False).mean().iloc[-1]
    
    return atr

def calculate_volume_ratio(df, period=20):
    """
    Calculate current volume vs average volume.
    
    Args:
        df: DataFrame with OHLC data
        period: Period for average calculation (default: 20)
    
    Returns:
        Volume ratio as float (1.0 = average, 2.0 = double average, etc.)
    """
    if 'tick_volume' not in df.columns:
        return 1.0
    
    if len(df) < period + 1:
        return 1.0
    
    avg_volume = df['tick_volume'].rolling(window=period).mean().iloc[-2]
    current_volume = df['tick_volume'].iloc[-2]
    
    if avg_volume == 0 or pd.isna(avg_volume):
        return 1.0
    
    return current_volume / avg_volume

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

def detect_trend(df, lookback=20):
    """
    Detects the current trend based on swing highs and lows.
    
    Args:
        df: DataFrame with OHLC data
        lookback: Number of candles to analyze
    
    Returns:
        "bullish", "bearish", or "ranging"
    """
    recent_df = df.iloc[-lookback:]
    
    # Calculate swing points
    recent_df = recent_df.copy()
    recent_df['swing_high'] = (recent_df['high'] > recent_df['high'].shift(1)) & \
                               (recent_df['high'] > recent_df['high'].shift(-1))
    recent_df['swing_low'] = (recent_df['low'] < recent_df['low'].shift(1)) & \
                              (recent_df['low'] < recent_df['low'].shift(-1))
    
    swing_highs = recent_df[recent_df['swing_high']]['high'].values
    swing_lows = recent_df[recent_df['swing_low']]['low'].values
    
    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return "ranging"
    
    # Check if making higher highs and higher lows (bullish)
    higher_highs = swing_highs[-1] > swing_highs[-2] if len(swing_highs) >= 2 else False
    higher_lows = swing_lows[-1] > swing_lows[-2] if len(swing_lows) >= 2 else False
    
    # Check if making lower highs and lower lows (bearish)
    lower_highs = swing_highs[-1] < swing_highs[-2] if len(swing_highs) >= 2 else False
    lower_lows = swing_lows[-1] < swing_lows[-2] if len(swing_lows) >= 2 else False
    
    if higher_highs and higher_lows:
        return "bullish"
    elif lower_highs and lower_lows:
        return "bearish"
    else:
        return "ranging"

def get_mtf_structure(symbol, timeframes=[mt5.TIMEFRAME_M5, mt5.TIMEFRAME_M15], lookback=50):
    """
    Analyzes market structure across multiple timeframes.
    
    Args:
        symbol: Trading symbol
        timeframes: List of MT5 timeframes to analyze
        lookback: Number of candles to analyze per timeframe
    
    Returns:
        Dictionary with structure analysis for each timeframe
    """
    mtf_analysis = {}
    
    for tf in timeframes:
        df = get_ohlc_data(symbol, tf, count=lookback)
        
        # Detect trend
        trend = detect_trend(df, lookback=min(20, lookback))
        
        # Detect MSS on this timeframe
        mss_type, _ = detect_mss_and_sl(df)
        
        # Find Order Block on this timeframe
        ob = find_order_block(df, mss_type, lookback=min(20, lookback)) if mss_type else None
        
        # Get timeframe name
        tf_name = get_timeframe_name(tf)
        
        mtf_analysis[tf_name] = {
            "timeframe": tf,
            "trend": trend,
            "mss": mss_type,
            "has_ob": ob is not None,
            "ob": ob
        }
    
    return mtf_analysis

def get_timeframe_name(timeframe):
    """Convert MT5 timeframe constant to readable name."""
    tf_map = {
        mt5.TIMEFRAME_M1: "M1",
        mt5.TIMEFRAME_M5: "M5",
        mt5.TIMEFRAME_M15: "M15",
        mt5.TIMEFRAME_M30: "M30",
        mt5.TIMEFRAME_H1: "H1",
        mt5.TIMEFRAME_H4: "H4",
        mt5.TIMEFRAME_D1: "D1"
    }
    return tf_map.get(timeframe, "Unknown")

def check_mtf_alignment(m1_signal, mtf_analysis, require_all_aligned=False):
    """
    Checks if M1 signal aligns with higher timeframe structure.
    
    Args:
        m1_signal: Direction of M1 signal ("bullish" or "bearish")
        mtf_analysis: Dictionary from get_mtf_structure()
        require_all_aligned: If True, all timeframes must align
    
    Returns:
        Dictionary with alignment details
    """
    if not m1_signal:
        return {"aligned": False, "reason": "No M1 signal"}
    
    aligned_timeframes = []
    misaligned_timeframes = []
    ranging_timeframes = []
    
    for tf_name, data in mtf_analysis.items():
        trend = data['trend']
        mss = data['mss']
        
        # Check alignment: either trend or MSS matches M1 signal
        is_aligned = (trend == m1_signal) or (mss == m1_signal)
        is_ranging = (trend == "ranging")
        
        if is_aligned:
            aligned_timeframes.append(tf_name)
        elif is_ranging:
            ranging_timeframes.append(tf_name)
        else:
            misaligned_timeframes.append(tf_name)
    
    total_tfs = len(mtf_analysis)
    aligned_count = len(aligned_timeframes)
    
    # Ranging is neutral - not against us
    neutral_count = len(ranging_timeframes)
    
    # Calculate alignment strength
    if require_all_aligned:
        is_aligned = aligned_count == total_tfs
    else:
        # At least 50% must be aligned or ranging
        is_aligned = (aligned_count + neutral_count) >= (total_tfs * 0.5)
    
    alignment_pct = (aligned_count / total_tfs * 100) if total_tfs > 0 else 0
    
    # Determine strength
    if alignment_pct >= 100:
        strength = "PERFECT"
    elif alignment_pct >= 50:
        strength = "STRONG"
    elif alignment_pct >= 30:
        strength = "WEAK"
    else:
        strength = "POOR"
    
    return {
        "aligned": is_aligned,
        "strength": strength,
        "alignment_pct": alignment_pct,
        "aligned_tfs": aligned_timeframes,
        "ranging_tfs": ranging_timeframes,
        "misaligned_tfs": misaligned_timeframes,
        "total_tfs": total_tfs
    }

def calculate_mtf_score_bonus(mtf_alignment):
    """
    Calculates bonus score points for MTF alignment.
    
    Args:
        mtf_alignment: Dictionary from check_mtf_alignment()
    
    Returns:
        Bonus score (0-20 points)
    """
    if not mtf_alignment['aligned']:
        return 0
    
    strength = mtf_alignment['strength']
    
    if strength == "PERFECT":
        return 20
    elif strength == "STRONG":
        return 15
    elif strength == "WEAK":
        return 10
    else:
        return 5

def detect_breaker_block(df, recent_obs, lookback=50):
    """
    Detects Breaker Blocks - Order Blocks that failed and now act as reversal zones.
    
    A Breaker Block forms when:
    1. An Order Block existed
    2. Price broke through it (instead of bouncing)
    3. That OB now acts as support/resistance on the opposite side
    
    Bullish Breaker Block: Old Bearish OB broken upward → Now acts as support
    Bearish Breaker Block: Old Bullish OB broken downward → Now acts as resistance
    
    Args:
        df: DataFrame with OHLC data
        recent_obs: List of recently detected OBs to check for breaks
        lookback: How far back to check
    
    Returns:
        List of Breaker Blocks with details
    """
    breaker_blocks = []
    
    if not recent_obs or len(recent_obs) == 0:
        return breaker_blocks
    
    recent_candles = df.iloc[-lookback:]
    current_price = df.iloc[-1]['close']
    
    for ob in recent_obs:
        ob_high = ob['high']
        ob_low = ob['low']
        ob_type = ob['type']
        
        # Check if OB was broken
        if ob_type == "bullish":
            # Bullish OB should act as support
            # If broken downward (price closes below OB low) → Becomes Bearish Breaker Block
            breaks = recent_candles[recent_candles['close'] < ob_low]
            
            if len(breaks) > 0:
                # This OB failed - now it's a Bearish Breaker Block (resistance)
                breaker_blocks.append({
                    "type": "bearish",
                    "original_ob_type": "bullish",
                    "high": ob_high,
                    "low": ob_low,
                    "break_time": breaks.iloc[-1]['time'],
                    "current_relevance": "high" if current_price < ob_high else "medium",
                    "quality": "high" if len(breaks) >= 2 else "medium"
                })
        
        elif ob_type == "bearish":
            # Bearish OB should act as resistance
            # If broken upward (price closes above OB high) → Becomes Bullish Breaker Block
            breaks = recent_candles[recent_candles['close'] > ob_high]
            
            if len(breaks) > 0:
                # This OB failed - now it's a Bullish Breaker Block (support)
                breaker_blocks.append({
                    "type": "bullish",
                    "original_ob_type": "bearish",
                    "high": ob_high,
                    "low": ob_low,
                    "break_time": breaks.iloc[-1]['time'],
                    "current_relevance": "high" if current_price > ob_low else "medium",
                    "quality": "high" if len(breaks) >= 2 else "medium"
                })
    
    return breaker_blocks

def find_historical_order_blocks(df, lookback=50):
    """
    Finds all historical Order Blocks in the lookback period.
    Used for Breaker Block detection.
    
    Args:
        df: DataFrame with OHLC data
        lookback: Number of candles to analyze
    
    Returns:
        List of Order Blocks
    """
    order_blocks = []
    recent_df = df.iloc[-lookback:]
    
    for i in range(2, len(recent_df) - 1):
        candle = recent_df.iloc[i]
        
        # Check if it's a potential Order Block (opposing candle before a move)
        is_bearish_candle = candle['close'] < candle['open']
        is_bullish_candle = candle['close'] > candle['open']
        
        # Look at the next few candles to see if there was a strong move
        next_candles = recent_df.iloc[i+1:min(i+6, len(recent_df))]
        
        if len(next_candles) < 2:
            continue
        
        # Check for bullish move after bearish candle (Bullish OB)
        if is_bearish_candle:
            bullish_moves = sum(next_candles['close'] > next_candles['open'])
            price_moved_up = next_candles.iloc[-1]['high'] > candle['high']
            
            if bullish_moves >= 2 and price_moved_up:
                order_blocks.append({
                    "type": "bullish",
                    "high": candle['high'],
                    "low": candle['low'],
                    "open": candle['open'],
                    "close": candle['close'],
                    "time": candle['time'],
                    "index": i
                })
        
        # Check for bearish move after bullish candle (Bearish OB)
        elif is_bullish_candle:
            bearish_moves = sum(next_candles['close'] < next_candles['open'])
            price_moved_down = next_candles.iloc[-1]['low'] < candle['low']
            
            if bearish_moves >= 2 and price_moved_down:
                order_blocks.append({
                    "type": "bearish",
                    "high": candle['high'],
                    "low": candle['low'],
                    "open": candle['open'],
                    "close": candle['close'],
                    "time": candle['time'],
                    "index": i
                })
    
    return order_blocks

def check_price_in_breaker_block(current_price, breaker_block, tolerance_pct=0.2):
    """
    Checks if current price is within or near a Breaker Block zone.
    
    Args:
        current_price: Current market price
        breaker_block: BB dictionary
        tolerance_pct: Percentage tolerance for "near" (default 0.2%)
    
    Returns:
        "inside", "near", or "outside"
    """
    bb_high = breaker_block['high']
    bb_low = breaker_block['low']
    bb_range = bb_high - bb_low
    tolerance = bb_range * (tolerance_pct / 100)
    
    # Check if price is inside the BB
    if bb_low <= current_price <= bb_high:
        return "inside"
    
    # Check if price is near the BB
    if (bb_low - tolerance) <= current_price <= (bb_high + tolerance):
        return "near"
    
    return "outside"

def enhance_setup_with_breaker_blocks(mss_type, entry_price, breaker_blocks):
    """
    Checks if the setup has Breaker Block confluence.
    
    Args:
        mss_type: "bullish" or "bearish"
        entry_price: Planned entry price
        breaker_blocks: List of detected Breaker Blocks
    
    Returns:
        Dictionary with BB confluence details
    """
    if not breaker_blocks:
        return None
    
    # Filter BBs that match our direction
    matching_bbs = [bb for bb in breaker_blocks if bb['type'] == mss_type]
    
    if not matching_bbs:
        return None
    
    # Find BBs near our entry
    relevant_bbs = []
    for bb in matching_bbs:
        position = check_price_in_breaker_block(entry_price, bb)
        if position in ["inside", "near"]:
            relevant_bbs.append({
                "bb": bb,
                "position": position,
                "quality": bb['quality']
            })
    
    if not relevant_bbs:
        return None
    
    # Sort by quality
    relevant_bbs.sort(key=lambda x: 0 if x['quality'] == 'high' else 1)
    
    best_bb = relevant_bbs[0]
    
    return {
        "has_bb": True,
        "bb_count": len(relevant_bbs),
        "best_bb": best_bb['bb'],
        "position": best_bb['position'],
        "quality": best_bb['quality'],
        "bonus_score": 15 if best_bb['quality'] == 'high' else 10
    }