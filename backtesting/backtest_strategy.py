import pandas as pd
import numpy as np
import datetime
import random
import os
import sys

# Ensure we can import dhanhq from the parent directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from dhanhq import DhanContext, dhanhq

# Configuration
CAPITAL = 500000
RISK_PER_TRADE = 5000  # 1% of 5L
MAX_TRADES_PER_DAY = 2
LOT_SIZE = 50  # Nifty Lot Size

# API Configuration (Set these via environment variables or edit here)
CLIENT_ID = os.getenv("DHAN_CLIENT_ID", "")
ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN", "")
# Security ID for Nifty Future (Update based on current contract)
# Example: Find the Security ID from Dhan Instrument list
SECURITY_ID = os.getenv("DHAN_SECURITY_ID", "13")
EXCHANGE_SEGMENT = "NSE_FNO"
INSTRUMENT_TYPE = "FUTIDX" # Future Index

def fetch_historical_data(client_id, access_token, security_id, days=5):
    """Fetches historical 1-minute data using DhanHQ API."""
    print("Initializing DhanHQ Client...")
    dhan_context = DhanContext(client_id, access_token)
    dhan = dhanhq(dhan_context)

    # Calculate dates
    to_date = datetime.datetime.now()
    from_date = to_date - datetime.timedelta(days=days)

    f_date = from_date.strftime("%Y-%m-%d")
    t_date = to_date.strftime("%Y-%m-%d")

    print(f"Fetching data from {f_date} to {t_date} for Security ID {security_id}...")

    try:
        response = dhan.intraday_minute_data(
            security_id=security_id,
            exchange_segment=EXCHANGE_SEGMENT,
            instrument_type=INSTRUMENT_TYPE,
            from_date=f_date,
            to_date=t_date,
            interval=1
        )

        if response.get('status') == 'failure':
            raise Exception(f"API Error: {response.get('remarks')}")

        data = response.get('data')
        if not data:
             raise Exception("No data returned from API (Empty response)")

        # Parse data
        # Data is dict with lists: open, high, low, close, volume, timestamp (epoch)
        # Verify required keys exist
        required_keys = ['open', 'high', 'low', 'close', 'volume', 'timestamp']
        if not all(k in data for k in required_keys):
             # Sometimes API might return different structure or partial data
             print(f"Available keys: {data.keys()}")
             raise Exception(f"Missing required keys in data. Expected {required_keys}")

        df = pd.DataFrame(data)

        if df.empty:
            raise Exception("Returned DataFrame is empty.")

        # Convert timestamp to datetime
        # Detect unit (seconds or ms)
        first_ts = df['timestamp'].iloc[0]
        unit = 's'
        if first_ts > 10000000000: # > 10^10 implies ms (13 digits)
            unit = 'ms'

        df['datetime'] = pd.to_datetime(df['timestamp'], unit=unit)

        # Set index
        df.set_index('datetime', inplace=True)

        # Ensure numeric columns
        cols = ['open', 'high', 'low', 'close', 'volume']
        for col in cols:
            df[col] = pd.to_numeric(df[col])

        print(f"Successfully fetched {len(df)} rows.")
        return df[['open', 'high', 'low', 'close', 'volume']]

    except Exception as e:
        print(f"Error fetching data: {e}")
        return pd.DataFrame()

def calculate_indicators(df):
    """Calculates necessary indicators for the strategy."""
    df['date'] = df.index.date

    # VWAP
    df['cum_vol'] = df.groupby('date')['volume'].cumsum()
    df['cum_vol_price'] = df.groupby('date').apply(lambda x: (x['close'] * x['volume']).cumsum()).reset_index(level=0, drop=True)
    df['vwap'] = df['cum_vol_price'] / df['cum_vol']

    # Volume Spike (Volume > 2 * SMA(20))
    df['vol_sma'] = df['volume'].rolling(window=20).mean()
    df['vol_spike'] = df['volume'] > (df['vol_sma'] * 2.0)

    # OR High/Low (9:15 - 9:30)
    # We will calculate this dynamically in the loop or pre-calculate
    # Pre-calculating is faster
    df['or_high'] = np.nan
    df['or_low'] = np.nan

    grouped = df.groupby('date')
    for date, group in grouped:
        # Get data between 9:15 and 9:30
        mask_or = (group.index.time >= datetime.time(9, 15)) & (group.index.time < datetime.time(9, 30))
        if mask_or.any():
            or_data = group[mask_or]
            or_h = or_data['high'].max()
            or_l = or_data['low'].min()

            # Broadcast to the rest of the day
            df.loc[group.index, 'or_high'] = or_h
            df.loc[group.index, 'or_low'] = or_l

    return df

def resample_to_3min(df):
    """Resamples 1-min data to 3-min data for swing calculation."""
    df_3min = df.resample('3min').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    })
    # Identify swings
    # Swing High: High[t-1] > High[t-2] and High[t-1] > High[t]
    # Swing Low: Low[t-1] < Low[t-2] and Low[t-1] < Low[t]

    df_3min['swing_high'] = (df_3min['high'].shift(1) > df_3min['high'].shift(2)) & (df_3min['high'].shift(1) > df_3min['high'])
    df_3min['swing_low'] = (df_3min['low'].shift(1) < df_3min['low'].shift(2)) & (df_3min['low'].shift(1) < df_3min['low'])

    # Record the Price of the swing
    df_3min['swing_high_price'] = np.where(df_3min['swing_high'], df_3min['high'].shift(1), np.nan)
    df_3min['swing_low_price'] = np.where(df_3min['swing_low'], df_3min['low'].shift(1), np.nan)

    # Forward fill to know the "most recent" swing
    df_3min['last_swing_high'] = df_3min['swing_high_price'].ffill()
    df_3min['last_swing_low'] = df_3min['swing_low_price'].ffill()

    # Shift forward by 1 bar (3 minutes) to prevent lookahead bias.
    # A swing confirmed by the completion of bar T is only known at T+1.
    df_3min['last_swing_high'] = df_3min['last_swing_high'].shift(1)
    df_3min['last_swing_low'] = df_3min['last_swing_low'].shift(1)

    return df_3min

def backtest_strategy(df):
    if df.empty:
        print("No data to backtest.")
        return []

    df = calculate_indicators(df)
    df_3min = resample_to_3min(df)

    # Merge 3min swing levels back to 1min df (forward fill)
    df = df.join(df_3min[['last_swing_high', 'last_swing_low']], how='left')
    df['last_swing_high'] = df['last_swing_high'].ffill()
    df['last_swing_low'] = df['last_swing_low'].ffill()

    trades = []
    active_position = None  # {type: 'CE'/'PE', entry_price: float, qty: int, sl: float, target: float, entry_time: datetime, entry_sl: float}

    daily_trades = {} # {date: count}

    print(f"Starting Backtest on {len(df)} bars...")

    for i in range(1, len(df)):
        current_bar = df.iloc[i]
        prev_bar = df.iloc[i-1]

        timestamp = df.index[i]
        current_date = timestamp.date()
        current_time = timestamp.time()

        if current_date not in daily_trades:
            daily_trades[current_date] = 0

        # Strategy Logic

        # 1. Entry Logic
        # Time 9:30 to 11:30
        entry_window = (current_time >= datetime.time(9, 30)) and (current_time <= datetime.time(11, 30))

        option_delta = 0.5

        if active_position is None:
            if entry_window and daily_trades[current_date] < MAX_TRADES_PER_DAY:

                # Check Signals
                # Buy CE
                if (current_bar['close'] > current_bar['or_high']) and \
                   (current_bar['close'] > current_bar['vwap']) and \
                   (current_bar['vol_spike']):

                    sl_level = current_bar['last_swing_low']
                    if pd.isna(sl_level):
                         sl_level = current_bar['or_low']

                    future_entry = current_bar['close']
                    future_risk = future_entry - sl_level

                    if future_risk > 0:
                        option_risk_pts = future_risk * option_delta

                        qty = int(RISK_PER_TRADE / option_risk_pts)
                        # Ensure lot size multiple
                        qty = (qty // LOT_SIZE) * LOT_SIZE

                        if qty > 0:
                            entry_option_price = 200 # Arbitrary ATM price

                            sl_option_price = entry_option_price - option_risk_pts
                            target_option_price = entry_option_price + option_risk_pts # 1:1 RR

                            active_position = {
                                'type': 'CE',
                                'entry_time': timestamp,
                                'entry_price': entry_option_price, # Option Price
                                'future_entry': future_entry,
                                'qty': qty,
                                'sl': sl_option_price,
                                'target': target_option_price,
                                'initial_sl': sl_option_price,
                                'sl_future_level': sl_level, # For trailing logic reference
                                'half_qty_booked': False
                            }

                            daily_trades[current_date] += 1
                            print(f"[{timestamp}] BUY CE | Fut: {future_entry:.2f} | SL_Fut: {sl_level:.2f} | OptPrice: {entry_option_price} | Qty: {qty}")

                # Buy PE
                elif (current_bar['close'] < current_bar['or_low']) and \
                     (current_bar['close'] < current_bar['vwap']) and \
                     (current_bar['vol_spike']):

                    sl_level = current_bar['last_swing_high']
                    if pd.isna(sl_level):
                        sl_level = current_bar['or_high']

                    future_entry = current_bar['close']
                    future_risk = sl_level - future_entry

                    if future_risk > 0:
                        option_risk_pts = future_risk * option_delta
                        qty = int(RISK_PER_TRADE / option_risk_pts)
                        qty = (qty // LOT_SIZE) * LOT_SIZE

                        if qty > 0:
                            entry_option_price = 200
                            sl_option_price = entry_option_price - option_risk_pts
                            target_option_price = entry_option_price + option_risk_pts

                            active_position = {
                                'type': 'PE',
                                'entry_time': timestamp,
                                'entry_price': entry_option_price,
                                'future_entry': future_entry,
                                'qty': qty,
                                'sl': sl_option_price,
                                'target': target_option_price,
                                'initial_sl': sl_option_price,
                                'sl_future_level': sl_level,
                                'half_qty_booked': False
                            }
                            daily_trades[current_date] += 1
                            print(f"[{timestamp}] BUY PE | Fut: {future_entry:.2f} | SL_Fut: {sl_level:.2f} | OptPrice: {entry_option_price} | Qty: {qty}")

        else:
            # Manage Active Position
            pos = active_position

            # Update Option Price based on Future Move
            future_curr = current_bar['close']
            future_change = future_curr - pos['future_entry']

            if pos['type'] == 'CE':
                option_curr = pos['entry_price'] + (future_change * option_delta)
            else: # PE
                option_curr = pos['entry_price'] - (future_change * option_delta) # Put goes up when future goes down

            # 1. Check SL Hit
            if option_curr <= pos['sl']:
                # Exit All
                pnl = (pos['sl'] - pos['entry_price']) * pos['qty']
                trades.append({
                    'entry_time': pos['entry_time'],
                    'exit_time': timestamp,
                    'type': pos['type'],
                    'pnl': pnl,
                    'exit_reason': 'SL Hit'
                })
                print(f"[{timestamp}] SL Hit ({pos['type']}) | PnL: {pnl:.2f}")
                active_position = None
                continue

            # 2. Check Target 1 Hit (1:1 RR)
            if not pos['half_qty_booked']:
                if option_curr >= pos['target']:
                    # Book 50%
                    booked_qty = int(pos['qty'] / 2)
                    # Adjust booked_qty to be lot multiple if possible? Or just half?
                    # Half of 50 is 25. If lot size is 50, strictly speaking we can't book partial.
                    # But if we have 100, we book 50.
                    # If we have 50 (1 lot), should we book?
                    # Exit Rules: "Target 1: 50% quantity at 1:1 RR".
                    # If Qty is 1 lot, 50% is 0.5 lot. Not possible.
                    # We should probably book entire position if < 2 lots?
                    # Or keep simple integer division.

                    if booked_qty > 0:
                        pnl = (pos['target'] - pos['entry_price']) * booked_qty
                        trades.append({
                            'entry_time': pos['entry_time'],
                            'exit_time': timestamp,
                            'type': pos['type'],
                            'pnl': pnl,
                            'exit_reason': 'Target 1'
                        })
                        print(f"[{timestamp}] Target 1 Hit ({pos['type']}) | Booked {booked_qty} | PnL: {pnl:.2f}")

                        # Update Position
                        pos['qty'] -= booked_qty
                        pos['half_qty_booked'] = True
                    # If booked_qty is 0 (e.g. 1 lot held), we proceed to trail with full qty.

            # 3. Trailing Logic

            # VWAP Cross Condition
            vwap_cross_exit = False
            if pos['type'] == 'CE':
                if current_bar['close'] < current_bar['vwap']: # Closed below VWAP
                     vwap_cross_exit = True
            else: # PE
                if current_bar['close'] > current_bar['vwap']:
                    vwap_cross_exit = True

            if vwap_cross_exit:
                # Exit Remaining
                pnl = (option_curr - pos['entry_price']) * pos['qty']
                trades.append({
                    'entry_time': pos['entry_time'],
                    'exit_time': timestamp,
                    'type': pos['type'],
                    'pnl': pnl,
                    'exit_reason': 'VWAP Cross'
                })
                print(f"[{timestamp}] VWAP Cross Exit ({pos['type']}) | PnL: {pnl:.2f}")
                active_position = None
                continue

            # Swing Trailing Logic
            if pos['type'] == 'CE':
                if not pd.isna(current_bar['last_swing_low']):
                     future_swing_level = current_bar['last_swing_low']
                     new_sl_opt = pos['entry_price'] + (future_swing_level - pos['future_entry']) * option_delta
                     if new_sl_opt > pos['sl']:
                         pos['sl'] = new_sl_opt

            else: # PE
                if not pd.isna(current_bar['last_swing_high']):
                     future_swing_level = current_bar['last_swing_high']
                     new_sl_opt = pos['entry_price'] + (pos['future_entry'] - future_swing_level) * option_delta
                     if new_sl_opt > pos['sl']:
                         pos['sl'] = new_sl_opt

            # 4. EOD Exit
            if current_time >= datetime.time(15, 15):
                pnl = (option_curr - pos['entry_price']) * pos['qty']
                trades.append({
                    'entry_time': pos['entry_time'],
                    'exit_time': timestamp,
                    'type': pos['type'],
                    'pnl': pnl,
                    'exit_reason': 'EOD'
                })
                print(f"[{timestamp}] EOD Exit ({pos['type']}) | PnL: {pnl:.2f}")
                active_position = None
                continue

    return trades

if __name__ == "__main__":
    if CLIENT_ID and ACCESS_TOKEN:
        print(f"Credentials found. Using Security ID: {SECURITY_ID}")
        df = fetch_historical_data(CLIENT_ID, ACCESS_TOKEN, SECURITY_ID, days=5)
    else:
        print("WARNING: DHAN_CLIENT_ID and/or DHAN_ACCESS_TOKEN not set in environment.")
        print("Please export these variables to use live historical data.")
        print("Example: export DHAN_CLIENT_ID='your_id'")
        print("         export DHAN_ACCESS_TOKEN='your_token'")
        print("         export DHAN_SECURITY_ID='13'")
        print("\nExiting as per request to use historical data.")
        # Alternatively, uncomment below to fallback to dummy data
        # print("Falling back to Dummy Data...")
        # df = generate_dummy_data(days=5)
        df = pd.DataFrame()

    if not df.empty:
        trades = backtest_strategy(df)

        print("\n--- Backtest Summary ---")
        total_pnl = sum(t['pnl'] for t in trades)
        print(f"Total PnL: {total_pnl:.2f}")
        print(f"Total Trades: {len(trades)}")

        df_trades = pd.DataFrame(trades)
        if not df_trades.empty:
            print(df_trades)
        else:
            print("No trades executed.")
