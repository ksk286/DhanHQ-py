import pandas as pd
import numpy as np
import datetime

def identify_small_pivots(df):
    """
    Identifies Small Pivot Highs (SPH) and Small Pivot Lows (SPL).
    """
    df['sph'] = False
    df['spl'] = False
    df['pivot_type'] = None # 'SPH' or 'SPL'

    pivots = []

    bars = df.reset_index().to_dict('records')
    n = len(bars)

    last_pivot_type = None

    # Infer interval (approx)
    if n > 1:
        interval = bars[1]['datetime'] - bars[0]['datetime']
    else:
        interval = datetime.timedelta(minutes=5)

    i = 0
    while i < n - 2:
        # SPH: i+1 and i+2 have Lower Close and Lower Low than i
        is_sph_candidate = (
            bars[i+1]['close'] < bars[i]['close'] and
            bars[i+1]['low'] < bars[i]['low'] and
            bars[i+2]['close'] < bars[i]['close'] and
            bars[i+2]['low'] < bars[i]['low']
        )

        # SPL: i+1 and i+2 have Higher Close and Higher High than i
        is_spl_candidate = (
            bars[i+1]['close'] > bars[i]['close'] and
            bars[i+1]['high'] > bars[i]['high'] and
            bars[i+2]['close'] > bars[i]['close'] and
            bars[i+2]['high'] > bars[i]['high']
        )

        current_time = bars[i]['datetime']
        high = bars[i]['high']
        low = bars[i]['low']

        # Confirmation Time: End of i+2 bar
        conf_time = bars[i+2]['datetime'] + interval

        if is_sph_candidate:
            if last_pivot_type == 'SPH':
                # Update if Higher
                last_sph = pivots[-1]
                if high > last_sph['price']:
                     # Remove old SPH marker from DF
                     df.at[last_sph['datetime'], 'sph'] = False
                     df.at[last_sph['datetime'], 'pivot_type'] = None
                     pivots.pop()

                     # Add new
                     df.at[current_time, 'sph'] = True
                     df.at[current_time, 'pivot_type'] = 'SPH'
                     pivots.append({'datetime': current_time, 'type': 'SPH', 'price': high, 'confirmed_at': conf_time})
                     # i += 2 ?
                     # If we update, we technically confirmed it at i+2.
                     # So we should skip?
                     # Actually, if we update, the confirmation is relative to *this* new pivot.
                     # So yes, skip to i+2.
                     i += 2
                     continue
            elif last_pivot_type != 'SPH':
                 # New SPH after SPL (or first one)
                 df.at[current_time, 'sph'] = True
                 df.at[current_time, 'pivot_type'] = 'SPH'
                 pivots.append({'datetime': current_time, 'type': 'SPH', 'price': high, 'confirmed_at': conf_time})
                 last_pivot_type = 'SPH'
                 i += 2
                 continue

        if is_spl_candidate:
            if last_pivot_type == 'SPL':
                # Update if Lower
                last_spl = pivots[-1]
                if low < last_spl['price']:
                     df.at[last_spl['datetime'], 'spl'] = False
                     df.at[last_spl['datetime'], 'pivot_type'] = None
                     pivots.pop()

                     df.at[current_time, 'spl'] = True
                     df.at[current_time, 'pivot_type'] = 'SPL'
                     pivots.append({'datetime': current_time, 'type': 'SPL', 'price': low, 'confirmed_at': conf_time})
                     i += 2
                     continue
            elif last_pivot_type != 'SPL':
                 df.at[current_time, 'spl'] = True
                 df.at[current_time, 'pivot_type'] = 'SPL'
                 pivots.append({'datetime': current_time, 'type': 'SPL', 'price': low, 'confirmed_at': conf_time})
                 last_pivot_type = 'SPL'
                 i += 2
                 continue

        i += 1

    return df, pivots

def identify_large_pivots(df, small_pivots):
    """
    Identifies Large Pivots (LPH, LPL).
    """
    df['lph'] = False
    df['lpl'] = False
    df['large_pivot_type'] = None

    large_pivots = []

    candidate_sphs = []
    candidate_spls = []

    # Optimization: Dict lookup for pivots
    sph_lookup = {p['datetime']: p['price'] for p in small_pivots if p['type'] == 'SPH'}
    spl_lookup = {p['datetime']: p['price'] for p in small_pivots if p['type'] == 'SPL'}

    last_sph = None
    last_spl = None

    bars = df.reset_index().to_dict('records')

    if len(bars) > 1:
        interval = bars[1]['datetime'] - bars[0]['datetime']
    else:
        interval = datetime.timedelta(minutes=5)

    for i, bar in enumerate(bars):
        timestamp = bar['datetime']
        close = bar['close']

        # 1. Update candidates if current bar is a small pivot
        if timestamp in sph_lookup:
            last_sph = {'datetime': timestamp, 'price': sph_lookup[timestamp], 'index': i}
            candidate_sphs.append(last_sph)

        if timestamp in spl_lookup:
            last_spl = {'datetime': timestamp, 'price': spl_lookup[timestamp], 'index': i}
            candidate_spls.append(last_spl)

        # 2. Check for Break of SPL -> Confirm LPH
        if last_spl and close < last_spl['price']:
            if candidate_sphs:
                valid_sphs = [p for p in candidate_sphs if p['index'] < i] # All prior SPHs
                if valid_sphs:
                    best_sph = max(valid_sphs, key=lambda x: x['price'])

                    # Mark LPH if not already marked
                    if not df.at[best_sph['datetime'], 'lph']:
                        df.at[best_sph['datetime'], 'lph'] = True
                        df.at[best_sph['datetime'], 'large_pivot_type'] = 'LPH'
                        best_sph_copy = best_sph.copy()
                        best_sph_copy['type'] = 'LPH'
                        # Confirmed at end of current bar
                        best_sph_copy['confirmed_at'] = timestamp + interval
                        large_pivots.append(best_sph_copy)

                        candidate_sphs = [p for p in candidate_sphs if p['index'] > best_sph['index']]

        # 3. Check for Break of SPH -> Confirm LPL
        if last_sph and close > last_sph['price']:
            if candidate_spls:
                valid_spls = [p for p in candidate_spls if p['index'] < i]
                if valid_spls:
                    best_spl = min(valid_spls, key=lambda x: x['price'])

                    if not df.at[best_spl['datetime'], 'lpl']:
                        df.at[best_spl['datetime'], 'lpl'] = True
                        df.at[best_spl['datetime'], 'large_pivot_type'] = 'LPL'
                        best_spl_copy = best_spl.copy()
                        best_spl_copy['type'] = 'LPL'
                        # Confirmed at end of current bar
                        best_spl_copy['confirmed_at'] = timestamp + interval
                        large_pivots.append(best_spl_copy)

                        candidate_spls = [p for p in candidate_spls if p['index'] > best_spl['index']]

    return df, large_pivots

if __name__ == "__main__":
    # Test Block with corrected data
    print("Testing Pivot Engine...")

    data = []
    base_time = datetime.datetime(2023, 1, 1, 9, 15)

    # Bar 0: High Pivot (100)
    data.append({'datetime': base_time, 'open': 95, 'high': 100, 'low': 90, 'close': 95})

    # Bar 1: Lower High/Low/Close
    data.append({'datetime': base_time + datetime.timedelta(minutes=5), 'open': 95, 'high': 98, 'low': 88, 'close': 92})

    # Bar 2: Lower High/Low/Close -> Confirms SPH at Bar 0
    data.append({'datetime': base_time + datetime.timedelta(minutes=10), 'open': 92, 'high': 96, 'low': 86, 'close': 90})

    # Bar 3: Transition to Low
    data.append({'datetime': base_time + datetime.timedelta(minutes=15), 'open': 90, 'high': 92, 'low': 80, 'close': 82})

    # Bar 4: Low Pivot (SPL) Candidate (Low 80)
    data.append({'datetime': base_time + datetime.timedelta(minutes=20), 'open': 82, 'high': 85, 'low': 80, 'close': 84})

    # Bar 5: Higher High/Low/Close
    data.append({'datetime': base_time + datetime.timedelta(minutes=25), 'open': 84, 'high': 88, 'low': 82, 'close': 86})

    # Bar 6: Higher High/Low/Close -> Confirms SPL at Bar 4?
    data.append({'datetime': base_time + datetime.timedelta(minutes=30), 'open': 86, 'high': 90, 'low': 83, 'close': 88})

    # Bar 7: Break SPH (100)
    data.append({'datetime': base_time + datetime.timedelta(minutes=35), 'open': 88, 'high': 105, 'low': 90, 'close': 102})

    df = pd.DataFrame(data)
    df.set_index('datetime', inplace=True)

    print("Data:")
    print(df[['high', 'low', 'close']])

    df, small_pivots = identify_small_pivots(df)
    print("\nSmall Pivots:")
    for p in small_pivots:
        print(f"{p['datetime']} {p['type']} {p['price']} ConfirmedAt: {p.get('confirmed_at')}")

    df, large_pivots = identify_large_pivots(df, small_pivots)
    print("\nLarge Pivots:")
    for p in large_pivots:
        print(f"{p['datetime']} {p['type']} {p['price']} ConfirmedAt: {p.get('confirmed_at')}")
