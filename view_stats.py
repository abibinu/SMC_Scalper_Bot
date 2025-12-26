from trade_logger import TradeLogger

logger = TradeLogger()

# Last 7 days performance
logger.print_performance_report(days=7)

# Last 30 days performance
logger.print_performance_report(days=30)

# Export to CSV for Excel analysis
logger.export_to_csv("trades_export.csv")
print("✅ Data exported! Open trades_export.csv in Excel")