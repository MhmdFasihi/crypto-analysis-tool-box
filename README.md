# crypto-analysis-tool-box

Multi-asset market, correlation and risk analytics for crypto, equities, metals and
energy — with a year-by-year report rendered as a shareable [reveal.js](https://revealjs.com)
deck.

Default universe (editable in `config/universe.json`):

| Key | Asset | Yahoo ticker | Class |
|---|---|---|---|
| `BTC` | Bitcoin | `BTC-USD` | Crypto |
| `ETH` | Ethereum | `ETH-USD` | Crypto |
| `SPX` | S&P 500 | `^GSPC` | Equity |
| `NDX` | Nasdaq 100 | `^NDX` | Equity |
| `GOLD` | Gold | `GC=F` | Metal |
| `SILVER` | Silver | `SI=F` | Metal |
| `BRENT` | Brent | `BZ=F` | Energy |
| `WTI` | WTI | `CL=F` | Energy |

## Build the report

```bash
pip install -r requirements.txt
make report            # 2016-01-01 -> today, from Yahoo Finance
open report/dist/market-report.html
```

The output is a **single self-contained HTML file** (~2 MB). reveal.js is vendored and
inlined, every chart is inline SVG, and there are no external requests — so it works
offline, from a file:// URL, from any static host, and behind a VPS with no CDN access.
Every table is also written to `report/dist/data/*.csv`.

Options:

```bash
python3 -m report.build_report \
    --start 2016-01-01 \
    --end 2026-08-27 \
    --rf 0.02 \            # annual risk-free rate used by Sharpe/Sortino/alpha
    --level 0.95 \         # VaR/CVaR confidence
    --benchmark SPX \      # beta / alpha / information ratio reference
    --corr-window 90 \     # rolling correlation window, trading days
    --var-window 250 \     # trailing window for the backtested rolling VaR
    --refresh              # ignore the local parquet cache
```

`make demo` builds the same deck from synthetic data with no network access — useful for
checking the pipeline or the styling. Decks built that way are stamped **SYNTHETIC DATA**
on the title slide.

## What's in the deck

| Section | Contents |
|---|---|
| How to read this | Calendar conventions, VaR sign convention, the four VaR methods, instrument caveats |
| The whole period | Rebased growth (log), performance/risk table, risk-return scatter |
| Risk-adjusted performance | Sharpe / Sortino / Calmar / Omega / Ulcer / beta / alpha / information ratio |
| Drawdown | Underwater small multiples, depth + date + time underwater |
| Value at Risk | Four methods side by side, CVaR, 10-day scaling, per-asset distributions |
| Backtest | Kupiec proportion-of-failures test on rolling VaR |
| Correlation | Clustered full-period matrix, tightest/loosest pairs, rolling correlation, per-year averages |
| Year by year | Return / volatility / Sharpe grids, then a section per calendar year (performance, risk, correlation) |
| Synthesis + appendix | Findings computed at build time, definitions, data limits |

Every headline sentence in the deck is **computed from the data at build time** — there
are no hardcoded conclusions, so re-running next quarter re-writes the narrative rather
than dating it.

## Serving it

It is one static file:

```bash
scp report/dist/market-report.html vps:/var/www/reports/
```

Press `Esc` for the slide map, `S` for speaker notes, `?` for shortcuts, and the button
top-right toggles light/dark (the choice is remembered per browser). Printing to PDF
works via reveal's `?print-pdf` query string.

## Analytics library

The report is a thin presentation layer over `crypto_toolbox/`, which has no reveal.js or
report dependencies and is reusable elsewhere (a dashboard, a notebook, a cron job):

```
crypto_toolbox/
├── data/
│   ├── universe.py     # asset registry, JSON-persisted
│   └── fetcher.py      # yfinance download + parquet cache
└── analytics/
    ├── returns.py      # alignment, returns, drawdown, annualisation
    ├── risk.py         # VaR x4, CVaR, rolling VaR, Kupiec backtest
    ├── ratios.py       # Sharpe, Sortino, Calmar, Omega, Ulcer, beta/alpha, IR, Treynor
    └── correlation.py  # matrices, clustering, rolling correlation and beta
```

```bash
make test    # 25 numeric tests against closed-form answers on synthetic series
```

## Adding an asset

Append to `config/universe.json` and rebuild — every chart, table and year section picks
it up:

```json
{ "key": "COPPER", "name": "Copper", "ticker": "HG=F",
  "asset_class": "Metal", "note": "Front-month future; includes roll effects." }
```

## Methodology notes

- **Two calendars.** Performance and risk statistics use each asset's own trading
  calendar, so Bitcoin annualises on ~365 observations a year and the S&P on ~252.
  Correlation and beta use the *intersection* calendar — the days every asset traded.
  Forward-filling weekends would invent flat days for equities and drag correlations
  toward zero.
- **VaR is a positive loss.** A 95% VaR of 3.2% means the loss on the worst 5% of days is
  at least 3.2%. CVaR is the mean loss on exactly those days, so CVaR ≥ VaR always.
- **VaR is backtested, not asserted.** Rolling VaR is re-estimated daily on a trailing
  window and lagged one day; the Kupiec test checks the observed breach rate against the
  promised one.
- **Known limits.** Equity series are price indices (no dividends); commodity series are
  front-month futures (roll effects included); no costs, financing or tax; √t VaR scaling
  assumes independent days; Pearson correlation is blind to tail dependence.

`legacy/daily__BTC_ETH.py` is the original day-of-week seasonality script, unchanged.
