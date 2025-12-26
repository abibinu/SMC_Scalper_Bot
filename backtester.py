import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import json

class Backtester:
    """
    Backtests the SMC trading strategy on historical data.
    Validates strategy parameters and provides performance metrics.
    """
    
    def __init__(self, symbol, initial_balance=10000, risk_per_trade=0.005):
        """
        Initialize Backtester.
        
        Args:
            symbol: Trading symbol (e.g., "EURUSD")
            initial_balance: Starting capital
            risk_per_trade: Base risk per trade as decimal
        """
        self.symbol = symbol
        self.initial_balance = initial_balance
        self.current_balance = initial_balance
        self.risk_per_trade = risk_per_trade
        
        self.trades = []
        self.equity_curve = []
        self.daily_returns = []
        
    def fetch_historical_data(self, start_date, end_date, timeframe=mt5.TIMEFRAME_M1):
        """
        Fetch historical OHLC data from MT5.
        
        Args:
            start_date: Start date (datetime object)
            end_date: End date (datetime object)
            timeframe: MT5 timeframe constant
        
        Returns:
            DataFrame with OHLC data
        """
        rates = mt5.copy_rates_range(self.symbol, timeframe, start_date, end_date)
        
        if rates is None or len(rates) == 0:
            raise Exception(f"Failed to fetch historical data for {self.symbol}")
        
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        
        print(f"✅ Fetched {len(df)} candles from {start_date} to {end_date}")
        return df
    
    def detect_mss(self, df, index):
        """Detect MSS at a specific candle index."""
        if index < 3:
            return None, None
        
        # Look at last 20 candles for swing points
        lookback = min(20, index)
        window = df.iloc[max(0, index-lookback):index]
        
        window = window.copy()
        window['swing_high'] = (window['high'] > window['high'].shift(1)) & \
                                (window['high'] > window['high'].shift(-1))
        window['swing_low'] = (window['low'] < window['low'].shift(1)) & \
                               (window['low'] < window['low'].shift(-1))
        
        current_candle = df.iloc[index-1]
        
        swing_highs = window[window['swing_high']]
        swing_lows = window[window['swing_low']]
        
        if swing_highs.empty or swing_lows.empty:
            return None, None
        
        last_swing_high = swing_highs.iloc[-1]['high']
        last_swing_low = swing_lows.iloc[-1]['low']
        
        if current_candle['close'] > last_swing_high:
            return "bullish", current_candle['low']
        elif current_candle['close'] < last_swing_low:
            return "bearish", current_candle['high']
        
        return None, None
    
    def find_order_block(self, df, index, mss_type, lookback=20):
        """Find Order Block at a specific index."""
        if not mss_type or index < lookback:
            return None
        
        window = df.iloc[max(0, index-lookback):index]
        
        if mss_type == "bullish":
            bearish = window[window['close'] < window['open']]
            if bearish.empty:
                return None
            ob = bearish.iloc[-1]
            return {
                'type': 'bullish',
                'high': ob['high'],
                'low': ob['low'],
                'body_high': max(ob['open'], ob['close']),
                'body_low': min(ob['open'], ob['close'])
            }
        else:
            bullish = window[window['close'] > window['open']]
            if bullish.empty:
                return None
            ob = bullish.iloc[-1]
            return {
                'type': 'bearish',
                'high': ob['high'],
                'low': ob['low'],
                'body_high': max(ob['open'], ob['close']),
                'body_low': min(ob['open'], ob['close'])
            }
    
    def find_fvg(self, df, index):
        """Find FVG at specific index."""
        if index < 4:
            return None
        
        c1 = df.iloc[index-4]
        c2 = df.iloc[index-3]
        c3 = df.iloc[index-2]
        
        if c3['low'] > c1['high']:
            return {'type': 'bullish', 'high': c3['low'], 'low': c1['high']}
        elif c3['high'] < c1['low']:
            return {'type': 'bearish', 'high': c1['low'], 'low': c3['high']}
        
        return None
    
    def check_confluence(self, ob, fvg, min_overlap=40):
        """Check OB and FVG confluence."""
        if not ob or not fvg or ob['type'] != fvg['type']:
            return None
        
        overlap_high = min(ob['high'], fvg['high'])
        overlap_low = max(ob['low'], fvg['low'])
        
        if overlap_low >= overlap_high:
            return None
        
        overlap_size = overlap_high - overlap_low
        fvg_size = fvg['high'] - fvg['low']
        
        overlap_pct = (overlap_size / fvg_size * 100) if fvg_size > 0 else 0
        
        if overlap_pct < min_overlap:
            return None
        
        return {
            'overlap_pct': overlap_pct,
            'quality': 'high' if overlap_pct >= 70 else 'medium' if overlap_pct >= 50 else 'low'
        }
    
    def calculate_setup_quality(self, mss, ob, fvg, confluence):
        """Calculate setup quality score."""
        score = 0
        
        if mss:
            score += 25
        if ob:
            score += 25
        if fvg:
            score += 25
        if confluence:
            if confluence['quality'] == 'high':
                score += 25
            elif confluence['quality'] == 'medium':
                score += 20
            else:
                score += 15
        
        quality = 'EXCELLENT' if score >= 90 else 'GOOD' if score >= 75 else 'FAIR' if score >= 60 else 'POOR'
        
        return {'score': score, 'quality': quality}
    
    def get_entry_price(self, ob, fvg, confluence):
        """Determine entry price."""
        if confluence:
            if confluence['quality'] == 'high':
                overlap_high = min(ob['high'], fvg['high'])
                overlap_low = max(ob['low'], fvg['low'])
                return (overlap_high + overlap_low) / 2
        
        if ob:
            return ob['body_low'] if ob['type'] == 'bullish' else ob['body_high']
        
        return None
    
    def simulate_trade(self, df, signal_index, mss_type, entry, sl, tp, quality_score):
        """
        Simulate a trade execution and outcome.
        
        Returns:
            Trade outcome dictionary
        """
        # Risk management
        risk_multiplier = 1.5 if quality_score >= 90 else 1.3 if quality_score >= 85 else 1.1 if quality_score >= 75 else 1.0
        adjusted_risk = self.risk_per_trade * risk_multiplier
        
        risk_amount = self.current_balance * adjusted_risk
        sl_distance = abs(entry - sl)

        # Prevent division by zero or invalid SL distance
        point = 0.0001  # For EURUSD
        if sl_distance < point:
            return {
                'outcome': 'expired',
                'pnl': 0,
                'pips': 0,
                'bars_to_fill': None
            }

        # Calculate lot size (simplified)
        lot_size = risk_amount / (sl_distance / point * 10)  # Simplified calculation
        
        # Look ahead to see if order would be filled
        max_lookback = 60  # Look 60 candles ahead (1 hour on M1)
        filled = False
        fill_index = None
        
        for i in range(signal_index, min(signal_index + max_lookback, len(df))):
            candle = df.iloc[i]
            
            # Check if limit order would be filled
            if mss_type == "bullish":
                if candle['low'] <= entry:
                    filled = True
                    fill_index = i
                    break
            else:
                if candle['high'] >= entry:
                    filled = True
                    fill_index = i
                    break
        
        if not filled:
            return {
                'outcome': 'expired',
                'pnl': 0,
                'pips': 0,
                'bars_to_fill': None
            }
        
        # Simulate trade progression
        bars_to_fill = fill_index - signal_index
        
        for i in range(fill_index, min(fill_index + 200, len(df))):  # Max 200 candles (3+ hours)
            candle = df.iloc[i]
            
            # Check if SL hit
            if mss_type == "bullish":
                if candle['low'] <= sl:
                    pnl = -risk_amount
                    pips = -abs(entry - sl) * 10000
                    return {
                        'outcome': 'loss',
                        'pnl': pnl,
                        'pips': pips,
                        'bars_to_fill': bars_to_fill,
                        'bars_held': i - fill_index,
                        'exit_price': sl
                    }
                # Check if TP hit
                if candle['high'] >= tp:
                    pnl = abs(tp - entry) / abs(entry - sl) * risk_amount
                    pips = abs(tp - entry) * 10000
                    return {
                        'outcome': 'win',
                        'pnl': pnl,
                        'pips': pips,
                        'bars_to_fill': bars_to_fill,
                        'bars_held': i - fill_index,
                        'exit_price': tp
                    }
            else:
                if candle['high'] >= sl:
                    pnl = -risk_amount
                    pips = -abs(sl - entry) * 10000
                    return {
                        'outcome': 'loss',
                        'pnl': pnl,
                        'pips': pips,
                        'bars_to_fill': bars_to_fill,
                        'bars_held': i - fill_index,
                        'exit_price': sl
                    }
                if candle['low'] <= tp:
                    pnl = abs(entry - tp) / abs(sl - entry) * risk_amount
                    pips = abs(entry - tp) * 10000
                    return {
                        'outcome': 'win',
                        'pnl': pnl,
                        'pips': pips,
                        'bars_to_fill': bars_to_fill,
                        'bars_held': i - fill_index,
                        'exit_price': tp
                    }
        
        # Trade didn't hit SL or TP within time limit
        return {
            'outcome': 'timeout',
            'pnl': 0,
            'pips': 0,
            'bars_to_fill': bars_to_fill
        }
    
    def run_backtest(self, start_date, end_date, config=None):
        """
        Run complete backtest over date range.
        
        Args:
            start_date: Start date
            end_date: End date
            config: Optional config dict with strategy parameters
        
        Returns:
            Backtest results dictionary
        """
        print(f"\n{'='*70}")
        print(f"🔬 STARTING BACKTEST")
        print(f"{'='*70}")
        print(f"Symbol: {self.symbol}")
        print(f"Period: {start_date.date()} to {end_date.date()}")
        print(f"Initial Balance: ${self.initial_balance:,.2f}")
        print(f"{'='*70}\n")
        
        # Fetch data
        df = self.fetch_historical_data(start_date, end_date)
        
        # Config
        min_quality = config.get('min_quality', 70) if config else 70
        min_confluence = config.get('min_confluence', 40) if config else 40
        require_confluence = config.get('require_confluence', True) if config else True
        
        # Reset state
        self.current_balance = self.initial_balance
        self.trades = []
        self.equity_curve = [self.initial_balance]
        
        signals_found = 0
        trades_taken = 0
        
        # Scan through data
        for i in range(50, len(df) - 200):  # Need buffer on both sides
            # Detect MSS
            mss_type, sl = self.detect_mss(df, i)
            
            if not mss_type:
                continue
            
            signals_found += 1
            
            # Find OB and FVG
            ob = self.find_order_block(df, i, mss_type)
            fvg = self.find_fvg(df, i)
            
            # Check confluence
            confluence = self.check_confluence(ob, fvg, min_confluence)
            
            if require_confluence and not confluence:
                continue
            
            # Quality check
            quality = self.calculate_setup_quality(mss_type, ob, fvg, confluence)
            
            if quality['score'] < min_quality:
                continue
            
            # Get entry
            entry = self.get_entry_price(ob, fvg, confluence)
            if not entry:
                continue
            
            # Calculate TP
            risk = abs(entry - sl)
            rr_ratio = 3.0 if quality['score'] >= 90 else 2.5 if quality['score'] >= 75 else 2.0
            
            if mss_type == "bullish":
                tp = entry + (risk * rr_ratio)
            else:
                tp = entry - (risk * rr_ratio)
            
            # Simulate trade
            result = self.simulate_trade(df, i, mss_type, entry, sl, tp, quality['score'])
            
            if result['outcome'] in ['win', 'loss']:
                trades_taken += 1
                
                # Update balance
                self.current_balance += result['pnl']
                self.equity_curve.append(self.current_balance)
                
                # Record trade
                trade_record = {
                    'date': df.iloc[i]['time'],
                    'direction': mss_type,
                    'entry': entry,
                    'sl': sl,
                    'tp': tp,
                    'quality_score': quality['score'],
                    'quality': quality['quality'],
                    'rr_ratio': rr_ratio,
                    **result
                }
                self.trades.append(trade_record)
            
            # Progress update every 1000 candles
            if i % 1000 == 0:
                print(f"Progress: {i}/{len(df)} candles | Balance: ${self.current_balance:,.2f}")
        
        # Calculate metrics
        results = self.calculate_metrics()
        results['signals_found'] = signals_found
        results['trades_taken'] = trades_taken
        
        return results
    
    def calculate_metrics(self):
        """Calculate comprehensive backtest metrics."""
        if not self.trades:
            return {'error': 'No trades taken'}
        
        df_trades = pd.DataFrame(self.trades)
        
        # Basic stats
        total_trades = len(df_trades)
        wins = df_trades[df_trades['outcome'] == 'win']
        losses = df_trades[df_trades['outcome'] == 'loss']
        
        win_count = len(wins)
        loss_count = len(losses)
        win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0
        
        # P&L
        total_pnl = df_trades['pnl'].sum()
        total_return_pct = ((self.current_balance - self.initial_balance) / self.initial_balance) * 100
        
        # Win/Loss stats
        avg_win = wins['pnl'].mean() if len(wins) > 0 else 0
        avg_loss = losses['pnl'].mean() if len(losses) > 0 else 0
        best_trade = df_trades['pnl'].max()
        worst_trade = df_trades['pnl'].min()
        
        # Profit factor
        gross_profit = wins['pnl'].sum() if len(wins) > 0 else 0
        gross_loss = abs(losses['pnl'].sum()) if len(losses) > 0 else 0
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 0
        
        # Drawdown
        equity = pd.Series(self.equity_curve)
        running_max = equity.expanding().max()
        drawdown = (equity - running_max) / running_max * 100
        max_drawdown = drawdown.min()
        
        # Sharpe ratio (simplified)
        returns = equity.pct_change().dropna()
        sharpe = (returns.mean() / returns.std() * np.sqrt(252)) if len(returns) > 1 else 0
        
        # Quality score correlation
        avg_quality_score = df_trades['quality_score'].mean()
        
        return {
            'total_trades': total_trades,
            'win_count': win_count,
            'loss_count': loss_count,
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'total_return_pct': total_return_pct,
            'final_balance': self.current_balance,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'best_trade': best_trade,
            'worst_trade': worst_trade,
            'profit_factor': profit_factor,
            'max_drawdown_pct': max_drawdown,
            'sharpe_ratio': sharpe,
            'avg_quality_score': avg_quality_score,
            'avg_rr_ratio': df_trades['rr_ratio'].mean()
        }
    
    def print_results(self, results):
        """Print formatted backtest results."""
        print(f"\n{'='*70}")
        print(f"📈 BACKTEST RESULTS")
        print(f"{'='*70}")
        
        if 'error' in results:
            print(f"❌ {results['error']}")
            return
        
        print(f"Signals Found: {results['signals_found']}")
        print(f"Trades Taken: {results['total_trades']} ({results['total_trades']/results['signals_found']*100:.1f}% of signals)")
        print(f"\n💰 Performance:")
        print(f"   Initial Balance: ${self.initial_balance:,.2f}")
        print(f"   Final Balance: ${results['final_balance']:,.2f}")
        print(f"   Total P&L: ${results['total_pnl']:+,.2f}")
        print(f"   Return: {results['total_return_pct']:+.2f}%")
        
        print(f"\n📊 Win Rate:")
        print(f"   Wins: {results['win_count']}")
        print(f"   Losses: {results['loss_count']}")
        print(f"   Win Rate: {results['win_rate']:.1f}%")
        
        print(f"\n💵 Trade Stats:")
        print(f"   Avg Win: ${results['avg_win']:,.2f}")
        print(f"   Avg Loss: ${results['avg_loss']:,.2f}")
        print(f"   Best Trade: ${results['best_trade']:,.2f}")
        print(f"   Worst Trade: ${results['worst_trade']:,.2f}")
        print(f"   Profit Factor: {results['profit_factor']:.2f}")
        
        print(f"\n📉 Risk Metrics:")
        print(f"   Max Drawdown: {results['max_drawdown_pct']:.2f}%")
        print(f"   Sharpe Ratio: {results['sharpe_ratio']:.2f}")
        
        print(f"\n⭐ Quality Metrics:")
        print(f"   Avg Setup Score: {results['avg_quality_score']:.0f}/100")
        print(f"   Avg R:R Ratio: {results['avg_rr_ratio']:.2f}")
        
        print(f"{'='*70}\n")
    
    def export_results(self, filename="backtest_results.json"):
        """Export backtest results and trades to JSON."""
        results = self.calculate_metrics()
        
        output = {
            'config': {
                'symbol': self.symbol,
                'initial_balance': self.initial_balance,
                'risk_per_trade': self.risk_per_trade
            },
            'results': results,
            'trades': self.trades,
            'equity_curve': self.equity_curve
        }
        
        with open(filename, 'w') as f:
            json.dump(output, f, indent=2, default=str)
        
        print(f"✅ Results exported to {filename}")


# Example usage
if __name__ == "__main__":
    # Initialize MT5
    if not mt5.initialize():
        print("MT5 initialization failed")
        exit()
    
    # Create backtester
    backtester = Backtester(symbol="EURUSD", initial_balance=10000)
    
    # Define backtest period
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)  # Last 30 days
    
    # Run backtest
    config = {
        'min_quality': 70,
        'min_confluence': 40,
        'require_confluence': True
    }
    
    results = backtester.run_backtest(start_date, end_date, config)
    
    # Print results
    backtester.print_results(results)
    
    # Export
    backtester.export_results()
    
    mt5.shutdown()
