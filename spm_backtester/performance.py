import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
from . import config

def calculate_metrics(trades_df, equity_curve):
    """
    Calculates performance metrics.
    """
    if trades_df.empty:
        return {}

    total_trades = len(trades_df)
    winning_trades = trades_df[trades_df['pnl'] > 0]
    losing_trades = trades_df[trades_df['pnl'] <= 0]

    num_winners = len(winning_trades)
    num_losers = len(losing_trades)

    win_rate = (num_winners / total_trades) * 100

    avg_win = winning_trades['pnl'].mean() if num_winners > 0 else 0
    avg_loss = losing_trades['pnl'].mean() if num_losers > 0 else 0

    risk_reward = abs(avg_win / avg_loss) if avg_loss != 0 else 0

    # Drawdown
    equity_df = pd.DataFrame(equity_curve)
    if equity_df.empty:
        return {}

    equity_df['peak'] = equity_df['equity'].cummax()
    equity_df['drawdown'] = (equity_df['equity'] - equity_df['peak']) / equity_df['peak']
    max_drawdown = equity_df['drawdown'].min() * 100 # Percentage

    # Consecutive Losses
    trades_df['is_loss'] = trades_df['pnl'] <= 0
    # Group consecutive losses
    consecutive_losses = 0
    current_streak = 0
    for is_loss in trades_df['is_loss']:
        if is_loss:
            current_streak += 1
        else:
            consecutive_losses = max(consecutive_losses, current_streak)
            current_streak = 0
    consecutive_losses = max(consecutive_losses, current_streak)

    # Expectancy = (Win% * AvgWin) - (Loss% * AvgLoss)
    win_prob = num_winners / total_trades
    loss_prob = num_losers / total_trades
    expectancy = (win_prob * avg_win) + (loss_prob * avg_loss) # avg_loss is negative

    # CAGR and Calmar (Approximate based on period)
    start_date = trades_df['entry_time'].min()
    end_date = trades_df['exit_time'].max()

    if pd.isna(start_date) or pd.isna(end_date):
        days = 0
    else:
        days = (end_date - start_date).days

    years = days / 365.0

    final_equity = equity_df['equity'].iloc[-1]
    initial_equity = config.INITIAL_CAPITAL

    if years > 0 and initial_equity > 0 and final_equity > 0:
        cagr = ((final_equity / initial_equity) ** (1/years)) - 1
        cagr *= 100
    else:
        cagr = 0

    calmar = abs(cagr / max_drawdown) if max_drawdown != 0 else 0

    return {
        'Total Trades': total_trades,
        'Win Rate (%)': win_rate,
        'Avg Win': avg_win,
        'Avg Loss': avg_loss,
        'Risk Reward Ratio': risk_reward,
        'Max Drawdown (%)': max_drawdown,
        'Consecutive Losses': consecutive_losses,
        'Expectancy': expectancy,
        'CAGR (%)': cagr,
        'Calmar Ratio': calmar,
        'Initial Capital': initial_equity,
        'Final Equity': final_equity,
        'Total PnL': final_equity - initial_equity
    }

def plot_results(df_3min, trades_df, equity_curve, small_pivots, large_pivots):
    """
    Generates and saves plots.
    """
    if not config.SAVE_PLOTS:
        return

    os.makedirs(config.PLOT_DIR, exist_ok=True)

    # 1. Equity Curve
    plt.figure(figsize=(12, 6))
    eq_df = pd.DataFrame(equity_curve)
    plt.plot(eq_df['datetime'], eq_df['equity'], label='Equity')
    plt.title('Equity Curve')
    plt.xlabel('Date')
    plt.ylabel('Capital')
    plt.grid(True)
    plt.legend()
    plt.savefig(os.path.join(config.PLOT_DIR, 'equity_curve.png'))
    plt.close()

    # 2. Drawdown
    plt.figure(figsize=(12, 6))
    eq_df['peak'] = eq_df['equity'].cummax()
    eq_df['dd'] = (eq_df['equity'] - eq_df['peak']) / eq_df['peak']
    plt.fill_between(eq_df['datetime'], eq_df['dd'], color='red', alpha=0.3)
    plt.title('Drawdown Curve')
    plt.xlabel('Date')
    plt.ylabel('Drawdown %')
    plt.grid(True)
    plt.savefig(os.path.join(config.PLOT_DIR, 'drawdown.png'))
    plt.close()

    # 3. Price Chart with Pivots and Trades (Last 5 days or all?)
    # Plotting all 3 years is too heavy. Let's plot last 500 bars (approx 3 days).
    subset_len = min(500, len(df_3min))
    df_subset = df_3min.iloc[-subset_len:]
    start_t = df_subset.index[0]
    end_t = df_subset.index[-1]

    plt.figure(figsize=(15, 8))
    plt.plot(df_subset.index, df_subset['close'], label='Close Price', alpha=0.5)

    # Plot Pivots
    # Filter pivots in range
    sphs = [p for p in small_pivots if p['type'] == 'SPH' and start_t <= p['datetime'] <= end_t]
    spls = [p for p in small_pivots if p['type'] == 'SPL' and start_t <= p['datetime'] <= end_t]
    lphs = [p for p in large_pivots if p['type'] == 'LPH' and start_t <= p['datetime'] <= end_t]
    lpls = [p for p in large_pivots if p['type'] == 'LPL' and start_t <= p['datetime'] <= end_t]

    for p in sphs:
        plt.plot(p['datetime'], p['price'], 'v', color='orange', markersize=4, label='SPH')
    for p in spls:
        plt.plot(p['datetime'], p['price'], '^', color='orange', markersize=4, label='SPL')

    for p in lphs:
        plt.plot(p['datetime'], p['price'], 'v', color='red', markersize=8, markeredgecolor='black', label='LPH')
    for p in lpls:
        plt.plot(p['datetime'], p['price'], '^', color='green', markersize=8, markeredgecolor='black', label='LPL')

    # Plot Trades
    trade_subset = trades_df[(trades_df['entry_time'] >= start_t) & (trades_df['entry_time'] <= end_t)]
    for idx, t in trade_subset.iterrows():
        color = 'green' if t['pnl'] > 0 else 'red'
        # Entry
        plt.plot(t['entry_time'], t['entry_price'], 'o', color='blue', markersize=5)
        # Exit
        plt.plot(t['exit_time'], t['exit_price'], 'x', color=color, markersize=5)
        # Line
        plt.plot([t['entry_time'], t['exit_time']], [t['entry_price'], t['exit_price']], color=color, linestyle='--', alpha=0.7)

    plt.title('Price Action with Structure & Trades (Last ~3 Days)')
    plt.grid(True)
    # Deduplicate legend
    handles, labels = plt.gca().get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    plt.legend(by_label.values(), by_label.keys())

    plt.savefig(os.path.join(config.PLOT_DIR, 'chart.png'))
    print(f"Plots saved to {config.PLOT_DIR}")
    plt.close()
