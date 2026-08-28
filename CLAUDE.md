# crypto-analysis-tool-box — working notes

Multi-asset market, correlation and risk analytics for crypto, equities, metals and
energy. Two deliverables share one analytics core: a **static yearly report**
(reveal.js deck, built) and a **live dashboard** (Reflex, not yet built).

## Layout

```
crypto_toolbox/          analytics core — pure pandas/numpy, NO ui imports
├── data/universe.py     asset registry, JSON-persisted to config/universe.json
├── data/fetcher.py      yfinance download + parquet cache in data_cache/
└── analytics/
    ├── returns.py       alignment, returns, drawdown, annualisation
    ├── risk.py          VaR x4, CVaR, rolling VaR, Kupiec backtest
    ├── ratios.py        Sharpe, Sortino, Calmar, Omega, Ulcer, beta/alpha, IR, Treynor
    └── correlation.py   matrices, clustering, rolling correlation and beta
report/                  presentation layer for the static deck
├── build_report.py      orchestration + slide builders + narrative generation
├── charts.py            inline-SVG chart toolkit
├── deck.py              reveal.js shell, CSS tokens, HTML components
├── theme.py             validated colour palette
└── vendor/reveal/       3 reveal.js files, inlined at build time
tests/test_analytics.py  25 numeric tests against closed-form answers
legacy/                  the original day-of-week script, unchanged
```

## Commands

```bash
make report      # 2016-today from Yahoo Finance -> report/dist/market-report.html
make refresh     # same, ignoring the parquet cache
make demo        # synthetic data, no network — for styling/pipeline work
make test        # 25 tests, ~9s
```

## Invariants — do not break these without saying so

1. **`crypto_toolbox/` never imports from `report/` or from any UI framework.** It is
   the shared core; the deck and the future dashboard are both thin layers over it.
   Anything a chart needs that isn't presentation belongs in the core, with a test.

2. **Two calendars, deliberately.** Performance and risk statistics use each asset's
   *own* trading calendar (BTC ~365 obs/yr, S&P ~252) via `periods_per_year()`.
   Correlation and beta use the *intersection* calendar (`align_prices(..., "intersection")`).
   Never forward-fill weekends into a correlation input — it invents flat equity days and
   drags every correlation toward zero.

3. **VaR and CVaR are positive loss magnitudes.** `historical_var(...) == 0.032` means a
   3.2% loss. CVaR >= VaR always. Every display layer must keep that convention or say
   loudly that it is inverting it.

4. **VaR is backtested, not asserted.** `rolling_var()` lags one day so only pre-session
   information is used; `kupiec_pof()` tests the breach rate. Any new VaR method needs a
   backtest slide/panel, not just a number.

5. **Report narrative is computed, never hardcoded.** Every headline and footnote sentence
   in the deck derives from the data at build time (see the `ranked()` helpers and the
   `gap_sentence` pattern in `build_report.py`). Sign-flip robustness matters: a sentence
   that says "wider" must check that the gap is actually positive.

6. **Charts follow the data-viz rules already applied here.** Palette in `report/theme.py`
   is validated for colour-vision deficiency in both light and dark mode — do not add ad-hoc
   hexes. Colour follows the entity, never its rank. No dual-axis charts. Diverging
   blue/red with a grey midpoint for signed values; single-hue blue ramp for magnitude.
   Heatmap cell ink comes from `_ink_for()` (fill luminance), not from the theme.

7. **Adding an asset is a config change, not a code change.** Append to
   `config/universe.json`; every chart, table and year section picks it up.

## Gotchas

- The generated deck and `data_cache/` are gitignored. `report/dist/market-report.html`
  is a build artefact — rebuild rather than commit it.
- `--demo` builds from synthetic data and stamps SYNTHETIC on the title slide. Never share
  a deck built that way; it is for pipeline and styling work only.
- Futures tickers (`GC=F`, `BZ=F`, `CL=F`, `SI=F`) are front-month continuations, so long
  holding-period returns include roll effects. `^GSPC` and `^NDX` are price indices —
  no dividends, so their Sharpe/alpha/Calmar are understated by ~1.5-2%/yr. Both caveats
  are stated in the deck and must stay stated in the dashboard.
- Yahoo occasionally returns a MultiIndex column frame; `fetcher.py` flattens it already.

## Verifying visual work

`make demo`, then screenshot the output with Playwright (Chromium is fine) and *look at
it* before calling a chart done. That pass is what caught `352136%` (now `3,522x`) and
white-on-pale-blue heatmap text in dark mode. The validator checks colour, not layout.

See `ROADMAP.md` for what is built and what is next.
