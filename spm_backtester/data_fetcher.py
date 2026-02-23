import pandas as pd
import numpy as np
import datetime
import os
import time
from . import config

# Try to import dhanhq, if not available, we will rely on mock/csv
try:
    from dhanhq import dhanhq
    DHAN_AVAILABLE = True
except ImportError:
    DHAN_AVAILABLE = False

class DataFetcher:
    def __init__(self, client_id=None, access_token=None):
        self.client_id = client_id or config.DHAN_CLIENT_ID
        self.access_token = access_token or config.DHAN_ACCESS_TOKEN
        self.dhan = None

        if DHAN_AVAILABLE and self.client_id != "YOUR_CLIENT_ID":
            try:
                self.dhan = dhanhq(self.client_id, self.access_token)
            except Exception as e:
                print(f"Failed to initialize DhanHQ: {e}")

    def fetch_data(self, symbol, start_date, end_date, interval='1'):
        """
        Fetches data from Dhan API. Fails if API not available.
        Interval: '1' for 1-minute.
        """
        if self.dhan:
            return self._fetch_from_dhan(symbol, start_date, end_date, interval)
        else:
            raise Exception("Dhan API not configured or available. Set DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN in environment.")

    def _fetch_from_dhan(self, symbol, start_date, end_date, interval):
        # Recursive fetch logic for 90 days limit
        print(f"Fetching data from Dhan for {symbol} from {start_date} to {end_date}")

        all_dfs = []
        current_start = start_date

        # Determine Security ID and Exchange Segment
        # NOTE: Dhan requires 'security_id' (string code) not symbol name.
        # User is expected to provide correct ID or update config/mapping.
        # For NIFTY 50 Futures, typically it's needed to look up.
        # Here we assume the symbol passed IS the security_id if purely numeric,
        # or we fallback to config default.
        if symbol.isdigit():
             security_id = symbol
        else:
             # Fallback to a default or require user input
             # For NIFTY 50 Index Future, ID changes every expiry.
             # Using a placeholder ID that user must update in config if needed.
             security_id = getattr(config, 'DHAN_SECURITY_ID', '1333')

        exchange_segment = getattr(config, 'DHAN_EXCHANGE_SEGMENT', 'NSE_FNO')
        instrument_type = getattr(config, 'DHAN_INSTRUMENT_TYPE', 'FUT')

        while current_start < end_date:
            current_end = min(current_start + datetime.timedelta(days=90), end_date)

            print(f"Fetching batch: {current_start.date()} to {current_end.date()}")

            try:
                # Actual API Call
                data = self.dhan.intraday_minute_data(
                    security_id=security_id,
                    exchange_segment=exchange_segment,
                    instrument_type=instrument_type,
                    from_date=current_start.strftime('%Y-%m-%d'),
                    to_date=current_end.strftime('%Y-%m-%d')
                )

                if data['status'] == 'success':
                    # data['data'] is typically a dict with lists: {'start_Time': [], 'open': [], ...}
                    # or a list of dicts. The library usually returns a dict matching the API response.
                    raw_data = data['data']

                    if isinstance(raw_data, dict):
                        df = pd.DataFrame(raw_data)
                    else:
                        # Assuming list of dicts if not dict of lists
                        df = pd.DataFrame(raw_data)

                    if not df.empty:
                        # Standardize columns
                        # Dhan API typically returns: start_Time (epoch), open, high, low, close, volume
                        # Check column names

                        # Handle Dhan timestamp (epoch or string?)
                        # Usually Dhan returns 'start_Time' as integer (epoch time)
                        if 'start_Time' in df.columns:
                             # Convert epoch to datetime
                             # Dhan epoch is usually standard unix timestamp
                             df['datetime'] = pd.to_datetime(df['start_Time'], unit='s')
                             # Convert to IST? Dhan returns time in IST usually? Or UTC?
                             # Usually Indian APIs return IST or timestamp. Pandas assumes UTC if unit='s'.
                             # We'll localize to UTC then convert to Asia/Kolkata if needed.
                             # For simplicity, assuming local naive time matching market hours.
                             # If values look like 167... it's epoch.
                             pass
                        elif 'date' in df.columns:
                             df['datetime'] = pd.to_datetime(df['date'])

                        # Ensure standard OHLCV columns
                        rename_map = {
                            'start_Time': 'datetime',
                            'o': 'open', 'h': 'high', 'l': 'low', 'c': 'close', 'v': 'volume',
                            'open': 'open', 'high': 'high', 'low': 'low', 'close': 'close', 'volume': 'volume'
                        }
                        df.rename(columns=rename_map, inplace=True)

                        # Set Index
                        if 'datetime' in df.columns:
                            df.set_index('datetime', inplace=True)
                            all_dfs.append(df)
                        else:
                            print("Warning: Could not identify datetime column in Dhan response.")
                            print(df.columns)
                    else:
                        print(f"No data returned for batch {current_start.date()}")

                else:
                    print(f"Dhan API Error: {data.get('remarks')}")
                    # If error is about invalid session, stop.
                    if "Session" in str(data.get('remarks')):
                        raise Exception("Invalid Session")

            except Exception as e:
                print(f"Error fetching batch: {e}")
                raise e # Stop if real API fails

            current_start = current_end + datetime.timedelta(days=1)
            time.sleep(0.5) # Rate limit

        if all_dfs:
            final_df = pd.concat(all_dfs)
            # Remove duplicates
            final_df = final_df[~final_df.index.duplicated(keep='first')]
            return final_df.sort_index()
        else:
            return None

    def generate_synthetic_data(self, start_date, end_date):
        """Generates synthetic 1-minute OHLCV data."""
        # Ensure dates are datetime objects
        if isinstance(start_date, str):
            start_date = datetime.datetime.strptime(start_date, "%Y-%m-%d")
        if isinstance(end_date, str):
            end_date = datetime.datetime.strptime(end_date, "%Y-%m-%d")

        print(f"Generating synthetic data from {start_date.date()} to {end_date.date()}...")

        data = []
        price = 19500.0 # Nifty-ish level

        current_date = start_date
        while current_date <= end_date:
            if current_date.weekday() < 5: # Mon-Fri
                # Market hours 9:15 to 15:30 -> 375 minutes
                market_open = current_date.replace(hour=9, minute=15, second=0, microsecond=0)

                # Random daily trend
                daily_trend = np.random.normal(0, 0.005)

                for i in range(375):
                    timestamp = market_open + datetime.timedelta(minutes=i)

                    # Random walk with drift
                    change = price * np.random.normal(daily_trend/375, 0.0005)

                    open_p = price
                    close_p = price + change
                    high_p = max(open_p, close_p) + abs(change) * np.random.random() * 2
                    low_p = min(open_p, close_p) - abs(change) * np.random.random() * 2
                    volume = int(np.random.lognormal(10, 1))

                    data.append({
                        'datetime': timestamp,
                        'open': open_p,
                        'high': high_p,
                        'low': low_p,
                        'close': close_p,
                        'volume': volume
                    })

                    price = close_p

            current_date += datetime.timedelta(days=1)

        df = pd.DataFrame(data)
        if not df.empty:
            df.set_index('datetime', inplace=True)
        return df

    def save_data(self, df, filename):
        filepath = os.path.join(config.DATA_DIR, filename)
        # Ensure index is datetime
        df.to_csv(filepath)
        print(f"Data saved to {filepath}")

    def load_data(self, filename):
        filepath = os.path.join(config.DATA_DIR, filename)
        if not os.path.exists(filepath):
            print(f"File {filepath} not found.")
            return None
        df = pd.read_csv(filepath, parse_dates=['datetime'], index_col='datetime')
        return df

    def resample_data(self, df, timeframe):
        """
        Resamples 1-min data to specified timeframe (e.g., '3min', '5min').
        """
        conversion = {
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum'
        }
        # Check if timeframe needs 'T' or 'min' for pandas
        # Pandas uses 'T' or 'min'.

        df_resampled = df.resample(timeframe).agg(conversion)
        # Drop rows with NaN (incomplete bars or non-trading times if any)
        df_resampled.dropna(inplace=True)
        return df_resampled

if __name__ == "__main__":
    # Test Block
    fetcher = DataFetcher()

    start = datetime.datetime.now() - datetime.timedelta(days=5)
    end = datetime.datetime.now()

    df = fetcher.fetch_data("TEST_SYMBOL", start, end)
    print(f"Generated {len(df)} rows.")
    print(df.head())

    fetcher.save_data(df, "test_data.csv")

    loaded_df = fetcher.load_data("test_data.csv")
    print(f"Loaded {len(loaded_df)} rows.")

    df_3min = fetcher.resample_data(loaded_df, "3min")
    print(f"Resampled to 3min: {len(df_3min)} rows.")
    print(df_3min.head())
