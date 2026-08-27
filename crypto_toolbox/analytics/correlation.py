"""Correlation, rolling co-movement and clustering order."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.cluster import hierarchy
from scipy.spatial.distance import squareform


def correlation_matrix(returns: pd.DataFrame, method: str = "pearson") -> pd.DataFrame:
    """Full-sample correlation of returns. ``method`` is pearson/spearman/kendall."""
    return returns.corr(method=method)


def cluster_order(corr: pd.DataFrame) -> list[str]:
    """Reorder assets so that things that move together sit together.

    Distance is sqrt(2 * (1 - rho)), the standard correlation metric, fed to
    average-linkage clustering; the leaf order is what the heatmap uses.
    """
    if corr.shape[0] < 3:
        return list(corr.columns)
    dist = np.sqrt(np.clip(2 * (1 - corr.values), 0, None))
    np.fill_diagonal(dist, 0.0)
    linkage = hierarchy.linkage(squareform(dist, checks=False), method="average")
    order = hierarchy.leaves_list(linkage)
    return [corr.columns[i] for i in order]


def rolling_correlation(returns: pd.DataFrame, base: str, others: list[str],
                        window: int = 90) -> pd.DataFrame:
    """Rolling pairwise correlation of ``base`` against each of ``others``."""
    out = {}
    for other in others:
        if other == base or other not in returns:
            continue
        out[other] = returns[base].rolling(window).corr(returns[other])
    return pd.DataFrame(out).dropna(how="all")


def rolling_beta(returns: pd.DataFrame, asset: str, benchmark: str,
                 window: int = 90) -> pd.Series:
    """Rolling CAPM beta of one asset against a benchmark column."""
    cov = returns[asset].rolling(window).cov(returns[benchmark])
    var = returns[benchmark].rolling(window).var()
    return (cov / var).dropna()


def yearly_correlation(returns: pd.DataFrame, method: str = "pearson") -> dict[int, pd.DataFrame]:
    """One correlation matrix per calendar year."""
    return {int(year): correlation_matrix(block, method)
            for year, block in returns.groupby(returns.index.year)}


def average_pairwise(corr: pd.DataFrame) -> float:
    """Mean off-diagonal correlation -- a single 'how correlated is everything' number."""
    values = corr.values
    mask = ~np.eye(values.shape[0], dtype=bool)
    return float(np.nanmean(values[mask]))
