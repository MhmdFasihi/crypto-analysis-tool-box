"""Return construction, alignment and drawdown mechanics.

Conventions used across the whole toolbox:

* ``prices``  -- wide DataFrame, one column per asset key, DatetimeIndex, daily.
* ``returns`` -- simple arithmetic returns unless a function says otherwise.
* Annualisation uses the *observed* periods per year of the aligned calendar,
  so a 7-day crypto series and a 5-day equity series are not silently mixed.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS = 252
CALENDAR_DAYS = 365


def align_prices(prices: pd.DataFrame, mode: str = "intersection") -> pd.DataFrame:
    """Put assets on a common calendar.

    ``intersection`` keeps only days every asset traded. That is the honest
    default for correlation and beta: crypto trades 7 days a week while the
    indices and futures do not, and a forward-filled weekend shows up as a
    fake zero return for the traditional assets, which drags every correlation
    toward zero.

    ``union`` keeps every calendar day any asset traded and forward-fills.
    Useful for a continuous price panel, misleading for co-movement stats.
    """
    if mode == "intersection":
        return prices.dropna(how="any")
    if mode == "union":
        return prices.ffill().dropna(how="all")
    raise ValueError(f"unknown alignment mode: {mode!r}")


def to_returns(prices: pd.DataFrame | pd.Series, log: bool = False):
    """Period-over-period returns of an aligned price panel."""
    if log:
        return np.log(prices / prices.shift(1)).dropna(how="all")
    return prices.pct_change().dropna(how="all")


def periods_per_year(index: pd.DatetimeIndex) -> float:
    """Observed sampling frequency, used for annualisation."""
    if len(index) < 3:
        return float(TRADING_DAYS)
    span_days = (index[-1] - index[0]).days
    if span_days <= 0:
        return float(TRADING_DAYS)
    return len(index) / (span_days / CALENDAR_DAYS)


def cumulative(returns: pd.DataFrame | pd.Series):
    """Growth of 1 unit, starting at 1.0."""
    return (1 + returns).cumprod()


def rebased(prices: pd.DataFrame | pd.Series, base: float = 100.0):
    """Price panel rebased so every series starts at ``base``."""
    return prices / prices.iloc[0] * base


def drawdown(returns: pd.Series) -> pd.Series:
    """Underwater curve: current value relative to the running peak."""
    curve = cumulative(returns)
    return curve / curve.cummax() - 1.0


def max_drawdown(returns: pd.Series) -> float:
    """Worst peak-to-trough loss, as a negative number."""
    if returns.empty:
        return float("nan")
    return float(drawdown(returns).min())


def drawdown_details(returns: pd.Series) -> dict:
    """Depth, trough date and recovery length of the worst drawdown."""
    if returns.empty:
        return {"max_drawdown": float("nan"), "trough": None, "days_underwater": 0}
    under = drawdown(returns)
    trough = under.idxmin()
    peak = under.loc[:trough]
    peak_date = peak[peak >= -1e-12].index[-1] if (peak >= -1e-12).any() else under.index[0]
    after = under.loc[trough:]
    recovered = after[after >= -1e-12]
    end = recovered.index[0] if len(recovered) else under.index[-1]
    return {
        "max_drawdown": float(under.min()),
        "peak": peak_date,
        "trough": trough,
        "recovery": recovered.index[0] if len(recovered) else None,
        "days_underwater": int((end - peak_date).days),
    }


def total_return(returns: pd.Series) -> float:
    """Compounded return over the whole sample."""
    if returns.empty:
        return float("nan")
    return float((1 + returns).prod() - 1)


def calendar_year_returns(returns: pd.DataFrame) -> pd.DataFrame:
    """Compounded return per calendar year, years as rows."""
    grouped = returns.groupby(returns.index.year)
    out = grouped.apply(lambda block: (1 + block).prod() - 1)
    out.index.name = "year"
    return out


def rolling_volatility(returns: pd.Series, window: int, ppy: float) -> pd.Series:
    """Annualised rolling standard deviation."""
    return returns.rolling(window).std(ddof=1) * np.sqrt(ppy)
