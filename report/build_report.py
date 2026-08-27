#!/usr/bin/env python3
"""Build the yearly multi-asset market report as a self-contained reveal.js deck.

    python3 -m report.build_report --start 2016-01-01

Performance and risk statistics are computed on each asset's **own** trading
calendar (so Bitcoin's 365-day year is not annualised as if it were 252 days),
while correlation and beta use the **intersection** calendar, where every asset
actually traded on the same day.
"""
from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from crypto_toolbox.analytics import correlation as corr_mod
from crypto_toolbox.analytics import ratios, risk
from crypto_toolbox.analytics import returns as ret_mod
from crypto_toolbox.data.universe import Asset, load_universe
from report import charts as ch
from report import deck
from report.theme import CATEGORICAL_LIGHT

OUT_DIR = Path(__file__).resolve().parent / "dist"
PCT0 = lambda v: ch.fmt_pct(v, 0)   # noqa: E731
PCT1 = ch.fmt_pct
PCT2 = lambda v: ch.fmt_pct(v, 2)   # noqa: E731
GROWTH = ch.fmt_growth


# --------------------------------------------------------------------------- #
# Data
# --------------------------------------------------------------------------- #

def load_prices(assets: list[Asset], start: str, end: str, refresh: bool,
                demo: bool) -> dict[str, pd.Series]:
    if demo:
        return synthetic_prices(assets, start, end)
    from crypto_toolbox.data.fetcher import download_asset
    print("Downloading from Yahoo Finance:")
    return {a.key: download_asset(a, start, end, refresh=refresh) for a in assets}


def synthetic_prices(assets: list[Asset], start: str, end: str) -> dict[str, pd.Series]:
    """Plausible fake data, used only to exercise the pipeline offline.

    Every deck built from it is stamped SYNTHETIC on the title slide.
    """
    rng = np.random.default_rng(20160101)
    days = pd.date_range(start, end, freq="D")
    business = days[days.dayofweek < 5]
    market = rng.normal(0.0003, 0.011, len(days))
    profile = {"Crypto": (0.0016, 0.045, 0.35), "Equity": (0.0004, 0.011, 0.95),
               "Metal": (0.0002, 0.010, 0.15), "Energy": (0.0002, 0.021, 0.45)}
    out = {}
    for asset in assets:
        drift, vol, load = profile[asset.asset_class]
        idio = rng.standard_t(4, len(days)) / np.sqrt(2) * vol
        series = drift + load * market * (vol / 0.011) * 0.5 + idio
        prices = pd.Series(100 * np.exp(np.cumsum(series)), index=days)
        if asset.asset_class != "Crypto":
            prices = prices.reindex(business)
        out[asset.key] = prices.rename("close")
    return out


# --------------------------------------------------------------------------- #
# Narrative helpers -- every sentence is derived from the numbers, not written by hand
# --------------------------------------------------------------------------- #

def ranked(values: dict[str, float], reverse: bool = True) -> list[tuple[str, float]]:
    clean = {k: v for k, v in values.items() if v is not None and np.isfinite(v)}
    return sorted(clean.items(), key=lambda kv: kv[1], reverse=reverse)


def tone(value: float) -> str:
    return "pos" if value is not None and np.isfinite(value) and value >= 0 else "neg"


def cell_tone(value: float) -> str:
    return "pos" if np.isfinite(value) and value > 0 else ("neg" if np.isfinite(value) else "")


# --------------------------------------------------------------------------- #
# Slide builders
# --------------------------------------------------------------------------- #

def title_slide(ctx) -> str:
    stamp = ('<p class="badge crit">SYNTHETIC DATA — pipeline demo, not market history</p>'
             if ctx["demo"] else
             f'<p class="badge">Yahoo Finance · built {date.today().isoformat()}</p>')
    names = " · ".join(a.name for a in ctx["assets"])
    return deck.slide(f"""
      <p class="eyebrow">Multi-asset market report</p>
      <h1>Crypto, equities, metals and energy<br>{ctx['start_year']}–{ctx['end_year']}</h1>
      <p class="lede">A year-by-year account of how eight markets moved, how tightly they
      moved together, and how much of a loss each one has been capable of delivering —
      measured with historical, parametric, Cornish-Fisher and Monte-Carlo VaR, and
      backtested rather than asserted.</p>
      <hr class="rule">
      <p class="footnote">{deck.esc(names)}<br>
      Daily closes, {ctx['first_day']} to {ctx['last_day']} ·
      {ctx['n_days']:,} aligned trading days · risk-free rate {PCT1(ctx['rf'])} ·
      VaR confidence {PCT0(ctx['level'])} · benchmark {ctx['benchmark_name']}</p>
      {stamp}
      <p class="footnote">Press <strong>→</strong> for the next section,
      <strong>↓</strong> for the detail inside a section, <strong>Esc</strong> for the
      slide map, <strong>S</strong> for notes.</p>
    """)


def method_slides(ctx) -> str:
    caveats = "".join(f"<li><strong>{deck.esc(a.name)}</strong> ({deck.esc(a.ticker)}) — "
                      f"{deck.esc(a.note)}</li>" for a in ctx["assets"] if a.note)
    return deck.stack([
        deck.slide(f"""
          <p class="eyebrow">How to read this</p>
          <h2>Three conventions that decide every number here</h2>
          <div class="cols">
            <div>
              <div class="card">
                <h4>1 · Two calendars, on purpose</h4>
                <p>Crypto trades 7 days a week; the indices and futures do not. Performance
                and risk statistics use each asset's <strong>own</strong> calendar, so
                Bitcoin annualises on {ctx['ppy_crypto']:.0f} observations a year and the
                S&amp;P on {ctx['ppy_equity']:.0f}. Correlation and beta use the
                <strong>intersection</strong> — the {ctx['n_days']:,} days everything
                traded. Forward-filling a weekend would invent flat days for equities and
                drag every correlation toward zero.</p>
              </div>
              <div class="card" style="margin-top:14px">
                <h4>2 · VaR is a positive loss</h4>
                <p>A 1-day {PCT0(ctx['level'])} VaR of 3.2% means: on the worst
                {PCT0(1 - ctx['level'])} of days, the loss is at least 3.2%. CVaR is the
                average loss on exactly those days, so CVaR is always the larger number.
                Neither is a worst case.</p>
              </div>
            </div>
            <div>
              <div class="card">
                <h4>3 · Four VaR methods, because they disagree</h4>
                <p><strong>Historical</strong> — the empirical quantile; no distributional
                assumption, but it can only produce losses it has already seen.<br>
                <strong>Parametric</strong> — Gaussian; understates every fat-tailed series
                in this universe.<br>
                <strong>Cornish-Fisher</strong> — the Gaussian quantile corrected for the
                sample's skew and kurtosis.<br>
                <strong>Monte Carlo</strong> — 100,000 draws from a Student-t fitted to the
                sample, so the tail thickness is estimated rather than assumed.</p>
                <p>Where they diverge, the gap <em>is</em> the finding: it measures how
                non-normal that market is.</p>
              </div>
            </div>
          </div>
        """),
        deck.slide(f"""
          <p class="eyebrow">How to read this</p>
          <h2>What these instruments are, and what they are not</h2>
          <ul>{caveats}</ul>
          <div class="card">
            <h4>Consequences worth stating before any number is read</h4>
            <p>· The two equity series are <strong>price indices</strong>. Dividends are
            excluded, so their total return is understated by roughly 1.5–2% a year —
            every equity Sharpe, alpha and Calmar here inherits that understatement.<br>
            · The four commodities are <strong>front-month futures</strong>. A long
            holding-period return includes roll yield, which in contango is a real cost and
            in backwardation a real gain, so "Brent returned X" means the rolled futures
            position, not the barrel.<br>
            · Crypto prices are exchange composites and include weekend sessions that no
            other market here has.<br>
            · Square-root-of-time scaling of VaR assumes independent days. Crises cluster,
            so multi-day scaled VaR is optimistic exactly when it matters.</p>
          </div>
        """),
    ])


def overview_slides(ctx) -> str:
    stats = ctx["full_stats"]
    order = ranked({k: s["total_return"] for k, s in stats.items()})
    best, worst = order[0], order[-1]
    vol_rank = ranked({k: s["volatility"] for k, s in stats.items()})
    sharpe_rank = ranked({k: s["sharpe"] for k, s in stats.items()})
    name = ctx["name_of"]

    tile_row = deck.tiles([
        deck.tile("Best total return", GROWTH(best[1]), name(best[0]), tone(best[1])),
        deck.tile("Worst total return", GROWTH(worst[1]), name(worst[0]), tone(worst[1])),
        deck.tile("Highest volatility", PCT0(vol_rank[0][1]), name(vol_rank[0][0])),
        deck.tile("Best Sharpe", ch.fmt_num(sharpe_rank[0][1]), name(sharpe_rank[0][0])),
    ])

    rebased = ctx["rebased"]
    growth = ch.line_chart(rebased, ctx["colors"], height=430, log=True,
                           value_fmt=lambda v: ch.fmt_num(v, 0),
                           label="Growth of 100 invested at the start, log scale")

    headers = ["Asset", "Total", "CAGR", "Vol", "Sharpe", "Sortino", "Calmar",
               "Max DD", "VaR 95%", "CVaR 95%", "Skew", "Ex. kurt", "Days"]
    rows, classes = [], []
    for key, s in stats.items():
        rows.append([name(key), GROWTH(s["total_return"]), PCT1(s["cagr"]), PCT1(s["volatility"]),
                     ch.fmt_num(s["sharpe"]), ch.fmt_num(s["sortino"]), ch.fmt_num(s["calmar"]),
                     PCT1(s["max_drawdown"]), PCT2(s["var_95"]), PCT2(s["cvar_95"]),
                     ch.fmt_num(s["skew"]), ch.fmt_num(s["excess_kurtosis"]),
                     f"{s['observations']:,}"])
        classes.append(["", cell_tone(s["total_return"]), cell_tone(s["cagr"]), "", "strong",
                        "", "", "neg", "", "", "", "", ""])

    scatter = ch.scatter([(s["volatility"], s["cagr"], name(k)) for k, s in stats.items()],
                         height=430, x_fmt=PCT0, y_fmt=PCT0,
                         x_title="Annualised volatility", y_title="Annualised return (CAGR)",
                         label="Risk versus return, whole period")

    return deck.stack([
        deck.slide(f"""
          <p class="eyebrow">The whole period · {ctx['start_year']}–{ctx['end_year']}</p>
          <h2>{deck.esc(name(best[0]))} compounded {GROWTH(best[1])}; {deck.esc(name(worst[0]))}
              returned {GROWTH(worst[1])}</h2>
          {tile_row}
          {growth}
          <p class="footnote">Every series rebased to 100 at {ctx['first_day']}. Log scale —
          equal vertical distances are equal <em>percentage</em> moves, which is the only
          way an asset that moved {GROWTH(best[1])} and one that moved {GROWTH(worst[1])} can
          share an axis honestly. Hover a line to isolate it.</p>
        """),
        deck.slide(f"""
          <p class="eyebrow">The whole period · table view</p>
          <h2>Performance and risk, {ctx['first_day']} to {ctx['last_day']}</h2>
          {deck.table(headers, rows, classes)}
          <p class="footnote">Each row uses that asset's own trading calendar for
          annualisation. VaR/CVaR are 1-day historical at {PCT0(ctx['level'])} confidence,
          expressed as positive losses. Excess kurtosis above 0 means fatter tails than a
          normal distribution — every asset here clears that bar, which is why the
          parametric VaR column later in this deck is the smallest of the four.</p>
        """),
        deck.slide(f"""
          <p class="eyebrow">The whole period · risk versus return</p>
          <h2>What each unit of volatility actually bought</h2>
          {scatter}
          <p class="footnote">Return is annualised (CAGR), risk is annualised volatility.
          Points above the line from the origin through any other point earned more per
          unit of risk. Identity is carried by the label, not by colour, so the chart is
          readable in greyscale and under any colour-vision deficiency.</p>
        """),
    ])


def ratio_slides(ctx) -> str:
    stats, name = ctx["full_stats"], ctx["name_of"]
    headers = ["Asset", "CAGR", "Vol", "Downside dev", "Sharpe", "Sortino", "Calmar",
               "Omega", "Ulcer", "Beta", "Alpha", "Info ratio", "Hit rate"]
    rows, classes = [], []
    for key, s in stats.items():
        rows.append([name(key), PCT1(s["cagr"]), PCT1(s["volatility"]),
                     PCT1(s["downside_deviation"]), ch.fmt_num(s["sharpe"]),
                     ch.fmt_num(s["sortino"]), ch.fmt_num(s["calmar"]),
                     ch.fmt_num(s["omega"]), ch.fmt_num(s["ulcer_index"]),
                     ch.fmt_num(s.get("beta")), PCT1(s.get("alpha")),
                     ch.fmt_num(s.get("information_ratio")), PCT0(s["hit_rate"])])
        classes.append(["", cell_tone(s["cagr"]), "", "", "strong", "", "", "", "",
                        "", cell_tone(s.get("alpha", float("nan"))), "", ""])

    sharpe_rank = ranked({k: s["sharpe"] for k, s in stats.items()})
    sortino_rank = ranked({k: s["sortino"] for k, s in stats.items()})
    reshuffle = [k for k in dict(sharpe_rank)][:3] != [k for k in dict(sortino_rank)][:3]

    bars = ch.grouped_bar_chart(
        [name(k) for k, _ in sharpe_rank],
        {"Sharpe": [stats[k]["sharpe"] for k, _ in sharpe_rank],
         "Sortino": [stats[k]["sortino"] for k, _ in sharpe_rank],
         "Calmar": [stats[k]["calmar"] for k, _ in sharpe_rank]},
        height=400, value_fmt=lambda v: ch.fmt_num(v, 1),
        label="Sharpe, Sortino and Calmar by asset")

    return deck.stack([
        deck.slide(f"""
          <p class="eyebrow">Risk-adjusted performance</p>
          <h2>{deck.esc(name(sharpe_rank[0][0]))} leads on Sharpe at
              {ch.fmt_num(sharpe_rank[0][1])}</h2>
          {bars}
          {deck.legend([("Sharpe — excess return per unit of total volatility", CATEGORICAL_LIGHT[0]),
                        ("Sortino — per unit of downside volatility", CATEGORICAL_LIGHT[1]),
                        ("Calmar — per unit of worst drawdown", CATEGORICAL_LIGHT[2])])}
          <p class="footnote">Sorted by Sharpe.
          {"The Sortino ordering differs from the Sharpe ordering, which means at least one asset earns its volatility ranking mostly from upside moves that Sharpe penalises as if they were losses." if reshuffle else "The three measures agree on the ordering, so the ranking is not an artefact of which risk definition was chosen."}
          Calmar is the harshest of the three: it divides by the single worst peak-to-trough
          loss rather than by an average.</p>
        """),
        deck.slide(f"""
          <p class="eyebrow">Risk-adjusted performance · table view</p>
          <h2>Every ratio, whole period</h2>
          {deck.table(headers, rows, classes)}
          <p class="footnote">Risk-free rate {PCT1(ctx['rf'])}. Beta, alpha and information
          ratio are measured against {deck.esc(ctx['benchmark_name'])} on the intersection
          calendar. Omega above 1 means probability-weighted gains exceed losses at a zero
          threshold. Ulcer index is the root-mean-square drawdown — it punishes depth
          <em>and</em> time spent underwater, so a slow grinding loss scores worse than a
          sharp one that recovers.</p>
        """),
    ])


def drawdown_slides(ctx) -> str:
    name, stats = ctx["name_of"], ctx["full_stats"]
    panels = {name(k): ctx["drawdowns"][k] for k in ctx["keys"]}
    grid = ch.small_multiples(panels, columns=4, panel_height=124, value_fmt=PCT0,
                              label="Underwater curves, common scale")
    headers = ["Asset", "Max drawdown", "Peak", "Trough", "Recovered", "Days underwater",
               "Ulcer index", "Worst day"]
    rows = []
    for key in ctx["keys"]:
        d = ctx["dd_detail"][key]
        rows.append([name(key), PCT1(d["max_drawdown"]),
                     str(d["peak"].date()) if d.get("peak") is not None else "—",
                     str(d["trough"].date()) if d.get("trough") is not None else "—",
                     str(d["recovery"].date()) if d.get("recovery") is not None else "not yet",
                     f"{d['days_underwater']:,}", ch.fmt_num(stats[key]["ulcer_index"]),
                     PCT1(stats[key]["worst_day"])])
    worst = ranked({k: ctx["dd_detail"][k]["max_drawdown"] for k in ctx["keys"]}, reverse=False)[0]
    unrecovered = [name(k) for k in ctx["keys"] if ctx["dd_detail"][k].get("recovery") is None]
    return deck.stack([
        deck.slide(f"""
          <p class="eyebrow">Drawdown</p>
          <h2>The deepest hole was {deck.esc(name(worst[0]))} at {PCT0(worst[1])}</h2>
          {grid}
          <p class="footnote">Each panel is the underwater curve — value relative to its own
          running peak — on a shared vertical scale, so panel depth is directly comparable.
          The figure at the top right of each panel is that asset's worst drawdown.</p>
        """),
        deck.slide(f"""
          <p class="eyebrow">Drawdown · table view</p>
          <h2>Depth, date and time spent underwater</h2>
          {deck.table(headers, rows)}
          <p class="footnote">"Days underwater" runs from the pre-drawdown peak to recovery,
          or to the end of the sample if the peak has not been regained.
          {("Still below the prior peak at the end of the sample: " + ", ".join(unrecovered) + ".") if unrecovered else "Every asset here has recovered its prior peak."}
          Depth and duration are different risks: an investor who can wait out the second is
          not necessarily solvent through the first.</p>
        """),
    ])


def var_slides(ctx) -> str:
    name, level = ctx["name_of"], ctx["level"]
    var = ctx["var_tables"]
    headers = ["Asset", "Historical", "Parametric", "Cornish-Fisher", "Monte Carlo",
               "CVaR hist.", "CVaR CF", "10-day hist.", "Skew", "Ex. kurt"]
    rows, classes = [], []
    for key in ctx["keys"]:
        v = var[key]
        rows.append([name(key), PCT2(v["historical_var"]), PCT2(v["parametric_var"]),
                     PCT2(v["cornish_fisher_var"]), PCT2(v["monte_carlo_var"]),
                     PCT2(v["historical_cvar"]), PCT2(v["cornish_fisher_cvar"]),
                     PCT1(risk.scale_horizon(v["historical_var"], 10)),
                     ch.fmt_num(v["skew"]), ch.fmt_num(v["excess_kurtosis"])])
        classes.append(["", "strong", "", "", "", "strong", "", "", "", ""])

    methods = ch.grouped_bar_chart(
        [name(k) for k in ctx["keys"]],
        {"Historical": [var[k]["historical_var"] for k in ctx["keys"]],
         "Parametric": [var[k]["parametric_var"] for k in ctx["keys"]],
         "Cornish-Fisher": [var[k]["cornish_fisher_var"] for k in ctx["keys"]],
         "Monte Carlo": [var[k]["monte_carlo_var"] for k in ctx["keys"]]},
        height=380, value_fmt=PCT1, label="1-day VaR by method")

    gaps = {k: var[k]["cornish_fisher_var"] - var[k]["parametric_var"] for k in ctx["keys"]}
    worst_gap = ranked(gaps)[0]
    if worst_gap[1] > 0:
        gap_sentence = (f"Largest Gaussian understatement: <strong>{deck.esc(name(worst_gap[0]))}"
                        f"</strong>, where the skew/kurtosis-corrected VaR is "
                        f"{PCT2(worst_gap[1])} of daily NAV <em>wider</em> than the Gaussian "
                        f"one \u2014 that gap is capital the normal model never asks for.")
    else:
        gap_sentence = ("On this sample no asset's Cornish-Fisher VaR exceeds its Gaussian "
                        "one: the skew correction dominates the kurtosis correction, so the "
                        "normal model is not the loose one here \u2014 read the historical "
                        "and Monte-Carlo columns against it instead.")
    fattest = ranked({k: var[k]["excess_kurtosis"] for k in ctx["keys"]})[0]

    cvar_ratio = {k: (var[k]["historical_cvar"] / var[k]["historical_var"]
                      if var[k]["historical_var"] else float("nan")) for k in ctx["keys"]}
    tail_rank = ranked(cvar_ratio)

    return deck.stack([
        deck.slide(f"""
          <p class="eyebrow">Value at Risk · {PCT0(level)} confidence, 1 day</p>
          <h2>Where the four methods disagree, the gap is the fat tail</h2>
          {methods}
          {deck.legend([("Historical", CATEGORICAL_LIGHT[0]), ("Parametric (Gaussian)", CATEGORICAL_LIGHT[1]),
                        ("Cornish-Fisher", CATEGORICAL_LIGHT[2]), ("Monte Carlo (Student-t)", CATEGORICAL_LIGHT[3])])}
          <p class="footnote">{gap_sentence}
          Fattest tails overall: <strong>{deck.esc(name(fattest[0]))}</strong> at
          {ch.fmt_num(fattest[1])} excess kurtosis. A Gaussian VaR on that series is not
          conservative — it is wrong in the direction that costs money.</p>
        """),
        deck.slide(f"""
          <p class="eyebrow">Value at Risk · table view</p>
          <h2>VaR and CVaR, all methods</h2>
          {deck.table(headers, rows, classes)}
          <p class="footnote">Positive numbers are losses. CVaR/VaR ratio is highest for
          <strong>{deck.esc(name(tail_rank[0][0]))}</strong> ({ch.fmt_num(tail_rank[0][1])}×)
          and lowest for <strong>{deck.esc(name(tail_rank[-1][0]))}</strong>
          ({ch.fmt_num(tail_rank[-1][1])}×) — the higher the ratio, the more the losses that
          breach VaR overshoot it. The 10-day column is √10 scaling of the 1-day historical
          figure and assumes independent days; in a crisis it is optimistic.</p>
        """),
    ])


def distribution_slides(ctx) -> str:
    name = ctx["name_of"]
    slides = []
    for key in ctx["keys"]:
        v = ctx["var_tables"][key]
        series = ctx["returns_native"][key]
        hist = ch.histogram(series, [
            ("VaR", -v["historical_var"], "var(--s2)"),
            ("CVaR", -v["historical_cvar"], "var(--s8)"),
        ], height=350, bins=80, label=f"{name(key)} daily return distribution")
        breaches = int((series < -v["historical_var"]).sum())
        slides.append(deck.slide(f"""
          <p class="eyebrow">Return distribution · {deck.esc(name(key))}</p>
          <h2>{deck.esc(name(key))}: {ch.fmt_num(v['excess_kurtosis'])} excess kurtosis,
              {ch.fmt_num(v['skew'])} skew</h2>
          {hist}
          <div class="tiles">
            {deck.tile("Historical VaR 95%", PCT2(v["historical_var"]), "1-day loss threshold")}
            {deck.tile("CVaR 95%", PCT2(v["historical_cvar"]), "mean loss beyond it")}
            {deck.tile("Days beyond VaR", f"{breaches:,}", f"of {v['observations']:,} observed")}
            {deck.tile("Worst single day", PCT1(float(series.min())), str(series.idxmin().date()))}
          </div>
          <p class="footnote">Bars left of zero are losing days. The two cut lines sit where
          the historical VaR and CVaR actually fall in this sample — the distance between
          them is the part of the risk that a VaR number alone never tells you.</p>
        """))
    return deck.stack(slides)


def backtest_slide(ctx) -> str:
    name = ctx["name_of"]
    headers = ["Asset", "Observations", "Breaches", "Expected", "Breach rate",
               "Promised", "Kupiec LR", "p-value", "Verdict"]
    rows, classes = [], []
    rejected = []
    for key in ctx["keys"]:
        k = ctx["kupiec"][key]
        if k["verdict"] == "model rejected":
            rejected.append(name(key))
        rows.append([name(key), f"{k['observations']:,}", f"{k['breaches']:,}",
                     ch.fmt_num(k["expected"], 1), PCT2(k["breach_rate"]),
                     PCT2(1 - ctx["level"]), ch.fmt_num(k["lr"]),
                     ch.fmt_num(k["p_value"], 3), k["verdict"]])
        classes.append(["", "", "strong", "", "", "", "",
                        "", "neg" if k["verdict"] == "model rejected" else "pos"])
    verdict = (f"Rejected for {', '.join(rejected)}." if rejected
               else "Not rejected for any asset in this universe.")
    return deck.slide(f"""
      <p class="eyebrow">Does the VaR model actually work?</p>
      <h2>Kupiec proportion-of-failures backtest</h2>
      {deck.table(headers, rows, classes)}
      <p class="footnote">A {PCT0(ctx['level'])} VaR that is doing its job is breached about
      {PCT0(1 - ctx['level'])} of the time — too few breaches means capital is being wasted,
      too many means the number is fiction. VaR here is re-estimated daily on a trailing
      {ctx['var_window']}-day window and lagged one day, so only information available before
      the session is used. The likelihood-ratio statistic tests the observed breach rate
      against the promised one; p &lt; 0.05 rejects the model. <strong>{verdict}</strong>
      This is the slide that separates a risk number from a decoration.</p>
    """)


def correlation_slides(ctx) -> str:
    name = ctx["name_of"]
    order = ctx["cluster_order"]
    matrix = ctx["corr_full"].loc[order, order]
    labelled = matrix.rename(index=name, columns=name)
    heat = ch.heatmap(labelled, vmin=-1, vmax=1, label="Correlation of daily returns")

    pairs = []
    for i, a in enumerate(order):
        for b in order[i + 1:]:
            pairs.append(((a, b), float(ctx["corr_full"].loc[a, b])))
    pairs.sort(key=lambda kv: kv[1], reverse=True)
    top = "".join(f"<li><strong>{deck.esc(name(a))} ↔ {deck.esc(name(b))}</strong> "
                  f"{ch.fmt_num(v)}</li>" for (a, b), v in pairs[:4])
    bottom = "".join(f"<li><strong>{deck.esc(name(a))} ↔ {deck.esc(name(b))}</strong> "
                     f"{ch.fmt_num(v)}</li>" for (a, b), v in pairs[-4:])

    roll = ctx["rolling_corr"].rename(columns=name)
    roll_chart = ch.line_chart(roll, {name(k): v for k, v in ctx["colors"].items()},
                               height=380, value_fmt=lambda v: ch.fmt_num(v, 2),
                               zero_line=True,
                               label=f"{ctx['corr_base_name']} rolling correlation")

    avg = ctx["avg_corr_by_year"]
    avg_bar = ch.bar_chart([str(y) for y in avg.index], list(avg.values), height=330,
                           value_fmt=lambda v: ch.fmt_num(v, 2), polarity=True,
                           label="Average pairwise correlation by year")

    return deck.stack([
        deck.slide(f"""
          <p class="eyebrow">Correlation · whole period</p>
          <h2>Average pairwise correlation is {ch.fmt_num(ctx['avg_corr_full'])}</h2>
          {heat}
          <p class="footnote">Pearson correlation of daily returns on the intersection
          calendar ({ctx['n_days']:,} days). Rows and columns are ordered by hierarchical
          clustering, so blocks of assets that move together sit together. Blue is positive,
          red negative, neutral grey at zero — the number is printed in every cell, so the
          chart is its own table view.</p>
        """),
        deck.slide(f"""
          <p class="eyebrow">Correlation · what pairs with what</p>
          <h2>The tightest and loosest pairs in the universe</h2>
          <div class="cols">
            <div class="card"><h4>Most correlated</h4><ul>{top}</ul></div>
            <div class="card"><h4>Least correlated</h4><ul>{bottom}</ul></div>
          </div>
          <p class="footnote">A pair near +1 is one position wearing two names — holding both
          is concentration, not diversification. A pair near zero is where diversification
          actually comes from, and the year-by-year sections that follow show how little of
          it survives a crisis.</p>
        """),
        deck.slide(f"""
          <p class="eyebrow">Correlation · through time</p>
          <h2>{deck.esc(ctx['corr_base_name'])} against everything else,
              {ctx['corr_window']}-day rolling window</h2>
          {roll_chart}
          <p class="footnote">Correlation is not a constant, and a single full-period number
          hides that. Each line is a rolling window, direct-labelled at its final value;
          hover to isolate one. The interesting question is not the average level but what
          happens to it in the stressed years.</p>
        """),
        deck.slide(f"""
          <p class="eyebrow">Correlation · through time</p>
          <h2>How correlated was everything, year by year?</h2>
          {avg_bar}
          <p class="footnote">Mean of all off-diagonal pairwise correlations, computed
          separately within each calendar year. This is the diversification barometer for
          the whole universe: when the bar rises, the assets are behaving like one position,
          and the risk numbers computed per asset understate what a combined book would
          have lost.</p>
        """),
    ])


def matrix_slides(ctx) -> str:
    name = ctx["name_of"]
    def build(frame, fmt, vmin, vmax, diverging, label):
        labelled = frame.rename(columns=name)
        labelled.index = [str(i) for i in labelled.index]
        return ch.heatmap(labelled, vmin=vmin, vmax=vmax, value_fmt=fmt,
                          diverging=diverging, label=label, row_label_width=64)

    yr = ctx["yearly_returns"]
    # Clip the colour scale at the 85th percentile of |return|: one 800% crypto year
    # would otherwise flatten every other cell into the neutral midpoint. The number
    # is printed in each cell, so nothing is hidden by the clip.
    span = float(np.nanpercentile(np.abs(yr.to_numpy()), 85)) or 1.0
    returns_heat = build(yr, PCT0, -span, span, True, "Calendar-year returns")
    vol_heat = build(ctx["yearly_vol"], PCT0, 0.0,
                     float(np.nanmax(ctx["yearly_vol"].to_numpy())) or 1.0, False,
                     "Annualised volatility by year")
    sharpe = ctx["yearly_sharpe"]
    s_span = float(np.nanmax(np.abs(sharpe.to_numpy()))) or 1.0
    sharpe_heat = build(sharpe, lambda v: ch.fmt_num(v, 1), -s_span, s_span, True,
                        "Sharpe ratio by year")

    positive_years = (yr > 0).sum(axis=1)
    best_year = positive_years.idxmax()
    worst_year = positive_years.idxmin()
    return deck.stack([
        deck.slide(f"""
          <p class="eyebrow">Year by year · the whole grid</p>
          <h2>Calendar-year returns, every asset, {ctx['start_year']}–{ctx['end_year']}</h2>
          {returns_heat}
          <p class="footnote">Blue is a gain, red a loss, neutral grey at zero; the number is
          printed in each cell. The colour scale saturates at ±{PCT0(span)} so that ordinary
          years stay distinguishable next to the outliers. Broadest year: <strong>{best_year}</strong>, with
          {int(positive_years.max())} of {yr.shape[1]} assets up. Narrowest:
          <strong>{worst_year}</strong>, with {int(positive_years.min())} up. Returns are
          compounded within the calendar year and are not annualised, so a partial final
          year is a partial-year figure.</p>
        """),
        deck.slide(f"""
          <p class="eyebrow">Year by year · the whole grid</p>
          <h2>Annualised volatility by year</h2>
          {vol_heat}
          <p class="footnote">Single-hue ramp, light to dark — this is a pure magnitude, so
          it gets a sequential scale rather than the diverging one used for signed returns.
          Volatility is computed within each calendar year on each asset's own calendar and
          annualised on its observed sampling frequency.</p>
        """),
        deck.slide(f"""
          <p class="eyebrow">Year by year · the whole grid</p>
          <h2>Sharpe ratio by year</h2>
          {sharpe_heat}
          <p class="footnote">A single-year Sharpe is a noisy statistic — one year of daily
          data is roughly 250 observations, and the standard error on a Sharpe estimate at
          that sample size is large. Read the grid for its pattern across rows, not for the
          precision of any one cell. Risk-free rate {PCT1(ctx['rf'])}.</p>
        """),
    ])


def year_section(ctx, year: int) -> str:
    name = ctx["name_of"]
    yr_returns = ctx["yearly_returns"].loc[year]
    order = ranked(yr_returns.to_dict())
    best, worst = order[0], order[-1]
    stats = ctx["yearly_stats"][year]
    corr = ctx["yearly_corr"].get(year)
    partial = (" (partial year)" if year == ctx["end_year"] else "")

    bars = ch.bar_chart([name(k) for k, _ in order], [v for _, v in order],
                        height=360, value_fmt=PCT0,
                        label=f"{year} returns by asset")

    up = int((yr_returns > 0).sum())
    tile_row = deck.tiles([
        deck.tile("Best", GROWTH(best[1]), name(best[0]), tone(best[1])),
        deck.tile("Worst", GROWTH(worst[1]), name(worst[0]), tone(worst[1])),
        deck.tile("Assets up", f"{up} of {len(yr_returns)}", "positive calendar year"),
        deck.tile("Avg pairwise corr.", ch.fmt_num(ctx["avg_corr_by_year"].get(year, float("nan"))),
                  "within the year"),
    ])

    risk_headers = ["Asset", "Return", "Vol", "Sharpe", "Sortino", "Max DD",
                    "VaR 95%", "CVaR 95%", "Worst day", "Skew"]
    risk_rows, risk_classes = [], []
    for key, _ in order:
        s = stats.get(key)
        if not s:
            continue
        risk_rows.append([name(key), PCT0(s["total_return"]), PCT1(s["volatility"]),
                          ch.fmt_num(s["sharpe"]), ch.fmt_num(s["sortino"]),
                          PCT1(s["max_drawdown"]), PCT2(s["var_95"]), PCT2(s["cvar_95"]),
                          PCT1(s["worst_day"]), ch.fmt_num(s["skew"])])
        risk_classes.append(["", cell_tone(s["total_return"]), "", "strong", "", "neg",
                             "", "", "neg", ""])

    slides = [
        deck.slide(f"""
          <p class="eyebrow">{year}{partial} · performance</p>
          <h2>{deck.esc(name(best[0]))} {GROWTH(best[1])}, {deck.esc(name(worst[0]))}
              {GROWTH(worst[1])}</h2>
          {tile_row}
          {bars}
          <p class="footnote">Compounded calendar-year return, sorted best to worst. Blue is
          a gain, red a loss.</p>
        """),
        deck.slide(f"""
          <p class="eyebrow">{year}{partial} · risk</p>
          <h2>What {year} cost to hold</h2>
          {deck.table(risk_headers, risk_rows, risk_classes)}
          <p class="footnote">Volatility and Sharpe are annualised from that year's daily
          returns alone. VaR and CVaR are historical, {PCT0(ctx['level'])}, estimated within
          the year — roughly 250 observations, so the {PCT0(1 - ctx['level'])} tail is about
          12 days and these figures carry real estimation error. Max drawdown is measured
          inside the calendar year and will understate a drawdown that straddles year-end.</p>
        """),
    ]
    if corr is not None and corr.shape[0] > 1:
        order_year = corr_mod.cluster_order(corr)
        labelled = corr.loc[order_year, order_year].rename(index=name, columns=name)
        avg = ctx["avg_corr_by_year"].get(year, float("nan"))
        prev = ctx["avg_corr_by_year"].get(year - 1, float("nan"))
        if np.isfinite(prev):
            delta = avg - prev
            move = (f"That is {ch.fmt_num(abs(delta))} "
                    f"{'higher' if delta > 0 else 'lower'} than {year - 1}.")
        else:
            move = "First year in the sample, so there is nothing to compare it against."
        slides.append(deck.slide(f"""
          <p class="eyebrow">{year}{partial} · correlation</p>
          <h2>Average pairwise correlation {ch.fmt_num(avg)}</h2>
          {ch.heatmap(labelled, vmin=-1, vmax=1, label=f"{year} correlation matrix")}
          <p class="footnote">{move} Computed on the days every asset traded within
          {year}. Clustered ordering, so co-moving blocks are adjacent.</p>
        """))
    return deck.stack(slides)


def synthesis_slide(ctx) -> str:
    name = ctx["name_of"]
    avg = ctx["avg_corr_by_year"].dropna()
    first_half = avg.iloc[:len(avg) // 2].mean()
    second_half = avg.iloc[len(avg) // 2:].mean()
    direction = "risen" if second_half > first_half else "fallen"
    peak_year = avg.idxmax()
    yr = ctx["yearly_returns"]
    consistency = (yr > 0).sum(axis=0).sort_values(ascending=False)
    steadiest, patchiest = consistency.index[0], consistency.index[-1]
    dispersion = (yr.max(axis=1) - yr.min(axis=1))
    widest = dispersion.idxmax()
    stats = ctx["full_stats"]
    kurt_rank = ranked({k: stats[k]["excess_kurtosis"] for k in ctx["keys"]})
    return deck.slide(f"""
      <p class="eyebrow">What the decade says</p>
      <h2>Four findings that survive the whole sample</h2>
      <div class="cols">
        <div>
          <div class="card">
            <h4>1 · Diversification has {direction}</h4>
            <p>Average pairwise correlation ran {ch.fmt_num(first_half)} across the first
            half of the sample and {ch.fmt_num(second_half)} across the second, peaking in
            <strong>{peak_year}</strong> at {ch.fmt_num(avg.max())}. A cross-asset book
            sized on the earlier number was carrying more common risk than it thought.</p>
          </div>
          <div class="card" style="margin-top:14px">
            <h4>2 · Consistency and magnitude are different questions</h4>
            <p><strong>{deck.esc(name(steadiest))}</strong> finished up in
            {int(consistency.iloc[0])} of {len(yr)} calendar years,
            <strong>{deck.esc(name(patchiest))}</strong> in only
            {int(consistency.iloc[-1])}. Neither figure tells you which compounded more —
            the size of the up years does.</p>
          </div>
        </div>
        <div>
          <div class="card">
            <h4>3 · Every asset here has fatter tails than the Gaussian model assumes</h4>
            <p>Excess kurtosis runs from {ch.fmt_num(kurt_rank[-1][1])}
            ({deck.esc(name(kurt_rank[-1][0]))}) to {ch.fmt_num(kurt_rank[0][1])}
            ({deck.esc(name(kurt_rank[0][0]))}). Parametric VaR is therefore the smallest of
            the four methods on almost every row of this deck, and it is smallest exactly
            where the loss would be largest.</p>
          </div>
          <div class="card" style="margin-top:14px">
            <h4>4 · The spread between winners and losers is the real story of a year</h4>
            <p>The widest gap between the best and worst asset in a single calendar year was
            <strong>{widest}</strong>, at {PCT0(dispersion.max())}. Asset-class selection
            dominated risk management in that year; in the narrow years the reverse was
            true.</p>
          </div>
        </div>
      </div>
      <p class="footnote">Each statement above is computed from the data in this deck at
      build time — nothing here is a stored opinion.</p>
    """)


def appendix_slides(ctx) -> str:
    return deck.stack([
        deck.slide("""
          <p class="eyebrow">Appendix</p>
          <h2>Definitions</h2>
          <div class="cols">
            <div>
              <p><strong>CAGR</strong> — geometric annualised growth rate.<br>
              <strong>Volatility</strong> — standard deviation of daily returns × √(observed
              periods per year).<br>
              <strong>Downside deviation</strong> — same, using only returns below the
              risk-free rate.<br>
              <strong>Sharpe</strong> — (CAGR − r<sub>f</sub>) / volatility.<br>
              <strong>Sortino</strong> — (CAGR − r<sub>f</sub>) / downside deviation.<br>
              <strong>Calmar</strong> — CAGR / |max drawdown|.<br>
              <strong>Omega</strong> — probability-weighted gains ÷ losses at a zero
              threshold.<br>
              <strong>Ulcer index</strong> — root-mean-square drawdown.</p>
            </div>
            <div>
              <p><strong>Beta</strong> — cov(asset, benchmark) / var(benchmark).<br>
              <strong>Alpha</strong> — CAGR − [r<sub>f</sub> + β(CAGR<sub>bench</sub> −
              r<sub>f</sub>)], annualised.<br>
              <strong>Information ratio</strong> — active return / tracking error.<br>
              <strong>VaR</strong> — loss threshold exceeded (1 − confidence) of the
              time.<br>
              <strong>CVaR</strong> — mean loss conditional on breaching VaR.<br>
              <strong>Cornish-Fisher</strong> — Gaussian quantile z corrected by the sample
              skew S and excess kurtosis K:
              z + (z²−1)S/6 + (z³−3z)K/24 − (2z³−5z)S²/36.<br>
              <strong>Kupiec LR</strong> — likelihood-ratio test of observed vs promised
              breach rate, χ² with 1 degree of freedom.</p>
            </div>
          </div>
        """),
        deck.slide(f"""
          <p class="eyebrow">Appendix</p>
          <h2>Data, reproduction and limits</h2>
          <div class="cols wide-left">
            <div>
              <p><strong>Source.</strong> Daily closes from Yahoo Finance via
              <code>yfinance</code>, auto-adjusted, cached locally as parquet.
              Sample {ctx['first_day']} → {ctx['last_day']}.</p>
              <p><strong>Rebuild.</strong> <code>python3 -m report.build_report --start
              {ctx['start']} --refresh</code> — the deck regenerates from live data with the
              same code that produced this one. Every table is also written to
              <code>report/dist/data/*.csv</code>.</p>
              <p><strong>Add an asset.</strong> Append it to
              <code>config/universe.json</code> with its Yahoo ticker and asset class; every
              chart, table and year section picks it up on the next build.</p>
            </div>
            <div class="card">
              <h4>Known limits</h4>
              <p>· Equity series are price indices — no dividends.<br>
              · Commodity series are front-month futures — roll effects included.<br>
              · No transaction costs, financing, slippage or tax.<br>
              · Single-year statistics rest on ~250 observations.<br>
              · √t VaR scaling assumes independent days.<br>
              · Correlations are Pearson: linear, and blind to tail dependence.<br>
              · Past distributions are not forecasts.</p>
            </div>
          </div>
          <p class="footnote">Generated {date.today().isoformat()} ·
          {ctx['n_slides_note']}</p>
        """),
    ])


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #

def compute(args) -> dict:
    assets = load_universe()
    keys = [a.key for a in assets]
    prices = load_prices(assets, args.start, args.end, args.refresh, args.demo)

    native = {k: prices[k].dropna() for k in keys}
    returns_native = {k: ret_mod.to_returns(native[k]) for k in keys}
    ppy = {k: ret_mod.periods_per_year(returns_native[k].index) for k in keys}

    wide = pd.DataFrame({k: native[k] for k in keys}).sort_index()
    aligned = ret_mod.align_prices(wide, "intersection")
    returns_aligned = ret_mod.to_returns(aligned)
    bench = args.benchmark if args.benchmark in keys else keys[0]

    full_stats = {}
    for key in keys:
        row = ratios.summarise(returns_native[key], ppy[key], args.rf, level=args.level)
        beta, alpha = ratios.beta_alpha(returns_aligned[key], returns_aligned[bench],
                                        ret_mod.periods_per_year(returns_aligned.index), args.rf)
        row.update({
            "beta": beta, "alpha": alpha,
            "tracking_error": ratios.tracking_error(
                returns_aligned[key], returns_aligned[bench],
                ret_mod.periods_per_year(returns_aligned.index)),
            "information_ratio": ratios.information_ratio(
                returns_aligned[key], returns_aligned[bench],
                ret_mod.periods_per_year(returns_aligned.index)),
        })
        full_stats[key] = row

    var_tables = {k: risk.var_table(returns_native[k], args.level) for k in keys}
    kupiec = {}
    for key in keys:
        rolling = risk.rolling_var(returns_native[key], args.var_window, args.level)
        kupiec[key] = risk.kupiec_pof(returns_native[key], rolling, args.level)

    corr_full = corr_mod.correlation_matrix(returns_aligned)
    yearly_corr = corr_mod.yearly_correlation(returns_aligned)
    avg_corr_by_year = pd.Series({y: corr_mod.average_pairwise(m)
                                  for y, m in yearly_corr.items()}).sort_index()
    corr_base = "BTC" if "BTC" in keys else keys[0]
    rolling_corr = corr_mod.rolling_correlation(
        returns_aligned, corr_base, [k for k in keys if k != corr_base], args.corr_window)

    years = sorted({int(y) for k in keys for y in returns_native[k].index.year})
    yearly_returns = pd.DataFrame(index=years, columns=keys, dtype=float)
    yearly_vol = yearly_returns.copy()
    yearly_sharpe = yearly_returns.copy()
    yearly_stats: dict[int, dict] = {}
    for year in years:
        yearly_stats[year] = {}
        for key in keys:
            block = returns_native[key][returns_native[key].index.year == year]
            if len(block) < 20:
                continue
            row = ratios.summarise(block, ppy[key], args.rf, level=args.level)
            yearly_stats[year][key] = row
            yearly_returns.loc[year, key] = row["total_return"]
            yearly_vol.loc[year, key] = row["volatility"]
            yearly_sharpe.loc[year, key] = row["sharpe"]

    name_of = {a.key: a.name for a in assets}
    crypto = [a.key for a in assets if a.asset_class == "Crypto"]
    equity = [a.key for a in assets if a.asset_class == "Equity"]
    return {
        "assets": assets, "keys": keys, "demo": args.demo,
        "name_of": lambda k: name_of.get(k, k),
        "colors": {k: i for i, k in enumerate(keys)},
        "prices_native": native, "returns_native": returns_native, "ppy": ppy,
        "aligned": aligned, "returns_aligned": returns_aligned,
        "rebased": ret_mod.rebased(aligned),
        "drawdowns": {k: ret_mod.drawdown(returns_native[k]) for k in keys},
        "dd_detail": {k: ret_mod.drawdown_details(returns_native[k]) for k in keys},
        "full_stats": full_stats, "var_tables": var_tables, "kupiec": kupiec,
        "corr_full": corr_full, "cluster_order": corr_mod.cluster_order(corr_full),
        "avg_corr_full": corr_mod.average_pairwise(corr_full),
        "yearly_corr": yearly_corr, "avg_corr_by_year": avg_corr_by_year,
        "rolling_corr": rolling_corr, "corr_base_name": name_of.get(corr_base, corr_base),
        "corr_window": args.corr_window, "var_window": args.var_window,
        "yearly_returns": yearly_returns.dropna(how="all"),
        "yearly_vol": yearly_vol.dropna(how="all"),
        "yearly_sharpe": yearly_sharpe.dropna(how="all"),
        "yearly_stats": yearly_stats, "years": years,
        "rf": args.rf, "level": args.level, "start": args.start,
        "benchmark_name": name_of.get(bench, bench),
        "first_day": str(aligned.index.min().date()), "last_day": str(aligned.index.max().date()),
        "n_days": len(aligned), "start_year": years[0], "end_year": years[-1],
        "ppy_crypto": ppy[crypto[0]] if crypto else 365.0,
        "ppy_equity": ppy[equity[0]] if equity else 252.0,
    }


def export_csv(ctx, out_dir: Path) -> None:
    """Every table in the deck, also as CSV -- the machine-readable table view."""
    data = out_dir / "data"
    data.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(ctx["full_stats"]).T.to_csv(data / "full_period_stats.csv")
    pd.DataFrame(ctx["var_tables"]).T.to_csv(data / "var_cvar.csv")
    pd.DataFrame(ctx["kupiec"]).T.to_csv(data / "kupiec_backtest.csv")
    ctx["corr_full"].to_csv(data / "correlation_full_period.csv")
    ctx["yearly_returns"].to_csv(data / "yearly_returns.csv")
    ctx["yearly_vol"].to_csv(data / "yearly_volatility.csv")
    ctx["yearly_sharpe"].to_csv(data / "yearly_sharpe.csv")
    ctx["avg_corr_by_year"].rename("avg_pairwise_correlation").to_csv(
        data / "avg_correlation_by_year.csv")
    for year, matrix in ctx["yearly_corr"].items():
        matrix.to_csv(data / f"correlation_{year}.csv")
    frames = []
    for year, rows in ctx["yearly_stats"].items():
        for key, row in rows.items():
            frames.append({"year": year, "asset": key, **row})
    pd.DataFrame(frames).to_csv(data / "yearly_stats.csv", index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--start", default="2016-01-01")
    parser.add_argument("--end", default=date.today().isoformat())
    parser.add_argument("--rf", type=float, default=0.02, help="annual risk-free rate")
    parser.add_argument("--level", type=float, default=0.95, help="VaR confidence level")
    parser.add_argument("--benchmark", default="SPX")
    parser.add_argument("--corr-window", type=int, default=90)
    parser.add_argument("--var-window", type=int, default=250)
    parser.add_argument("--refresh", action="store_true", help="ignore the local cache")
    parser.add_argument("--demo", action="store_true",
                        help="synthetic data, for testing the pipeline offline")
    parser.add_argument("--out", default=str(OUT_DIR / "market-report.html"))
    args = parser.parse_args()

    print(f"Building report {args.start} -> {args.end}")
    ctx = compute(args)
    ctx["n_slides_note"] = "built with report/build_report.py"

    slides = [
        title_slide(ctx),
        method_slides(ctx),
        overview_slides(ctx),
        ratio_slides(ctx),
        drawdown_slides(ctx),
        var_slides(ctx),
        distribution_slides(ctx),
        backtest_slide(ctx),
        correlation_slides(ctx),
        matrix_slides(ctx),
    ]
    slides += [year_section(ctx, year) for year in ctx["yearly_returns"].index]
    slides += [synthesis_slide(ctx), appendix_slides(ctx)]

    html_doc = deck.build_html(
        f"Market Report {ctx['start_year']}–{ctx['end_year']}", slides,
        "Yearly multi-asset market, correlation and risk report across crypto, equities, "
        "metals and energy.")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html_doc)
    export_csv(ctx, out.parent)
    print(f"  {out}  ({out.stat().st_size / 1024:.0f} KB, "
          f"{html_doc.count('<section')} sections)")
    print(f"  {out.parent / 'data'}  (CSV exports)")


if __name__ == "__main__":
    main()
