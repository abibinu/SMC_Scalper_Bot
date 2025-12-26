import MetaTrader5 as mt5
from datetime import datetime, timedelta
from backtester import Backtester

def main():
    # Initialize MT5
    if not mt5.initialize():
        print("❌ MT5 initialization failed")
        return
    
    # Create backtester
    backtester = Backtester(
        symbol="EURUSD",
        initial_balance=10000,
        risk_per_trade=0.005
    )
    
    # Define test period
    end_date = datetime.now()
    start_date = end_date - timedelta(days=60)  # Test last 60 days
    
    # Configure strategy parameters
    config = {
        'min_quality': 70,
        'min_confluence': 40,
        'require_confluence': True
    }
    
    print("\n🔬 Starting Backtest...")
    print(f"Testing {(end_date - start_date).days} days of data\n")
    
    # Run backtest
    results = backtester.run_backtest(start_date, end_date, config)
    
    # Print results
    backtester.print_results(results)
    
    # Export for analysis
    backtester.export_results("backtest_results.json")
    
    # Cleanup
    mt5.shutdown()

if __name__ == "__main__":
    main()