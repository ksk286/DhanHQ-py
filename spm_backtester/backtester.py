import pandas as pd
import numpy as np
import datetime
from . import config
from .data_fetcher import DataFetcher
from .pivot_engine import identify_small_pivots, identify_large_pivots
from .strategy import SPMStrategy
from .risk_manager import RiskManager

class Backtester:
    def __init__(self, symbol=config.SYMBOL, start_date=None, end_date=None):
        self.symbol = symbol
        self.start_date = start_date
        self.end_date = end_date
        self.data_fetcher = DataFetcher()
        self.strategy = SPMStrategy()
        self.risk_manager = RiskManager()

        self.trades = []
        self.equity_curve = []

    def run(self):
        # 1. Fetch Data
        print(f"Fetching data for {self.symbol}...")
        df_1min = self.data_fetcher.fetch_data(self.symbol, self.start_date, self.end_date)

        if df_1min is None or df_1min.empty:
            print("No data found.")
            return

        # 2. Resample Data
        print("Resampling data...")
        df_3min = self.data_fetcher.resample_data(df_1min, config.TIMEFRAME_EXECUTION)
        df_5min = self.data_fetcher.resample_data(df_1min, config.TIMEFRAME_STRUCTURE)

        # 3. Calculate Pivots on 5-min Data (Full History)
        print("Calculating pivots...")
        df_5min, small_pivots = identify_small_pivots(df_5min)
        df_5min, large_pivots = identify_large_pivots(df_5min, small_pivots)

        # 4. Backtest Loop
        print("Starting backtest loop...")

        active_position = None # {'type', 'entry_price', 'qty', 'sl', 'entry_time'}

        # Iterate through 3-min bars
        for timestamp, row in df_3min.iterrows():
            current_time = timestamp

            # Decision made at end of 3-min bar
            decision_time = current_time + pd.Timedelta(minutes=3)

            # Filter pivots available at decision_time
            available_sphs = [p for p in small_pivots if p['type'] == 'SPH' and p.get('confirmed_at') and p['confirmed_at'] <= decision_time]
            available_spls = [p for p in small_pivots if p['type'] == 'SPL' and p.get('confirmed_at') and p['confirmed_at'] <= decision_time]
            available_lphs = [p for p in large_pivots if p['type'] == 'LPH' and p.get('confirmed_at') and p['confirmed_at'] <= decision_time]
            available_lpls = [p for p in large_pivots if p['type'] == 'LPL' and p.get('confirmed_at') and p['confirmed_at'] <= decision_time]

            last_lph = available_lphs[-1] if available_lphs else None
            last_lpl = available_lpls[-1] if available_lpls else None

            recent_sphs = available_sphs[-20:]
            recent_spls = available_spls[-20:]

            pivot_state = {
                'last_lph': last_lph,
                'last_lpl': last_lpl,
                'recent_sphs': recent_sphs,
                'recent_spls': recent_spls
            }

            # Check Exit
            if active_position:
                # Assuming strategy handles SL and Trailing
                # Pass current bar (row) to check against SL
                # row is the 3-min bar that JUST completed at decision_time?
                # Yes. row['close'] is Close at decision_time.

                # Check if exit triggered
                exit_price, exit_reason = self.strategy.check_exit(active_position, row, pivot_state)

                # EOD Square-off check (15:15)
                # row index is start time (e.g., 15:12). End is 15:15.
                # If decision_time >= 15:15, exit.
                if decision_time.time() >= datetime.datetime.strptime(config.SQUARE_OFF_TIME, "%H:%M").time():
                     if not exit_price: # If not already hit SL
                         exit_price = row['close']
                         exit_reason = "EOD Square-off"

                if exit_price:
                    # Execute Exit
                    exec_price = exit_price
                    # Apply Slippage
                    if active_position['type'] == 'BUY':
                        exec_price -= config.SLIPPAGE_POINTS
                    else:
                        exec_price += config.SLIPPAGE_POINTS

                    pnl = (exec_price - active_position['entry_price']) * active_position['qty']
                    if active_position['type'] == 'SELL':
                        pnl = (active_position['entry_price'] - exec_price) * active_position['qty']

                    # Deduct Brokerage
                    pnl -= (config.BROKERAGE_PER_ORDER * 2)

                    self.trades.append({
                        'entry_time': active_position['entry_time'],
                        'exit_time': decision_time,
                        'type': active_position['type'],
                        'entry_price': active_position['entry_price'],
                        'exit_price': exec_price,
                        'qty': active_position['qty'],
                        'pnl': pnl,
                        'reason': exit_reason
                    })

                    self.risk_manager.update_capital(self.risk_manager.current_capital + pnl)
                    active_position = None

            # Check Entry
            if not active_position:
                # Don't take new trades after 3:00 PM (15:00)
                if decision_time.time() < datetime.time(15, 0):
                    signal = self.strategy.get_signal(row, pivot_state)

                    if signal:
                        qty = self.risk_manager.calculate_position_size(signal['price'], signal['sl'])

                        if qty > 0:
                            entry_price = signal['price']
                            if signal['type'] == 'BUY':
                                entry_price += config.SLIPPAGE_POINTS
                            else:
                                entry_price -= config.SLIPPAGE_POINTS

                            active_position = {
                                'type': signal['type'],
                                'entry_time': decision_time,
                                'entry_price': entry_price,
                                'sl': signal['sl'],
                                'qty': qty
                            }
                            # print(f"Trade Taken: {signal['type']} at {decision_time} Price {entry_price}")

            # Track Equity
            self.equity_curve.append({
                'datetime': decision_time,
                'equity': self.risk_manager.current_capital
            })

        print("Backtest complete.")
        trades_df = pd.DataFrame(self.trades)
        return trades_df, df_3min, small_pivots, large_pivots, self.equity_curve

if __name__ == "__main__":
    import datetime
    start = datetime.datetime.now() - datetime.timedelta(days=10)
    end = datetime.datetime.now()

    bt = Backtester(start_date=start, end_date=end)
    trades_df, _, _, _, _ = bt.run()
    if not trades_df.empty:
        print(trades_df.head())
        print(f"Total Trades: {len(trades_df)}")
        print(f"Total PnL: {trades_df['pnl'].sum()}")
    else:
        print("No trades executed.")
