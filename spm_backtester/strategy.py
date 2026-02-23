import pandas as pd
import numpy as np
from . import config

class SPMStrategy:
    def __init__(self):
        self.initial_capital = config.INITIAL_CAPITAL
        self.risk_percent = config.RISK_PER_TRADE_PERCENT

        # State to avoid repeated signals on same bar/pivot
        self.last_signal_time = None
        self.last_trade_exit_time = None

    def get_signal(self, current_bar, pivot_state, active_position=None):
        """
        Checks for entry signals.
        pivot_state: dict containing 'last_lph', 'last_lpl', 'recent_sphs', 'recent_spls'
        """
        if active_position:
            return None # Already in a trade

        timestamp = current_bar.name
        close = current_bar['close']
        high = current_bar['high']
        low = current_bar['low']

        last_lph = pivot_state.get('last_lph')
        last_lpl = pivot_state.get('last_lpl')
        recent_sphs = pivot_state.get('recent_sphs', [])
        recent_spls = pivot_state.get('recent_spls', [])

        signal = None

        # --- LONG ENTRY LOGIC ---
        # 1. Break of LPH
        if last_lph:
            if close > last_lph['price']:
                # Valid Breakout
                # Check if we already traded this break?
                # Assuming backtester handles "one trade at a time".

                # SL = Last SPL
                # Find most recent SPL
                if recent_spls:
                    # Last SPL is the one with latest timestamp
                    sl_spl = recent_spls[-1]
                    sl_price = sl_spl['price']

                    signal = {
                        'type': 'BUY',
                        'price': close, # Market Entry on Close
                        'sl': sl_price,
                        'reason': 'Break of LPH'
                    }

        # 2. Break of SPH > LPL (or SPH > LPH)
        # We check all recent SPHs.
        if not signal and last_lpl:
            # Filter SPHs that are ABOVE Last LPL
            valid_sphs = [p for p in recent_sphs if p['price'] > last_lpl['price']]

            for sph in valid_sphs:
                # If Price breaks SPH
                # Note: We should check if we just broke it (CrossOver)
                # But current_bar['close'] > sph implies we are above.
                # If we were already above, we might be late.
                # Ideally check `open < sph` and `close > sph`?
                # Or just `close > sph` and we haven't taken this trade yet.
                # Since we check every bar, `close > sph` is fine, provided we track state.
                # But if we stay above SPH for 10 bars, we don't want 10 buy signals.
                # The Backtester prevents taking new trade if one is active.

                if close > sph['price']:
                    # SL = Last SPL
                    if recent_spls:
                        sl_spl = recent_spls[-1]
                        sl_price = sl_spl['price']

                        signal = {
                            'type': 'BUY',
                            'price': close,
                            'sl': sl_price,
                            'reason': f"Break of SPH ({sph['price']})"
                        }
                        break

        # --- SHORT ENTRY LOGIC ---
        # 1. Break of LPL
        if not signal and last_lpl:
            if close < last_lpl['price']:
                if recent_sphs:
                    sl_sph = recent_sphs[-1]
                    sl_price = sl_sph['price']

                    signal = {
                        'type': 'SELL',
                        'price': close,
                        'sl': sl_price,
                        'reason': 'Break of LPL'
                    }

        # 2. Break of SPL < LPH
        if not signal and last_lph:
            valid_spls = [p for p in recent_spls if p['price'] < last_lph['price']]

            for spl in valid_spls:
                if close < spl['price']:
                    if recent_sphs:
                        sl_sph = recent_sphs[-1]
                        sl_price = sl_sph['price']

                        signal = {
                            'type': 'SELL',
                            'price': close,
                            'sl': sl_price,
                            'reason': f"Break of SPL ({spl['price']})"
                        }
                        break

        # --- SL VALIDATION ---
        if signal:
            # Max 0.3% Rule
            # "Or max 0.3% of instrument value"
            max_sl_dist = close * 0.003
            current_sl_dist = abs(close - signal['sl'])

            if current_sl_dist > max_sl_dist:
                if signal['type'] == 'BUY':
                    signal['sl'] = close - max_sl_dist
                else:
                    signal['sl'] = close + max_sl_dist
                signal['reason'] += " (Max SL Adjusted)"

            # Ensure SL is on correct side
            if signal['type'] == 'BUY' and signal['sl'] >= close:
                 signal = None # Invalid SL
            elif signal['type'] == 'SELL' and signal['sl'] <= close:
                 signal = None

        return signal

    def check_exit(self, position, current_bar, pivot_state):
        """
        Checks for exit signals (SL, Trailing SL).
        Returns exit_price if exit triggered, else None.
        """
        timestamp = current_bar.name
        close = current_bar['close']
        high = current_bar['high']
        low = current_bar['low']

        exit_signal = None

        # 1. Check Hard SL
        if position['type'] == 'BUY':
            if low <= position['sl']:
                return position['sl'], "Stop Loss"
        else:
            if high >= position['sl']:
                return position['sl'], "Stop Loss"

        # 2. Aggressive Trail
        # "After 0.5% profit -> trail to previous bar low/high"
        profit_pct = 0
        if position['type'] == 'BUY':
            profit_pct = (close - position['entry_price']) / position['entry_price']
            if profit_pct >= 0.005:
                # Trail to prev bar low
                # Accessing prev bar low requires history or passing it.
                # Assuming current_bar has 'low' of current completed bar.
                # If we are strictly bar-by-bar, we set SL for *next* bar based on *current* bar.
                # So we update SL.
                new_sl = low
                if new_sl > position['sl']:
                    position['sl'] = new_sl
                    # print(f"Aggressive Trail Update: {new_sl}")

        else: # SELL
            profit_pct = (position['entry_price'] - close) / position['entry_price']
            if profit_pct >= 0.005:
                new_sl = high
                if new_sl < position['sl']:
                    position['sl'] = new_sl

        # 3. Structural Trail (Successive SPL/SPH)
        # Update SL if a new SPL/SPH forms
        recent_sphs = pivot_state.get('recent_sphs', [])
        recent_spls = pivot_state.get('recent_spls', [])

        if position['type'] == 'BUY':
            if recent_spls:
                latest_spl = recent_spls[-1]
                # If this SPL is higher than current SL, trail.
                # And it must be after entry? usually yes.
                if latest_spl['price'] > position['sl']:
                    position['sl'] = latest_spl['price']

        else: # SELL
             if recent_sphs:
                latest_sph = recent_sphs[-1]
                if latest_sph['price'] < position['sl']:
                    position['sl'] = latest_sph['price']

        return None, None
