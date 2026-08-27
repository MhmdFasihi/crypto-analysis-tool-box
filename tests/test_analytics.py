"""Numeric checks on series whose answers are known in closed form.

Run with:  python3 -m pytest tests -q
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from crypto_toolbox.analytics import correlation as corr_mod
from crypto_toolbox.analytics import ratios, risk
from crypto_toolbox.analytics import returns as ret_mod


@pytest.fixture
def flat_then_crash() -> pd.Series:
    """100 days of +1%, 60 of -1%, 100 of +0.5% -- drawdown known exactly."""
    idx = pd.bdate_range("2020-01-01", periods=260)
    return pd.Series(np.r_[np.full(100, 0.01), np.full(60, -0.01), np.full(100, 0.005)],
                     index=idx)


@pytest.fixture
def gaussian() -> pd.Series:
    rng = np.random.default_rng(0)
    return pd.Series(rng.normal(0.0, 0.01, 20_000),
                     index=pd.bdate_range("2000-01-03", periods=20_000))


# --- returns and drawdown ------------------------------------------------- #

def test_total_return_compounds(flat_then_crash):
    expected = 1.01 ** 100 * 0.99 ** 60 * 1.005 ** 100 - 1
    assert ret_mod.total_return(flat_then_crash) == pytest.approx(expected)


def test_max_drawdown_matches_closed_form(flat_then_crash):
    assert ret_mod.max_drawdown(flat_then_crash) == pytest.approx(0.99 ** 60 - 1)


def test_drawdown_details_locates_peak_and_trough(flat_then_crash):
    detail = ret_mod.drawdown_details(flat_then_crash)
    assert detail["peak"] == flat_then_crash.index[99]
    assert detail["trough"] == flat_then_crash.index[159]
    assert detail["recovery"] is None  # +0.5% x 100 does not undo -1% x 60


def test_periods_per_year_detects_calendar():
    daily = pd.date_range("2020-01-01", periods=730, freq="D")
    business = pd.bdate_range("2020-01-01", periods=520)
    assert ret_mod.periods_per_year(daily) == pytest.approx(365, abs=2)
    assert ret_mod.periods_per_year(business) == pytest.approx(261, abs=3)


def test_intersection_alignment_drops_weekend_only_days():
    crypto = pd.Series(1.0, index=pd.date_range("2021-01-01", periods=28, freq="D"))
    equity = pd.Series(1.0, index=pd.bdate_range("2021-01-01", periods=20))
    wide = pd.DataFrame({"C": crypto, "E": equity})
    aligned = ret_mod.align_prices(wide, "intersection")
    assert (aligned.index.dayofweek < 5).all()
    assert len(aligned) == len(equity.index.intersection(crypto.index))


# --- VaR / CVaR ----------------------------------------------------------- #

def test_all_var_methods_agree_on_gaussian_data(gaussian):
    theory = stats.norm.ppf(0.95) * 0.01
    table = risk.var_table(gaussian, 0.95)
    for key in ("historical_var", "parametric_var", "cornish_fisher_var", "monte_carlo_var"):
        assert table[key] == pytest.approx(theory, rel=0.05), key


def test_gaussian_cvar_matches_closed_form(gaussian):
    theory = 0.01 * stats.norm.pdf(stats.norm.ppf(0.05)) / 0.05
    assert risk.historical_cvar(gaussian, 0.95) == pytest.approx(theory, rel=0.05)
    assert risk.parametric_cvar(gaussian, 0.95) == pytest.approx(theory, rel=0.02)


def test_cvar_is_never_smaller_than_var(gaussian):
    table = risk.var_table(gaussian, 0.95)
    assert table["historical_cvar"] >= table["historical_var"]
    assert table["parametric_cvar"] >= table["parametric_var"]


def test_cornish_fisher_widens_var_on_fat_left_tail():
    """A left-skewed, fat-tailed sample: the corrected VaR must exceed the Gaussian one."""
    rng = np.random.default_rng(3)
    fat = pd.Series(-np.abs(stats.t.rvs(3, size=20_000, random_state=rng)) * 0.01
                    + rng.normal(0.001, 0.004, 20_000))
    assert fat.kurtosis() > 1 and fat.skew() < 0
    assert risk.cornish_fisher_var(fat, 0.99) > risk.parametric_var(fat, 0.99)


def test_higher_confidence_means_larger_var(gaussian):
    assert risk.historical_var(gaussian, 0.99) > risk.historical_var(gaussian, 0.95)


def test_horizon_scaling_is_sqrt_of_time():
    assert risk.scale_horizon(0.02, 4) == pytest.approx(0.04)


def test_rolling_var_uses_only_past_information(gaussian):
    rolling = risk.rolling_var(gaussian, 250, 0.95)
    assert rolling.iloc[:250].isna().all()  # 250 window + 1 lag


def test_kupiec_accepts_a_correct_model(gaussian):
    rolling = risk.rolling_var(gaussian, 250, 0.95)
    result = risk.kupiec_pof(gaussian, rolling, 0.95)
    assert result["breach_rate"] == pytest.approx(0.05, abs=0.01)
    assert result["verdict"] == "model holds"


def test_kupiec_rejects_a_deliberately_wrong_model(gaussian):
    too_tight = pd.Series(0.005, index=gaussian.index)  # far below the true 95% VaR
    result = risk.kupiec_pof(gaussian, too_tight, 0.95)
    assert result["breach_rate"] > 0.20
    assert result["verdict"] == "model rejected"


# --- ratios --------------------------------------------------------------- #

def test_cagr_recovers_a_known_growth_rate():
    idx = pd.bdate_range("2015-01-01", periods=252 * 4)
    daily = 1.10 ** (1 / 252) - 1
    series = pd.Series(daily, index=idx)
    assert ratios.cagr(series, 252) == pytest.approx(0.10, rel=1e-3)


def test_sharpe_is_excess_return_over_volatility():
    idx = pd.bdate_range("2015-01-01", periods=2520)
    rng = np.random.default_rng(5)
    series = pd.Series(rng.normal(0.0005, 0.01, 2520), index=idx)
    manual = (ratios.cagr(series, 252) - 0.02) / ratios.annualised_volatility(series, 252)
    assert ratios.sharpe(series, 252, 0.02) == pytest.approx(manual)


def test_sortino_ignores_upside_volatility():
    """Two series, same downside, different upside: Sortino ties, Sharpe does not."""
    base = np.r_[np.full(200, 0.004), np.full(50, -0.01)]
    spiky = base.copy()
    spiky[:200:10] = 0.05  # add upside bursts only
    idx = pd.bdate_range("2015-01-01", periods=250)
    a, b = pd.Series(base, index=idx), pd.Series(spiky, index=idx)
    assert ratios.downside_deviation(a, 252) == pytest.approx(
        ratios.downside_deviation(b, 252), rel=1e-9)
    assert ratios.annualised_volatility(b, 252) > ratios.annualised_volatility(a, 252)


def test_beta_recovers_a_known_loading():
    idx = pd.bdate_range("2015-01-01", periods=3000)
    rng = np.random.default_rng(11)
    bench = pd.Series(rng.normal(0.0003, 0.01, 3000), index=idx)
    asset = 1.5 * bench + pd.Series(rng.normal(0, 0.004, 3000), index=idx)
    beta, _ = ratios.beta_alpha(asset, bench, 252, 0.0)
    assert beta == pytest.approx(1.5, abs=0.05)


def test_alpha_is_zero_for_a_pure_beta_position():
    idx = pd.bdate_range("2015-01-01", periods=3000)
    rng = np.random.default_rng(12)
    bench = pd.Series(rng.normal(0.0004, 0.01, 3000), index=idx)
    _, alpha = ratios.beta_alpha(bench, bench, 252, 0.02)
    assert alpha == pytest.approx(0.0, abs=1e-9)


def test_omega_above_one_when_gains_dominate():
    series = pd.Series([0.02, 0.02, -0.01, 0.01, -0.005])
    assert ratios.omega(series) > 1


def test_summarise_has_every_expected_field():
    idx = pd.bdate_range("2015-01-01", periods=1000)
    rng = np.random.default_rng(6)
    series = pd.Series(rng.normal(0.0004, 0.012, 1000), index=idx)
    row = ratios.summarise(series, 252, 0.02, benchmark=series)
    for field in ("cagr", "volatility", "sharpe", "sortino", "calmar", "omega",
                  "max_drawdown", "ulcer_index", "var_95", "cvar_95", "beta", "alpha"):
        assert field in row and np.isfinite(row[field]), field


# --- correlation ---------------------------------------------------------- #

def test_correlation_matrix_is_symmetric_with_unit_diagonal():
    rng = np.random.default_rng(8)
    frame = pd.DataFrame(rng.normal(size=(600, 4)), columns=list("ABCD"))
    corr = corr_mod.correlation_matrix(frame)
    assert np.allclose(np.diag(corr), 1.0)
    assert np.allclose(corr.values, corr.values.T)


def test_cluster_order_groups_co_moving_assets():
    rng = np.random.default_rng(9)
    driver = rng.normal(size=800)
    other = rng.normal(size=800)
    frame = pd.DataFrame({
        "A": driver + rng.normal(0, 0.05, 800),
        "B": other + rng.normal(0, 0.05, 800),
        "C": driver + rng.normal(0, 0.05, 800),
        "D": other + rng.normal(0, 0.05, 800),
    })
    order = corr_mod.cluster_order(corr_mod.correlation_matrix(frame))
    assert abs(order.index("A") - order.index("C")) == 1
    assert abs(order.index("B") - order.index("D")) == 1


def test_average_pairwise_excludes_the_diagonal():
    corr = pd.DataFrame([[1.0, 0.5], [0.5, 1.0]], index=list("AB"), columns=list("AB"))
    assert corr_mod.average_pairwise(corr) == pytest.approx(0.5)


def test_rolling_beta_tracks_a_regime_change():
    idx = pd.bdate_range("2015-01-01", periods=1200)
    rng = np.random.default_rng(13)
    bench = pd.Series(rng.normal(0, 0.01, 1200), index=idx)
    asset = pd.concat([0.5 * bench.iloc[:600], 2.0 * bench.iloc[600:]])
    frame = pd.DataFrame({"A": asset, "B": bench})
    rolling = corr_mod.rolling_beta(frame, "A", "B", 120)
    assert rolling.iloc[200] == pytest.approx(0.5, abs=0.05)
    assert rolling.iloc[-1] == pytest.approx(2.0, abs=0.05)
