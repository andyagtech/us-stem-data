"""Summary and institution tools: the figures the assistant could not reach.

    key_figures           the headline number from every finding, with limits
    compare_institutions  one row per institution, ranked, or rolled up by state

WHY THESE EXIST. The assistant ships a knowledge file per finding, so it could
describe the institution table or the wage comparison and then not give a
number from either: the datasets behind them are in the zip but no tool read
them. These two close that, and they are deliberately not a generic "open any
dataset" tool -- a tool that returns arbitrary JSON returns arbitrary JSON to
the model, limits stripped, and the limits are the part that must survive.

Same contract as ``tools.py``: schemas built with its ``_fn``, integers clamped
with ``_clamp``, every result carries a ``source`` the render tools copy
verbatim, and failures come back as ``{"error": ...}`` rather than raised.

EVERY RESULT CARRIES ITS LIMIT. Not as decoration: a share quoted without its
denominator, or the per-doctorate ratio quoted without what its denominator
covers, is a misreport. The fields are on the row and the caution is on the
result.
"""
from __future__ import annotations

import json
import os

try:                                              # package layout
    from . import data_store as ds
    from .tools import _clamp, _fn
except ImportError:                               # flat Lambda layout
    import data_store as ds
    from tools import _clamp, _fn

SRC_SUMMARY = ("Site summary of published findings (/data/summary.json); each "
               "figure names the dataset it came from")
SRC_INST = ("IPEDS Completions, Fall Enrollment and Institutional "
            "Characteristics; NSF HERD FY2024; NSF Federal Support Survey "
            "FY2023 (see /institutions.html)")

_summary = None
_inst = None


def _load(name):
    p = os.path.join(ds.DATA_DIR, name)
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def summary():
    global _summary
    if _summary is None:
        _summary = _load("summary.json") or {}
    return _summary


def institutions():
    global _inst
    if _inst is None:
        _inst = _load("institutions_compact.json") or {}
    return _inst


# ---------------------------------------------------------------------------
SCHEMAS = [
    _fn(
        "key_figures",
        "The headline figure from every finding on this site, in one call: the "
        "non-resident shares at both degree levels, graduate enrolment, the "
        "institution counts, the federal money, the wage comparison, the "
        "green-card route and the foreign-born share of the workforce. CALL "
        "THIS FIRST for any broad question -- what does this site find, what is "
        "the headline, is the share rising, how big is the effect -- rather "
        "than assembling an answer from several narrower tools. Every figure "
        "comes back with the dataset it was read from and the limit on how it "
        "may be read; quote the limit with the number, never the number alone. "
        "For anything conditional -- by year, state, institution or occupation "
        "-- use the dataset named on the figure instead.",
        {"keys": {"type": "array", "items": {"type": "string"},
                  "description": "Optional. Specific figure keys to return; "
                                 "omit for all of them."}},
    ),
    _fn(
        "compare_institutions",
        "The per-institution table: core-STEM master's and doctorates with "
        "their non-resident shares and how those shares changed since 2010-14, "
        "graduate enrolment, federal obligations and R&D, and published "
        "graduate tuition -- all on one row per institution, for 2,290 "
        "institutions on the federal unit identifier. Use it to compare two "
        "named institutions, to rank institutions on any of those measures, to "
        "look one up, or to roll the whole thing up to a state. This is the "
        "only tool that can put degrees, enrolment and federal money in the "
        "same sentence for one institution.",
        {
            "mode": {"type": "string",
                     "enum": ["lookup", "rank", "state"],
                     "description": "lookup = named institutions, one row each; "
                                    "rank = the national ranking on one measure; "
                                    "state = the rollup, one row per state."},
            "names": {"type": "array", "items": {"type": "string"},
                      "description": "For lookup: institution names or parts of "
                                     "them, matched case-insensitively. Two or "
                                     "more gives a comparison."},
            "measure": {"type": "string",
                        "description": "For rank: which ranking. One of "
                                       "stem_masters_awarded, "
                                       "stem_masters_non_resident, "
                                       "stem_masters_non_resident_share, "
                                       "stem_masters_share_change, "
                                       "stem_doctorates_awarded, "
                                       "stem_doctorates_non_resident, "
                                       "stem_doctorates_non_resident_share, "
                                       "stem_doctorates_share_change, "
                                       "graduate_non_resident, "
                                       "graduate_non_resident_share, "
                                       "federal_obligations, federal_rd, "
                                       "federal_training, "
                                       "federal_per_doctorate, "
                                       "graduate_tuition_out_of_state."},
            "state": {"type": "string",
                      "description": "For state: a two-letter code to return "
                                     "one state; omit for all of them."},
            "limit": {"type": "integer", "description": "1-25, default 10."},
        },
        required=["mode"],
    ),
]


# ---------------------------------------------------------------------------
def _t_key_figures(args):
    d = summary()
    figs = d.get("figures") or {}
    if not figs:
        return {"error": "summary.json is not in this build"}
    want = args.get("keys") or []
    if want:
        rows = {k: figs[k] for k in want if k in figs}
        missing = [k for k in want if k not in figs]
    else:
        rows, missing = figs, []
    return {
        "source": SRC_SUMMARY,
        "figures": rows,
        "unknown_keys": missing,
        "available_keys": sorted(figs) if missing else None,
        "caution": ("Every figure carries a 'limit'. Quote it with the number: "
                    "these are the qualifications that make each figure true, "
                    "and a summary is exactly where they get lost."),
    }


def _t_compare_institutions(args):
    d = institutions()
    rows = d.get("institutions") or []
    if not rows:
        return {"error": "institutions_compact.json is not in this build"}
    mode = args.get("mode")
    limit = _clamp(args.get("limit"), 1, 25, 10)
    base = {"source": SRC_INST, "fields": d.get("fields"),
            "windows": d.get("windows")}

    if mode == "state":
        want = (args.get("state") or "").strip().upper()
        states = d.get("states") or []
        if want:
            hit = [s for s in states if s["state"] == want]
            if not hit:
                return {"error": f"no state {want!r}",
                        "available": sorted(s["state"] for s in states)}
            base["states"] = hit
        else:
            base["states"] = states[:limit]
            base["state_count"] = len(states)
        base["caution"] = ("Shares here are recomputed from the sums, never "
                           "averaged across institutions. They cover only "
                           "institutions present in this table.")
        return base

    if mode == "rank":
        measure = (args.get("measure") or "").strip()
        rankings = d.get("rankings") or {}
        if measure not in rankings:
            return {"error": f"no ranking {measure!r}",
                    "available": sorted(rankings)}
        base["measure"] = measure
        base["rows"] = rankings[measure][:limit]
        base["ranked_pool"] = (d.get("ranked_counts") or {}).get(measure)
        base["floors"] = d.get("floors")
        base["caution"] = (
            "A share is a ratio: quote the denominator, which is on the "
            "institution's own row via lookup. Share rankings apply a cohort "
            "floor -- 'floors' says which -- because a programme of five, all "
            "non-resident, reads 100% and means nothing.")
        if measure == "federal_per_doctorate":
            base["caution"] += (
                " This one is an intensity ratio and NOT a price: federal "
                "obligations fund research whose outputs include papers, "
                "instruments, facilities and staff, not only degrees. The top "
                "of this ranking is medical schools -- check fps and fpp on "
                "the institution's row, which say how much of its doctoral "
                "output the denominator covers.")
        return base

    names = [str(n).strip().lower() for n in (args.get("names") or [])
             if str(n).strip()]
    if not names:
        return {"error": "lookup needs at least one name"}
    found, misses = [], []
    for want in names[:10]:
        hits = [r for r in rows if want in r["n"].lower()]
        if not hits:
            misses.append(want)
            continue
        # "Purdue University" matches six campuses and the one meant is the
        # main one. Rank exact name first, then names that START with the
        # query, then by size -- shortest-name-first was tried and returned
        # Global, Northwest and Fort Wayne while burying the flagship.
        def rank(r):
            n = r["n"].lower()
            size = (r.get("g") or 0) + (r.get("m") or 0) + (r.get("d") or 0)
            return (n != want, not n.startswith(want), -size)
        found.extend(sorted(hits, key=rank)[:3])
    base["rows"] = found[:limit]
    base["not_found"] = misses
    base["caution"] = (
        "A field that is absent means no data, not zero -- an institution with "
        "no federal figures was not surveyed, it did not spend nothing. "
        "Non-resident is a visa category, not a birthplace, so every share is "
        "a floor on the foreign-born proportion.")
    return base


IMPL = {"key_figures": _t_key_figures,
        "compare_institutions": _t_compare_institutions}
