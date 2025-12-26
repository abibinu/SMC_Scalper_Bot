import sqlite3
from datetime import datetime
import json
import pandas as pd
from pathlib import Path

class TradeLogger:
    """
    Logs all trades to SQLite database for analysis and backtesting validation.
    Tracks setup quality, outcomes, and performance metrics.
    """
    
    def __init__(self, db_path="trades.db"):
        """
        Initialize Trade Logger.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._create_tables()
    
    def _create_tables(self):
        """Create database tables if they don't exist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Trades table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_number INTEGER UNIQUE NOT NULL,
                symbol TEXT NOT NULL,
                direction TEXT NOT NULL,
                entry_price REAL NOT NULL,
                stop_loss REAL NOT NULL,
                take_profit REAL NOT NULL,
                lot_size REAL NOT NULL,
                
                -- Trade outcome
                status TEXT NOT NULL, -- 'pending', 'active', 'closed', 'cancelled'
                exit_price REAL,
                pnl REAL,
                pnl_pct REAL,
                pips REAL,
                outcome TEXT, -- 'win', 'loss', 'breakeven'
                
                -- Setup quality metrics
                setup_score INTEGER,
                quality_rating TEXT,
                ob_present BOOLEAN,
                fvg_present BOOLEAN,
                confluence_pct REAL,
                confluence_quality TEXT,
                
                -- Multi-timeframe data
                mtf_enabled BOOLEAN,
                mtf_alignment_pct REAL,
                mtf_strength TEXT,
                
                -- Breaker block data
                bb_confluence BOOLEAN,
                bb_quality TEXT,
                
                -- Risk metrics
                risk_amount REAL,
                risk_pct REAL,
                risk_multiplier REAL,
                rr_ratio REAL,
                
                -- Market conditions
                atr_pips REAL,
                volume_ratio REAL,
                spread_pips REAL,
                
                -- Timestamps
                signal_time TEXT NOT NULL,
                order_placed_time TEXT NOT NULL,
                order_filled_time TEXT,
                order_closed_time TEXT,
                
                -- Additional notes
                notes TEXT,
                
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')
        
        # Daily performance table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT UNIQUE NOT NULL,
                starting_balance REAL NOT NULL,
                ending_balance REAL NOT NULL,
                total_trades INTEGER DEFAULT 0,
                winning_trades INTEGER DEFAULT 0,
                losing_trades INTEGER DEFAULT 0,
                breakeven_trades INTEGER DEFAULT 0,
                total_pnl REAL DEFAULT 0,
                total_pnl_pct REAL DEFAULT 0,
                win_rate REAL DEFAULT 0,
                avg_win REAL DEFAULT 0,
                avg_loss REAL DEFAULT 0,
                largest_win REAL DEFAULT 0,
                largest_loss REAL DEFAULT 0,
                profit_factor REAL DEFAULT 0,
                max_drawdown_pct REAL DEFAULT 0,
                
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        ''')
        
        # Weekly performance table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS weekly_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                week_start_date TEXT NOT NULL,
                week_number INTEGER NOT NULL,
                year INTEGER NOT NULL,
                starting_balance REAL NOT NULL,
                ending_balance REAL NOT NULL,
                total_trades INTEGER DEFAULT 0,
                winning_trades INTEGER DEFAULT 0,
                losing_trades INTEGER DEFAULT 0,
                total_pnl REAL DEFAULT 0,
                total_pnl_pct REAL DEFAULT 0,
                win_rate REAL DEFAULT 0,
                
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(week_number, year)
            )
        ''')
        
        conn.commit()
        conn.close()
        print(f"✅ Trade logging database initialized: {self.db_path}")
    
    def log_trade_signal(self, ticket_number, symbol, direction, entry_price, 
                        stop_loss, take_profit, lot_size, setup_analysis,
                        mtf_alignment=None, bb_confluence=None, 
                        risk_amount=0, risk_pct=0, risk_multiplier=1.0,
                        rr_ratio=2.0, atr_pips=0, volume_ratio=1.0, spread_pips=0):
        """
        Log a new trade when order is placed.
        
        Args:
            All trade setup parameters and metrics
        
        Returns:
            True if logged successfully
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        now = datetime.utcnow().isoformat()
        
        try:
            cursor.execute('''
                INSERT INTO trades (
                    ticket_number, symbol, direction, entry_price, stop_loss, take_profit, lot_size,
                    status, setup_score, quality_rating,
                    ob_present, fvg_present, confluence_pct, confluence_quality,
                    mtf_enabled, mtf_alignment_pct, mtf_strength,
                    bb_confluence, bb_quality,
                    risk_amount, risk_pct, risk_multiplier, rr_ratio,
                    atr_pips, volume_ratio, spread_pips,
                    signal_time, order_placed_time, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                ticket_number, symbol, direction, entry_price, stop_loss, take_profit, lot_size,
                'pending', setup_analysis.get('score', 0), setup_analysis.get('quality', 'N/A'),
                setup_analysis.get('ob_present', False), setup_analysis.get('fvg_present', False),
                setup_analysis.get('confluence_pct', 0), setup_analysis.get('confluence_quality', None),
                mtf_alignment is not None, 
                mtf_alignment.get('alignment_pct', 0) if mtf_alignment else 0,
                mtf_alignment.get('strength', None) if mtf_alignment else None,
                bb_confluence is not None,
                bb_confluence.get('quality', None) if bb_confluence else None,
                risk_amount, risk_pct, risk_multiplier, rr_ratio,
                atr_pips, volume_ratio, spread_pips,
                now, now, now, now
            ))
            
            conn.commit()
            print(f"✅ Trade logged: Ticket #{ticket_number}")
            return True
            
        except sqlite3.IntegrityError:
            print(f"⚠️  Trade #{ticket_number} already exists in database")
            return False
        except Exception as e:
            print(f"❌ Failed to log trade: {e}")
            return False
        finally:
            conn.close()
    
    def update_trade_status(self, ticket_number, status, exit_price=None, 
                           pnl=None, outcome=None):
        """
        Update trade status when filled, modified, or closed.
        
        Args:
            ticket_number: MT5 ticket number
            status: 'active', 'closed', 'cancelled'
            exit_price: Exit price if closed
            pnl: Profit/loss amount
            outcome: 'win', 'loss', 'breakeven'
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        now = datetime.utcnow().isoformat()
        
        try:
            # Build update query dynamically
            updates = ["status = ?", "updated_at = ?"]
            values = [status, now]
            
            if status == 'active':
                updates.append("order_filled_time = ?")
                values.append(now)
            
            if status == 'closed' and exit_price is not None:
                updates.extend([
                    "order_closed_time = ?",
                    "exit_price = ?",
                    "pnl = ?",
                    "outcome = ?"
                ])
                values.extend([now, exit_price, pnl, outcome])
                
                # Calculate pips and pnl_pct
                cursor.execute("SELECT entry_price, stop_loss, risk_amount FROM trades WHERE ticket_number = ?", 
                             (ticket_number,))
                result = cursor.fetchone()
                if result:
                    entry_price, stop_loss, risk_amount = result
                    pips = abs(exit_price - entry_price) * 10000  # Forex calculation
                    if outcome == 'loss':
                        pips = -pips
                    
                    pnl_pct = (pnl / risk_amount * 100) if risk_amount > 0 else 0
                    
                    updates.extend(["pips = ?", "pnl_pct = ?"])
                    values.extend([pips, pnl_pct])
            
            values.append(ticket_number)
            
            query = f"UPDATE trades SET {', '.join(updates)} WHERE ticket_number = ?"
            cursor.execute(query, values)
            
            conn.commit()
            print(f"✅ Trade #{ticket_number} updated: {status}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to update trade: {e}")
            return False
        finally:
            conn.close()
    
    def calculate_daily_performance(self, date=None):
        """
        Calculate and store daily performance metrics.
        
        Args:
            date: Date to calculate (default: today)
        """
        if date is None:
            date = datetime.now().date().isoformat()
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Get all closed trades for the day
            cursor.execute('''
                SELECT pnl, outcome, risk_amount 
                FROM trades 
                WHERE DATE(order_closed_time) = ? AND status = 'closed'
            ''', (date,))
            
            trades = cursor.fetchall()
            
            if not trades:
                print(f"ℹ️  No closed trades for {date}")
                return
            
            total_trades = len(trades)
            winning_trades = sum(1 for t in trades if t[1] == 'win')
            losing_trades = sum(1 for t in trades if t[1] == 'loss')
            breakeven_trades = sum(1 for t in trades if t[1] == 'breakeven')
            
            total_pnl = sum(t[0] for t in trades)
            win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0
            
            wins = [t[0] for t in trades if t[1] == 'win']
            losses = [t[0] for t in trades if t[1] == 'loss']
            
            avg_win = sum(wins) / len(wins) if wins else 0
            avg_loss = sum(losses) / len(losses) if losses else 0
            largest_win = max(wins) if wins else 0
            largest_loss = min(losses) if losses else 0
            
            gross_profit = sum(wins) if wins else 0
            gross_loss = abs(sum(losses)) if losses else 0
            profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 0
            
            # Get starting balance (would need to be tracked separately)
            # For now, use a placeholder
            starting_balance = 10000  # You'd get this from account history
            ending_balance = starting_balance + total_pnl
            total_pnl_pct = (total_pnl / starting_balance * 100) if starting_balance > 0 else 0
            
            now = datetime.utcnow().isoformat()
            
            # Insert or update daily performance
            cursor.execute('''
                INSERT OR REPLACE INTO daily_performance (
                    date, starting_balance, ending_balance,
                    total_trades, winning_trades, losing_trades, breakeven_trades,
                    total_pnl, total_pnl_pct, win_rate,
                    avg_win, avg_loss, largest_win, largest_loss,
                    profit_factor, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                date, starting_balance, ending_balance,
                total_trades, winning_trades, losing_trades, breakeven_trades,
                total_pnl, total_pnl_pct, win_rate,
                avg_win, avg_loss, largest_win, largest_loss,
                profit_factor, now, now
            ))
            
            conn.commit()
            print(f"✅ Daily performance calculated for {date}")
            
        except Exception as e:
            print(f"❌ Failed to calculate daily performance: {e}")
        finally:
            conn.close()
    
    def get_trade_statistics(self, days=30):
        """
        Get comprehensive trade statistics for the last N days.
        
        Returns:
            Dictionary with all statistics
        """
        conn = sqlite3.connect(self.db_path)
        
        query = f'''
            SELECT 
                COUNT(*) as total_trades,
                SUM(CASE WHEN outcome = 'win' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN outcome = 'loss' THEN 1 ELSE 0 END) as losses,
                SUM(pnl) as total_pnl,
                AVG(CASE WHEN outcome = 'win' THEN pnl END) as avg_win,
                AVG(CASE WHEN outcome = 'loss' THEN pnl END) as avg_loss,
                MAX(pnl) as best_trade,
                MIN(pnl) as worst_trade,
                AVG(setup_score) as avg_setup_score,
                AVG(rr_ratio) as avg_rr_ratio
            FROM trades
            WHERE status = 'closed' 
            AND DATE(order_closed_time) >= DATE('now', '-{days} days')
        '''
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        stats = df.iloc[0].to_dict()

        # Handle None values from SQL (when no trades exist)
        numeric_fields = ['wins', 'losses', 'total_pnl', 'avg_win', 'avg_loss',
                         'best_trade', 'worst_trade', 'avg_setup_score', 'avg_rr_ratio']
        for field in numeric_fields:
            if stats[field] is None:
                stats[field] = 0

        if stats['total_trades'] > 0:
            stats['win_rate'] = (stats['wins'] / stats['total_trades'] * 100)
            gross_profit = stats['wins'] * stats['avg_win'] if stats['avg_win'] else 0
            gross_loss = abs(stats['losses'] * stats['avg_loss']) if stats['avg_loss'] else 0
            stats['profit_factor'] = (gross_profit / gross_loss) if gross_loss > 0 else 0
        else:
            stats['win_rate'] = 0
            stats['profit_factor'] = 0
        
        return stats
    
    def export_to_csv(self, filename="trades_export.csv"):
        """Export all trades to CSV for external analysis."""
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql_query("SELECT * FROM trades ORDER BY created_at DESC", conn)
        conn.close()
        
        df.to_csv(filename, index=False)
        print(f"✅ Trades exported to {filename}")
    
    def print_performance_report(self, days=7):
        """Print a formatted performance report."""
        stats = self.get_trade_statistics(days)
        
        print(f"\n{'='*60}")
        print(f"📊 TRADING PERFORMANCE REPORT (Last {days} Days)")
        print(f"{'='*60}")
        print(f"Total Trades: {stats['total_trades']:.0f}")
        print(f"Wins: {stats['wins']:.0f} | Losses: {stats['losses']:.0f}")
        print(f"Win Rate: {stats['win_rate']:.1f}%")
        print(f"Total P&L: ${stats['total_pnl']:,.2f}")
        print(f"Average Win: ${stats['avg_win']:,.2f}")
        print(f"Average Loss: ${stats['avg_loss']:,.2f}")
        print(f"Best Trade: ${stats['best_trade']:,.2f}")
        print(f"Worst Trade: ${stats['worst_trade']:,.2f}")
        print(f"Profit Factor: {stats['profit_factor']:.2f}")
        print(f"Avg Setup Score: {stats['avg_setup_score']:.0f}/100")
        print(f"Avg R:R Ratio: {stats['avg_rr_ratio']:.2f}")
        print(f"{'='*60}\n")


# Example usage
if __name__ == "__main__":
    logger = TradeLogger()
    
    # Simulate logging a trade
    setup = {
        'score': 85,
        'quality': 'GOOD',
        'ob_present': True,
        'fvg_present': True,
        'confluence_pct': 75,
        'confluence_quality': 'high'
    }
    
    logger.log_trade_signal(
        ticket_number=123456,
        symbol="EURUSD",
        direction="BUY",
        entry_price=1.10000,
        stop_loss=1.09900,
        take_profit=1.10200,
        lot_size=0.10,
        setup_analysis=setup,
        risk_amount=50.0,
        risk_pct=0.5,
        rr_ratio=2.0,
        atr_pips=5.5
    )
    
    # Print report
    logger.print_performance_report(days=30)
