import MetaTrader5 as mt5
import os
from dotenv import load_dotenv
from config import MAX_SPREAD_PIPS

load_dotenv()

def mt5_connect():
    """Initializes connection to the MetaTrader 5 terminal."""
    mt5_account = int(os.getenv("MT5_ACCOUNT"))
    mt5_password = os.getenv("MT5_PASSWORD")
    mt5_server = os.getenv("MT5_SERVER")

    if not mt5.initialize(login=mt5_account, password=mt5_password, server=mt5_server):
        raise Exception(f"initialize() failed, error code = {mt5.last_error()}")

def verify_demo_account():
    """Verifies that the account is a demo account."""
    account_info = mt5.account_info()
    if account_info.trade_mode != mt5.ACCOUNT_TRADE_MODE_DEMO:
        raise Exception("This bot is intended to run on a demo account only.")

def check_spread(symbol):
    """Checks if the current spread is within the acceptable range."""
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        print(f"Failed to get symbol info for {symbol}")
        return False
    spread = (symbol_info.ask - symbol_info.bid) / symbol_info.point
    return spread <= MAX_SPREAD_PIPS

def calculate_lot_size(account_balance, risk_per_trade, stop_loss_pips, symbol):
    """Calculates the lot size based on risk percentage and stop loss distance in pips."""
    risk_amount = account_balance * risk_per_trade
    
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        print(f"Failed to get symbol info for {symbol}")
        return None
        
    point = symbol_info.point
    tick_value = symbol_info.trade_tick_value
    
    lot_size = risk_amount / (stop_loss_pips * tick_value)

    # Adjust lot size to symbol's volume constraints
    volume_min = symbol_info.volume_min
    volume_max = symbol_info.volume_max
    volume_step = symbol_info.volume_step

    lot_size = max(volume_min, lot_size)
    lot_size = min(volume_max, lot_size)
    
    lot_size = round(lot_size / volume_step) * volume_step
    
    return round(lot_size, 2)

def execute_limit_order(order_type, symbol, lot_size, price, sl, tp, magic_number):
    """Executes a limit order on the MT5 terminal."""
    request = {
        "action": mt5.TRADE_ACTION_PENDING,
        "symbol": symbol,
        "volume": lot_size,
        "type": order_type,
        "price": price,
        "sl": sl,
        "tp": tp,
        "magic": magic_number,
        "comment": "SMC_BOT",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_RETURN,
    }
    
    result = mt5.order_send(request)
    return result

def is_position_open(symbol):
    """Checks if there is an open position for a given symbol."""
    positions = mt5.positions_get(symbol=symbol)
    return len(positions) > 0
