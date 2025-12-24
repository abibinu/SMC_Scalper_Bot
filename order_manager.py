import MetaTrader5 as mt5
from datetime import datetime, timedelta

class OrderManager:
    """Manages pending orders and open positions with advanced logic."""
    
    def __init__(self, magic_number, max_order_age_minutes=30, breakeven_trigger_rr=1.0):
        """
        Initialize Order Manager.
        
        Args:
            magic_number: Bot's unique identifier
            max_order_age_minutes: Cancel pending orders older than this (default: 30 min)
            breakeven_trigger_rr: Move SL to breakeven after this R:R is reached (default: 1.0)
        """
        self.magic_number = magic_number
        self.max_order_age_minutes = max_order_age_minutes
        self.breakeven_trigger_rr = breakeven_trigger_rr
        self.managed_positions = {}  # Track positions we've already modified
    
    def get_pending_orders(self, symbol=None):
        """Retrieve all pending orders for this bot."""
        orders = mt5.orders_get(symbol=symbol) if symbol else mt5.orders_get()
        if orders is None:
            return []
        return [order for order in orders if order.magic == self.magic_number]
    
    def cancel_old_orders(self, symbol=None):
        """Cancel pending orders that are older than max_order_age_minutes."""
        pending_orders = self.get_pending_orders(symbol)
        current_time = datetime.now()
        cancelled_count = 0
        
        for order in pending_orders:
            order_time = datetime.fromtimestamp(order.time_setup)
            order_age = (current_time - order_time).total_seconds() / 60
            
            if order_age > self.max_order_age_minutes:
                result = self._cancel_order(order.ticket)
                if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                    print(f"✓ Cancelled old order #{order.ticket} (age: {order_age:.1f} min)")
                    cancelled_count += 1
                else:
                    print(f"✗ Failed to cancel order #{order.ticket}: {result.comment if result else 'Unknown error'}")
        
        return cancelled_count
    
    def _cancel_order(self, ticket):
        """Cancel a specific order by ticket."""
        request = {
            "action": mt5.TRADE_ACTION_REMOVE,
            "order": ticket,
        }
        result = mt5.order_send(request)
        return result
    
    def manage_breakeven(self, symbol=None):
        """
        Move stop loss to breakeven for positions that have reached the breakeven trigger.
        Returns the number of positions modified.
        """
        positions = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
        if positions is None:
            return 0
        
        # Filter positions by magic number
        positions = [pos for pos in positions if pos.magic == self.magic_number]
        modified_count = 0
        
        for position in positions:
            # Skip if already managed
            if position.ticket in self.managed_positions:
                continue
            
            # Get current price
            symbol_info = mt5.symbol_info(position.symbol)
            if symbol_info is None:
                continue
            
            current_price = symbol_info.bid if position.type == mt5.POSITION_TYPE_BUY else symbol_info.ask
            entry_price = position.price_open
            stop_loss = position.sl
            take_profit = position.tp
            
            # Calculate distances
            if position.type == mt5.POSITION_TYPE_BUY:
                # Long position
                distance_to_tp = take_profit - entry_price
                current_profit = current_price - entry_price
                risk = entry_price - stop_loss
            else:
                # Short position
                distance_to_tp = entry_price - take_profit
                current_profit = entry_price - current_price
                risk = stop_loss - entry_price
            
            # Check if breakeven should be triggered
            if risk > 0:
                current_rr = current_profit / risk
                
                if current_rr >= self.breakeven_trigger_rr:
                    # Move SL to breakeven (entry price + small buffer)
                    point = symbol_info.point
                    buffer_pips = 2  # Small buffer to avoid premature exit
                    
                    if position.type == mt5.POSITION_TYPE_BUY:
                        new_sl = entry_price + (buffer_pips * point)
                    else:
                        new_sl = entry_price - (buffer_pips * point)
                    
                    # Only modify if new SL is better than current SL
                    if (position.type == mt5.POSITION_TYPE_BUY and new_sl > stop_loss) or \
                       (position.type == mt5.POSITION_TYPE_SELL and new_sl < stop_loss):
                        
                        result = self._modify_position_sl(position.ticket, position.symbol, new_sl, take_profit)
                        
                        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                            print(f"✓ Moved position #{position.ticket} to breakeven (RR: {current_rr:.2f})")
                            self.managed_positions[position.ticket] = True
                            modified_count += 1
                        else:
                            print(f"✗ Failed to modify position #{position.ticket}: {result.comment if result else 'Unknown error'}")
        
        return modified_count
    
    def _modify_position_sl(self, ticket, symbol, new_sl, tp):
        """Modify the stop loss of an open position."""
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "position": ticket,
            "symbol": symbol,
            "sl": new_sl,
            "tp": tp,
        }
        result = mt5.order_send(request)
        return result
    
    def cleanup_closed_positions(self):
        """Remove closed positions from the managed list."""
        open_tickets = {pos.ticket for pos in mt5.positions_get() or []}
        closed_tickets = [ticket for ticket in self.managed_positions.keys() if ticket not in open_tickets]
        
        for ticket in closed_tickets:
            del self.managed_positions[ticket]
        
        return len(closed_tickets)
    
    def get_status_report(self, symbol=None):
        """Generate a status report of orders and positions."""
        pending = self.get_pending_orders(symbol)
        positions = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
        positions = [pos for pos in (positions or []) if pos.magic == self.magic_number]
        
        report = {
            "pending_orders": len(pending),
            "open_positions": len(positions),
            "managed_positions": len(self.managed_positions),
            "details": {
                "pending": [{"ticket": o.ticket, "type": o.type, "price": o.price_open} for o in pending],
                "positions": [{"ticket": p.ticket, "type": p.type, "profit": p.profit} for p in positions]
            }
        }
        
        return report