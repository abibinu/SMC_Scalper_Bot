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
ORDER_MANAGEMENT_CHECK_INTERVAL = 30  # Check orders every 60 seconds

# -- Order Block Settings --
OB_LOOKBACK_CANDLES = 20  # How many candles to look back for Order Blocks
MIN_CONFLUENCE_OVERLAP = 30  # Minimum overlap % between OB and FVG (30-100)
REQUIRE_CONFLUENCE = False  # If True, only trade when OB+FVG confluence exists
MIN_SETUP_QUALITY_SCORE = 60  # Minimum quality score to take trade (0-100)

# -- Multi-Timeframe (MTF) Settings --
ENABLE_MTF_CONFIRMATION = True  # Enable multi-timeframe analysis
MTF_TIMEFRAMES = ["M5", "M15"]  # Timeframes to check (options: M5, M15, M30, H1)
REQUIRE_ALL_TF_ALIGNED = False  # If True, all timeframes must align (stricter)
MTF_MIN_ALIGNMENT_PCT = 50  # Minimum % of timeframes that must align (0-100)
MTF_SCORE_BONUS = True  # Add bonus score for MTF alignment

# -- Breaker Block (BB) Settings --
ENABLE_BREAKER_BLOCKS = True  # Enable Breaker Block detection
BB_LOOKBACK_CANDLES = 50  # How many candles to look back for BBs
BB_SCORE_BONUS = True  # Add bonus score for BB confluence
BB_MIN_QUALITY = "medium"  # Minimum BB quality to consider (options: "high", "medium")

# -- Telegram Notifications --
ENABLE_TELEGRAM = True  # Enable Telegram notifications
TELEGRAM_NOTIFY_SIGNALS = True  # Notify on new signals
TELEGRAM_NOTIFY_TRADES = True  # Notify on trade placements
TELEGRAM_NOTIFY_FILLS = True  # Notify when orders fill
TELEGRAM_NOTIFY_BREAKEVEN = True  # Notify when SL moved to BE
TELEGRAM_NOTIFY_CLOSES = True  # Notify when positions close
TELEGRAM_NOTIFY_SKIPS = False  # Notify when signals are skipped (can be noisy)
TELEGRAM_DAILY_SUMMARY = True  # Send daily summary at end of NY session

# -- MT5 Credentials --
# It is mandatory to set the following environment variables:
# MT5_ACCOUNT
# MT5_PASSWORD
# MT5_SERVER

# -- Telegram Credentials --
# To enable Telegram notifications, set these environment variables:
# TELEGRAM_BOT_TOKEN 
# TELEGRAM_CHAT_ID 