# -- Constants -- 
SYMBOL = "EURUSD"
RISK_PER_TRADE = 0.005 # 0.5% base risk (will be multiplied 0.5x-1.5x based on quality)
MAGIC_NUMBER = 123456
MAX_SPREAD_PIPS = 4.0  # Tighter spread requirement

# -- Trading Session Times (UTC) --
LONDON_SESSION_START = "08:00"  # Avoid London open volatility
LONDON_SESSION_END = "16:00"
NEW_YORK_SESSION_START = "13:30"  # Avoid NY open volatility
NEW_YORK_SESSION_END = "20:00"

# -- Order Management Settings --
MAX_ORDER_AGE_MINUTES = 20  # Shorter expiry for faster-moving M1
BREAKEVEN_TRIGGER_RR = 1.0  # Move SL to breakeven after 1:1 reward
ORDER_MANAGEMENT_CHECK_INTERVAL = 30

# -- Order Block Settings --
OB_LOOKBACK_CANDLES = 30  # Increased for better OB identification
MIN_CONFLUENCE_OVERLAP = 40  # Higher minimum for quality (40-100)
REQUIRE_CONFLUENCE = True  # ALWAYS require OB+FVG confluence
MIN_SETUP_QUALITY_SCORE = 70  # Increased from 60 - be more selective

# -- Multi-Timeframe (MTF) Settings --
ENABLE_MTF_CONFIRMATION = True
MTF_TIMEFRAMES = ["M5", "M15"]  # Check M5 and M15 alignment
REQUIRE_ALL_TF_ALIGNED = False  # At least 50% must align
MTF_MIN_ALIGNMENT_PCT = 50  # Minimum 50% of timeframes aligned
MTF_SCORE_BONUS = True

# -- Breaker Block (BB) Settings --
ENABLE_BREAKER_BLOCKS = True
BB_LOOKBACK_CANDLES = 100  # Increased for more historical context
BB_SCORE_BONUS = True
BB_MIN_QUALITY = "medium"

# -- Volume & Volatility Filters --
MIN_VOLUME_RATIO = 0.6  # Must be 60% of average volume (avoid dead markets)
MIN_ATR_PIPS = 2.5  # Minimum 2.5 pips ATR (avoid low volatility)
MAX_ATR_PIPS = 15.0  # Maximum 15 pips ATR (avoid extreme volatility)

# -- Dynamic Risk Management --
ENABLE_DYNAMIC_RISK = True  # Scale position size based on setup quality
MIN_RISK_MULTIPLIER = 0.5  # Poor setups: 0.5x base risk
MAX_RISK_MULTIPLIER = 1.5  # Excellent setups: 1.5x base risk

# -- Dynamic Take Profit --
ENABLE_DYNAMIC_TP = True  # Adjust TP based on setup quality
MIN_RR_RATIO = 2.0  # Minimum 1:2 R:R
MAX_RR_RATIO = 3.0  # Maximum 1:3 R:R (for excellent setups)

# -- Telegram Notifications --
ENABLE_TELEGRAM = True
TELEGRAM_NOTIFY_SIGNALS = True
TELEGRAM_NOTIFY_TRADES = True
TELEGRAM_NOTIFY_FILLS = True
TELEGRAM_NOTIFY_BREAKEVEN = True
TELEGRAM_NOTIFY_CLOSES = True
TELEGRAM_NOTIFY_SKIPS = False  # Keep false to reduce noise
TELEGRAM_DAILY_SUMMARY = True

# -- MT5 Credentials --
# Set these environment variables:
# MT5_ACCOUNT
# MT5_PASSWORD
# MT5_SERVER

# -- Telegram Credentials --
# Set these environment variables:
# TELEGRAM_BOT_TOKEN 
# TELEGRAM_CHAT_ID

# -- Advanced Filters (New) --
AVOID_HIGH_IMPACT_NEWS = True  # Skip trades during major news
NEWS_BUFFER_MINUTES = 30  # Minutes before/after news to avoid