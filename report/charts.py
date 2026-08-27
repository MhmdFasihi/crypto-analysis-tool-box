"""Inline-SVG chart primitives for the report.

Everything renders to a self-contained ``<svg>`` string that inherits colours
from CSS custom properties (``--s1``..``--s8``, ``--grid``, ``--ink``...), so
the same markup is correct in light and dark mode. Marks follow the data-viz
mark spec: 2px lines, hairline recessive grid, 4px rounded data-ends anchored
to the baseline, a 2px surface gap between adjacent fills, selective direct
labels rather than a number on every point.
"""
from __future__ import annotations

import math
from datetime import date

import numpy as np
import pandas as pd

W = 1000  # all charts share one viewBox width; height varies per form


def esc(text) -> str:
    return (str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def fmt_pct(value, digits: int = 1) -> str:
    if value is None or (isinstance(value, float) and not math.isfinite(value)):
        return "n/a"
    return f"{value * 100:.{digits}f}%"


def fmt_num(value, digits: int = 2) -> str:
    if value is None or (isinstance(value, float) and not math.isfinite(value)):
        return "n/a"
    return f"{value:,.{digits}f}"


def fmt_growth(value, digits: int = 0) -> str:
    """Percent for ordinary returns, a growth multiple once percent stops reading.

    "352,136%" is a number nobody parses; "3,522x" is the same fact, legible.
    """
    if value is None or (isinstance(value, float) and not math.isfinite(value)):
        return "n/a"
    if value >= 9.99:
        return f"{1 + value:,.0f}x"
    return f"{value * 100:.{digits}f}%"


def nice_ticks(lo: float, hi: float, count: int = 5) -> list[float]:
    """Human-readable tick positions spanning [lo, hi]."""
    if not math.isfinite(lo) or not math.isfinite(hi) or hi <= lo:
        return [lo, hi]
    raw = (hi - lo) / max(count, 1)
    mag = 10 ** math.floor(math.log10(raw))
    step = min([m * mag for m in (1, 2, 2.5, 5, 10)], key=lambda s: abs(s - raw))
    start = math.floor(lo / step) * step
    ticks, value = [], start
    while value <= hi + step * 0.5:
        if value >= lo - step * 0.001:
            ticks.append(round(value, 10))
        value += step
    return ticks


class Frame:
    """Plot geometry plus data->pixel scales."""

    def __init__(self, height: int, left: int = 62, right: int = 124,
                 top: int = 18, bottom: int = 34):
        self.width, self.height = W, height
        self.l, self.r, self.t, self.b = left, right, top, bottom
        self.x0, self.x1 = left, W - right
        self.y0, self.y1 = top, height - bottom

    def sx(self, value, lo, hi):
        if hi == lo:
            return (self.x0 + self.x1) / 2
        return self.x0 + (value - lo) / (hi - lo) * (self.x1 - self.x0)

    def sy(self, value, lo, hi):
        if hi == lo:
            return (self.y0 + self.y1) / 2
        return self.y1 - (value - lo) / (hi - lo) * (self.y1 - self.y0)


def _open(height: int, label: str) -> str:
    return (f'<svg class="chart" viewBox="0 0 {W} {height}" role="img" '
            f'preserveAspectRatio="xMidYMid meet" aria-label="{esc(label)}">')


def _grid(f: Frame, ticks, lo, hi, fmt) -> str:
    """Hairline horizontal grid with axis labels on the left."""
    out = []
    for tick in ticks:
        y = f.sy(tick, lo, hi)
        if not (f.y0 - 1 <= y <= f.y1 + 1):
            continue
        out.append(f'<line class="grid" x1="{f.x0}" x2="{f.x1}" y1="{y:.1f}" y2="{y:.1f}"/>')
        out.append(f'<text class="tick" x="{f.x0 - 10}" y="{y + 4:.1f}" '
                   f'text-anchor="end">{esc(fmt(tick))}</text>')
    return "".join(out)


def _place_labels(entries: list[tuple[float, str, str]], y0: float, y1: float,
                  gap: float = 15.0) -> list[tuple[float, str, str]]:
    """Push overlapping end-labels apart so none collide or leave the plot."""
    entries = sorted(entries, key=lambda e: e[0])
    placed = []
    for y, text, colour in entries:
        y = max(y, y0 + 6)
        if placed and y - placed[-1][0] < gap:
            y = placed[-1][0] + gap
        placed.append((y, text, colour))
    overflow = placed[-1][0] - (y1 - 2) if placed else 0
    if overflow > 0:  # ran off the bottom: pull the whole stack up
        placed = [(y - overflow, t, c) for y, t, c in placed]
    return placed


# --------------------------------------------------------------------------- #
# Time series
# --------------------------------------------------------------------------- #

def line_chart(frame: pd.DataFrame, colors: dict[str, int], *, height: int = 400,
               log: bool = False, value_fmt=fmt_num, label: str = "",
               end_labels: bool = True, zero_line: bool = False,
               highlight: list[str] | None = None) -> str:
    """Multi-series time series. One line per column, direct-labelled at the end."""
    frame = frame.dropna(how="all")
    f = Frame(height)
    values = frame.to_numpy(dtype=float)
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return f'{_open(height, label)}</svg>'
    lo, hi = float(np.nanmin(finite)), float(np.nanmax(finite))
    if log:
        lo, hi = max(lo, 1e-9), hi
        tlo, thi = math.log10(lo), math.log10(hi)
        pad = (thi - tlo) * 0.06 or 0.1
        tlo, thi = tlo - pad, thi + pad
        ticks = [10 ** t for t in range(math.floor(tlo), math.ceil(thi) + 1)]
        to_axis = math.log10
    else:
        pad = (hi - lo) * 0.08 or abs(hi) * 0.1 or 1.0
        tlo, thi = lo - pad, hi + pad
        ticks = nice_ticks(tlo, thi, 5)
        to_axis = lambda v: v  # noqa: E731

    parts = [_open(height, label)]
    parts.append(_grid(f, [to_axis(t) for t in ticks], tlo, thi,
                       lambda v: value_fmt(10 ** v if log else v)))

    if zero_line and tlo < 0 < thi:
        y = f.sy(0, tlo, thi)
        parts.append(f'<line class="axis" x1="{f.x0}" x2="{f.x1}" y1="{y:.1f}" y2="{y:.1f}"/>')

    # x axis: one tick per year boundary
    index = frame.index
    n = len(index) - 1
    years = pd.Series(index.year, index=range(len(index)))
    first_of_year = years[~years.duplicated()]
    for pos, year in first_of_year.items():
        x = f.sx(pos, 0, n)
        parts.append(f'<line class="grid" x1="{x:.1f}" x2="{x:.1f}" y1="{f.y0}" y2="{f.y1}"/>')
        parts.append(f'<text class="tick" x="{x:.1f}" y="{f.y1 + 22}" '
                     f'text-anchor="middle">{year}</text>')
    parts.append(f'<line class="axis" x1="{f.x0}" x2="{f.x1}" y1="{f.y1}" y2="{f.y1}"/>')

    ends = []
    for column in frame.columns:
        slot = colors.get(column, 0) + 1
        series = frame[column].astype(float)
        points = []
        for pos, value in enumerate(series.to_numpy()):
            if not np.isfinite(value) or (log and value <= 0):
                continue
            points.append(f"{f.sx(pos, 0, n):.1f},{f.sy(to_axis(value), tlo, thi):.1f}")
        if not points:
            continue
        dim = " dim" if highlight and column not in highlight else ""
        path = " ".join(points)
        parts.append(f'<g class="series{dim}" style="--c:var(--s{slot})">'
                     f'<title>{esc(column)}</title>'
                     f'<polyline class="hit" points="{path}"/>'
                     f'<polyline class="line" points="{path}"/></g>')
        last = series.dropna()
        if end_labels and len(last):
            ends.append((f.sy(to_axis(float(last.iloc[-1])), tlo, thi),
                         f"{column} {value_fmt(float(last.iloc[-1]))}", f"var(--s{slot})"))

    for y, text, colour in _place_labels(ends, f.y0, f.y1):
        parts.append(f'<text class="end-label" x="{f.x1 + 8}" y="{y:.1f}" '
                     f'fill="{colour}">{esc(text)}</text>')
    parts.append("</svg>")
    return "".join(parts)


def area_chart(series: pd.Series, *, height: int = 260, slot: int = 1,
               value_fmt=fmt_pct, label: str = "", invert: bool = False) -> str:
    """Single-series filled area, used for underwater/drawdown curves."""
    series = series.dropna().astype(float)
    f = Frame(height, right=30)
    if series.empty:
        return f'{_open(height, label)}</svg>'
    lo, hi = float(series.min()), float(series.max())
    lo, hi = (min(lo, 0.0), max(hi, 0.0))
    pad = (hi - lo) * 0.08 or 0.01
    tlo, thi = lo - pad, hi + pad
    ticks = nice_ticks(tlo, thi, 4)

    parts = [_open(height, label), _grid(f, ticks, tlo, thi, value_fmt)]
    n = len(series) - 1
    base = f.sy(0, tlo, thi)
    pts = [f"{f.sx(i, 0, n):.1f},{f.sy(v, tlo, thi):.1f}" for i, v in enumerate(series.to_numpy())]
    parts.append(f'<path class="area" style="--c:var(--s{slot})" '
                 f'd="M {f.x0:.1f},{base:.1f} L {" L ".join(pts)} L {f.x1:.1f},{base:.1f} Z"/>')
    parts.append(f'<polyline class="line" style="--c:var(--s{slot})" points="{" ".join(pts)}"/>')
    parts.append(f'<line class="axis" x1="{f.x0}" x2="{f.x1}" y1="{base:.1f}" y2="{base:.1f}"/>')

    index = series.index
    years = pd.Series(index.year, index=range(len(index)))
    for pos, year in years[~years.duplicated()].items():
        x = f.sx(pos, 0, n)
        parts.append(f'<text class="tick" x="{x:.1f}" y="{f.y1 + 22}" '
                     f'text-anchor="middle">{year}</text>')
    parts.append("</svg>")
    return "".join(parts)


# --------------------------------------------------------------------------- #
# Categorical
# --------------------------------------------------------------------------- #

def bar_chart(labels: list[str], values: list[float], *, height: int = 380,
              value_fmt=fmt_pct, label: str = "", polarity: bool = True,
              slot: int = 1) -> str:
    """Vertical bars from a zero baseline.

    ``polarity`` colours by sign (blue up / red down) -- a diverging encoding of
    a signed quantity, not a value ramp on nominal categories.
    """
    f = Frame(height, left=68, right=24, top=26, bottom=46)
    finite = [v for v in values if v is not None and math.isfinite(v)]
    if not finite:
        return f'{_open(height, label)}</svg>'
    lo, hi = min(min(finite), 0.0), max(max(finite), 0.0)
    pad = (hi - lo) * 0.16 or 0.01
    tlo, thi = lo - pad, hi + pad
    parts = [_open(height, label), _grid(f, nice_ticks(tlo, thi, 5), tlo, thi, value_fmt)]

    n = len(labels)
    slot_w = (f.x1 - f.x0) / max(n, 1)
    bar_w = min(slot_w - 14, 62)
    base = f.sy(0, tlo, thi)
    radius = 4
    for i, (name, value) in enumerate(zip(labels, values)):
        if value is None or not math.isfinite(value):
            continue
        cx = f.x0 + slot_w * (i + 0.5)
        x = cx - bar_w / 2
        y = f.sy(value, tlo, thi)
        colour = ("var(--up)" if value >= 0 else "var(--down)") if polarity else f"var(--s{slot})"
        h = abs(y - base)
        r = min(radius, h)
        if value >= 0:  # rounded top, square foot on the baseline
            d = (f"M {x:.1f},{base:.1f} V {y + r:.1f} Q {x:.1f},{y:.1f} {x + r:.1f},{y:.1f} "
                 f"H {x + bar_w - r:.1f} Q {x + bar_w:.1f},{y:.1f} {x + bar_w:.1f},{y + r:.1f} "
                 f"V {base:.1f} Z")
            ty = y - 9
        else:
            d = (f"M {x:.1f},{base:.1f} V {y - r:.1f} Q {x:.1f},{y:.1f} {x + r:.1f},{y:.1f} "
                 f"H {x + bar_w - r:.1f} Q {x + bar_w:.1f},{y:.1f} {x + bar_w:.1f},{y - r:.1f} "
                 f"V {base:.1f} Z")
            ty = y + 18
        parts.append(f'<g class="mark"><title>{esc(name)}: {esc(value_fmt(value))}</title>'
                     f'<path fill="{colour}" d="{d}"/></g>')
        parts.append(f'<text class="value" x="{cx:.1f}" y="{ty:.1f}" '
                     f'text-anchor="middle">{esc(value_fmt(value))}</text>')
        parts.append(f'<text class="cat" x="{cx:.1f}" y="{f.height - 14}" '
                     f'text-anchor="middle">{esc(name)}</text>')
    parts.append(f'<line class="axis" x1="{f.x0}" x2="{f.x1}" y1="{base:.1f}" y2="{base:.1f}"/>')
    parts.append("</svg>")
    return "".join(parts)


def grouped_bar_chart(categories: list[str], groups: dict[str, list[float]], *,
                      height: int = 380, value_fmt=fmt_pct, label: str = "") -> str:
    """Bars grouped by category, one colour slot per group, 2px gap between bars.

    Series identity comes from the HTML legend rendered beside the chart, so no
    second legend is drawn inside the SVG.
    """
    f = Frame(height, left=68, right=24, top=18, bottom=46)
    finite = [v for vals in groups.values() for v in vals if v is not None and math.isfinite(v)]
    if not finite:
        return f'{_open(height, label)}</svg>'
    lo, hi = min(min(finite), 0.0), max(finite)
    pad = (hi - lo) * 0.16 or 0.01
    tlo, thi = lo - pad, hi + pad
    parts = [_open(height, label), _grid(f, nice_ticks(tlo, thi, 5), tlo, thi, value_fmt)]

    n, g = len(categories), len(groups)
    slot_w = (f.x1 - f.x0) / max(n, 1)
    bar_w = max((slot_w - 22) / max(g, 1) - 2, 4)
    base = f.sy(0, tlo, thi)
    for gi, (gname, values) in enumerate(groups.items()):
        for i, value in enumerate(values):
            if value is None or not math.isfinite(value):
                continue
            left = f.x0 + slot_w * i + 11 + gi * (bar_w + 2)
            y = f.sy(value, tlo, thi)
            h = abs(y - base)
            r = min(4, h)
            top = min(y, base)
            d = (f"M {left:.1f},{base:.1f} V {top + r:.1f} Q {left:.1f},{top:.1f} "
                 f"{left + r:.1f},{top:.1f} H {left + bar_w - r:.1f} "
                 f"Q {left + bar_w:.1f},{top:.1f} {left + bar_w:.1f},{top + r:.1f} "
                 f"V {base:.1f} Z")
            parts.append(f'<g class="mark"><title>{esc(categories[i])} · {esc(gname)}: '
                         f'{esc(value_fmt(value))}</title>'
                         f'<path fill="var(--s{gi + 1})" d="{d}"/></g>')
    for i, name in enumerate(categories):
        cx = f.x0 + slot_w * (i + 0.5)
        parts.append(f'<text class="cat" x="{cx:.1f}" y="{f.height - 14}" '
                     f'text-anchor="middle">{esc(name)}</text>')
    parts.append(f'<line class="axis" x1="{f.x0}" x2="{f.x1}" y1="{base:.1f}" y2="{base:.1f}"/>')
    parts.append("</svg>")
    return "".join(parts)


def heatmap(matrix: pd.DataFrame, *, height: int | None = None, vmin: float = -1.0,
            vmax: float = 1.0, value_fmt=lambda v: f"{v:.2f}", label: str = "",
            diverging: bool = True, row_label_width: int = 92) -> str:
    """Matrix heatmap with the number printed in every cell (its own table view).

    Diverging blue<->red with a neutral grey midpoint for signed quantities;
    a single-hue blue ramp when the quantity is pure magnitude.
    """
    rows, cols = list(matrix.index), list(matrix.columns)
    cell_h = 42
    top, bottom = 30, 14
    height = height or top + bottom + cell_h * len(rows)
    cell_w = (W - row_label_width - 16) / max(len(cols), 1)
    parts = [_open(height, label)]
    for j, col in enumerate(cols):
        x = row_label_width + cell_w * (j + 0.5)
        parts.append(f'<text class="cat" x="{x:.1f}" y="{top - 12}" '
                     f'text-anchor="middle">{esc(col)}</text>')
    for i, row in enumerate(rows):
        y = top + cell_h * i
        parts.append(f'<text class="cat" x="{row_label_width - 12}" y="{y + cell_h / 2 + 4:.1f}" '
                     f'text-anchor="end">{esc(row)}</text>')
        for j, col in enumerate(cols):
            value = matrix.iloc[i, j]
            x = row_label_width + cell_w * j
            if value is None or (isinstance(value, float) and not math.isfinite(value)):
                fill, ink = "var(--mid)", "var(--muted)"
                text = "n/a"
            else:
                t = 0.0 if vmax == vmin else (float(value) - vmin) / (vmax - vmin)
                fill = _diverging(t) if diverging else _sequential(t)
                ink = "var(--ink)" if fill.startswith("var(") else _ink_for(fill)
                text = value_fmt(float(value))
            parts.append(f'<g class="mark"><title>{esc(row)} / {esc(col)}: {esc(text)}</title>'
                         f'<rect x="{x + 1:.1f}" y="{y + 1:.1f}" width="{cell_w - 2:.1f}" '
                         f'height="{cell_h - 2}" rx="3" fill="{fill}"/></g>')
            parts.append(f'<text class="cell" x="{x + cell_w / 2:.1f}" y="{y + cell_h / 2 + 4:.1f}" '
                         f'text-anchor="middle" fill="{ink}">{esc(text)}</text>')
    parts.append("</svg>")
    return "".join(parts)


def _ink_for(fill: str) -> str:
    """Black or white text, chosen from the fill's luminance.

    Heatmap fills are fixed hexes rather than theme tokens, so the readable ink
    cannot be inherited from the mode -- a pale blue cell needs dark text in
    dark mode exactly as it does in light mode.
    """
    if not fill.startswith("#"):
        return "var(--ink)"
    r, g, b = (int(fill[i:i + 2], 16) / 255 for i in (1, 3, 5))
    channels = [(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4) for c in (r, g, b)]
    luminance = 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]
    return "#0b0b0b" if luminance > 0.42 else "#ffffff"


def _diverging(t: float) -> str:
    """t in [0,1] -> warm..grey..cool. Neutral grey at the midpoint, never a hue."""
    from report.theme import DIVERGING_COOL, DIVERGING_WARM
    t = min(max(t, 0.0), 1.0)
    if abs(t - 0.5) < 0.04:
        return "var(--mid)"
    if t < 0.5:
        arm = DIVERGING_WARM[::-1]
        idx = int((0.5 - t) / 0.5 * (len(arm) - 1))
        return arm[::-1][min(idx, len(arm) - 1)]
    idx = int((t - 0.5) / 0.5 * (len(DIVERGING_COOL) - 1))
    return DIVERGING_COOL[min(idx, len(DIVERGING_COOL) - 1)]


def _sequential(t: float) -> str:
    from report.theme import SEQUENTIAL
    t = min(max(t, 0.0), 1.0)
    return SEQUENTIAL[min(int(t * (len(SEQUENTIAL) - 1)), len(SEQUENTIAL) - 1)]


def scatter(points: list[tuple[float, float, str]], *, height: int = 420,
            x_fmt=fmt_pct, y_fmt=fmt_pct, x_title: str = "", y_title: str = "",
            label: str = "") -> str:
    """Labelled scatter. Identity is carried by the label, never by hue alone."""
    f = Frame(height, left=72, right=40, top=22, bottom=54)
    xs = [p[0] for p in points if math.isfinite(p[0])]
    ys = [p[1] for p in points if math.isfinite(p[1])]
    if not xs or not ys:
        return f'{_open(height, label)}</svg>'
    xlo, xhi = min(xs), max(xs)
    ylo, yhi = min(ys), max(ys)
    xpad, ypad = (xhi - xlo) * 0.16 or 0.01, (yhi - ylo) * 0.16 or 0.01
    xlo, xhi, ylo, yhi = xlo - xpad, xhi + xpad, min(ylo - ypad, 0), yhi + ypad
    parts = [_open(height, label), _grid(f, nice_ticks(ylo, yhi, 5), ylo, yhi, y_fmt)]
    for tick in nice_ticks(xlo, xhi, 5):
        x = f.sx(tick, xlo, xhi)
        if not (f.x0 - 1 <= x <= f.x1 + 1):
            continue
        parts.append(f'<line class="grid" x1="{x:.1f}" x2="{x:.1f}" y1="{f.y0}" y2="{f.y1}"/>')
        parts.append(f'<text class="tick" x="{x:.1f}" y="{f.y1 + 22}" '
                     f'text-anchor="middle">{esc(x_fmt(tick))}</text>')
    if ylo < 0 < yhi:
        y = f.sy(0, ylo, yhi)
        parts.append(f'<line class="axis" x1="{f.x0}" x2="{f.x1}" y1="{y:.1f}" y2="{y:.1f}"/>')
    for px, py, name in points:
        if not (math.isfinite(px) and math.isfinite(py)):
            continue
        cx, cy = f.sx(px, xlo, xhi), f.sy(py, ylo, yhi)
        parts.append(f'<g class="mark"><title>{esc(name)}: {esc(x_fmt(px))} risk, '
                     f'{esc(y_fmt(py))} return</title>'
                     f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="7" fill="var(--s1)" '
                     f'stroke="var(--surface)" stroke-width="2"/></g>')
        anchor = "end" if cx > f.x1 - 90 else "start"
        dx = -12 if anchor == "end" else 12
        parts.append(f'<text class="point-label" x="{cx + dx:.1f}" y="{cy + 4:.1f}" '
                     f'text-anchor="{anchor}">{esc(name)}</text>')
    parts.append(f'<text class="axis-title" x="{(f.x0 + f.x1) / 2:.1f}" y="{f.height - 12}" '
                 f'text-anchor="middle">{esc(x_title)}</text>')
    parts.append(f'<text class="axis-title" transform="translate(16,{(f.y0 + f.y1) / 2:.1f}) '
                 f'rotate(-90)" text-anchor="middle">{esc(y_title)}</text>')
    parts.append("</svg>")
    return "".join(parts)


def histogram(values: pd.Series, markers: list[tuple[str, float, str]], *,
              height: int = 360, bins: int = 70, label: str = "") -> str:
    """Return distribution with VaR/CVaR cut lines drawn where they actually fall."""
    clean = values.dropna().astype(float)
    f = Frame(height, left=62, right=28, top=44, bottom=46)
    if clean.empty:
        return f'{_open(height, label)}</svg>'
    counts, edges = np.histogram(clean, bins=bins)
    lo, hi = float(edges[0]), float(edges[-1])
    top = float(counts.max()) * 1.1
    parts = [_open(height, label), _grid(f, nice_ticks(0, top, 4), 0, top,
                                         lambda v: f"{int(v)}")]
    base = f.sy(0, 0, top)
    for i, count in enumerate(counts):
        x0, x1 = f.sx(edges[i], lo, hi), f.sx(edges[i + 1], lo, hi)
        y = f.sy(count, 0, top)
        centre = (edges[i] + edges[i + 1]) / 2
        colour = "var(--s1)" if centre >= 0 else "var(--down)"
        parts.append(f'<g class="mark"><title>{fmt_pct(edges[i])} to {fmt_pct(edges[i+1])}: '
                     f'{int(count)} days</title>'
                     f'<rect x="{x0 + 1:.1f}" y="{y:.1f}" width="{max(x1 - x0 - 2, 1):.1f}" '
                     f'height="{max(base - y, 0):.1f}" rx="2" fill="{colour}" '
                     f'opacity="0.85"/></g>')
    for i, (name, value, colour) in enumerate(markers):
        if not math.isfinite(value) or not (lo <= value <= hi):
            continue
        x = f.sx(value, lo, hi)
        parts.append(f'<line class="marker" x1="{x:.1f}" x2="{x:.1f}" y1="{f.y0}" y2="{base:.1f}" '
                     f'stroke="{colour}"/>')
        parts.append(f'<text class="marker-label" x="{x:.1f}" y="{f.y0 - 22 + i * 16:.1f}" '
                     f'text-anchor="middle" fill="{colour}">{esc(name)} {fmt_pct(value)}</text>')
    for tick in nice_ticks(lo, hi, 7):
        x = f.sx(tick, lo, hi)
        if f.x0 - 1 <= x <= f.x1 + 1:
            parts.append(f'<text class="tick" x="{x:.1f}" y="{f.y1 + 22}" '
                         f'text-anchor="middle">{fmt_pct(tick, 0)}</text>')
    parts.append(f'<line class="axis" x1="{f.x0}" x2="{f.x1}" y1="{base:.1f}" y2="{base:.1f}"/>')
    parts.append("</svg>")
    return "".join(parts)


def small_multiples(panels: dict[str, pd.Series], *, columns: int = 4,
                    panel_height: int = 132, value_fmt=fmt_pct, label: str = "",
                    slot: int = 8) -> str:
    """A grid of one-series area panels -- same y-scale, so panels are comparable."""
    names = list(panels)
    rows = math.ceil(len(names) / columns)
    pad_x, pad_y, top = 14, 34, 12
    cell_w = (W - pad_x * (columns + 1)) / columns
    height = top + rows * (panel_height + pad_y)
    everything = pd.concat(panels.values())
    lo = float(everything.min()) if len(everything) else -0.1
    lo = min(lo, 0.0) * 1.06
    parts = [_open(int(height), label)]
    for i, name in enumerate(names):
        r, c = divmod(i, columns)
        ox = pad_x + c * (cell_w + pad_x)
        oy = top + r * (panel_height + pad_y) + 18
        series = panels[name].dropna()
        parts.append(f'<text class="panel-title" x="{ox:.1f}" y="{oy - 6:.1f}">{esc(name)}</text>')
        parts.append(f'<line class="axis" x1="{ox:.1f}" x2="{ox + cell_w:.1f}" '
                     f'y1="{oy:.1f}" y2="{oy:.1f}"/>')
        if series.empty:
            continue
        n = len(series) - 1
        pts = []
        for k, value in enumerate(series.to_numpy()):
            x = ox + (k / n if n else 0.5) * cell_w
            y = oy + min(max(value / lo if lo else 0, 0), 1) * panel_height
            pts.append(f"{x:.1f},{y:.1f}")
        worst = float(series.min())
        parts.append(f'<path class="area" style="--c:var(--s{slot})" '
                     f'd="M {ox:.1f},{oy:.1f} L {" L ".join(pts)} L {ox + cell_w:.1f},{oy:.1f} Z"/>')
        parts.append(f'<polyline class="line" style="--c:var(--s{slot})" points="{" ".join(pts)}"/>')
        parts.append(f'<text class="panel-value" x="{ox + cell_w:.1f}" y="{oy - 6:.1f}" '
                     f'text-anchor="end">{esc(value_fmt(worst))}</text>')
    parts.append("</svg>")
    return "".join(parts)
