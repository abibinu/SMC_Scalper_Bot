import os
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

class TelegramNotifier:
    """Handles Telegram notifications for trading events."""
    
    def __init__(self, enabled=True):
        """
        Initialize Telegram Notifier.
        
        Environment variables required:
        - TELEGRAM_BOT_TOKEN: Your bot token from @BotFather
        - TELEGRAM_CHAT_ID: Your chat ID (get from @userinfobot)
        """
        self.enabled = enabled
        
        if self.enabled:
            self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
            self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
            
            if not self.bot_token or not self.chat_id:
                print("⚠️  Telegram credentials not found. Notifications disabled.")
                print("   Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env file")
                self.enabled = False
    
    def send_message(self, message, parse_mode="HTML"):
        """Send a message via Telegram."""
        if not self.enabled:
            return False
        
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            data = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": parse_mode
            }
            response = requests.post(url, data=data, timeout=10)
            return response.status_code == 200
        except Exception as e:
            print(f"❌ Telegram notification failed: {e}")
            return False
    
    def notify_bot_started(self, account_balance, symbol, risk_pct, settings):
        """Notify when bot starts."""
        message = f"""
🤖 <b>Bot Started</b>

💰 Account: ${account_balance:,.2f}
📊 Symbol: {symbol}
⚠️ Risk: {risk_pct*100}% per trade

<b>Settings:</b>
📦 OB Lookback: {settings.get('ob_lookback', 'N/A')} candles
🎯 Min Quality: {settings.get('min_quality', 'N/A')}/100
📈 MTF: {settings.get('mtf_enabled', 'N/A')}
🔄 Breaker Blocks: {settings.get('bb_enabled', 'N/A')}

<i>{datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC</i>
"""
        self.send_message(message)
    
    def notify_signal_detected(self, signal_type, quality_score, quality_rating, mtf_alignment=None):
        """Notify when a trading signal is detected."""
        emoji = "🟢" if signal_type == "bullish" else "🔴"
        
        message = f"""
{emoji} <b>SIGNAL DETECTED</b>

📊 Direction: {signal_type.upper()}
⭐ Quality: {quality_rating} ({quality_score}/100)
"""
        
        if mtf_alignment:
            alignment_emoji = "✅" if mtf_alignment['strength'] == "PERFECT" else "🟡" if mtf_alignment['strength'] == "STRONG" else "⚠️"
            message += f"{alignment_emoji} MTF: {mtf_alignment['strength']} ({mtf_alignment['alignment_pct']:.0f}%)\n"
        
        message += f"\n<i>Analyzing trade setup...</i>"
        
        self.send_message(message)
    
    def notify_trade_placed(self, order_type, symbol, entry, sl, tp, lot_size, risk_amount, potential_profit, ticket_number):
        """Notify when a trade order is placed."""
        direction = "BUY" if "BUY" in str(order_type) else "SELL"
        emoji = "🟢" if direction == "BUY" else "🔴"
        
        sl_pips = abs(entry - sl) * 10000  # Approximate for forex
        tp_pips = abs(tp - entry) * 10000
        
        message = f"""
{emoji} <b>ORDER PLACED</b>

📊 {direction} {symbol}
🎯 Entry: {entry:.5f}
🛑 SL: {sl:.5f} ({sl_pips:.1f} pips)
💰 TP: {tp:.5f} ({tp_pips:.1f} pips)
📦 Lot Size: {lot_size}

⚠️ Risk: ${risk_amount:.2f}
💵 Potential: ${potential_profit:.2f} (2R)

🎫 Ticket: #{ticket_number}
<i>{datetime.utcnow().strftime('%H:%M:%S')} UTC</i>
"""
        self.send_message(message)
    
    def notify_order_filled(self, ticket_number, entry_price, direction):
        """Notify when a pending order is filled."""
        emoji = "🟢" if direction == "bullish" else "🔴"
        
        message = f"""
{emoji} <b>ORDER FILLED</b>

🎫 Ticket: #{ticket_number}
📍 Entry: {entry_price:.5f}
⏰ {datetime.utcnow().strftime('%H:%M:%S')} UTC

Position is now active!
"""
        self.send_message(message)
    
    def notify_breakeven_moved(self, ticket_number, symbol, new_sl):
        """Notify when stop loss is moved to breakeven."""
        message = f"""
🎯 <b>BREAKEVEN TRIGGERED</b>

🎫 Ticket: #{ticket_number}
📊 {symbol}
🛑 New SL: {new_sl:.5f} (Breakeven)

Position is now risk-free! 🎉
"""
        self.send_message(message)
    
    def notify_order_cancelled(self, ticket_number, reason="Expired"):
        """Notify when an order is cancelled."""
        message = f"""
🗑️ <b>ORDER CANCELLED</b>

🎫 Ticket: #{ticket_number}
📝 Reason: {reason}
⏰ {datetime.utcnow().strftime('%H:%M:%S')} UTC
"""
        self.send_message(message)
    
    def notify_position_closed(self, ticket_number, symbol, entry, exit_price, profit, pips, outcome):
        """Notify when a position is closed."""
        emoji = "✅" if profit > 0 else "❌"
        outcome_text = "WIN" if profit > 0 else "LOSS"
        
        message = f"""
{emoji} <b>POSITION CLOSED - {outcome_text}</b>

🎫 Ticket: #{ticket_number}
📊 {symbol}
📍 Entry: {entry:.5f}
🚪 Exit: {exit_price:.5f}
📊 Pips: {pips:+.1f}
💰 P&L: ${profit:+.2f}

<i>{datetime.utcnow().strftime('%H:%M:%S')} UTC</i>
"""
        self.send_message(message)
    
    def notify_signal_skipped(self, reason, details=None):
        """Notify when a signal is skipped."""
        message = f"""
⚠️ <b>SIGNAL SKIPPED</b>

📝 Reason: {reason}
"""
        if details:
            message += f"ℹ️ Details: {details}\n"
        
        message += f"\n<i>{datetime.utcnow().strftime('%H:%M:%S')} UTC</i>"
        
        self.send_message(message)
    
    def notify_breaker_block_detected(self, bb_type, zone_high, zone_low, quality):
        """Notify when a Breaker Block is detected."""
        emoji = "🟢" if bb_type == "bullish" else "🔴"
        
        message = f"""
{emoji} <b>BREAKER BLOCK DETECTED</b>

📊 Type: {bb_type.upper()} BB
📦 Zone: {zone_low:.5f} - {zone_high:.5f}
⭐ Quality: {quality.upper()}

Failed OB now acting as reversal zone!
"""
        self.send_message(message)
    
    def notify_daily_summary(self, trades_taken, winners, losers, total_pnl, win_rate, balance):
        """Send daily summary."""
        emoji = "📈" if total_pnl > 0 else "📉" if total_pnl < 0 else "➡️"
        
        message = f"""
{emoji} <b>DAILY SUMMARY</b>

📊 Trades: {trades_taken}
✅ Wins: {winners}
❌ Losses: {losers}
📈 Win Rate: {win_rate:.1f}%
💰 P&L: ${total_pnl:+.2f}
💵 Balance: ${balance:,.2f}

<i>{datetime.utcnow().strftime('%Y-%m-%d')} UTC</i>
"""
        self.send_message(message)
    
    def notify_error(self, error_message):
        """Notify when an error occurs."""
        message = f"""
❌ <b>ERROR OCCURRED</b>

{error_message}

⏰ {datetime.utcnow().strftime('%H:%M:%S')} UTC
"""
        self.send_message(message)
    
    def test_connection(self):
        """Test Telegram connection."""
        if not self.enabled:
            print("❌ Telegram is disabled")
            return False
        
        message = "✅ <b>Telegram Connection Test</b>\n\nBot is connected and ready to send notifications!"
        success = self.send_message(message)
        
        if success:
            print("✅ Telegram test message sent successfully!")
        else:
            print("❌ Telegram test message failed")
        
        return success