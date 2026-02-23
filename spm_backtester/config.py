# Configuration for SPM Backtester

import os

# Dhan API Credentials
# Replace with your actual credentials or set via environment variables
DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID", "YOUR_CLIENT_ID")
DHAN_ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN", "YOUR_ACCESS_TOKEN")

# Data Fetching
SYMBOL = "NIFTY 50" # Default Symbol Name
DHAN_SECURITY_ID = "1333" # Default Security ID (e.g. NIFTY 50 Index Future). Update this!
DHAN_EXCHANGE_SEGMENT = "NSE_FNO" # Or NSE_EQ
DHAN_INSTRUMENT_TYPE = "FUT" # FUT/OPT or INDEX

# Backtesting Parameters
INITIAL_CAPITAL = 500000
RISK_PER_TRADE_PERCENT = 0.02 # 2%
MAX_RISK_PER_TRADE = 10000 # Max Risk Amount (INR)
SLIPPAGE_POINTS = 0.5 # Points per trade (entry+exit)
BROKERAGE_PER_ORDER = 20 # Flat fee per order

# Strategy Parameters
# Timeframes
TIMEFRAME_EXECUTION = "3min"
TIMEFRAME_STRUCTURE = "5min"

# Session Times
MARKET_OPEN_TIME = "09:15"
MARKET_CLOSE_TIME = "15:30"
SQUARE_OFF_TIME = "15:15"

# Plotting
SHOW_PLOTS = True
SAVE_PLOTS = True
PLOT_DIR = "plots"
DATA_DIR = "data"
