import pandas as pd
import numpy as np
import datetime
import random

# Configuration
CAPITAL = 500000
RISK_PER_TRADE = 5000  # 1% of 5L
MAX_TRADES_PER_DAY = 2
LOT_SIZE = 50  # Nifty Lot Size

def generate_dummy_data(days=5):
    """Generates synthetic 1-minute OHLCV data for Nifty Future."""
    start_date = datetime.datetime.now().replace(hour=9, minute=15, second=0, microsecond=0) - datetime.timedelta(days=days)
    data = []

    price = 19500.0

    for day in range(days):
        current_time = start_date + datetime.timedelta(days=day)
        # Market hours 9:15 to 15:30 -> 375 minutes
        market_open = current_time.replace(hour=9, minute=15)

        daily_volatility = random.uniform(0.005, 0.015)

        for i in range(375):
            timestamp = market_open + datetime.timedelta(minutes=i)

            change = price * random.normalvariate(0, daily_volatility / np.sqrt(375))
            open_p = price
            close_p = price + change
            high_p = max(open_p, close_p) + abs(change) * random.random()
            low_p = min(open_p, close_p) - abs(change) * random.random()
            volume = int(random.lognormvariate(10, 1))

            data.append({
                'datetime': timestamp,
                'open': open_p,
                'high': high_p,
                'low': low_p,
                'close': close_p,
                'volume': volume
            })

            price = close_p

    df = pd.DataFrame(data)
    df.set_index('datetime', inplace=True)
    return df

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

def get_3min_swing(df, current_idx):
    """
    Identifies the most recent swing high/low based on 3-minute resampling.
    This is a simplified implementation looking back at recent 3-min bars.
    """
    # Look back last 60 minutes to find swings
    # Resample last 60 mins of data to 3min

    # Optimization: Pass the resampled 3min dataframe and find the last swing
    # But for backtesting row-by-row, we can just look at the pre-calculated swings
    pass

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

    return df_3min

def backtest_strategy(df):
    df = calculate_indicators(df)
    df_3min = resample_to_3min(df)

    # Merge 3min swing levels back to 1min df (forward fill)
    # We need to be careful about lookahead bias.
    # The 3min swing at 9:33 is known at 9:33:00 (or end of it).
    # Resample sets label to left edge usually.
    # If 3min bar is 9:30-9:33. High is known at 9:33.
    # So at 9:33, we know the swing of the *previous* bar?
    # Logic: Swing High at T-1.
    # If we are at 9:33 (end of bar), and 9:30-9:33 was a swing high? No, that's current bar.
    # Swing High logic: High[t-1] > High[t-2] & High[t-1] > High[t].
    # So we need t (current completed bar) to confirm t-1 was a swing.
    # So the swing is confirmed 1 bar *after* the peak.
    # If working with 3-min bars, the swing determined by bars ending 9:30, 9:33, 9:36.
    # At 9:36, we compare 9:33 High with 9:30 and 9:36. If 9:33 is highest, then 9:33 was a swing high.
    # So we know it at 9:36.

    # Merge on time index
    # Forward fill the swings

    df = df.join(df_3min[['last_swing_high', 'last_swing_low']], how='left')
    df['last_swing_high'] = df['last_swing_high'].ffill()
    df['last_swing_low'] = df['last_swing_low'].ffill()

    trades = []
    active_position = None  # {type: 'CE'/'PE', entry_price: float, qty: int, sl: float, target: float, entry_time: datetime, entry_sl: float}

    daily_trades = {} # {date: count}

    print("Starting Backtest...")

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

        # Simulating Option Price
        # Assume ATM Option Delta 0.5. Price approx (Future - Strike) + TimeValue.
        # Simplification: Trade the Future directly but apply Option logic (Risk/Reward).
        # OR: Simulate Option Price = FuturePrice * 0.01 (Example) + Intrinsic.
        # Better: Assume we buy ATM. Delta 0.5.
        # Entry Price (Option) = 100 (Arbitrary base)
        # Option moves 0.5 points for every 1 point move in Future.
        # This preserves the "Strategy Logic" while abstracting Option Pricing model.

        option_delta = 0.5

        if active_position is None:
            if entry_window and daily_trades[current_date] < MAX_TRADES_PER_DAY:

                # Check Signals
                # Buy CE
                if (current_bar['close'] > current_bar['or_high']) and \
                   (current_bar['close'] > current_bar['vwap']) and \
                   (current_bar['vol_spike']):

                    # Entry Setup
                    # SL = Recent 3-min Swing Low
                    # If no swing low (early in day), use OR Low or Day Low?
                    # Fallback to OR Low if Swing Low is NaN or too far/close
                    sl_level = current_bar['last_swing_low']
                    if pd.isna(sl_level):
                         sl_level = current_bar['or_low']

                    # Entry execution
                    # Option Entry Calculation
                    # Future Entry = Current Close
                    # Future SL = sl_level
                    # Risk in Future Points = Future Entry - Future SL
                    # Option Risk Points = Future Risk Points * Delta

                    future_entry = current_bar['close']
                    future_risk = future_entry - sl_level

                    if future_risk > 0:
                        option_risk_pts = future_risk * option_delta

                        # Position Sizing
                        # Risk = 5000
                        # Qty = Risk / Option Risk Pts
                        qty = int(RISK_PER_TRADE / option_risk_pts)
                        # Round to nearest lot size? Or just raw?
                        # Using raw for precision in backtest

                        # Simulated Option Price (Base 200 + Intrinsic?)
                        # Just track PnL based on points
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
                    # Trail rest
                    # Usually move SL to Cost? Strategy says "Trail rest using Previous 3-min swing..."
                    # We continue to trailing logic below

            # 3. Trailing Logic
            # "Trail rest using: Previous 3-min swing low/high OR VWAP cross"
            # Update SL based on conditions

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
            # Update SL to recent swing
            if pos['type'] == 'CE':
                if not pd.isna(current_bar['last_swing_low']):
                     # Option SL level calculation based on Future Swing
                     # New SL Option = Entry Option + (Future Swing - Future Entry) * Delta
                     # Basically mapping Future Swing Level to Option Price
                     future_swing_level = current_bar['last_swing_low']

                     # Trail up only
                     # If future swing is higher than previous reference level?
                     # We need to maintain the SL price.

                     new_sl_opt = pos['entry_price'] + (future_swing_level - pos['future_entry']) * option_delta

                     if new_sl_opt > pos['sl']:
                         pos['sl'] = new_sl_opt
                         # print(f"[{timestamp}] Trailing SL Updated to {pos['sl']:.2f}")

            else: # PE
                if not pd.isna(current_bar['last_swing_high']):
                     future_swing_level = current_bar['last_swing_high']

                     # Put Price increases as Future decreases.
                     # SL for Put is below current price.
                     # If Future Swing High moves down, Put SL moves up.
                     # New SL Opt = Entry Opt - (Future Swing - Future Entry) * Delta ?
                     # Wait. Put PnL = (Entry Future - Current Future) * Delta
                     # Price = Entry Opt + PnL

                     # If Future is at Swing High (Stop Level for Put).
                     # PnL at Stop = (Entry Future - Swing High) * Delta
                     # SL Opt Price = Entry Opt + (Entry Future - Swing High) * Delta

                     new_sl_opt = pos['entry_price'] + (pos['future_entry'] - future_swing_level) * option_delta

                     if new_sl_opt > pos['sl']:
                         pos['sl'] = new_sl_opt
                         # print(f"[{timestamp}] Trailing SL Updated to {pos['sl']:.2f}")

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
    print("Generating Dummy Data...")
    df = generate_dummy_data(days=5)
    print("Data Generated. Rows:", len(df))

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
