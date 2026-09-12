#!/usr/bin/env python3
"""OG card template + chart primitives.

House style is lifted from site/presentation.html: paper #F3F4F2, ink #171A18,
accent #A32B3C for the non-resident series, #8A918B for baselines; Newsreader
for display, Public Sans for body, IBM Plex Mono for figures.

Two deliberate departures from the deck:
  * One fixed light ground. An OG card is a static PNG — there is no dark mode
    to respond to, and half the timelines showing it are dark, so the card has
    to carry its own background.
  * Everything is scaled up. A 1200x630 card is shown at roughly 500px wide in
    a timeline, so type that reads fine on the deck turns to grey mush here.
    One large figure and one clear chart, nothing else.
"""
from html import escape as esc

W, H = 1200, 630

PAPER = "#F3F4F2"
PANEL = "#FFFFFF"
INK = "#171A18"
INK2 = "#4B524C"
INK3 = "#7E857F"
RULE = "#DBDED9"
RULE2 = "#C6CAC4"
NRA = "#A32B3C"
BASE = "#8A918B"
MUTED = "#B9BEB9"
FILL = "rgba(163,43,60,.10)"
SERIES = ["#A32B3C", "#0891B2", "#A8761A", "#4C5FC7", "#9C5A2E"]


# --------------------------------------------------------------------------
# charts (hand-rolled SVG, same approach as the deck)
# --------------------------------------------------------------------------

def count_axis(peak, divisions=4):
    """Pick a top-of-axis whose gridlines are all round numbers.

    Fitting the axis to the data gives ticks like 62.5 and 187.5, which read as
    machine output rather than as a considered chart. Instead we choose a round
    step (1/2/2.5/5 x 10^k) big enough that `divisions` of it clear the peak.
    """
    import math
    if peak <= 0:
        return divisions, list(range(divisions + 1))
    raw = peak / divisions
    mag = 10 ** math.floor(math.log10(raw))
    for m in (1, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10):
        step = m * mag
        if step * divisions >= peak:
            break
    if step == int(step):
        step = int(step)
    return step * divisions, [step * i for i in range(divisions + 1)]


def _short(v):
    """Axis labels: 1,037,165 becomes 1M — a card has no room for the digits."""
    v = float(v)
    for div, suf in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(v) >= div:
            n = v / div
            return (f"{n:.0f}" if abs(n - round(n)) < 0.05 else f"{n:.1f}") + suf
    return _fmt(v)


def _fmt(v):
    if isinstance(v, float) and abs(v - round(v)) > 1e-9:
        return f"{v:,.1f}"
    return f"{round(v):,}"


# Axis ladders chosen so every gridline lands on a round number — a tick
# reading "56.2%" is a tell that the axis was fitted to the data, not chosen.
PCT_LADDER = [(12, 12, [0, 3, 6, 9, 12]), (25, 25, [0, 5, 10, 15, 20, 25]),
              (36, 40, [0, 10, 20, 30, 40]), (54, 60, [0, 15, 30, 45, 60]),
              (72, 80, [0, 20, 40, 60, 80]), (200, 100, [0, 25, 50, 75, 100])]


def pct_axis(vmax):
    for cap, top, ticks in PCT_LADDER:
        if vmax <= cap:
            return top, ticks
    return 100, [0, 25, 50, 75, 100]


def line_chart(series, years=None, pct=True, ymax=None, ymin=0, w=620, h=300,
               xstep=None, ticks=None, aria=""):
    """series: [{'points': {year: value}, 'color', 'tip', 'dash', 'width'}]"""
    pad = {"t": 16, "r": 84, "b": 34, "l": 54 if pct else 62}
    xs = years or sorted({int(y) for s in series for y in s["points"]})
    if not xs:
        return ""
    peak = max(v for s in series for v in s["points"].values())
    if pct and ticks is None:
        auto_max, ticks = pct_axis(peak)
        vmax = ymax or auto_max
        if ymax and ymax != auto_max:
            _, ticks = pct_axis(ymax)
            vmax = ymax
    elif ticks is None:
        vmax, ticks = count_axis(peak)
        if ymax:
            vmax, ticks = count_axis(ymax)
    else:
        vmax = ymax or peak
    n = max(1, len(xs) - 1)

    def X(y):
        return pad["l"] + xs.index(int(y)) * (w - pad["l"] - pad["r"]) / n

    def Y(v):
        return pad["t"] + (1 - (v - ymin) / (vmax - ymin)) * (h - pad["t"] - pad["b"])

    if ticks is None:
        ticks = [ymin + (vmax - ymin) * i / 4 for i in range(5)]
    o = [f'<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" aria-label="{esc(aria)}">']
    for t in ticks:
        o.append(f'<line x1="{pad["l"]}" x2="{w-pad["r"]}" y1="{Y(t):.1f}" y2="{Y(t):.1f}" stroke="{RULE}" stroke-width="1"/>')
        lab = (_fmt(t) + "%") if pct else _short(t)
        o.append(f'<text class="ax" x="{pad["l"]-10}" y="{Y(t)+5.5:.1f}" text-anchor="end">{lab}</text>')
    step = xstep or max(1, round(len(xs) / 5))
    for i, y in enumerate(xs):
        if i % step == 0 or i == len(xs) - 1:
            o.append(f'<text class="ax" x="{X(y):.1f}" y="{h-pad["b"]+22:.1f}" text-anchor="middle">{str(y)[2:]}</text>')
    for s in series:
        pts = [(X(y), Y(s["points"][y])) for y in xs if s["points"].get(y) is not None]
        if not pts:
            continue
        if s.get("area"):
            d = (f'M{pts[0][0]:.1f},{Y(ymin):.1f} '
                 + " ".join(f"L{x:.1f},{y:.1f}" for x, y in pts)
                 + f' L{pts[-1][0]:.1f},{Y(ymin):.1f}Z')
            o.append(f'<path d="{d}" fill="{s["area"]}"/>')
        d = "M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        dash = f' stroke-dasharray="{s["dash"]}"' if s.get("dash") else ""
        o.append(f'<path d="{d}" fill="none" stroke="{s["color"]}" stroke-width="{s.get("width",3.2)}"'
                 f' stroke-linejoin="round" stroke-linecap="round"{dash}/>')
        lx, ly = pts[-1]
        o.append(f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="5.5" fill="{s["color"]}" stroke="{PANEL}" stroke-width="2.5"/>')
        if s.get("tip"):
            o.append(f'<text class="dl" x="{lx+12:.1f}" y="{ly+6:.1f}" fill="{s["color"]}">{esc(s["tip"])}</text>')
    o.append("</svg>")
    return "".join(o)


def bar_chart(points, color=NRA, pct=False, w=620, h=300, ymax=None, xstep=None,
              aria=""):
    pad = {"t": 16, "r": 18, "b": 34, "l": 66}
    xs = sorted(points)
    if not xs:
        return ""
    peak = ymax or max(points.values())
    if pct:
        vmax, ticks = pct_axis(peak)
    else:
        vmax, ticks = count_axis(peak)
    bw = (w - pad["l"] - pad["r"]) / len(xs)

    def Y(v):
        return pad["t"] + (1 - v / vmax) * (h - pad["t"] - pad["b"])

    o = [f'<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" aria-label="{esc(aria)}">']
    for v in ticks:
        o.append(f'<line x1="{pad["l"]}" x2="{w-pad["r"]}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" stroke="{RULE}" stroke-width="1"/>')
        o.append(f'<text class="ax" x="{pad["l"]-10}" y="{Y(v)+5.5:.1f}" text-anchor="end">{_short(v)}{"%" if pct else ""}</text>')
    step = xstep or max(1, round(len(xs) / 5))
    for i, x in enumerate(xs):
        px = pad["l"] + i * bw + 2.5
        o.append(f'<rect x="{px:.1f}" y="{Y(points[x]):.1f}" width="{bw-5:.1f}"'
                 f' height="{max(1.5, Y(0)-Y(points[x])):.1f}" rx="3" fill="{color}"/>')
        if i % step == 0 or i == len(xs) - 1:
            lab = str(x)[2:] if str(x).isdigit() and len(str(x)) == 4 else str(x)
            o.append(f'<text class="ax" x="{px+(bw-5)/2:.1f}" y="{h-pad["b"]+22:.1f}" text-anchor="middle">{esc(lab)}</text>')
    o.append("</svg>")
    return "".join(o)


def hbar_chart(rows, color=NRA, unit="", w=620, h=300, aria=""):
    """rows: [(label, value)] — the fallback when a page has no time series."""
    if not rows:
        return ""
    rows = rows[:5]
    vmax = max(v for _, v in rows) or 1
    lw = 228
    gap = 14
    bh = (h - gap * (len(rows) - 1)) / len(rows)
    o = [f'<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" aria-label="{esc(aria)}">']
    for i, (lab, val) in enumerate(rows):
        y = i * (bh + gap)
        bl = (w - lw - 108) * val / vmax
        o.append(f'<text class="hb" x="0" y="{y+bh/2+6:.1f}">{esc(lab[:26])}</text>')
        o.append(f'<rect x="{lw}" y="{y+bh/2-13:.1f}" width="{max(3,bl):.1f}" height="26" rx="3" fill="{color}"/>')
        o.append(f'<text class="hv" x="{lw+max(3,bl)+12:.1f}" y="{y+bh/2+7:.1f}">{_fmt(val)}{esc(unit)}</text>')
    o.append("</svg>")
    return "".join(o)


# --------------------------------------------------------------------------
# card
# --------------------------------------------------------------------------

CSS = """
*{box-sizing:border-box;margin:0;padding:0;}
html,body{width:%(W)spx;height:%(H)spx;overflow:hidden;}
body{background:%(PAPER)s;color:%(INK)s;
  font-family:'Public Sans',-apple-system,'Helvetica Neue',sans-serif;
  -webkit-font-smoothing:antialiased;text-rendering:geometricPrecision;}
.card{width:%(W)spx;height:%(H)spx;padding:44px 56px 34px;display:flex;
  flex-direction:column;position:relative;}
.card:before{content:'';position:absolute;left:0;top:0;width:100%%;height:7px;
  background:%(NRA)s;}
.eyebrow{display:flex;align-items:baseline;gap:16px;
  font-family:'IBM Plex Mono',ui-monospace,monospace;font-size:15px;
  letter-spacing:.14em;text-transform:uppercase;color:%(INK3)s;white-space:nowrap;}
.eyebrow .tag{color:%(NRA)s;}
.eyebrow .sep{color:%(RULE2)s;}
.body{flex:1;display:grid;grid-template-columns:432px minmax(0,1fr);
  gap:44px;align-items:center;min-height:0;padding:18px 0 6px;}
.left{display:flex;flex-direction:column;gap:20px;min-width:0;}
h1{font-family:'Newsreader',Georgia,serif;font-weight:500;font-size:44px;
  line-height:1.08;letter-spacing:-.019em;max-width:15ch;}
h1.sm{font-size:37px;}
h1.xs{font-size:32px;line-height:1.12;}
.hero{font-family:'IBM Plex Mono',monospace;font-variant-numeric:tabular-nums;
  font-size:82px;line-height:.9;letter-spacing:-.045em;color:%(NRA)s;
  font-weight:500;white-space:nowrap;}
.hero.sm{font-size:64px;}
.hero.xs{font-size:52px;}
.hero .u{font-size:.44em;color:%(INK3)s;letter-spacing:0;margin-left:.08em;}
.herolab{font-size:19px;line-height:1.32;color:%(INK2)s;max-width:24ch;}
.rulehero{border-top:2px solid %(INK)s;padding-top:16px;}
.stats{display:flex;gap:34px;flex-wrap:wrap;}
.stat .n{font-family:'IBM Plex Mono',monospace;font-variant-numeric:tabular-nums;
  font-size:31px;line-height:1;letter-spacing:-.03em;}
.stat .n.acc{color:%(NRA)s;}
.stat .l{font-size:14px;color:%(INK3)s;margin-top:8px;max-width:16ch;line-height:1.3;}
.figure{background:%(PANEL)s;border:1px solid %(RULE)s;border-radius:5px;
  padding:20px 24px 16px;box-shadow:0 1px 2px rgba(23,26,24,.05),0 10px 28px rgba(23,26,24,.07);}
.figure h3{font-size:19px;font-weight:600;letter-spacing:-.006em;line-height:1.25;}
.figure .sub{font-size:14.5px;color:%(INK3)s;margin-top:4px;line-height:1.3;}
.figure svg{display:block;width:100%%;height:auto;overflow:visible;margin-top:12px;}
.ax{font-family:'IBM Plex Mono',monospace;font-size:14px;fill:%(INK3)s;}
.dl{font-family:'IBM Plex Mono',monospace;font-size:17px;font-weight:500;}
.hb{font-family:'Public Sans',sans-serif;font-size:16.5px;fill:%(INK2)s;}
.hv{font-family:'IBM Plex Mono',monospace;font-size:17px;font-weight:500;fill:%(INK)s;}
.legend{display:flex;gap:20px;flex-wrap:wrap;font-size:14.5px;color:%(INK2)s;
  margin-top:12px;}
.legend span{display:inline-flex;align-items:center;gap:8px;}
.legend i{width:18px;height:4px;border-radius:2px;display:inline-block;}
.foot{display:flex;align-items:center;gap:18px;border-top:1px solid %(RULE)s;
  padding-top:14px;font-size:14px;color:%(INK3)s;}
.foot .dom{font-family:'IBM Plex Mono',monospace;letter-spacing:.06em;
  color:%(INK2)s;white-space:nowrap;}
.foot .src{margin-left:auto;text-align:right;line-height:1.3;max-width:62ch;}
""" % dict(W=W, H=H, PAPER=PAPER, INK=INK, INK2=INK2, INK3=INK3, RULE=RULE,
           RULE2=RULE2, NRA=NRA, PANEL=PANEL)


def _hero_class(text):
    n = len(text)
    return "" if n <= 8 else ("sm" if n <= 12 else "xs")


def _h1_class(text):
    n = len(text)
    return "" if n <= 44 else ("sm" if n <= 66 else "xs")


def render(spec, font_css):
    """spec keys: eyebrow, tag, headline, hero{value,unit,label}, stats[],
    figure{title,sub,svg,legend[]}, footer."""
    hero = spec.get("hero") or {}
    left = []
    left.append(f'<h1 class="{_h1_class(spec["headline"])}">{esc(spec["headline"])}</h1>')
    if hero.get("value"):
        unit = f'<span class="u">{esc(hero["unit"])}</span>' if hero.get("unit") else ""
        left.append(
            '<div class="rulehero">'
            f'<div class="hero {_hero_class(str(hero["value"]))}">{esc(str(hero["value"]))}{unit}</div>'
            f'<div class="herolab" style="margin-top:14px">{esc(hero.get("label",""))}</div>'
            "</div>")
    if spec.get("stats"):
        cells = "".join(
            f'<div class="stat"><div class="n{" acc" if s.get("acc") else ""}">{esc(str(s["n"]))}</div>'
            f'<div class="l">{esc(s["l"])}</div></div>' for s in spec["stats"])
        left.append(f'<div class="stats">{cells}</div>')

    fig = spec.get("figure") or {}
    right = ""
    if fig.get("svg"):
        legend = ""
        if fig.get("legend"):
            legend = '<div class="legend">' + "".join(
                f'<span><i style="background:{c}"></i>{esc(t)}</span>'
                for t, c in fig["legend"]) + "</div>"
        right = (f'<div class="figure"><h3>{esc(fig.get("title",""))}</h3>'
                 f'<p class="sub">{esc(fig.get("sub",""))}</p>{fig["svg"]}{legend}</div>')

    eyebrow = f'<span>{esc(spec.get("eyebrow",""))}</span>'
    if spec.get("tag"):
        eyebrow += f'<span class="sep">/</span><span class="tag">{esc(spec["tag"])}</span>'

    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<style>{font_css}</style><style>{CSS}</style></head><body>
<div class="card">
  <div class="eyebrow">{eyebrow}</div>
  <div class="body"><div class="left">{''.join(left)}</div><div>{right}</div></div>
  <div class="foot"><span class="dom">phd-demographics.andy-barr.com</span>
    <span class="src">{esc(spec.get("footer",""))}</span></div>
</div></body></html>"""
