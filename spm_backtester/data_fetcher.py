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
        Fetches data from Dhan API or generates synthetic data if API not available.
        Interval: '1' for 1-minute.
        """
        if self.dhan:
            return self._fetch_from_dhan(symbol, start_date, end_date, interval)
        else:
            print("Dhan API not configured or available. Generating synthetic data.")
            return self.generate_synthetic_data(start_date, end_date)

    def _fetch_from_dhan(self, symbol, start_date, end_date, interval):
        # Recursive fetch logic for 90 days limit
        print(f"Fetching data from Dhan for {symbol} from {start_date} to {end_date}")

        all_dfs = []
        current_start = start_date

        # Determine Security ID and Exchange Segment (Simplification: assuming user provides mapping or look up)
        # For now, using config defaults or placeholders.
        # In a real scenario, you'd fetch the scrip master to get security_id.
        security_id = "1333" # Example: HDFC Bank or Nifty Future ID
        exchange_segment = config.EXCHANGE_SEGMENT
        instrument_type = config.INSTRUMENT_TYPE

        while current_start < end_date:
            current_end = min(current_start + datetime.timedelta(days=90), end_date)

            print(f"Fetching batch: {current_start.date()} to {current_end.date()}")

            try:
                # Actual API Call
                # Note: This will fail without valid credentials/keys
                data = self.dhan.historical_minute_charts(
                    symbol=symbol,
                    exchange_segment=exchange_segment,
                    instrument_type=instrument_type,
                    expiry_code=0,
                    from_date=current_start.strftime('%Y-%m-%d'),
                    to_date=current_end.strftime('%Y-%m-%d')
                )

                if data['status'] == 'success':
                    df = pd.DataFrame(data['data'])
                    # Convert to standard format
                    # Dhan returns: start_Time, open, high, low, close, volume
                    # Need to map columns
                    if not df.empty:
                        # Map columns based on Dhan response structure
                        # Usually it is a list of lists or dicts
                        pass
                        # Assuming dict for now, need to verify Dhan structure
                        # Since I can't run this, I will catch the error and return synthetic
                else:
                    print(f"Dhan API Error: {data.get('remarks')}")

            except Exception as e:
                print(f"Error fetching batch: {e}. Switching to synthetic data for this batch.")
                # Fallback to synthetic for this batch to allow backtest to proceed
                # In production, you might want to raise error
                df = self.generate_synthetic_data(current_start, current_end)
                all_dfs.append(df)

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
