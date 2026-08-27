"""Download and cache daily price history from Yahoo Finance."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import yfinance as yf

from crypto_toolbox.data.universe import Asset, load_universe

CACHE_DIR = Path(__file__).resolve().parents[2] / "data_cache"


def _cache_path(ticker: str) -> Path:
    return CACHE_DIR / f"{ticker.replace('^', '_').replace('=', '-')}.parquet"


def download_asset(asset: Asset, start: str, end: str, refresh: bool = False) -> pd.Series:
    """Return a daily close series for one asset, cached on disk."""
    path = _cache_path(asset.ticker)
    if path.exists() and not refresh:
        return pd.read_parquet(path)["close"]

    frame = yf.download(
        asset.ticker, start=start, end=end, interval="1d",
        auto_adjust=True, progress=False, threads=False,
    )
    if frame.empty:
        raise RuntimeError(f"no data returned for {asset.ticker}")
    if isinstance(frame.columns, pd.MultiIndex):
        frame.columns = frame.columns.get_level_values(0)

    close = frame["Close"].dropna()
    close.index = pd.to_datetime(close.index).tz_localize(None).normalize()
    close = close[~close.index.duplicated(keep="last")].rename("close")

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    close.to_frame().to_parquet(path)
    return close


def download_universe(start: str, end: str, refresh: bool = False,
                      assets: list[Asset] | None = None) -> pd.DataFrame:
    """Return a wide close-price frame, one column per asset key."""
    assets = assets or load_universe()
    series = {}
    for asset in assets:
        series[asset.key] = download_asset(asset, start, end, refresh=refresh)
        print(f"  {asset.key:<7} {asset.ticker:<8} {len(series[asset.key]):>5} rows  "
              f"{series[asset.key].index.min().date()} -> {series[asset.key].index.max().date()}")
    return pd.DataFrame(series).sort_index()
