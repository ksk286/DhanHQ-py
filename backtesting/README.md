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

2.  **Run the Backtest**:
    ```bash
    python backtest_strategy.py
    ```

    The script will generate dummy Nifty Future data (Random Walk) and simulate the strategy execution, printing a trade log and final PnL.

## Customization

*   **Data**: Replace `generate_dummy_data()` with your own data loading function (e.g., `pd.read_csv('nifty_future.csv')`). Ensure the DataFrame has `datetime` index and columns: `open`, `high`, `low`, `close`, `volume`.
*   **Parameters**: Adjust `CAPITAL`, `RISK_PER_TRADE`, `MAX_TRADES_PER_DAY` at the top of the script.
