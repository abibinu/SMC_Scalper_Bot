import time
import MetaTrader5 as mt5
from datetime import datetime, time as dt_time, timedelta
from config import (
    SYMBOL, RISK_PER_TRADE, MAGIC_NUMBER, 
    LONDON_SESSION_START, LONDON_SESSION_END, 
    NEW_YORK_SESSION_START, NEW_YORK_SESSION_END,
    MAX_ORDER_AGE_MINUTES, BREAKEVEN_TRIGGER_RR,
    ORDER_MANAGEMENT_CHECK_INTERVAL,
    OB_LOOKBACK_CANDLES, MIN_CONFLUENCE_OVERLAP,
    REQUIRE_CONFLUENCE, MIN_SETUP_QUALITY_SCORE,
    ENABLE_MTF_CONFIRMATION, MTF_TIMEFRAMES,
    REQUIRE_ALL_TF_ALIGNED, MTF_MIN_ALIGNMENT_PCT,
    MTF_SCORE_BONUS
)
from engine import (
    get_ohlc_data, detect_mss_and_sl, find_fvg,
    find_order_block, check_confluence, get_refined_entry,
    analyze_setup_quality, get_mtf_structure, check_mtf_alignment,
    calculate_mtf_score_bonus
)
from trading_functions import (
    mt5_connect, verify_demo_account, check_spread, 
    calculate_lot_size, execute_limit_order, is_position_open
)
from order_manager import OrderManager

def is_in_trading_session():
    """Checks if the current time is within the London or New York trading sessions."""
    utc_now = datetime.utcnow()
    current_time = utc_now.time()
    
    london_start = dt_time.fromisoformat(LONDON_SESSION_START)
    london_end = dt_time.fromisoformat(LONDON_SESSION_END)
    ny_start = dt_time.fromisoformat(NEW_YORK_SESSION_START)
    ny_end = dt_time.fromisoformat(NEW_YORK_SESSION_END)

    in_london = london_start <= current_time <= london_end
    in_ny = ny_start <= current_time <= ny_end
    
    return in_london or in_ny

def main():
    """Main function to run the trading bot."""
    print("=" * 60)
    print("SMC Institutional Scalper Bot v3.0")
    print("=" * 60)
    
    mt5_connect()
    verify_demo_account()
    
    # Get account info and display
    account_info = mt5.account_info()
    
    # Initialize Order Manager
    order_manager = OrderManager(
        magic_number=MAGIC_NUMBER,
        max_order_age_minutes=MAX_ORDER_AGE_MINUTES,
        breakeven_trigger_rr=BREAKEVEN_TRIGGER_RR
    )
    
    print(f"✓ Bot running on demo account")
    print(f"✓ Account Balance: ${account_info.balance:,.2f}")
    print(f"✓ Account Equity: ${account_info.equity:,.2f}")
    print(f"✓ Free Margin: ${account_info.margin_free:,.2f}")
    print(f"✓ Symbol: {SYMBOL}")
    print(f"✓ Risk per trade: {RISK_PER_TRADE * 100}%")
    print(f"✓ Order expiration: {MAX_ORDER_AGE_MINUTES} minutes")
    print(f"✓ Breakeven trigger: {BREAKEVEN_TRIGGER_RR}:1 R:R")
    print(f"✓ OB lookback: {OB_LOOKBACK_CANDLES} candles")
    print(f"✓ Min confluence: {MIN_CONFLUENCE_OVERLAP}%")
    print(f"✓ Require confluence: {'Yes' if REQUIRE_CONFLUENCE else 'No'}")
    print(f"✓ Min setup quality: {MIN_SETUP_QUALITY_SCORE}/100")
    print(f"✓ MTF Confirmation: {'Enabled' if ENABLE_MTF_CONFIRMATION else 'Disabled'}")
    if ENABLE_MTF_CONFIRMATION:
        print(f"   - Timeframes: {', '.join(MTF_TIMEFRAMES)}")
        print(f"   - Require all aligned: {'Yes' if REQUIRE_ALL_TF_ALIGNED else 'No'}")
        print(f"   - Min alignment: {MTF_MIN_ALIGNMENT_PCT}%")
    print("=" * 60)

    last_order_management_check = datetime.utcnow()
    
    try:
        while True:
            # Calculate time to next M1 candle close
            now = datetime.utcnow()
            next_candle = (now + timedelta(minutes=1)).replace(second=0, microsecond=0)
            sleep_seconds = (next_candle - now).total_seconds()
            
            # Periodic order management checks (every ORDER_MANAGEMENT_CHECK_INTERVAL seconds)
            time_since_last_check = (now - last_order_management_check).total_seconds()
            if time_since_last_check >= ORDER_MANAGEMENT_CHECK_INTERVAL:
                # Cancel old pending orders
                cancelled = order_manager.cancel_old_orders(SYMBOL)
                if cancelled > 0:
                    print(f"🗑️  Cancelled {cancelled} expired order(s)")
                
                # Move positions to breakeven
                modified = order_manager.manage_breakeven(SYMBOL)
                if modified > 0:
                    print(f"🎯 Moved {modified} position(s) to breakeven")
                
                # Cleanup closed positions from tracking
                order_manager.cleanup_closed_positions()
                
                last_order_management_check = now
            
            # Sleep until next candle
            time.sleep(max(1, sleep_seconds))
            
            # Check if in trading session
            if not is_in_trading_session():
                continue

            # Check if we already have a position or pending order
            if is_position_open(SYMBOL):
                continue
            
            pending_orders = order_manager.get_pending_orders(SYMBOL)
            if len(pending_orders) > 0:
                continue
                
            # Check spread
            if not check_spread(SYMBOL):
                print(f"⚠️  Spread too high for {SYMBOL}, skipping")
                continue

            # Fetch OHLC data
            df = get_ohlc_data(SYMBOL, mt5.TIMEFRAME_M1, count=100)
            
            # Detect MSS
            mss_type, stop_loss = detect_mss_and_sl(df)
            
            if mss_type:
                # Find Order Block
                order_block = find_order_block(df, mss_type, lookback=OB_LOOKBACK_CANDLES)
                
                # Find FVG
                fvg = find_fvg(df)
                
                # Check for confluence between OB and FVG
                confluence = check_confluence(order_block, fvg, min_overlap_pct=MIN_CONFLUENCE_OVERLAP)
                
                # Analyze setup quality
                setup_analysis = analyze_setup_quality(mss_type, order_block, fvg, confluence)
                
                # Apply filters
                if REQUIRE_CONFLUENCE and not confluence:
                    print(f"⚠️  {mss_type.upper()} MSS detected but no OB+FVG confluence. Skipping.")
                    continue
                
                if setup_analysis['score'] < MIN_SETUP_QUALITY_SCORE:
                    print(f"⚠️  Setup quality too low ({setup_analysis['score']}/100). Skipping.")
                    continue
                
                # At this point we have a valid setup
                print(f"\n{'='*60}")
                print(f"🎯 SIGNAL DETECTED: {mss_type.upper()} MSS")
                print(f"{'='*60}")
                print(f"📊 Setup Quality: {setup_analysis['quality']} ({setup_analysis['score']}/100)")
                for factor in setup_analysis['factors']:
                    print(f"   {factor}")
                print(f"{'='*60}")
                
                # Determine entry price using refined logic
                entry_price = get_refined_entry(order_block, fvg, confluence)
                
                if entry_price is None:
                    print(f"❌ Could not determine entry price. Skipping.")
                    continue
                
                # Display OB and FVG info
                if order_block:
                    print(f"📦 Order Block Zone: {order_block['low']:.5f} - {order_block['high']:.5f}")
                if fvg:
                    print(f"📊 FVG Zone: {fvg['low']:.5f} - {fvg['high']:.5f}")
                if confluence:
                    print(f"🎯 Confluence Zone: {confluence['overlap_low']:.5f} - {confluence['overlap_high']:.5f}")
                    print(f"   Overlap: {confluence['overlap_pct']:.1f}% ({confluence['quality'].upper()})")
                
                # Calculate SL and TP
                point = mt5.symbol_info(SYMBOL).point
                sl_pips = abs(entry_price - stop_loss) / point
                tp_pips = sl_pips * 2 # 1:2 Risk-to-Reward
                
                take_profit = entry_price + (tp_pips * point) if mss_type == "bullish" else entry_price - (tp_pips * point)

                # Calculate Lot Size
                account_info = mt5.account_info()
                lot_size = calculate_lot_size(
                    account_info.balance, 
                    RISK_PER_TRADE, 
                    sl_pips, 
                    SYMBOL
                )

                print(f"{'='*60}")
                print(f"💰 Trade Details:")
                print(f"   Entry: {entry_price:.5f}")
                print(f"   SL: {stop_loss:.5f} ({sl_pips:.1f} pips)")
                print(f"   TP: {take_profit:.5f} ({tp_pips:.1f} pips)")
                print(f"   Lot Size: {lot_size}")
                print(f"   Risk: ${account_info.balance * RISK_PER_TRADE:.2f}")

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
                else:
                    print(f"❌ Order failed: {result.comment if result else 'Unknown error'}")
                
                print(f"{'='*60}\n")

    except KeyboardInterrupt:
        print("\n\n🛑 Bot stopped by user.")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Final status report
        print("\n" + "=" * 60)
        print("📊 Final Status Report")
        print("=" * 60)
        status = order_manager.get_status_report(SYMBOL)
        print(f"Pending Orders: {status['pending_orders']}")
        print(f"Open Positions: {status['open_positions']}")
        print(f"Managed Positions: {status['managed_positions']}")
        print("=" * 60)
        
        mt5.shutdown()
        print("✓ MetaTrader5 connection closed.")

if __name__ == "__main__":
    main()