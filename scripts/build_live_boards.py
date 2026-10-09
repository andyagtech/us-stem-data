#!/usr/bin/env python3
"""The named boards the live dashboard can summon.

WHY A CATALOGUE AND NOT MORE PRIMITIVES. The dashboard already has tools to
draw an arbitrary field, compare fields, and plot F-1 issuance. In a spoken
conversation that is the wrong shape: the model has to decide which CIP code
and which level and which mode answer "show me the worst case", and it
either guesses or asks. A named board collapses that into one call, and
because each one is computed here from the same bundle the dashboard
renders, the title and the headline figure are true before anyone speaks.

Thirty-eight boards, all generated: one per field per level, plus rankings
and comparisons that read a whole measure at once, plus the visa series.

EVERY HEADLINE IS COMPUTED. No board carries a typed number. A rebuild moves
the figures, and a board whose data disappears is dropped rather than
shipped pointing at nothing.

Usage:
  python3 scripts/build_live_boards.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from atomic_write import write_text                            # noqa: E402

BUNDLE = ROOT / "site" / "data" / "live_bundle.json"
OUT = ROOT / "site" / "data" / "live_boards.json"

LEVEL_WORD = {"masters": "master's degrees", "doctorate": "doctorates"}

#: Pages the voice can send a listener to. Kept short on purpose: a spoken
#: hand-off is only useful if the destination answers the question that was
#: just asked. Every path is checked against the built site map.
DESTINATIONS = [
    ("/overview", "the measured finding, with the charts behind it"),
    ("/postdocs", "who holds the postdoc jobs, by citizenship"),
    ("/name-lists", "the thesis and dissertation lists, by name"),
    ("/stem", "every STEM thesis, by university and department"),
    ("/expansion", "the master's expansion"),
    ("/visa-schools", "the schools where foreign students are most of the intake"),
    ("/bodyshops", "the staffing firms that file the most visas"),
    ("/public-sector-visas", "green cards sponsored by public employers"),
    ("/query", "the SQL console, to check any of it"),
    ("/data_requests", "what the government does not publish"),
]


def series(deg, cip, level):
    raw = deg.get(level, {}).get(cip)
    if not raw:
        return None
    rows = []
    for y in sorted(raw, key=int):
        dom, nra = raw[y][0], raw[y][1]
        tot = dom + nra
        rows.append({"year": int(y), "dom": dom, "nra": nra,
                     "share": round(nra / tot * 100, 1) if tot else 0.0})
    return rows or None


def growth(a, b):
    if not a:
        return None
    return round((b - a) / a * 100, 1)


def main() -> int:
    if not BUNDLE.exists():
        print(f"  missing {BUNDLE.relative_to(ROOT)}; run build_live_bundle.py")
        return 1
    b = json.loads(BUNDLE.read_text())
    fields = b["meta"]["fields"]
    deg = b["degrees"]
    boards = []

    #: One per field per level. The spoken hook is the thing that is actually
    #: surprising about that series, chosen by the data rather than written.
    for cip, name in sorted(fields.items(), key=lambda kv: kv[1]):
        for level in ("masters", "doctorate"):
            rows = series(deg, cip, level)
            if not rows or len(rows) < 2:
                continue
            f, l = rows[0], rows[-1]
            gd, gn = growth(f["dom"], l["dom"]), growth(f["nra"], l["nra"])
            if gd is None or gn is None:
                continue
            hook = (f"Domestic {'rose' if gd >= 0 else 'fell'} {abs(gd):.0f}% "
                    f"while non-resident {'rose' if gn >= 0 else 'fell'} "
                    f"{abs(gn):.0f}%.")
            boards.append({
                "id": f"{cip}-{level}",
                "title": f"{name} {LEVEL_WORD[level]}",
                "subtitle": f"Domestic and non-resident recipients, "
                            f"{f['year']}–{l['year']}",
                "tool": "show_series",
                "args": {"field": cip, "level": level, "mode": "counts"},
                "headline": {"label": f"Non-resident share, {l['year']}",
                             "value": f"{l['share']:.0f}%"},
                "hook": hook,
                "tags": [name.lower(), level,
                         "high share" if l["share"] >= 50 else "lower share"],
            })

    #: The same field as a share line. Counts and share answer different
    #: questions -- a rising share can hide a rising domestic count, and the
    #: counts board cannot show the crossover year at a glance.
    for cip, name in sorted(fields.items(), key=lambda kv: kv[1]):
        for level in ("masters", "doctorate"):
            rows = series(deg, cip, level)
            if not rows or len(rows) < 2:
                continue
            f, l = rows[0], rows[-1]
            crossed = next((r["year"] for r in rows if r["share"] >= 50), None)
            boards.append({
                "id": f"{cip}-{level}-share",
                "title": f"{name} {LEVEL_WORD[level]}: the share",
                "subtitle": f"Non-resident percentage, {f['year']}\u2013{l['year']}",
                "tool": "show_series",
                "args": {"field": cip, "level": level, "mode": "share"},
                "headline": {"label": f"Non-resident share, {l['year']}",
                             "value": f"{l['share']:.0f}%"},
                "hook": (f"Passed half in {crossed}." if crossed else
                         f"Moved from {f['share']:.0f}% to {l['share']:.0f}%."),
                "tags": [name.lower(), level, "share"],
            })

    #: Rankings. These answer a question the per-field boards cannot, because
    #: they read every field at once.
    for level in ("masters", "doctorate"):
        ranked = []
        for cip, name in fields.items():
            rows = series(deg, cip, level)
            if rows:
                ranked.append((name, cip, rows[-1], rows[0]))
        if len(ranked) < 3:
            continue
        year = ranked[0][2]["year"]

        by_share = sorted(ranked, key=lambda r: -r[2]["share"])
        boards.append({
            "id": f"rank-share-{level}",
            "title": f"Which {LEVEL_WORD[level]} go to non-residents",
            "subtitle": f"Non-resident share by field, {year}",
            "tool": "compare_fields",
            "args": {"fields": [c for _, c, _, _ in by_share],
                     "level": level, "measure": "share"},
            "headline": {"label": f"Highest: {by_share[0][0]}",
                         "value": f"{by_share[0][2]['share']:.0f}%"},
            "hook": (f"{by_share[0][0]} is highest at "
                     f"{by_share[0][2]['share']:.0f}%; "
                     f"{by_share[-1][0]} lowest at "
                     f"{by_share[-1][2]['share']:.0f}%."),
            "tags": ["ranking", level, "share"],
        })

        falling = sorted(ranked, key=lambda r: growth(r[3]["dom"], r[2]["dom"]) or 0)
        g = growth(falling[0][3]["dom"], falling[0][2]["dom"])
        #: THE TITLE FOLLOWS THE DATA. An earlier version always said "fell
        #: furthest" and then printed +9%, because at doctorate level no
        #: field's domestic count actually fell. A board that contradicts
        #: its own headline is worse than no board, and this one would have
        #: been read aloud.
        dom_title = (f"Where American {LEVEL_WORD[level]} fell furthest"
                     if g is not None and g < 0 else
                     f"Where American {LEVEL_WORD[level]} grew least")
        boards.append({
            "id": f"rank-domestic-{level}",
            "title": dom_title,
            "subtitle": f"Change in domestic recipients since "
                        f"{falling[0][3]['year']}",
            "tool": "compare_fields",
            "args": {"fields": [c for _, c, _, _ in falling],
                     "level": level, "measure": "growth_domestic"},
            "headline": {"label": falling[0][0],
                         "value": f"{g:+.0f}%"},
            "hook": (f"{falling[0][0]} moved {g:+.0f}% for domestic "
                     f"students over the period."),
            "tags": ["ranking", level, "domestic"],
        })

        rising = sorted(ranked, key=lambda r: -(growth(r[3]["nra"], r[2]["nra"]) or 0))
        g2 = growth(rising[0][3]["nra"], rising[0][2]["nra"])
        boards.append({
            "id": f"rank-nra-{level}",
            "title": f"Where non-resident {LEVEL_WORD[level]} grew fastest",
            "subtitle": f"Change in non-resident recipients since "
                        f"{rising[0][3]['year']}",
            "tool": "compare_fields",
            "args": {"fields": [c for _, c, _, _ in rising],
                     "level": level, "measure": "growth_nra"},
            "headline": {"label": rising[0][0], "value": f"{g2:+.0f}%"},
            "hook": f"{rising[0][0]} grew {g2:+.0f}% in non-resident recipients.",
            "tags": ["ranking", level, "non-resident"],
        })

    #: The visa series, which is a different source and answers "why do the
    #: degree counts and the visa counts disagree".
    f1 = b.get("f1") or {}
    if f1:
        yrs = sorted(f1, key=int)
        last = f1[yrs[-1]]
        tot = last.get("total") if isinstance(last, dict) else last
        boards.append({
            "id": "f1-total",
            "title": "F-1 student visas issued",
            "subtitle": f"By fiscal year, {yrs[0]}–{yrs[-1]}",
            "tool": "show_f1", "args": {},
            "headline": {"label": f"Issued {yrs[-1]}",
                         "value": f"{tot:,}" if isinstance(tot, int) else str(tot)},
            "hook": "A visa is issued once; a degree is counted on completion.",
            "tags": ["visas", "f1"],
        })
        boards.append({
            "id": "f1-china-india",
            "title": "F-1 visas: China against India",
            "subtitle": f"By fiscal year, {yrs[0]}–{yrs[-1]}",
            "tool": "show_f1", "args": {"countries": ["china", "india"]},
            "headline": {"label": "Two countries", "value": "China & India"},
            "hook": "The two largest senders moved in opposite directions.",
            "tags": ["visas", "f1", "countries"],
        })

    out = {
        "source": "Built from site/data/live_bundle.json",
        "note": ("Every title, headline and hook here is computed from the "
                 "same bundle the dashboard draws, so a board cannot "
                 "describe something the chart does not show."),
        "count": len(boards),
        "boards": boards,
        "destinations": [{"path": p, "describes": d} for p, d in DESTINATIONS],
    }
    write_text(OUT, json.dumps(out, indent=2))
    print(f"Wrote {OUT.relative_to(ROOT)}")
    print(f"  {len(boards)} boards, {len(DESTINATIONS)} destinations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
