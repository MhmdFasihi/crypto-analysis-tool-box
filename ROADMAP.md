# Roadmap

Three phases. Phase 0 is done and pushed; phase 1 is planned and approved; phase 2 is
deployment.

---

## Phase 0 — Analytics core + yearly report ✅ done

**Shipped:** `crypto_toolbox/` (analytics library, 25 passing tests) and `report/`
(a 64-slide reveal.js deck built from 2016→today daily data).

The deck covers: method and instrument caveats · rebased log growth · full-period
performance/risk table · risk-return scatter · Sharpe/Sortino/Calmar/Omega/Ulcer/beta/
alpha/IR · drawdown small multiples and depth/duration table · four VaR methods side by
side with CVaR and 10-day scaling · per-asset return distributions with VaR/CVaR cut
lines · Kupiec backtest · clustered correlation matrix, tightest/loosest pairs, rolling
correlation, average pairwise by year · return/volatility/Sharpe grids by year · a
section per calendar year (performance, risk, correlation) · computed synthesis ·
definitions and limits.

Output is a **single self-contained HTML file** — reveal.js inlined, charts as inline
SVG, zero external requests — plus CSV exports of every table.

**Open item:** the deck has only ever been built here from synthetic data, because this
build environment's egress policy blocks Yahoo Finance. **First job locally: run
`make report` and review the real numbers.** Expect to adjust narrative thresholds once
real correlations and kurtosis are in play — for example the year-heatmap colour clip
(85th percentile of |return|) and the rolling-correlation window.

---

## Phase 1 — Live dashboard (Reflex) — next

The approved shape: **5 pages, Recharts + Plotly, per-asset (no portfolio aggregation),
built on the existing analytics core.** `crypto_toolbox/` already provides every
computation the pages need, so this phase is presentation and state management.

**Prerequisite:** authorize the Reflex MCP server — `/mcp` in an interactive session.
It is already registered in this project's local config
(`claude mcp add --transport http reflex https://build.reflex.dev/mcp`) but needs a
browser OAuth flow.

### 1.1 Shell
`rxconfig.py`, app entry, routes, theme (reuse the tokens in `report/theme.py`),
sidebar, and one **shared settings state** — tickers, date range, return frequency,
risk-free rate, VaR confidence, benchmark, rolling windows. One filter row scoping every
page; never per-chart filters.

### 1.2 Data state
A cached state layer over `fetcher.py` so a page switch doesn't re-download. Manual
refresh action. Surface the calendar-alignment choice in the UI rather than hiding it.

### 1.3 Pages, in build order
1. **Overview** — KPI tiles, normalized performance, drawdown, period-return table
2. **Correlation** — clustered matrix heatmap (Plotly), rolling pairwise correlation,
   rolling beta, correlation Δ vs prior period
3. **Risk** — VaR/CVaR by method, rolling VaR with realized returns overlaid, breach
   count, Kupiec test, distribution histogram, tail stats
4. **Ratios** — the full ratio table plus rolling Sharpe
5. **Settings** — add/remove/rename tickers (validated against yfinance), asset-class
   grouping, cache controls, CSV export

### 1.4 Verification
Run the app, load every page against live data, screenshot each one. A page that has
never been looked at is not done.

### Deferred by decision, easy to add later
- **Portfolio aggregation** — weights UI, portfolio VaR/CVaR (with diversification
  benefit vs the sum of individual VaRs), portfolio ratios. The module boundary already
  leaves room; nothing needs restructuring.
- **Seasonality page** from `legacy/daily__BTC_ETH.py` (day-of-week return distributions).

---

## Phase 2 — Deployment (personal VPS)

**The report** is already deployable: one static file.
`scp report/dist/market-report.html vps:/var/www/reports/`. Optionally a cron job running
`make refresh` weekly so the deck stays current — the narrative regenerates itself, so it
never goes stale in the way a hand-written report does.

**The dashboard** needs a process: `reflex export` or `reflex run --env prod` behind a
reverse proxy (nginx/Caddy) with TLS. Decisions to make when we get there:
- Auth, or leave it public? A public URL is a public document.
- Where the price cache lives and how often it refreshes.
- Whether the report build runs on the same box (it only needs `make refresh` + cron).

---

## Known limits, carried through every phase

Equity series are price indices (no dividends). Commodity series are front-month futures
(roll effects included). No transaction costs, financing, slippage or tax. Single-year
statistics rest on ~250 observations. √t VaR scaling assumes independent days, which is
optimistic exactly in a crisis. Pearson correlation is linear and blind to tail
dependence. Past distributions are not forecasts.

These are stated on the deck's method and appendix slides and must stay visible in the
dashboard too — a risk number without its assumptions is decoration.
