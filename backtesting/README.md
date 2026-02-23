# Nifty Option Backtesting Strategy

This directory contains a Python script to backtest an intraday Nifty Options strategy based on Nifty Future price action.

## Strategy Overview

*   **Instrument**: Nifty ATM Options (Weekly Expiry).
*   **Timeframe**: 1-minute chart (Entries), 3-minute chart (Trailing Stop).
*   **Entry Time**: 09:30 AM to 11:30 AM.
*   **Setup**:
    *   Calculate Opening Range (OR) High/Low (09:15 - 09:30).
    *   Buy CE if Close > OR High AND Close > VWAP AND Volume Spike.
    *   Buy PE if Close < OR Low AND Close < VWAP AND Volume Spike.
*   **Risk Management**:
    *   Max 2 trades per day.
    *   Risk per trade: 1% of Capital (₹5,00,000) = ₹5,000.
    *   Position Sizing: Risk / (Entry - Initial SL).
*   **Exit Rules**:
    *   Target 1: Book 50% quantity at 1:1 Risk:Reward.
    *   Trailing Stop: Trail remaining quantity using Previous 3-min Swing Low/High OR VWAP Cross.

## Usage

1.  **Install Dependencies**:
    ```bash
    pip install pandas numpy
    ```
    Also ensure `dhanhq` is installed (available in the parent repository).

2.  **Set Environment Variables**:
    To use real historical data, you must provide your DhanHQ API credentials.
    
    ```bash
    export DHAN_CLIENT_ID="your_client_id"
    export DHAN_ACCESS_TOKEN="your_access_token"
    # Optional: Set the specific Nifty Future Security ID (Default: 13 which is Index, needs to be Future ID)
    export DHAN_SECURITY_ID="YOUR_NIFTY_FUT_SECURITY_ID"
    ```

3.  **Run the Backtest**:
    ```bash
    python backtest_strategy.py
    ```

    The script will fetch 5 days of historical 1-minute data for the specified Security ID and run the backtest.

## Notes

*   **Security ID**: The script defaults `SECURITY_ID` to "13" (Nifty Index). For accurate backtesting, you **must** find the Security ID of the specific Nifty Future contract you want to test (e.g., current month expiry) and set the `DHAN_SECURITY_ID` environment variable.
*   **Data**: The script fetches data using `dhan.intraday_minute_data`. Ensure your API subscription supports this.
*   **Option Pricing**: The backtest simulates option prices using a Delta of 0.5 (ATM) relative to the Future price movement, as historical option charts for specific strikes are harder to map dynamically without an Option Chain history database.
