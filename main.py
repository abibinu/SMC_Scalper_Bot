import time
import MetaTrader5 as mt5
from risk_manager import RiskManager
from news_calendar import NewsCalendar
from trade_logger import TradeLogger
from datetime import datetime, time as dt_time, timedelta
from config import (
    SYMBOL, RISK_PER_TRADE, MAGIC_NUMBER, MAX_SPREAD_PIPS,
    LONDON_SESSION_START, LONDON_SESSION_END,
    NEW_YORK_SESSION_START, NEW_YORK_SESSION_END,
    MAX_ORDER_AGE_MINUTES, BREAKEVEN_TRIGGER_RR,
    ORDER_MANAGEMENT_CHECK_INTERVAL,
    OB_LOOKBACK_CANDLES, MIN_CONFLUENCE_OVERLAP,
    REQUIRE_CONFLUENCE, MIN_SETUP_QUALITY_SCORE,
    ENABLE_MTF_CONFIRMATION, MTF_TIMEFRAMES,
    REQUIRE_ALL_TF_ALIGNED, MTF_MIN_ALIGNMENT_PCT,
    MTF_SCORE_BONUS,
    ENABLE_BREAKER_BLOCKS, BB_LOOKBACK_CANDLES,
    BB_SCORE_BONUS, BB_MIN_QUALITY,
    ENABLE_TELEGRAM, TELEGRAM_NOTIFY_SIGNALS,
    TELEGRAM_NOTIFY_TRADES, TELEGRAM_NOTIFY_FILLS,
    TELEGRAM_NOTIFY_BREAKEVEN, TELEGRAM_NOTIFY_CLOSES,
    TELEGRAM_NOTIFY_SKIPS, ENABLE_RISK_MANAGER, MAX_DAILY_LOSS_PCT, MAX_WEEKLY_LOSS_PCT,
    MAX_DAILY_TRADES, RISK_STATE_FILE,
    AVOID_HIGH_IMPACT_NEWS, NEWS_BUFFER_MINUTES, NEWS_CACHE_FILE,
    ENABLE_TRADE_LOGGING, TRADE_DB_PATH, AUTO_CALCULATE_DAILY_PERFORMANCE
)
from engine import (
    get_ohlc_data, detect_mss_and_sl, find_fvg,
    find_order_block, check_confluence, get_refined_entry,
    analyze_setup_quality, get_mtf_structure, check_mtf_alignment,
    calculate_mtf_score_bonus, find_historical_order_blocks,
    detect_breaker_block, enhance_setup_with_breaker_blocks,
    calculate_atr, calculate_volume_ratio
)
from pytz import timezone
from telegram_notifier import TelegramNotifier
from trading_functions import (
    mt5_connect, verify_demo_account, check_spread, 
    calculate_lot_size, execute_limit_order, is_position_open
)
from order_manager import OrderManager

def is_high_impact_news_time():
    """
    Check if we're within 30 minutes of major news events.
    You should expand this with actual news calendar integration.
    """
    utc_now = datetime.utcnow()
    current_time = utc_now.time()
    
    # Major news times (UTC) - expand this list
    news_times = [
        (dt_time(8, 0), dt_time(8, 30)),   # EUR news
        (dt_time(12, 30), dt_time(13, 0)),  # USD news
        (dt_time(14, 0), dt_time(14, 30)),  # FOMC minutes
    ]
    
    for start, end in news_times:
        if start <= current_time <= end:
            return True
    
    return False

def is_in_trading_session():
    """
    Checks if the current time is within the London or New York trading sessions.
    MT5 server time is typically UTC or broker-specific, so we use UTC for consistency.
    """
    # Get server time from MT5 (more reliable than system time)
    server_time_struct = mt5.symbol_info_tick(SYMBOL).time
    server_time = datetime.utcfromtimestamp(server_time_struct)
    current_time = server_time.time()
    
    london_start = dt_time.fromisoformat(LONDON_SESSION_START)
    london_end = dt_time.fromisoformat(LONDON_SESSION_END)
    ny_start = dt_time.fromisoformat(NEW_YORK_SESSION_START)
    ny_end = dt_time.fromisoformat(NEW_YORK_SESSION_END)

    in_london = london_start <= current_time <= london_end
    in_ny = ny_start <= current_time <= ny_end
    
    return in_london or in_ny

def get_dynamic_risk_multiplier(setup_score, mtf_alignment=None, bb_confluence=None):
    """
    Adjust position size based on setup quality.
    Higher quality = larger position (up to 1.5x base risk).
    Lower quality = smaller position (down to 0.5x base risk).
    """
    base_multiplier = 1.0
    
    # Adjust based on setup score
    if setup_score >= 95:
        base_multiplier = 1.5
    elif setup_score >= 85:
        base_multiplier = 1.3
    elif setup_score >= 75:
        base_multiplier = 1.1
    elif setup_score < 65:
        base_multiplier = 0.7
    elif setup_score < 55:
        base_multiplier = 0.5
    
    # Bonus for MTF alignment
    if mtf_alignment and mtf_alignment.get('strength') == 'PERFECT':
        base_multiplier *= 1.1
    
    # Bonus for Breaker Block confluence
    if bb_confluence and bb_confluence.get('quality') == 'high':
        base_multiplier *= 1.1
    
    # Cap at 1.5x max
    return min(base_multiplier, 1.5)

def calculate_dynamic_tp(mss_type, entry, sl, atr, setup_score):
    """
    Calculate dynamic take profit based on volatility and setup quality.
    Better setups get wider targets.
    """
    risk = abs(entry - sl)
    
    # Base R:R ratio
    if setup_score >= 90:
        rr_ratio = 3.0  # Excellent setups: 1:3
    elif setup_score >= 75:
        rr_ratio = 2.5  # Good setups: 1:2.5
    else:
        rr_ratio = 2.0  # Fair setups: 1:2
    
    # Adjust for volatility
    # Higher ATR = more room to breathe
    point = mt5.symbol_info(SYMBOL).point
    sl_in_atr = risk / (atr * point)
    
    if sl_in_atr < 1.5:  # Tight stop relative to ATR
        rr_ratio *= 0.9  # Reduce target slightly
    
    reward = risk * rr_ratio
    
    if mss_type == "bullish":
        tp = entry + reward
    else:
        tp = entry - reward
    
    return tp, rr_ratio

def main():
    """Main function to run the trading bot."""
    print("=" * 60)
    print("SMC Institutional Scalper Bot v5.0 - Enhanced")
    print("=" * 60)
    
    mt5_connect()
    verify_demo_account()
    
    # Get account info and display
    account_info = mt5.account_info()

    # 1. Risk Manager
    risk_manager = RiskManager(
        max_daily_loss_pct=MAX_DAILY_LOSS_PCT,
        max_weekly_loss_pct=MAX_WEEKLY_LOSS_PCT,
        max_daily_trades=MAX_DAILY_TRADES,
        state_file=RISK_STATE_FILE
    ) if ENABLE_RISK_MANAGER else None
    
    # 2. News Calendar
    news_calendar = NewsCalendar(
        cache_file=NEWS_CACHE_FILE,
        buffer_minutes=NEWS_BUFFER_MINUTES
    ) if AVOID_HIGH_IMPACT_NEWS else None
    
    # Fetch today's news events
    if news_calendar:
        news_calendar.force_refresh()
        news_calendar.print_todays_events()
    
    # 3. Trade Logger
    trade_logger = TradeLogger(
        db_path=TRADE_DB_PATH
    ) if ENABLE_TRADE_LOGGING else None
    
    # Initialize Order Manager
    order_manager = OrderManager(
        magic_number=MAGIC_NUMBER,
        max_order_age_minutes=MAX_ORDER_AGE_MINUTES,
        breakeven_trigger_rr=BREAKEVEN_TRIGGER_RR
    )
    
    # Initialize Telegram Notifier
    telegram = TelegramNotifier(enabled=ENABLE_TELEGRAM)
    
    # Test Telegram connection
    if ENABLE_TELEGRAM:
        telegram.test_connection()

    # Print Risk Status
    if risk_manager:
        risk_manager.print_risk_status()
    
    print(f"✓ Bot running on demo account")
    print(f"✓ Account Balance: ${account_info.balance:,.2f}")
    print(f"✓ Symbol: {SYMBOL}")
    print(f"✓ Base Risk: {RISK_PER_TRADE * 100}% (dynamic 0.5x-1.5x)")
    print(f"✓ Dynamic TP: 2-3R based on quality")
    print(f"✓ MTF Confirmation: {'Enabled' if ENABLE_MTF_CONFIRMATION else 'Disabled'}")
    print(f"✓ Breaker Blocks: {'Enabled' if ENABLE_BREAKER_BLOCKS else 'Disabled'}")
    print("=" * 60)
    
    # Send startup notification
    if ENABLE_TELEGRAM:
        settings = {
            'ob_lookback': OB_LOOKBACK_CANDLES,
            'min_quality': MIN_SETUP_QUALITY_SCORE,
            'mtf_enabled': 'Yes' if ENABLE_MTF_CONFIRMATION else 'No',
            'bb_enabled': 'Yes' if ENABLE_BREAKER_BLOCKS else 'No'
        }
        telegram.notify_bot_started(account_info.balance, SYMBOL, RISK_PER_TRADE, settings)

    last_order_management_check = datetime.utcnow()
    
    try:
        while True:
            # Calculate time to next M1 candle close
            now = datetime.utcnow()
            next_candle = (now + timedelta(minutes=1)).replace(second=0, microsecond=0)
            sleep_seconds = (next_candle - now).total_seconds()
            
            # Periodic order management
            time_since_last_check = (now - last_order_management_check).total_seconds()
            if time_since_last_check >= ORDER_MANAGEMENT_CHECK_INTERVAL:
                pending_orders_before = order_manager.get_pending_orders(SYMBOL)
                cancelled = order_manager.cancel_old_orders(SYMBOL)
                if cancelled > 0 and ENABLE_TELEGRAM and TELEGRAM_NOTIFY_TRADES:
                    for order in pending_orders_before[:cancelled]:
                        telegram.notify_order_cancelled(order.ticket, "Expired")

                if trade_logger:
                # Check for filled orders
                    positions = mt5.positions_get(symbol=SYMBOL)
                    if positions:
                        for pos in positions:
                            if pos.magic == MAGIC_NUMBER:
                                # Update to active if it was pending
                                trade_logger.update_trade_status(
                                    pos.ticket, 
                                    status='active'
                                )
                
                positions_before = {pos.ticket for pos in mt5.positions_get(symbol=SYMBOL) or []}
                modified = order_manager.manage_breakeven(SYMBOL)
                if modified > 0 and ENABLE_TELEGRAM and TELEGRAM_NOTIFY_BREAKEVEN:
                    positions_after = mt5.positions_get(symbol=SYMBOL) or []
                    for pos in positions_after:
                        if pos.ticket in positions_before and pos.ticket in order_manager.managed_positions:
                            telegram.notify_breakeven_moved(pos.ticket, pos.symbol, pos.sl)
                
                order_manager.cleanup_closed_positions()
                last_order_management_check = now
            
            # Sleep until next candle
            time.sleep(max(1, sleep_seconds))
            
            # === PRE-TRADE FILTERS ===

            # 0. RISK MANAGER CHECK
            if risk_manager:
                can_trade, reason = risk_manager.can_trade()
                if not can_trade:
                    print(f"🛑 Trading suspended: {reason}")
                    if telegram:
                        telegram.send_message(f"🛑 <b>Trading Suspended</b>\n\n{reason}")
                    
                    # Sleep for 5 minutes before checking again
                    time.sleep(300)
                    continue
                
                # Update high watermarks periodically
                risk_manager.update_high_watermarks()
            
            # 1. Check trading session
            if not is_in_trading_session():
                continue

            # 2. Check for existing positions/orders
            if is_position_open(SYMBOL):
                continue
            
            pending_orders = order_manager.get_pending_orders(SYMBOL)
            if len(pending_orders) > 0:
                continue
            
            # 3. Spread filter
            if not check_spread(SYMBOL):
                continue
            
            # 4. High-impact news filter (UPDATED)
            if news_calendar:
                is_news, reason = news_calendar.is_high_impact_news_time()
                if is_news:
                    print(f"⚠️  High-impact news: {reason}")
                    if ENABLE_TELEGRAM and TELEGRAM_NOTIFY_SKIPS:
                        telegram.notify_signal_skipped("High-impact news", reason)
                    continue

            # === MARKET ANALYSIS ===
            
            # Fetch OHLC data
            df = get_ohlc_data(SYMBOL, mt5.TIMEFRAME_M1, count=100)
            
            # Calculate ATR from H1 timeframe for better stability
            atr = calculate_atr(SYMBOL, period=14, timeframe=mt5.TIMEFRAME_H1)
            point = mt5.symbol_info(SYMBOL).point
            atr_pips = atr / (point * 10)
            
            # Volume filter
            volume_ratio = calculate_volume_ratio(df)
            
            # Skip in extremely low volatility (less than 3 pips ATR)
            if atr_pips < 3.0:
                # Only print this message every 30 minutes to reduce noise
                if int(now.minute) % 30 == 0:
                    print(f"⚠️  ATR too low ({atr_pips:.1f} pips). Market too quiet.")
                continue
            
            # Skip in abnormally low volume
            if volume_ratio < 0.5:
                continue
            
            # Detect MSS
            mss_type, stop_loss = detect_mss_and_sl(df)
            
            if not mss_type:
                continue
            
            # Find Order Block
            order_block = find_order_block(df, mss_type, lookback=OB_LOOKBACK_CANDLES)
            
            # Find FVG
            fvg = find_fvg(df)
            
            # Check confluence
            confluence = check_confluence(order_block, fvg, min_overlap_pct=MIN_CONFLUENCE_OVERLAP)
            
            # === MULTI-TIMEFRAME ANALYSIS ===
            mtf_alignment = None
            if ENABLE_MTF_CONFIRMATION:
                # Convert timeframe strings to MT5 constants
                tf_map = {
                    "M5": mt5.TIMEFRAME_M5,
                    "M15": mt5.TIMEFRAME_M15,
                    "M30": mt5.TIMEFRAME_M30,
                    "H1": mt5.TIMEFRAME_H1
                }
                mtf_timeframes = [tf_map[tf] for tf in MTF_TIMEFRAMES if tf in tf_map]
                
                mtf_structure = get_mtf_structure(SYMBOL, timeframes=mtf_timeframes)
                mtf_alignment = check_mtf_alignment(mss_type, mtf_structure, 
                                                     require_all_aligned=REQUIRE_ALL_TF_ALIGNED)
                
                # Filter out if MTF is misaligned
                if mtf_alignment['alignment_pct'] < MTF_MIN_ALIGNMENT_PCT:
                    print(f"⚠️  MTF misaligned ({mtf_alignment['alignment_pct']:.0f}%). Skipping.")
                    if ENABLE_TELEGRAM and TELEGRAM_NOTIFY_SKIPS:
                        telegram.notify_signal_skipped("MTF misalignment", 
                                                       f"{mtf_alignment['alignment_pct']:.0f}%")
                    continue
            
            # === BREAKER BLOCK ANALYSIS ===
            bb_confluence = None
            if ENABLE_BREAKER_BLOCKS:
                historical_obs = find_historical_order_blocks(df, lookback=BB_LOOKBACK_CANDLES)
                breaker_blocks = detect_breaker_block(df, historical_obs, lookback=BB_LOOKBACK_CANDLES)
                
                if breaker_blocks:
                    # Get refined entry first
                    entry_price = get_refined_entry(order_block, fvg, confluence)
                    if entry_price:
                        bb_confluence = enhance_setup_with_breaker_blocks(mss_type, entry_price, breaker_blocks)
                        
                        if bb_confluence and bb_confluence.get('quality') == 'high':
                            print(f"🔄 High-quality Breaker Block detected!")
                            if ENABLE_TELEGRAM:
                                bb = bb_confluence['best_bb']
                                telegram.notify_breaker_block_detected(
                                    bb['type'], bb['high'], bb['low'], bb['quality']
                                )
            
            # === SETUP QUALITY ANALYSIS ===
            setup_analysis = analyze_setup_quality(mss_type, order_block, fvg, confluence)
            
            # Add MTF bonus
            if mtf_alignment and MTF_SCORE_BONUS:
                mtf_bonus = calculate_mtf_score_bonus(mtf_alignment)
                setup_analysis['score'] += mtf_bonus
                setup_analysis['factors'].append(f"✓ MTF Bonus: +{mtf_bonus} pts")
            
            # Add BB bonus
            if bb_confluence and BB_SCORE_BONUS:
                bb_bonus = bb_confluence.get('bonus_score', 0)
                setup_analysis['score'] += bb_bonus
                setup_analysis['factors'].append(f"✓ BB Bonus: +{bb_bonus} pts")
            
            # Filter by minimum quality
            if setup_analysis['score'] < MIN_SETUP_QUALITY_SCORE:
                print(f"⚠️  Setup quality too low ({setup_analysis['score']}/100). Skipping.")
                continue
            
            # Confluence requirement
            if REQUIRE_CONFLUENCE and not confluence:
                print(f"⚠️  No OB+FVG confluence. Skipping.")
                continue
            
            # === VALID SETUP DETECTED ===
            print(f"\n{'='*60}")
            print(f"🎯 HIGH-QUALITY SIGNAL: {mss_type.upper()} MSS")
            print(f"{'='*60}")
            print(f"📊 Setup Score: {setup_analysis['quality']} ({setup_analysis['score']}/100)")
            print(f"📈 ATR: {atr_pips:.1f} pips")
            print(f"📊 Volume: {volume_ratio:.2f}x average")
            
            if mtf_alignment:
                print(f"🔄 MTF: {mtf_alignment['strength']} ({mtf_alignment['alignment_pct']:.0f}%)")
            
            for factor in setup_analysis['factors']:
                print(f"   {factor}")
            print(f"{'='*60}")
            
            # Notify signal
            if ENABLE_TELEGRAM and TELEGRAM_NOTIFY_SIGNALS:
                telegram.notify_signal_detected(
                    mss_type, 
                    setup_analysis['score'], 
                    setup_analysis['quality'],
                    mtf_alignment
                )
            
            # === TRADE EXECUTION ===
            
            # Determine entry
            entry_price = get_refined_entry(order_block, fvg, confluence)
            
            if entry_price is None:
                print(f"❌ Could not determine entry. Skipping.")
                continue
            
            # Calculate dynamic TP
            take_profit, rr_ratio = calculate_dynamic_tp(mss_type, entry_price, stop_loss, 
                                                          atr, setup_analysis['score'])
            
            # Calculate dynamic lot size
            sl_pips = abs(entry_price - stop_loss) / point
            
            risk_multiplier = get_dynamic_risk_multiplier(
                setup_analysis['score'], 
                mtf_alignment, 
                bb_confluence
            )
            
            adjusted_risk = RISK_PER_TRADE * risk_multiplier
            
            account_info = mt5.account_info()
            lot_size = calculate_lot_size(
                account_info.balance, 
                adjusted_risk,
                sl_pips, 
                SYMBOL
            )
            
            tp_pips = abs(take_profit - entry_price) / point
            risk_amount = account_info.balance * adjusted_risk
            potential_profit = risk_amount * rr_ratio

            print(f"💰 Trade Details:")
            print(f"   Entry: {entry_price:.5f}")
            print(f"   SL: {stop_loss:.5f} ({sl_pips:.1f} pips)")
            print(f"   TP: {take_profit:.5f} ({tp_pips:.1f} pips)")
            print(f"   R:R: 1:{rr_ratio:.1f}")
            print(f"   Lot Size: {lot_size}")
            print(f"   Risk: ${risk_amount:.2f} ({adjusted_risk*100:.2f}%)")
            print(f"   Potential: ${potential_profit:.2f}")

            # Execute Trade
            order_type = mt5.ORDER_TYPE_BUY_LIMIT if mss_type == "bullish" else mt5.ORDER_TYPE_SELL_LIMIT
            result = execute_limit_order(
                order_type,
                SYMBOL, 
                lot_size, 
                entry_price, 
                stop_loss, 
                take_profit, 
                MAGIC_NUMBER
            )
            
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                print(f"✅ Order placed successfully (Ticket: #{result.order})")

            if trade_logger:
            # Prepare setup analysis for logging
                setup_for_log = {
                    'score': setup_analysis['score'],
                    'quality': setup_analysis['quality'],
                    'ob_present': order_block is not None,
                    'fvg_present': fvg is not None,
                    'confluence_pct': confluence.get('overlap_pct', 0) if confluence else 0,
                    'confluence_quality': confluence.get('quality', None) if confluence else None
                }
                
                trade_logger.log_trade_signal(
                    ticket_number=result.order,
                    symbol=SYMBOL,
                    direction=mss_type,
                    entry_price=entry_price,
                    stop_loss=stop_loss,
                    take_profit=take_profit,
                    lot_size=lot_size,
                    setup_analysis=setup_for_log,
                    mtf_alignment=mtf_alignment,
                    bb_confluence=bb_confluence,
                    risk_amount=risk_amount,
                    risk_pct=adjusted_risk,
                    risk_multiplier=risk_multiplier,
                    rr_ratio=rr_ratio,
                    atr_pips=atr_pips,
                    volume_ratio=volume_ratio,
                    spread_pips=0  # Calculate if needed
                )
        
            # ============ Record Trade in Risk Manager (NEW) ============
            if risk_manager:
                risk_manager.record_trade()
                
                if ENABLE_TELEGRAM and TELEGRAM_NOTIFY_TRADES:
                    telegram.notify_trade_placed(
                        order_type, SYMBOL, entry_price, stop_loss, take_profit,
                        lot_size, risk_amount, potential_profit, result.order
                    )
            else:
                print(f"❌ Order failed: {result.comment if result else 'Unknown error'}")
            
            print(f"{'='*60}\n")

    except KeyboardInterrupt:
        print("\n\n🛑 Bot stopped by user.")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        
        if ENABLE_TELEGRAM:
            telegram.notify_error(str(e))
    finally:
        print("\n" + "=" * 60)
        print("📊 Final Status Report")
        print("=" * 60)
        status = order_manager.get_status_report(SYMBOL)
        print(f"Pending Orders: {status['pending_orders']}")
        print(f"Open Positions: {status['open_positions']}")
        if risk_manager:
         risk_manager.print_risk_status()
    
        # Trade Performance
        if trade_logger:
            print("\n" + "=" * 60)
            trade_logger.print_performance_report(days=7)
            
            # Calculate today's performance
            if AUTO_CALCULATE_DAILY_PERFORMANCE:
                trade_logger.calculate_daily_performance()
        print("=" * 60)
        
        mt5.shutdown()
        print("✓ MetaTrader5 connection closed.")

if __name__ == "__main__":
    main()