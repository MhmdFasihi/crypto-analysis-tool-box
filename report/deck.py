"""Reveal.js deck shell: CSS tokens, layout components, HTML assembly."""
from __future__ import annotations

import html
from pathlib import Path

VENDOR = Path(__file__).resolve().parent / "vendor" / "reveal" / "dist"

CSS = """
:root {
  --surface:#fcfcfb; --plane:#f9f9f7; --ink:#0b0b0b; --ink-2:#52514e; --muted:#898781;
  --grid:#e1e0d9; --axis:#c3c2b7; --mid:#f0efec; --on-strong:#ffffff; --rule:rgba(11,11,11,.10);
  --s1:#2a78d6; --s2:#eb6834; --s3:#1baf7a; --s4:#eda100;
  --s5:#e87ba4; --s6:#008300; --s7:#4a3aa7; --s8:#e34948;
  --up:#2a78d6; --down:#d03b3b; --good:#0ca30c; --warn:#fab219; --crit:#d03b3b;
}
.reveal-viewport[data-mode="dark"] {
  --surface:#1a1a19; --plane:#0d0d0d; --ink:#ffffff; --ink-2:#c3c2b7; --muted:#898781;
  --grid:#2c2c2a; --axis:#383835; --mid:#383835; --on-strong:#0b0b0b; --rule:rgba(255,255,255,.10);
  --s1:#3987e5; --s2:#d95926; --s3:#199e70; --s4:#c98500;
  --s5:#d55181; --s6:#008300; --s7:#9085e9; --s8:#e66767;
  --up:#3987e5; --down:#e66767;
}
.reveal-viewport { background:var(--plane); transition:background .2s; }
.reveal { font-family:system-ui,-apple-system,"Segoe UI",sans-serif; color:var(--ink);
          font-size:26px; font-weight:400; }
.reveal .slides { text-align:left; }
.reveal .slides section { height:100%; }
/* Reveal sets display:block inline on the current slide, so centring lives on a
   wrapper instead of on the section itself. */
.slide-body { display:flex; flex-direction:column; justify-content:center;
              height:100%; box-sizing:border-box; }
.reveal h1,.reveal h2,.reveal h3,.reveal h4 { font-family:inherit; color:var(--ink);
  text-transform:none; letter-spacing:-.015em; font-weight:600; margin:0 0 .4em; }
.reveal h1 { font-size:2.1em; } .reveal h2 { font-size:1.32em; }
.reveal h3 { font-size:1.02em; } .reveal h4 { font-size:.72em; color:var(--ink-2); font-weight:600; }
.reveal p, .reveal li { color:var(--ink-2); font-size:.68em; line-height:1.5; }
.reveal strong { color:var(--ink); font-weight:600; }
.reveal a { color:var(--s1); }
.reveal section img, .reveal section svg { border:0; box-shadow:none; background:transparent; }
.reveal .progress { color:var(--s1); height:3px; }
.reveal .controls { color:var(--muted); }
.reveal .slide-number { background:transparent; color:var(--muted); font-size:15px; }

.eyebrow { font-size:.5em; letter-spacing:.13em; text-transform:uppercase;
           color:var(--muted); font-weight:600; margin:0 0 .5em; }
.lede { font-size:.62em; color:var(--ink-2); max-width:52em; }
.footnote { font-size:.42em; color:var(--muted); line-height:1.5; margin-top:.9em; }
.rule { border:0; border-top:1px solid var(--rule); margin:.7em 0; }

/* charts */
.chart { width:100%; height:auto; display:block; overflow:visible; }
.chart .grid { stroke:var(--grid); stroke-width:1; }
.chart .axis { stroke:var(--axis); stroke-width:1; }
.chart .line { fill:none; stroke:var(--c,var(--s1)); stroke-width:2;
               stroke-linejoin:round; stroke-linecap:round; }
.chart .area { fill:var(--c,var(--s1)); opacity:.16; }
.chart .hit { fill:none; stroke:transparent; stroke-width:14; }
.chart .series { transition:opacity .12s; }
.chart:hover .series:not(:hover) { opacity:.22; }
.chart .series.dim { opacity:.3; }
.chart .tick { fill:var(--muted); font-size:14px; font-variant-numeric:tabular-nums; }
.chart .cat { fill:var(--ink-2); font-size:15px; }
.chart .value { fill:var(--ink); font-size:15px; font-weight:600;
                font-variant-numeric:tabular-nums; }
.chart .cell { font-size:14px; font-weight:600; font-variant-numeric:tabular-nums; }
.chart .end-label { font-size:15px; font-weight:600; font-variant-numeric:tabular-nums; }
.chart .point-label { fill:var(--ink); font-size:15px; font-weight:600; }
.chart .axis-title { fill:var(--muted); font-size:14px; }
.chart .marker { stroke-width:2; stroke-dasharray:none; }
.chart .marker-label { font-size:14px; font-weight:600; font-variant-numeric:tabular-nums; }
.chart .panel-title { fill:var(--ink); font-size:15px; font-weight:600; }
.chart .panel-value { fill:var(--down); font-size:14px; font-weight:600;
                      font-variant-numeric:tabular-nums; }
.chart .mark { cursor:default; }

/* tables */
table.data { width:100%; border-collapse:collapse; font-size:.44em;
             font-variant-numeric:tabular-nums; color:var(--ink-2); }
table.data th { text-align:right; font-weight:600; color:var(--muted); padding:.5em .55em;
                border-bottom:1px solid var(--axis); white-space:nowrap; font-size:.95em; }
table.data th:first-child, table.data td:first-child { text-align:left; color:var(--ink);
                font-weight:600; white-space:nowrap; }
table.data td { text-align:right; padding:.42em .55em; border-bottom:1px solid var(--grid); }
table.data tbody tr:hover { background:var(--mid); }
table.data td.pos { color:var(--up); } table.data td.neg { color:var(--down); }
table.data td.strong { color:var(--ink); font-weight:600; }
.table-wrap { overflow-x:auto; }

/* tiles */
.tiles { display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin:.5em 0; }
.tiles.five { grid-template-columns:repeat(5,1fr); }
.tile { background:var(--surface); border:1px solid var(--rule); border-radius:10px;
        padding:14px 16px; }
.tile .k { font-size:.4em; color:var(--muted); text-transform:uppercase;
           letter-spacing:.09em; font-weight:600; }
.tile .v { font-size:.86em; font-weight:600; color:var(--ink); margin-top:.15em; }
.tile .s { font-size:.38em; color:var(--muted); margin-top:.2em; }
.tile .v.pos { color:var(--up); } .tile .v.neg { color:var(--down); }
.hero { font-size:2.6em; font-weight:600; color:var(--ink); line-height:1; }

.cols { display:grid; grid-template-columns:1fr 1fr; gap:26px; align-items:start; }
.cols.wide-left { grid-template-columns:1.55fr 1fr; }
.cols.wide-right { grid-template-columns:1fr 1.55fr; }
.card { background:var(--surface); border:1px solid var(--rule); border-radius:10px;
        padding:16px 18px; }
.legend { display:flex; flex-wrap:wrap; gap:8px 18px; margin:.4em 0 .2em; }
.legend span { font-size:.42em; color:var(--ink-2); display:inline-flex; align-items:center;
               gap:6px; }
.legend i { width:11px; height:11px; border-radius:3px; display:inline-block; }
.badge { display:inline-block; font-size:.36em; font-weight:600; padding:.25em .6em;
         border-radius:999px; border:1px solid var(--rule); color:var(--ink-2); }
.badge.good { color:var(--good); } .badge.crit { color:var(--crit); }

#theme-toggle { position:fixed; top:14px; right:16px; z-index:60; font:inherit;
  font-size:13px; padding:6px 12px; border-radius:999px; cursor:pointer;
  background:var(--surface); color:var(--ink-2); border:1px solid var(--rule); }
@media print { #theme-toggle { display:none; } }
"""

SCRIPT = """
const viewport = document.querySelector('.reveal-viewport') || document.body;
const stored = (() => { try { return localStorage.getItem('mkt-report-theme'); }
                        catch (e) { return null; } })();
const system = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
let mode = stored || system;
const toggle = document.getElementById('theme-toggle');
function apply() {
  viewport.dataset.mode = mode;
  toggle.textContent = mode === 'dark' ? 'Light mode' : 'Dark mode';
  try { localStorage.setItem('mkt-report-theme', mode); } catch (e) {}
}
toggle.addEventListener('click', () => { mode = mode === 'dark' ? 'light' : 'dark'; apply(); });
apply();
Reveal.initialize({ width: 1360, height: 820, margin: 0.045, minScale: 0.2, maxScale: 1.6,
  hash: true, slideNumber: 'c/t', transition: 'fade', transitionSpeed: 'fast',
  controlsTutorial: false, pdfSeparateFragments: false });
"""


def esc(text) -> str:
    return html.escape(str(text))


def slide(body: str, *, notes: str = "") -> str:
    note = f'<aside class="notes">{esc(notes)}</aside>' if notes else ""
    return f'<section><div class="slide-body">{body}</div>{note}</section>' 


def stack(slides: list[str]) -> str:
    """A vertical stack of slides (down-arrow navigation)."""
    return "<section>" + "".join(slides) + "</section>"


def tile(key: str, value: str, sub: str = "", tone: str = "") -> str:
    tone = f" {tone}" if tone else ""
    sub = f'<div class="s">{esc(sub)}</div>' if sub else ""
    return (f'<div class="tile"><div class="k">{esc(key)}</div>'
            f'<div class="v{tone}">{esc(value)}</div>{sub}</div>')


def tiles(items: list[str], five: bool = False) -> str:
    return f'<div class="tiles{" five" if five else ""}">{"".join(items)}</div>'


def legend(entries: list[tuple[str, str]]) -> str:
    body = "".join(f'<span><i style="background:{colour}"></i>{esc(name)}</span>'
                   for name, colour in entries)
    return f'<div class="legend">{body}</div>'


def table(headers: list[str], rows: list[list[str]], classes: list[list[str]] | None = None) -> str:
    head = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = []
    for i, row in enumerate(rows):
        cells = []
        for j, cell in enumerate(row):
            cls = classes[i][j] if classes and i < len(classes) and j < len(classes[i]) else ""
            cells.append(f'<td class="{cls}">{esc(cell)}</td>' if cls else f"<td>{esc(cell)}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    return (f'<div class="table-wrap"><table class="data"><thead><tr>{head}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div>')


def build_html(title: str, slides: list[str], description: str) -> str:
    reveal_css = (VENDOR / "reset.css").read_text() + (VENDOR / "reveal.css").read_text()
    reveal_js = (VENDOR / "reveal.js").read_text()
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<style>{reveal_css}</style>
<style>{CSS}</style>
</head>
<body>
<button id="theme-toggle" type="button">Dark mode</button>
<div class="reveal"><div class="slides">
{"".join(slides)}
</div></div>
<script>{reveal_js}</script>
<script>{SCRIPT}</script>
</body>
</html>
"""
