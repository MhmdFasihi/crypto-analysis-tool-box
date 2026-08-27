"""Value at Risk, Expected Shortfall and VaR backtesting.

Sign convention: **VaR and CVaR are returned as positive loss magnitudes.**
A 1-day 95% VaR of 0.032 means "on the worst 5% of days, the loss is at least
3.2%". CVaR is the average loss on exactly those days, so CVaR >= VaR always.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

METHODS = ("historical", "parametric", "cornish_fisher", "monte_carlo")


def historical_var(returns: pd.Series, level: float = 0.95) -> float:
    """Empirical quantile of the loss distribution. No distributional assumption."""
    clean = returns.dropna()
    if len(clean) < 30:
        return float("nan")
    return float(-np.quantile(clean, 1 - level))


def historical_cvar(returns: pd.Series, level: float = 0.95) -> float:
    """Mean loss beyond the historical VaR threshold."""
    clean = returns.dropna()
    if len(clean) < 30:
        return float("nan")
    cutoff = np.quantile(clean, 1 - level)
    tail = clean[clean <= cutoff]
    return float(-tail.mean()) if len(tail) else float("nan")


def parametric_var(returns: pd.Series, level: float = 0.95) -> float:
    """Gaussian VaR. Understates risk for the fat-tailed series in this universe."""
    clean = returns.dropna()
    if len(clean) < 30:
        return float("nan")
    z = stats.norm.ppf(1 - level)
    return float(-(clean.mean() + z * clean.std(ddof=1)))


def parametric_cvar(returns: pd.Series, level: float = 0.95) -> float:
    """Gaussian expected shortfall: mu - sigma * phi(z) / (1 - level)."""
    clean = returns.dropna()
    if len(clean) < 30:
        return float("nan")
    z = stats.norm.ppf(1 - level)
    tail = stats.norm.pdf(z) / (1 - level)
    return float(-(clean.mean() - clean.std(ddof=1) * tail))


def _cornish_fisher_z(level: float, skew: float, excess_kurt: float) -> float:
    """Quantile of the Gaussian, corrected for the sample's skew and kurtosis."""
    z = stats.norm.ppf(1 - level)
    return (z
            + (z ** 2 - 1) * skew / 6
            + (z ** 3 - 3 * z) * excess_kurt / 24
            - (2 * z ** 3 - 5 * z) * skew ** 2 / 36)


def cornish_fisher_var(returns: pd.Series, level: float = 0.95) -> float:
    """Modified VaR: Gaussian shape adjusted for the third and fourth moments."""
    clean = returns.dropna()
    if len(clean) < 30:
        return float("nan")
    z = _cornish_fisher_z(level, float(clean.skew()), float(clean.kurtosis()))
    return float(-(clean.mean() + z * clean.std(ddof=1)))


def cornish_fisher_cvar(returns: pd.Series, level: float = 0.95) -> float:
    """Expected shortfall under the Cornish-Fisher quantile, by tail averaging."""
    clean = returns.dropna()
    if len(clean) < 30:
        return float("nan")
    var = cornish_fisher_var(clean, level)
    tail = clean[clean <= -var]
    return float(-tail.mean()) if len(tail) else var


def monte_carlo_var(returns: pd.Series, level: float = 0.95, draws: int = 100_000,
                    seed: int = 7) -> tuple[float, float]:
    """VaR and CVaR from a Student-t fitted to the sample.

    A t distribution is used rather than a normal because every asset here has
    excess kurtosis; the fitted degrees of freedom are the tail-thickness knob.
    Returns ``(var, cvar)``.
    """
    clean = returns.dropna()
    if len(clean) < 30:
        return float("nan"), float("nan")
    df, loc, scale = stats.t.fit(clean.values)
    rng = np.random.default_rng(seed)
    sample = stats.t.rvs(df, loc=loc, scale=scale, size=draws, random_state=rng)
    cutoff = np.quantile(sample, 1 - level)
    return float(-cutoff), float(-sample[sample <= cutoff].mean())


def var_table(returns: pd.Series, level: float = 0.95) -> dict[str, float]:
    """All four methods side by side, plus the tail moments that explain them."""
    mc_var, mc_cvar = monte_carlo_var(returns, level)
    clean = returns.dropna()
    return {
        "historical_var": historical_var(returns, level),
        "historical_cvar": historical_cvar(returns, level),
        "parametric_var": parametric_var(returns, level),
        "parametric_cvar": parametric_cvar(returns, level),
        "cornish_fisher_var": cornish_fisher_var(returns, level),
        "cornish_fisher_cvar": cornish_fisher_cvar(returns, level),
        "monte_carlo_var": mc_var,
        "monte_carlo_cvar": mc_cvar,
        "skew": float(clean.skew()) if len(clean) > 2 else float("nan"),
        "excess_kurtosis": float(clean.kurtosis()) if len(clean) > 3 else float("nan"),
        "observations": int(len(clean)),
    }


def scale_horizon(var: float, days: int) -> float:
    """Square-root-of-time scaling. Assumes i.i.d. returns -- optimistic in a crisis."""
    return var * np.sqrt(days)


def rolling_var(returns: pd.Series, window: int = 250, level: float = 0.95,
                method: str = "historical") -> pd.Series:
    """Rolling VaR estimated on a trailing window, aligned to the day it applies to."""
    fn = {"historical": historical_var,
          "parametric": parametric_var,
          "cornish_fisher": cornish_fisher_var}[method]
    values = returns.rolling(window).apply(lambda w: fn(pd.Series(w), level), raw=False)
    return values.shift(1)  # only information available before the day starts


def kupiec_pof(returns: pd.Series, var_series: pd.Series, level: float = 0.95) -> dict:
    """Kupiec proportion-of-failures test.

    A VaR model is only credible if breaches happen about (1 - level) of the
    time. This likelihood-ratio test asks whether the observed breach rate is
    consistent with the promised one; p < 0.05 rejects the model.
    """
    paired = pd.concat([returns, var_series], axis=1).dropna()
    paired.columns = ["ret", "var"]
    n = len(paired)
    if n < 100:
        return {"observations": n, "breaches": 0, "expected": 0.0,
                "breach_rate": float("nan"), "lr": float("nan"), "p_value": float("nan"),
                "verdict": "insufficient data"}
    breaches = int((paired["ret"] < -paired["var"]).sum())
    p = 1 - level
    expected = n * p
    if breaches == 0:
        lr = -2 * n * np.log(1 - p)
    else:
        rate = breaches / n
        lr = -2 * ((n - breaches) * np.log(1 - p) + breaches * np.log(p)
                   - (n - breaches) * np.log(1 - rate) - breaches * np.log(rate))
    p_value = float(1 - stats.chi2.cdf(lr, df=1))
    return {
        "observations": n,
        "breaches": breaches,
        "expected": float(expected),
        "breach_rate": breaches / n,
        "lr": float(lr),
        "p_value": p_value,
        "verdict": "model rejected" if p_value < 0.05 else "model holds",
    }
