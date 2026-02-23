# Structural Pivot Method (SPM) Backtester

This project implements a fully automated backtesting system for the Structural Pivot Method (SPM) described by Madan Kumar.

## Features

*   **Modular Architecture**: Separate modules for data fetching, pivot calculation, strategy logic, risk management, and performance analysis.
*   **Pivot Engine**: Implements SPM rules for Small Pivots (SPH/SPL) and Large Pivots (LPH/LPL) with strict mechanical definitions.
*   **Backtester**: Bar-by-bar simulation with no lookahead bias.
*   **Risk Management**: Configurable position sizing, stop loss, and trailing stop mechanisms.
*   **Performance Metrics**: Detailed report including Win Rate, Drawdown, Sharpe/Calmar ratios, and Equity Curve.
*   **Visualization**: Generates price charts with pivot markers and trade execution points.

## Installation

1.  Clone the repository.
2.  Install dependencies:
    ```bash
    pip install pandas numpy matplotlib dhanhq
    ```
    (Note: `dhanhq` is optional if running with synthetic data)

## Configuration

Edit `spm_backtester/config.py` to set:
*   Dhan API Credentials (if using live data).
*   Risk Parameters (Initial Capital, Risk per Trade).
*   Timeframes (Execution and Structure).

## Usage

Run the backtester from the root directory:

```bash
python main.py --symbol "NIFTY 50" --days 365
```

Arguments:
*   `--symbol`: Trading Symbol (default: "NIFTY 50")
*   `--days`: Number of days to backtest (default: 1095 / 3 years)
*   `--start`: Start Date (YYYY-MM-DD)
*   `--end`: End Date (YYYY-MM-DD)

## Output

*   **Console**: Summary of performance metrics.
*   **CSV**: Trade log saved to current directory.
*   **Plots**: Saved to `plots/` directory (Equity Curve, Drawdown, Price Chart).

## Project Structure

*   `spm_backtester/`
    *   `data_fetcher.py`: Handles data retrieval and synthetic generation.
    *   `pivot_engine.py`: Core logic for identifying SPH, SPL, LPH, LPL.
    *   `strategy.py`: Implements entry and exit rules.
    *   `backtester.py`: Orchestrates the simulation.
    *   `risk_manager.py`: Position sizing and capital management.
    *   `performance.py`: Metrics and plotting.
    *   `config.py`: Configuration settings.
    *   `main.py`: CLI entry point.
*   `main.py`: Root entry point wrapper.
