#!/usr/bin/env python3
"""Non-resident share for one field at one institution, and the extremes.

WHY THIS EXISTS. Asked "which university awarded every industrial
engineering doctorate to non-residents", the assistant answered that no
such university exists. University of Houston awarded 28 of 28. The
figure is on the site and in the index this bundle already ships.

The existing level tool could not see it: it is scoped to a fixed set of
core-STEM CIP families and ranks at its own cohort floors, so a
28-degree programme in a family outside that set is invisible. Rather
than widen a tool that is correct about its own question, this answers
the other question -- any CIP code, any institution, no family list.

It computes the same thing the site's field_by_institution table does,
from the same index, so the assistant and the page cannot disagree.

ONE BASIS, ONE WINDOW. IPEDS recoded award levels in 2010 and the
transition years are carried under both bases, so summing across them
counts those years twice. This reads aw17 only, over 2015-2022, which
is the window the site publishes.
"""
from __future__ import annotations

from collections import defaultdict

try:
    from chat import data_store as ds
except Exception:                                              # noqa: BLE001
    import data_store as ds

BASIS = "aw17"
YEAR_LO, YEAR_HI = 2015, 2022
#: A share needs a denominator worth quoting. Twenty degrees over eight
#: years is the floor the site uses for the same table.
MIN_AWARDS = 20

_cache: dict | None = None


def _table() -> dict:
    """{(unitid, cip): [awards, nonresident]}, built once per container."""
    global _cache
    if _cache is None:
        acc: dict = defaultdict(lambda: [0, 0])
        for year, unitid, cip, basis, total, nra in ds.load_index():
            if basis != BASIS or not YEAR_LO <= year <= YEAR_HI:
                continue
            cell = acc[(unitid, cip)]
            cell[0] += total
            cell[1] += nra
        _cache = dict(acc)
    return _cache


def _row(unitid: str, cip: str, awards: int, nra: int) -> dict:
    names = ds.institutions()
    name, state = names.get(unitid, (f"UNITID {unitid}", ""))
    return {
        "institution": name,
        "state": state,
        "unitid": unitid,
        "cipcode": cip,
        "field": ds.cip_titles().get(cip, cip),
        "doctorates": awards,
        "nonresident": nra,
        "nonresident_share": round(nra / awards * 100, 1) if awards else None,
    }


def field_extremes(args: dict) -> dict:
    """Institutions with the highest non-resident share in a field."""
    q = (args.get("field") or "").strip().lower()
    cip_arg = (args.get("cipcode") or "").strip()
    try:
        limit = max(1, min(25, int(args.get("limit", 10))))
    except (TypeError, ValueError):
        limit = 10
    try:
        floor = max(5, int(args.get("min_doctorates", MIN_AWARDS)))
    except (TypeError, ValueError):
        floor = MIN_AWARDS

    titles = ds.cip_titles()
    if cip_arg:
        wanted = {c for c in titles if c == cip_arg or c.startswith(cip_arg)}
    elif q:
        wanted = {c for c, t in titles.items() if q in t.lower()}
    else:
        wanted = None

    if wanted is not None and not wanted:
        return {"error": f"No IPEDS field matches {args.get('field') or cip_arg!r}.",
                "hint": "Try a broader word: 'industrial', 'petroleum', 'computer'."}

    rows = []
    for (unitid, cip), (awards, nra) in _table().items():
        if wanted is not None and cip not in wanted:
            continue
        if awards < floor:
            continue
        rows.append(_row(unitid, cip, awards, nra))

    rows.sort(key=lambda r: (-(r["nonresident_share"] or 0), -r["doctorates"]))
    hundred = [r for r in rows if r["nonresident_share"] == 100]

    return {
        "source": (f"IPEDS Completions, award basis {BASIS}, doctorates "
                   f"pooled {YEAR_LO}-{YEAR_HI}"),
        "scope": ("Degrees CONFERRED, not people, and not a statement about "
                  "any individual's origin. A non-resident is a student on a "
                  "temporary visa as the institution reported them."),
        "matched_fields": sorted(titles[c] for c in wanted)[:12] if wanted else "all",
        "floor": f"{floor}+ doctorates over {YEAR_LO}-{YEAR_HI}",
        "qualifying": len(rows),
        "at_one_hundred_percent": len(hundred),
        "rows": rows[:limit],
        "caution": ("Always quote a share with its denominator, which is on "
                    "every row. Twenty-eight of twenty-eight and 280 of 280 "
                    "are the same percentage and not the same finding."),
    }


#: The same envelope every other extension uses:
#: {"type": "function", "function": {...}}. Declaring the bare function
#: object instead made tools.py raise KeyError('function') on import,
#: and an extension that raises is logged and skipped -- the assistant
#: would have come up without this tool and said nothing about it.
SCHEMAS = [{
    "type": "function",
    "function": {
        "name": "field_extremes",
        "description": (
            "Institutions ranked by the non-resident share of DOCTORATES in "
            "one field of study, from IPEDS field codes. Use this for any "
            "question of the form 'which university has the highest share in "
            "X', 'where did every doctorate go to a non-resident', or 'what "
            "is the share in X at Y'. Works for ANY field, including ones "
            "outside the core-STEM families that level_rankings covers -- "
            "industrial engineering, econometrics, petroleum and so on. Give "
            "either a word from the field name or a CIP code prefix."),
        "parameters": {
            "type": "object",
            "properties": {
                "field": {
                    "type": "string",
                    "description": ("A word from the IPEDS field title, e.g. "
                                    "'industrial', 'petroleum', "
                                    "'econometrics'.")},
                "cipcode": {
                    "type": "string",
                    "description": ("A CIP code or prefix, e.g. '14.3501' or "
                                    "'14.' for all engineering.")},
                "min_doctorates": {
                    "type": "integer",
                    "description": "Cohort floor, default 20."},
                "limit": {
                    "type": "integer",
                    "description": "Rows, default 10."},
            },
            "required": [],
        },
    },
}]

IMPL = {"field_extremes": field_extremes}
