# Importing required libraries
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime, timedelta
import yfinance as yf
import argparse

# Setting the plot style
plt.style.use('seaborn-v0_8-whitegrid')

def download_crypto_data(tickers, start_date, end_date):
    """
    Download cryptocurrency data from Yahoo Finance.

    Args:
        tickers (list): List of cryptocurrency tickers to download.
        start_date (datetime): Start date for the data.
        end_date (datetime): End date for the data.

    Returns:
        dict: A dictionary containing DataFrames for each cryptocurrency.
    """
    data = {}
    for ticker in tickers:
        print(f"Downloading data for {ticker}...")
        data[ticker] = yf.download(ticker, start=start_date, end=end_date)
    return data

def calculate_daily_returns(data):
    """
    Calculate daily returns for the given cryptocurrency data.

    Args:
        data (DataFrame): DataFrame containing cryptocurrency price data.

    Returns:
        DataFrame: DataFrame with daily returns added.
    """
    data['Return'] = data['Close'].pct_change() * 100  # Calculate daily returns as percentage
    return data.dropna()  # Drop NaN values

def group_returns_by_day(data, days_order):
    """
    Group returns by day of the week and calculate statistics.

    Args:
        data (DataFrame): DataFrame containing daily returns.
        days_order (list): List of days of the week for ordering.

    Returns:
        DataFrame: DataFrame with mean, std, and count of returns grouped by day.
    """
    data.loc[:, 'Day'] = data.index.day_name()  # Add day of week using .loc
    return data.groupby('Day')['Return'].agg(['mean', 'std', 'count']).reindex(days_order)

def create_radial_plot(ax, means_dict, days_circle):
    """
    Create a radial plot for average daily returns.

    Args:
        ax (matplotlib.axes.Axes): The axes to plot on.
        means_dict (dict): Dictionary of average returns for each cryptocurrency.
        days_circle (list): List of days of the week for plotting.

    Returns:
        None
    """
    # Setting up the angles for 7 days of week (in radians)
    angles = np.linspace(0, 2 * np.pi, len(days_circle), endpoint=False).tolist()
    angles += angles[:1]  # Make a full circle for plotting

    for crypto, means in means_dict.items():
        means += means[:1]  # Make a full circle for plotting
        ax.fill(angles, means, alpha=0.3, label=f'{crypto} Return')
        ax.plot(angles, means, 'o-', linewidth=2)

    # Setting the angle names
    ax.set_xticks(angles[:-1])  # Set ticks for the 7 days
    ax.set_xticklabels(days_circle)  # Use only the original days for labels
    ax.set_rlabel_position(0)
    ax.grid(True)
    ax.legend(loc='upper right', bbox_to_anchor=(0.1, 0.1))
    ax.set_title("Average Daily Return by Day of Week", size=14, pad=20)

def create_box_plot(ax, data_dict, days_order):
    """
    Create a box plot for daily returns by day of the week.

    Args:
        ax (matplotlib.axes.Axes): The axes to plot on.
        data_dict (dict): Dictionary of DataFrames for each cryptocurrency.
        days_order (list): List of days of the week for ordering.

    Returns:
        None
    """
    # Creating a DataFrame for the box plot
    box_data = pd.DataFrame()
    for crypto, data in data_dict.items():
        # Include the 'Day' column from the original data
        temp_df = pd.DataFrame({
            'Day': data.index.day_name().tolist(),  # Get the day names from the index
            'Return': data['Return'].tolist(),
            'Cryptocurrency': [crypto] * len(data)
        })
        box_data = pd.concat([box_data, temp_df], ignore_index=True)

    # Reordering the days
    box_data['Day'] = pd.Categorical(box_data['Day'], categories=days_order, ordered=True)

    # Creating box plots
    sns.boxplot(x='Day', y='Return', hue='Cryptocurrency', data=box_data,
                palette='Set2', ax=ax)

    # Add jittered points
    sns.stripplot(x='Day', y='Return', hue='Cryptocurrency', data=box_data,
                  palette='dark', size=2, alpha=0.3, dodge=True, ax=ax)

    # Adjusting legend
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles[:len(data_dict)], labels[:len(data_dict)], title='Cryptocurrency')

    # Adding a horizontal line at y=0
    ax.axhline(y=0, color='black', linestyle='-', alpha=0.3)

    ax.set_title('Distribution of Daily Returns by Day of Week', size=14)
    ax.set_xlabel('Day of Week', size=12)
    ax.set_ylabel('Return (%)', size=12)

def main():
    # Define the list of cryptocurrencies and the look-back period
    cryptocurrencies = ['SOL-USD', 'ETH-USD']  # You can add more cryptocurrencies here
    look_back_days = 365  # Number of days to look back

    # Set up argument parser
    parser = argparse.ArgumentParser(description='Analyze weekly returns of cryptocurrencies.')
    parser.add_argument('--currencies', nargs='+', default=cryptocurrencies,
                        help='List of cryptocurrencies to analyze (default: BTC-USD ETH-USD)')
    parser.add_argument('--days', type=int, default=look_back_days,
                        help='Number of days to analyze (default: 90)')
    args = parser.parse_args()

    # Setting start and end dates using datetime.now and timedelta
    end_date = datetime.now()
    start_date = end_date - timedelta(days=args.days)

    # Downloading cryptocurrency data
    data = download_crypto_data(args.currencies, start_date, end_date)

    # Calculate daily returns and group by day for each cryptocurrency
    days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    returns_by_crypto = {}
    means_by_crypto = {}

    for ticker in args.currencies:
        crypto_data = calculate_daily_returns(data[ticker])
        returns_by_crypto[ticker] = group_returns_by_day(crypto_data, days_order)
        means_by_crypto[ticker] = returns_by_crypto[ticker]['mean'].values.tolist()

    # Print returns by day of the week for each cryptocurrency
    for ticker in args.currencies:
        print(f"{ticker} returns by day of week:")
        print(returns_by_crypto[ticker]['mean'])
        print("\n")

    # Create a single figure for both plots
    fig = plt.figure(figsize=(20, 10))

    # Create radial plot
    ax1 = fig.add_subplot(121, projection='polar')
    create_radial_plot(ax1, means_by_crypto, days_order)

    # Create box plot
    ax2 = fig.add_subplot(122)
    create_box_plot(ax2, data, days_order)  # Pass the original data instead of grouped data

    # Adjust layout and display the plot
    plt.tight_layout()
    plt.savefig('crypto_weekly_returns.png', dpi=300, bbox_inches='tight')
    plt.show()

if __name__ == "__main__":
    main()