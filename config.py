# -- Constants -- 
SYMBOL = "EURUSD"
RISK_PER_TRADE = 0.005 # 0.5% base risk (will be multiplied 0.5x-1.5x based on quality)
MAGIC_NUMBER = 123456
MAX_SPREAD_PIPS = 4.0  # Tighter spread requirement

# -- Trading Session Times (UTC) --
LONDON_SESSION_START = "08:00"
LONDON_SESSION_END = "16:00"
NEW_YORK_SESSION_START = "13:30"
NEW_YORK_SESSION_END = "20:00"

# -- Order Management Settings --
MAX_ORDER_AGE_MINUTES = 20
BREAKEVEN_TRIGGER_RR = 1.0
ORDER_MANAGEMENT_CHECK_INTERVAL = 30

# -- Order Block Settings --
OB_LOOKBACK_CANDLES = 30
MIN_CONFLUENCE_OVERLAP = 40
REQUIRE_CONFLUENCE = True
MIN_SETUP_QUALITY_SCORE = 70

# -- Multi-Timeframe (MTF) Settings --
ENABLE_MTF_CONFIRMATION = True
MTF_TIMEFRAMES = ["M5", "M15"]
REQUIRE_ALL_TF_ALIGNED = False
MTF_MIN_ALIGNMENT_PCT = 50
MTF_SCORE_BONUS = True

# -- Breaker Block (BB) Settings --
ENABLE_BREAKER_BLOCKS = True
BB_LOOKBACK_CANDLES = 100
BB_SCORE_BONUS = True
BB_MIN_QUALITY = "medium"

# -- Volume & Volatility Filters --
MIN_VOLUME_RATIO = 0.6
MIN_ATR_PIPS = 3.0
MAX_ATR_PIPS = 20.0

# -- Dynamic Risk Management --
ENABLE_DYNAMIC_RISK = True
MIN_RISK_MULTIPLIER = 0.5
MAX_RISK_MULTIPLIER = 1.5

# -- Dynamic Take Profit --
ENABLE_DYNAMIC_TP = True
MIN_RR_RATIO = 2.0
MAX_RR_RATIO = 3.0

# -- Telegram Notifications --
ENABLE_TELEGRAM = True
TELEGRAM_NOTIFY_SIGNALS = True
TELEGRAM_NOTIFY_TRADES = True
TELEGRAM_NOTIFY_FILLS = True
TELEGRAM_NOTIFY_BREAKEVEN = True
TELEGRAM_NOTIFY_CLOSES = True
TELEGRAM_NOTIFY_SKIPS = False
TELEGRAM_DAILY_SUMMARY = True

# ============================================================================
# NEW: RISK MANAGEMENT SETTINGS
# ============================================================================

# -- Daily/Weekly Drawdown Protection --
ENABLE_RISK_MANAGER = True
MAX_DAILY_LOSS_PCT = 0.03  # Stop trading after 3% daily loss
MAX_WEEKLY_LOSS_PCT = 0.05  # Stop trading after 5% weekly loss
MAX_DAILY_TRADES = 20  # Maximum trades per day

# -- Risk State File --
RISK_STATE_FILE = "risk_state.json"

# ============================================================================
# NEW: NEWS CALENDAR SETTINGS
# ============================================================================

# -- News Avoidance --
AVOID_HIGH_IMPACT_NEWS = True
NEWS_BUFFER_MINUTES = 30  # Minutes before/after news to avoid trading
NEWS_CACHE_FILE = "news_cache.json"

# -- News Calendar Source --
# Options: 'forexfactory' (requires scraping), 'manual' (fallback)
NEWS_SOURCE = 'forexfactory'

# -- Manual News Times (UTC) - Fallback if API fails --
MANUAL_NEWS_TIMES = [
    ("08:30", "09:00"),   # EUR economic data
    ("12:30", "13:30"),   # US economic data (NFP, CPI, etc.)
    ("14:00", "16:00"),   # FOMC meetings/minutes
]

# ============================================================================
# NEW: TRADE LOGGING SETTINGS
# ============================================================================

# -- Database Logging --
ENABLE_TRADE_LOGGING = True
TRADE_DB_PATH = "trades.db"

# -- Performance Reporting --
AUTO_CALCULATE_DAILY_PERFORMANCE = True
PERFORMANCE_REPORT_DAYS = 7  # Days to include in reports

# -- CSV Export --
AUTO_EXPORT_CSV = False  # Set to True to auto-export trades daily
CSV_EXPORT_PATH = "trades_export.csv"

# ============================================================================
# NEW: BACKTESTING SETTINGS
# ============================================================================

# -- Backtest Configuration --
BACKTEST_INITIAL_BALANCE = 10000
BACKTEST_LOOKBACK_DAYS = 30  # Test last N days

# -- Backtest Output --
BACKTEST_RESULTS_FILE = "backtest_results.json"

# ============================================================================
# ENVIRONMENT VARIABLES (Required in .env file)
# ============================================================================

# MT5_ACCOUNT
# MT5_PASSWORD
# MT5_SERVER

# TELEGRAM_BOT_TOKEN 
# TELEGRAM_CHAT_ID

# ============================================================================
# VALIDATION RULES
# ============================================================================

def validate_config():
    """Validate configuration settings."""
    errors = []
    
    if MAX_DAILY_LOSS_PCT <= 0 or MAX_DAILY_LOSS_PCT > 0.1:
        errors.append("MAX_DAILY_LOSS_PCT should be between 0 and 0.1 (0-10%)")
    
    if MAX_WEEKLY_LOSS_PCT <= 0 or MAX_WEEKLY_LOSS_PCT > 0.2:
        errors.append("MAX_WEEKLY_LOSS_PCT should be between 0 and 0.2 (0-20%)")
    
    if MAX_DAILY_LOSS_PCT >= MAX_WEEKLY_LOSS_PCT:
        errors.append("MAX_WEEKLY_LOSS_PCT should be greater than MAX_DAILY_LOSS_PCT")
    
    if NEWS_BUFFER_MINUTES < 15 or NEWS_BUFFER_MINUTES > 120:
        errors.append("NEWS_BUFFER_MINUTES should be between 15 and 120 minutes")
    
    if MIN_SETUP_QUALITY_SCORE < 0 or MIN_SETUP_QUALITY_SCORE > 100:
        errors.append("MIN_SETUP_QUALITY_SCORE should be between 0 and 100")
    
    if errors:
        print("⚠️  Configuration Validation Errors:")
        for error in errors:
            print(f"   - {error}")
        return False
    
    print("✅ Configuration validated successfully")
    return True

if __name__ == "__main__":
    validate_config()