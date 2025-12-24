# -- Constants -- 
SYMBOL = "EURUSD"
RISK_PER_TRADE = 0.005 # 0.5% risk per trade
MAGIC_NUMBER = 123456
MAX_SPREAD_PIPS = 1.5

# -- Trading Session Times (UTC) --
LONDON_SESSION_START = "07:00"
LONDON_SESSION_END = "16:00"
NEW_YORK_SESSION_START = "12:00"
NEW_YORK_SESSION_END = "21:00"

# -- Order Management Settings --
MAX_ORDER_AGE_MINUTES = 30  # Cancel pending orders older than this
BREAKEVEN_TRIGGER_RR = 1.0  # Move SL to breakeven after 1:1 reward is reached
ORDER_MANAGEMENT_CHECK_INTERVAL = 60  # Check orders every 60 seconds

# -- Order Block Settings --
OB_LOOKBACK_CANDLES = 20  # How many candles to look back for Order Blocks
MIN_CONFLUENCE_OVERLAP = 30  # Minimum overlap % between OB and FVG (30-100)
REQUIRE_CONFLUENCE = False  # If True, only trade when OB+FVG confluence exists
MIN_SETUP_QUALITY_SCORE = 65  # Minimum quality score to take trade (0-100)

# -- Multi-Timeframe (MTF) Settings --
ENABLE_MTF_CONFIRMATION = True  # Enable multi-timeframe analysis
MTF_TIMEFRAMES = ["M5"]  # Timeframes to check (options: M5, M15, M30, H1)
REQUIRE_ALL_TF_ALIGNED = False  # If True, all timeframes must align (stricter)
MTF_MIN_ALIGNMENT_PCT = 30  # Minimum % of timeframes that must align (0-100)
MTF_SCORE_BONUS = True  # Add bonus score for MTF alignment

# -- MT5 Credentials --
# It is mandatory to set the following environment variables:
# MT5_ACCOUNT
# MT5_PASSWORD
# MT5_SERVER