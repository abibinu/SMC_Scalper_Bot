import MetaTrader5 as mt5
from datetime import datetime, timedelta
import json
import os

class RiskManager:
    """
    Manages account-level risk with daily/weekly drawdown limits.
    Prevents catastrophic losses by implementing circuit breakers.
    """
    
    def __init__(self, max_daily_loss_pct=0.03, max_weekly_loss_pct=0.05, 
                 max_daily_trades=20, state_file="risk_state.json"):
        """
        Initialize Risk Manager.
        
        Args:
            max_daily_loss_pct: Maximum daily loss as % of balance (default: 3%)
            max_weekly_loss_pct: Maximum weekly loss as % of balance (default: 5%)
            max_daily_trades: Maximum number of trades per day
            state_file: File to persist risk state across restarts
        """
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_weekly_loss_pct = max_weekly_loss_pct
        self.max_daily_trades = max_daily_trades
        self.state_file = state_file
        
        # Load or initialize state
        self.state = self._load_state()
        
        # Check if we need to reset daily/weekly counters
        self._check_and_reset_periods()
    
    def _load_state(self):
        """Load risk state from file or create new state."""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        
        # Default state
        return {
            "daily_start_balance": None,
            "daily_start_date": None,
            "daily_trades_count": 0,
            "daily_high_balance": None,
            "weekly_start_balance": None,
            "weekly_start_date": None,
            "weekly_high_balance": None,
            "is_daily_locked": False,
            "is_weekly_locked": False,
            "lock_reason": None
        }
    
    def _save_state(self):
        """Persist risk state to file."""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=2)
        except Exception as e:
            print(f"⚠️  Failed to save risk state: {e}")
    
    def _check_and_reset_periods(self):
        """Check if daily/weekly periods have elapsed and reset counters."""
        today = datetime.now().date().isoformat()
        current_week = datetime.now().isocalendar()[1]  # Week number
        
        # Reset daily counters
        if self.state["daily_start_date"] != today:
            account_info = mt5.account_info()
            if account_info:
                self.state["daily_start_balance"] = account_info.balance
                self.state["daily_high_balance"] = account_info.balance
                self.state["daily_start_date"] = today
                self.state["daily_trades_count"] = 0
                self.state["is_daily_locked"] = False
                print(f"📅 New trading day. Starting balance: ${account_info.balance:,.2f}")
        
        # Reset weekly counters (on Monday)
        stored_week = None
        if self.state["weekly_start_date"]:
            stored_date = datetime.fromisoformat(self.state["weekly_start_date"])
            stored_week = stored_date.isocalendar()[1]
        
        if stored_week != current_week:
            account_info = mt5.account_info()
            if account_info:
                self.state["weekly_start_balance"] = account_info.balance
                self.state["weekly_high_balance"] = account_info.balance
                self.state["weekly_start_date"] = datetime.now().date().isoformat()
                self.state["is_weekly_locked"] = False
                print(f"📅 New trading week. Starting balance: ${account_info.balance:,.2f}")
        
        self._save_state()
    
    def can_trade(self):
        """
        Check if trading is allowed based on risk limits.
        
        Returns:
            Tuple: (can_trade: bool, reason: str or None)
        """
        # Refresh period checks
        self._check_and_reset_periods()
        
        # Check if locked
        if self.state["is_daily_locked"]:
            return False, f"Daily loss limit reached: {self.state['lock_reason']}"
        
        if self.state["is_weekly_locked"]:
            return False, f"Weekly loss limit reached: {self.state['lock_reason']}"
        
        # Get current balance
        account_info = mt5.account_info()
        if not account_info:
            return False, "Cannot retrieve account info"
        
        current_balance = account_info.balance
        
        # Check daily loss limit
        if self.state["daily_start_balance"]:
            daily_loss = self.state["daily_start_balance"] - current_balance
            daily_loss_pct = daily_loss / self.state["daily_start_balance"]
            
            if daily_loss_pct >= self.max_daily_loss_pct:
                self.state["is_daily_locked"] = True
                self.state["lock_reason"] = f"Daily loss {daily_loss_pct*100:.2f}% >= {self.max_daily_loss_pct*100}%"
                self._save_state()
                return False, self.state["lock_reason"]
            
            # Also check drawdown from daily high
            if self.state["daily_high_balance"]:
                drawdown = self.state["daily_high_balance"] - current_balance
                drawdown_pct = drawdown / self.state["daily_high_balance"]
                
                if drawdown_pct >= self.max_daily_loss_pct:
                    self.state["is_daily_locked"] = True
                    self.state["lock_reason"] = f"Drawdown from daily high {drawdown_pct*100:.2f}%"
                    self._save_state()
                    return False, self.state["lock_reason"]
        
        # Check weekly loss limit
        if self.state["weekly_start_balance"]:
            weekly_loss = self.state["weekly_start_balance"] - current_balance
            weekly_loss_pct = weekly_loss / self.state["weekly_start_balance"]
            
            if weekly_loss_pct >= self.max_weekly_loss_pct:
                self.state["is_weekly_locked"] = True
                self.state["lock_reason"] = f"Weekly loss {weekly_loss_pct*100:.2f}% >= {self.max_weekly_loss_pct*100}%"
                self._save_state()
                return False, self.state["lock_reason"]
            
            # Also check drawdown from weekly high
            if self.state["weekly_high_balance"]:
                drawdown = self.state["weekly_high_balance"] - current_balance
                drawdown_pct = drawdown / self.state["weekly_high_balance"]
                
                if drawdown_pct >= self.max_weekly_loss_pct:
                    self.state["is_weekly_locked"] = True
                    self.state["lock_reason"] = f"Drawdown from weekly high {drawdown_pct*100:.2f}%"
                    self._save_state()
                    return False, self.state["lock_reason"]
        
        # Check daily trade limit
        if self.state["daily_trades_count"] >= self.max_daily_trades:
            return False, f"Daily trade limit reached ({self.max_daily_trades} trades)"
        
        return True, None
    
    def record_trade(self):
        """Record that a trade was placed."""
        self.state["daily_trades_count"] += 1
        self._save_state()
    
    def update_high_watermarks(self):
        """Update daily and weekly high balance watermarks."""
        account_info = mt5.account_info()
        if not account_info:
            return
        
        current_balance = account_info.balance
        
        # Update daily high
        if not self.state["daily_high_balance"] or current_balance > self.state["daily_high_balance"]:
            self.state["daily_high_balance"] = current_balance
        
        # Update weekly high
        if not self.state["weekly_high_balance"] or current_balance > self.state["weekly_high_balance"]:
            self.state["weekly_high_balance"] = current_balance
        
        self._save_state()
    
    def get_risk_status(self):
        """
        Get current risk status and statistics.
        
        Returns:
            Dictionary with risk metrics
        """
        account_info = mt5.account_info()
        if not account_info:
            return None
        
        current_balance = account_info.balance
        
        status = {
            "current_balance": current_balance,
            "can_trade": self.can_trade()[0],
            "lock_reason": self.state.get("lock_reason"),
            "daily_trades_count": self.state["daily_trades_count"],
            "daily_trades_remaining": max(0, self.max_daily_trades - self.state["daily_trades_count"])
        }
        
        # Daily stats
        if self.state["daily_start_balance"]:
            daily_pnl = current_balance - self.state["daily_start_balance"]
            daily_pnl_pct = (daily_pnl / self.state["daily_start_balance"]) * 100
            daily_loss_buffer = (self.max_daily_loss_pct * 100) + daily_pnl_pct
            
            status["daily_pnl"] = daily_pnl
            status["daily_pnl_pct"] = daily_pnl_pct
            status["daily_loss_buffer_pct"] = daily_loss_buffer
            status["daily_start_balance"] = self.state["daily_start_balance"]
        
        # Weekly stats
        if self.state["weekly_start_balance"]:
            weekly_pnl = current_balance - self.state["weekly_start_balance"]
            weekly_pnl_pct = (weekly_pnl / self.state["weekly_start_balance"]) * 100
            weekly_loss_buffer = (self.max_weekly_loss_pct * 100) + weekly_pnl_pct
            
            status["weekly_pnl"] = weekly_pnl
            status["weekly_pnl_pct"] = weekly_pnl_pct
            status["weekly_loss_buffer_pct"] = weekly_loss_buffer
            status["weekly_start_balance"] = self.state["weekly_start_balance"]
        
        return status
    
    def print_risk_status(self):
        """Print formatted risk status."""
        status = self.get_risk_status()
        if not status:
            print("⚠️  Cannot retrieve risk status")
            return
        
        print(f"\n{'='*60}")
        print(f"🛡️  RISK MANAGEMENT STATUS")
        print(f"{'='*60}")
        print(f"💰 Current Balance: ${status['current_balance']:,.2f}")
        print(f"🚦 Trading Allowed: {'✅ YES' if status['can_trade'] else '🛑 NO'}")
        
        if not status['can_trade']:
            print(f"❌ Reason: {status['lock_reason']}")
        
        print(f"\n📊 Daily Statistics:")
        if "daily_start_balance" in status:
            print(f"   Start: ${status['daily_start_balance']:,.2f}")
            print(f"   P&L: ${status['daily_pnl']:+,.2f} ({status['daily_pnl_pct']:+.2f}%)")
            print(f"   Loss Buffer: {status['daily_loss_buffer_pct']:.2f}% remaining")
        print(f"   Trades: {status['daily_trades_count']}/{self.max_daily_trades}")
        
        print(f"\n📈 Weekly Statistics:")
        if "weekly_start_balance" in status:
            print(f"   Start: ${status['weekly_start_balance']:,.2f}")
            print(f"   P&L: ${status['weekly_pnl']:+,.2f} ({status['weekly_pnl_pct']:+.2f}%)")
            print(f"   Loss Buffer: {status['weekly_loss_buffer_pct']:.2f}% remaining")
        
        print(f"{'='*60}\n")
    
    def reset_locks(self):
        """Manually reset locks (use with caution!)."""
        self.state["is_daily_locked"] = False
        self.state["is_weekly_locked"] = False
        self.state["lock_reason"] = None
        self._save_state()
        print("⚠️  Risk locks have been manually reset!")
