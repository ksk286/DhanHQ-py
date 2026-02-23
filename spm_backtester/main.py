import sys
import os
import datetime
import argparse
import pandas as pd

# Shim for running as script
if __package__ is None or __package__ == "":
    # Add project root to path
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

    # Import config directly if running as script
    # But relative import "from . import config" fails if __package__ is None.
    # We can fake it by importing as a module.
    # Or cleaner: Just use absolute imports if possible?
    # Relative imports require __package__ to be set.

    # Let's try setting __package__ manually?
    # This is tricky.
    # Better: Use try/except or absolute imports with path modification.

    # Let's just import config directly using importlib or sys.path
    try:
        from spm_backtester import config
        from spm_backtester.backtester import Backtester
        from spm_backtester.performance import calculate_metrics, plot_results
    except ImportError:
        # Fallback if run from inside spm_backtester dir?
        import config
        from backtester import Backtester
        from performance import calculate_metrics, plot_results
else:
    from . import config
    from .backtester import Backtester
    from .performance import calculate_metrics, plot_results

def main():
    parser = argparse.ArgumentParser(description="SPM Backtester")
    parser.add_argument("--symbol", type=str, default=config.SYMBOL, help="Trading Symbol")
    parser.add_argument("--days", type=int, default=365*3, help="Number of days to backtest (default 3 years)")
    parser.add_argument("--start", type=str, help="Start Date YYYY-MM-DD")
    parser.add_argument("--end", type=str, help="End Date YYYY-MM-DD")

    args = parser.parse_args()

    end_date = datetime.datetime.now()
    if args.end:
        end_date = datetime.datetime.strptime(args.end, "%Y-%m-%d")

    start_date = end_date - datetime.timedelta(days=args.days)
    if args.start:
        start_date = datetime.datetime.strptime(args.start, "%Y-%m-%d")

    print(f"--- SPM Backtester ---")
    print(f"Symbol: {args.symbol}")
    print(f"Period: {start_date.date()} to {end_date.date()}")

    bt = Backtester(symbol=args.symbol, start_date=start_date, end_date=end_date)
    trades_df, df_3min, small_pivots, large_pivots, equity_curve = bt.run()

    if trades_df.empty:
        print("No trades executed.")
        return

    # Metrics
    metrics = calculate_metrics(trades_df, equity_curve)

    print("\n--- Performance Metrics ---")
    for k, v in metrics.items():
        if isinstance(v, float):
            print(f"{k}: {v:.2f}")
        else:
            print(f"{k}: {v}")

    # Save Trades
    trades_file = f"trades_{args.symbol}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.csv"
    trades_df.to_csv(trades_file)
    print(f"\nTrades saved to {trades_file}")

    # Plots
    if config.SHOW_PLOTS or config.SAVE_PLOTS:
        print("Generating plots...")
        plot_results(df_3min, trades_df, equity_curve, small_pivots, large_pivots)

if __name__ == "__main__":
    main()
