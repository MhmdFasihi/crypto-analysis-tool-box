"""Performance and risk-adjusted ratios.

Every ratio here takes a return series and the observed periods-per-year, so
the same code is correct for a 7-day crypto calendar and a 5-day equity one.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from crypto_toolbox.analytics import risk
from crypto_toolbox.analytics.returns import (drawdown, drawdown_details,
                                              max_drawdown, periods_per_year,
                                              total_return)


def cagr(returns: pd.Series, ppy: float) -> float:
    """Geometric annualised growth rate."""
    clean = returns.dropna()
    if len(clean) < 2:
        return float("nan")
    years = len(clean) / ppy
    return float((1 + total_return(clean)) ** (1 / years) - 1)


def annualised_volatility(returns: pd.Series, ppy: float) -> float:
    return float(returns.std(ddof=1) * np.sqrt(ppy))


def downside_deviation(returns: pd.Series, ppy: float, mar: float = 0.0) -> float:
    """Volatility of returns below the minimum acceptable return only."""
    shortfall = np.minimum(returns.dropna() - mar / ppy, 0.0)
    if shortfall.empty:
        return float("nan")
    return float(np.sqrt((shortfall ** 2).mean()) * np.sqrt(ppy))


def sharpe(returns: pd.Series, ppy: float, rf: float = 0.0) -> float:
    """Excess return per unit of total volatility."""
    vol = annualised_volatility(returns, ppy)
    if not vol:
        return float("nan")
    return (cagr(returns, ppy) - rf) / vol


def sortino(returns: pd.Series, ppy: float, rf: float = 0.0) -> float:
    """Excess return per unit of *downside* volatility."""
    dd = downside_deviation(returns, ppy, rf)
    if not dd:
        return float("nan")
    return (cagr(returns, ppy) - rf) / dd


def calmar(returns: pd.Series, ppy: float) -> float:
    """Annualised return per unit of worst drawdown."""
    mdd = abs(max_drawdown(returns))
    if not mdd:
        return float("nan")
    return cagr(returns, ppy) / mdd


def omega(returns: pd.Series, threshold: float = 0.0) -> float:
    """Ratio of probability-weighted gains to losses above/below a threshold."""
    clean = returns.dropna() - threshold
    gains = clean[clean > 0].sum()
    losses = -clean[clean < 0].sum()
    if not losses:
        return float("inf") if gains else float("nan")
    return float(gains / losses)


def ulcer_index(returns: pd.Series) -> float:
    """Root-mean-square drawdown: penalises depth *and* time underwater."""
    under = drawdown(returns)
    if under.empty:
        return float("nan")
    return float(np.sqrt((under ** 2).mean()))


def beta_alpha(returns: pd.Series, benchmark: pd.Series, ppy: float,
               rf: float = 0.0) -> tuple[float, float]:
    """CAPM beta and annualised Jensen's alpha against a benchmark."""
    paired = pd.concat([returns, benchmark], axis=1).dropna()
    if len(paired) < 30:
        return float("nan"), float("nan")
    asset, bench = paired.iloc[:, 0], paired.iloc[:, 1]
    var_b = bench.var(ddof=1)
    if not var_b:
        return float("nan"), float("nan")
    beta = float(asset.cov(bench) / var_b)
    alpha = cagr(asset, ppy) - (rf + beta * (cagr(bench, ppy) - rf))
    return beta, float(alpha)


def tracking_error(returns: pd.Series, benchmark: pd.Series, ppy: float) -> float:
    paired = pd.concat([returns, benchmark], axis=1).dropna()
    if len(paired) < 30:
        return float("nan")
    return float((paired.iloc[:, 0] - paired.iloc[:, 1]).std(ddof=1) * np.sqrt(ppy))


def information_ratio(returns: pd.Series, benchmark: pd.Series, ppy: float) -> float:
    """Active return per unit of tracking error."""
    te = tracking_error(returns, benchmark, ppy)
    if not te or np.isnan(te):
        return float("nan")
    paired = pd.concat([returns, benchmark], axis=1).dropna()
    active = cagr(paired.iloc[:, 0], ppy) - cagr(paired.iloc[:, 1], ppy)
    return float(active / te)


def treynor(returns: pd.Series, benchmark: pd.Series, ppy: float, rf: float = 0.0) -> float:
    """Excess return per unit of market beta."""
    beta, _ = beta_alpha(returns, benchmark, ppy, rf)
    if not beta or np.isnan(beta):
        return float("nan")
    return float((cagr(returns, ppy) - rf) / beta)


def summarise(returns: pd.Series, ppy: float | None = None, rf: float = 0.0,
              benchmark: pd.Series | None = None, level: float = 0.95) -> dict:
    """One row of the performance/risk table for a single asset."""
    clean = returns.dropna()
    ppy = ppy if ppy is not None else periods_per_year(clean.index)
    detail = drawdown_details(clean)
    row = {
        "total_return": total_return(clean),
        "cagr": cagr(clean, ppy),
        "volatility": annualised_volatility(clean, ppy),
        "downside_deviation": downside_deviation(clean, ppy, rf),
        "sharpe": sharpe(clean, ppy, rf),
        "sortino": sortino(clean, ppy, rf),
        "calmar": calmar(clean, ppy),
        "omega": omega(clean),
        "max_drawdown": detail["max_drawdown"],
        "days_underwater": detail["days_underwater"],
        "ulcer_index": ulcer_index(clean),
        "skew": float(clean.skew()) if len(clean) > 2 else float("nan"),
        "excess_kurtosis": float(clean.kurtosis()) if len(clean) > 3 else float("nan"),
        "hit_rate": float((clean > 0).mean()) if len(clean) else float("nan"),
        "best_day": float(clean.max()) if len(clean) else float("nan"),
        "worst_day": float(clean.min()) if len(clean) else float("nan"),
        "var_95": risk.historical_var(clean, level),
        "cvar_95": risk.historical_cvar(clean, level),
        "observations": int(len(clean)),
    }
    if benchmark is not None:
        beta, alpha = beta_alpha(clean, benchmark, ppy, rf)
        row.update({
            "beta": beta,
            "alpha": alpha,
            "tracking_error": tracking_error(clean, benchmark, ppy),
            "information_ratio": information_ratio(clean, benchmark, ppy),
            "treynor": treynor(clean, benchmark, ppy, rf),
        })
    return row
