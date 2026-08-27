"""Asset universe: friendly names, Yahoo Finance tickers and asset classes."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "universe.json"


@dataclass(frozen=True)
class Asset:
    key: str          # short stable id used in code and files
    name: str         # display name
    ticker: str       # Yahoo Finance symbol
    asset_class: str  # Crypto | Equity | Metal | Energy
    note: str = ""    # caveats worth surfacing in the report


DEFAULT_UNIVERSE: list[Asset] = [
    Asset("BTC", "Bitcoin", "BTC-USD", "Crypto", "Trades 7 days a week."),
    Asset("ETH", "Ethereum", "ETH-USD", "Crypto", "Trades 7 days a week."),
    Asset("SPX", "S&P 500", "^GSPC", "Equity", "Price index, excludes dividends."),
    Asset("NDX", "Nasdaq 100", "^NDX", "Equity", "Price index, excludes dividends."),
    Asset("GOLD", "Gold", "GC=F", "Metal", "Front-month future; includes roll effects."),
    Asset("SILVER", "Silver", "SI=F", "Metal", "Front-month future; includes roll effects."),
    Asset("BRENT", "Brent", "BZ=F", "Energy", "Front-month future; includes roll effects."),
    Asset("WTI", "WTI", "CL=F", "Energy", "Front-month future; includes roll effects."),
]


def load_universe() -> list[Asset]:
    """Return the configured universe, falling back to the defaults."""
    if CONFIG_PATH.exists():
        raw = json.loads(CONFIG_PATH.read_text())
        return [Asset(**item) for item in raw["assets"]]
    return list(DEFAULT_UNIVERSE)


def save_universe(assets: list[Asset]) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps({"assets": [asdict(a) for a in assets]}, indent=2) + "\n")


if __name__ == "__main__":
    save_universe(DEFAULT_UNIVERSE)
    print(f"wrote {CONFIG_PATH}")
