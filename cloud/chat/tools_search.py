"""
Search / discovery data tools for the chat assistant.

Three tools, registered by the caller from ``SCHEMAS`` and ``IMPL``:

  find_departments   Let the user find the extreme institution x CIP cells
                     themselves instead of quoting a curated handful.
  search_records     Term search over the 517,715 harvested dissertation and
                     thesis titles, answered as counts by institution,
                     department and year.
  similar_to         Nearest-neighbour universities on stated, auditable axes.

Conventions are the ones in ``tools.py``: schemas built with ``_fn``, integer
arguments run through ``_clamp``, all reads go through ``data_store`` (``ds``),
errors are returned as ``{"error": ...}`` rather than raised, and every payload
that can contain scraped text carries the ``_untrusted`` banner plus a
``scope`` / ``searched`` string saying exactly what was counted.

WHY search_records RETURNS COUNTS AND NOT RECORDS
-------------------------------------------------
Two independent reasons, both measured rather than assumed:

  SIZE.  The corpus is 517,715 records in 99 MB of per-university JSON.  Packed
  down to (university, department, year, title, degree) it is 56.7 MB raw and
  17.5 MB gzipped; the titles alone are 15.2 MB gzipped.  A record-level
  inverted index over title terms (df>=5) is 3.68 M postings, 6.24 MB of
  delta-varints, 5.69 MB gzipped -- and that is before any record table to
  render a hit from.  The Lambda ships 2.0 MB of data today against a ~6 MB
  budget, so record-level full-text search does not fit and is not attempted.
  What does fit is an inverted index whose postings resolve to
  (university, department, year) cells: 38,875 cells, 37,141 terms, 3.7 MB
  LZMA, ~145 ms to inflate.  That is what ``search_index.bin`` is.

  PRIVACY.  The records name individual people.  The site already publishes
  them, so this is not new exposure, but a chat tool that returned title +
  author rows on a name query would be a people-finder built on top of a
  demographic study, which is not what the project is for.  Aggregating to
  (institution, department, year) makes the tool answer questions about fields
  and places, which is the question the project is actually about, and makes
  the largest untrusted-text surface in the project unreachable as free text:
  the index stores term -> counts, never a title string.

The cost of the aggregation is stated in every result: single-term counts are
exact record counts; multi-term queries resolve at cell grain and are reported
as upper bounds, flagged with ``exact: false``.
"""
from __future__ import annotations

import array
import json
import lzma
import math
import os
import re
import struct
import sys
from collections import Counter, defaultdict
from itertools import accumulate

try:
    from . import data_store as ds
    from .tools import UNTRUSTED, _clamp, _fn
except ImportError:  # flat Lambda layout
    import data_store as ds
    from tools import UNTRUSTED, _clamp, _fn


SEARCH_INDEX_FILE = "search_index.bin"

# Terms below this document frequency are not in the index (see the builder).
MIN_DF = 5
MIN_TERM_LEN = 3
MAX_QUERY_TERMS = 6

_TOKEN = re.compile(r"[a-z0-9]+")

# Deliberately short.  This list is applied identically by the builder and at
# query time; changing it invalidates the shipped index.
STOPWORDS = frozenset("""
a an the of and or in on for to with from by at as is are be been was were this
that these those into over under between within without their its his her our
your not no nor but if then than so such using use used
""".split())


def tokenize(text: str) -> list:
    """Title -> index terms.  Shared by scripts/build_chat_search_index.py."""
    return [t for t in _TOKEN.findall((text or "").lower())
            if len(t) >= MIN_TERM_LEN and t not in STOPWORDS and not t.isdigit()]


# ---------------------------------------------------------------------------
# search index reader
# ---------------------------------------------------------------------------
_search = None      # dict header + blob, or {"error": ...}


def _read_varints(blob, start, end):
    """Decode a varint run.  Returns a flat list of ints."""
    out, n, shift, i = [], 0, 0, start
    while i < end:
        b = blob[i]
        n |= (b & 0x7F) << shift
        i += 1
        if b < 0x80:
            out.append(n)
            n, shift = 0, 0
        else:
            shift += 7
    return out


def _le(typecode, buf):
    a = array.array(typecode)
    a.frombytes(buf)
    if sys.byteorder != "little":
        a.byteswap()
    return a


def load_search_index():
    """Inflate ``search_index.bin`` once per container.

    Everything per-term and per-cell is a binary section mapped with
    array.array; only a ~40 kB JSON header is parsed.  An earlier build put the
    cell table and the term offsets in the JSON header and cost 2.0 s of cold
    start against 0.15 s for the LZMA inflate, which is why the format looks
    the way it does.
    """
    global _search
    if _search is None:
        path = os.path.join(ds.DATA_DIR, SEARCH_INDEX_FILE)
        if not os.path.exists(path):
            _search = {"error": f"{SEARCH_INDEX_FILE} was not bundled into this deployment."}
            return _search
        with open(path, "rb") as fh:
            raw = lzma.decompress(fh.read())
        (hlen,) = struct.unpack("<I", raw[:4])
        ix = json.loads(raw[4:4 + hlen].decode("utf-8"))
        body = memoryview(raw)[4 + hlen:]

        def sect(name):
            off, ln = ix["sections"][name]
            return body[off:off + ln]

        ix["vocab"] = bytes(sect("vocab")).decode("utf-8").split("\n")
        ix["term_index"] = {t: i for i, t in enumerate(ix["vocab"])}
        ix["cell_u"] = _le("B", bytes(sect("cell_u")))
        ix["cell_d"] = _le("H", bytes(sect("cell_d")))
        ix["cell_y"] = _le("H", bytes(sect("cell_y")))
        dlen = _le("I", bytes(sect("dlen")))
        clen = _le("I", bytes(sect("clen")))
        ix["dlen"], ix["clen"] = dlen, clen
        ix["doff"] = list(accumulate(dlen, initial=0))
        ix["coff"] = list(accumulate(clen, initial=0))
        ix["pdelta"] = bytes(sect("pdelta"))
        ix["pcount"] = bytes(sect("pcount"))
        _search = ix
    return _search


def _postings(ix, term):
    """term -> {cell_id: record_count}.  Empty dict if the term is not indexed."""
    i = ix["term_index"].get(term)
    if i is None:
        return {}
    do, dl = ix["doff"][i], ix["dlen"][i]
    co, cl = ix["coff"][i], ix["clen"][i]
    deltas = _read_varints(ix["pdelta"], do, do + dl)
    counts = _read_varints(ix["pcount"], co, co + cl)
    out, cid = {}, 0
    for j, d in enumerate(deltas):
        cid += d
        out[cid] = counts[j]
    return out


# ---------------------------------------------------------------------------
# SCHEMAS
# ---------------------------------------------------------------------------
SCHEMAS = [
    _fn(
        "find_departments",
        "Find institution x CIP departments of research doctorates that match a "
        "threshold, instead of quoting a curated example. Years in the window are "
        "POOLED, so min_total is a cohort over the whole window: "
        "min_share=80, min_total=50, years=[2021,2025] answers 'departments over 80% "
        "non-resident with 50+ doctorates in the last five years' in one call. "
        "The result reports how many rows the same filters would return at min_total=1 "
        "so the reader can see how much of the answer is threshold artefact.",
        {
            "min_share": {"type": "number",
                          "description": "Minimum non-resident share, percent. Omit for no floor."},
            "max_share": {"type": "number",
                          "description": "Maximum non-resident share, percent. Use with min_share "
                                         "to select a band, or alone to find the low end."},
            "min_total": {"type": "integer",
                          "description": "Minimum pooled cohort size over the whole year window. "
                                         "Default 20. This threshold decides the answer: at 1 the "
                                         "top of the list is departments of one to three people. "
                                         "Do not go below 10 without saying so."},
            "cip": {"type": "array", "items": {"type": "string"},
                    "description": "CIP code prefixes, e.g. ['14'] for engineering. "
                                   "Use cip_search if unsure."},
            "state": {"type": "array", "items": {"type": "string"},
                      "description": "Two-letter state postal codes to restrict to, e.g. ['TX','CA']."},
            "years": {"type": "array", "items": {"type": "integer"},
                      "description": "[start, end] inclusive, e.g. [2021, 2025]. A single value "
                                     "means that one year. More than two values are taken as an "
                                     "explicit set of years. Default [2020, 2025]."},
            "sort": {"type": "string", "enum": ["share", "total", "nra", "share_asc"],
                     "description": "Default 'share' (highest non-resident share first). "
                                    "'share_asc' for the lowest."},
            "limit": {"type": "integer", "description": "1-60, default 25."},
        },
    ),
    _fn(
        "search_records",
        "Term search over the titles of 517,715 harvested dissertation and thesis "
        "records from 105 university repositories. IT RETURNS COUNTS, NOT RECORDS: "
        "how many titles contain the term, and how they break down by institution, "
        "department and year. It does not return titles, author names or links to "
        "individual records, and it does not search authors or abstracts. "
        "Single-term counts are exact record counts; multi-term queries are resolved "
        "at institution x department x year grain and returned as upper bounds with "
        "exact=false. Use it for 'how much work is there on X and where', not to look "
        "up a person.",
        {
            "query": {"type": "string",
                      "description": "One or more title words, e.g. 'semiconductor' or "
                                     "'quantum computing'. Prefer a single distinctive word: "
                                     "single-term counts are exact."},
            "university": {"type": "string",
                           "description": "Site university key, e.g. mit, utdallas. "
                                          "Use list_universities to find one."},
            "field": {"type": "string",
                      "description": "Department label filter, substring match, e.g. "
                                     "'Electrical' or 'Physics'. These are the site's own "
                                     "department labels, not CIP codes."},
            "year": {"type": "array", "items": {"type": "integer"},
                     "description": "[start, end] inclusive, or a single year. "
                                    "Default: all years, 1966-2026."},
            "limit": {"type": "integer",
                      "description": "How many institutions and departments to rank. 1-50, default 25."},
        },
        ["query"],
    ),
    _fn(
        "similar_to",
        "Find the universities on this site whose profile is closest to a given one. "
        "The comparison axes and the distance measure are returned with the result so "
        "the ranking can be checked rather than trusted: 'profile' is z-scored "
        "Euclidean distance over six axes, the other modes are cosine distance over a "
        "share vector.",
        {
            "university": {"type": "string",
                           "description": "Site university key, e.g. mit, njit, utdallas."},
            "by": {"type": "string",
                   "enum": ["profile", "field_mix", "origins", "scale"],
                   "description": "profile = six standardised non-resident and scale axes "
                                  "(default). field_mix = department composition of the "
                                  "dissertation record set. origins = name-origin mix of authors. "
                                  "scale = size only (records, doctorates per year, R&D dollars)."},
            "limit": {"type": "integer", "description": "1-20, default 5."},
        },
        ["university"],
    ),
]


# ---------------------------------------------------------------------------
# 1. find_departments
# ---------------------------------------------------------------------------
def _year_window(years, default=(2020, ds.INDEX_MAX_YEAR), bounds=None):
    """[start, end] -> a set of years, plus a label.  Returns (set, label).

    `bounds` clamps the caller's years to what the underlying artifact actually
    covers, and differs per tool: the IPEDS index runs 1995-2025, the harvested
    record corpus runs 1966-2026.  Clamping to the wrong one silently rewrites
    the question -- year=[1970,1980] against the record corpus came back
    labelled "1995-1995" before this argument existed.
    """
    lo_d, hi_d = default
    lo_b, hi_b = bounds or (ds.INDEX_MIN_YEAR, ds.INDEX_MAX_YEAR)
    if not years:
        return set(range(lo_d, hi_d + 1)), f"{lo_d}-{hi_d}"
    vals = []
    for y in years:
        try:
            vals.append(int(y))
        except (TypeError, ValueError):
            continue
    vals = [max(lo_b, min(hi_b, v)) for v in vals]
    if not vals:
        return set(range(lo_d, hi_d + 1)), f"{lo_d}-{hi_d}"
    if len(vals) == 1:
        return {vals[0]}, str(vals[0])
    if len(vals) == 2:
        lo, hi = min(vals), max(vals)
        return set(range(lo, hi + 1)), f"{lo}-{hi}"
    return set(vals), ",".join(str(v) for v in sorted(set(vals)))


# IPEDS award-level basis.  The index carries two: `aw09` (award level 9,
# "doctor's degree") for the years before the 2010 taxonomy change, and `aw17`
# (award level 17, "doctor's degree - research/scholarship") after it.  2008 and
# 2009 carry BOTH, because some institutions reported the new level early — in
# 2009 aw17 covers 24,742 awards against aw09's 37,461 — so summing the column
# blind would double-count those two years and undercount if aw17 were
# preferred there.  One basis per year, switching at the taxonomy change.
AW17_FROM = 2010


def _basis_for_year(year: int) -> str:
    return "aw17" if year >= AW17_FROM else "aw09"


def _t_find_departments(args):
    years, year_label = _year_window(args.get("years"))
    min_total = _clamp(args.get("min_total", 20), 1, 1000000, 20)
    limit = _clamp(args.get("limit", 25), 1, 60, 25)
    sort = args.get("sort") or "share"

    min_share = args.get("min_share")
    max_share = args.get("max_share")
    try:
        min_share = float(min_share) if min_share is not None else None
        max_share = float(max_share) if max_share is not None else None
    except (TypeError, ValueError):
        return {"error": "min_share and max_share must be numbers (percent, 0-100)."}
    if min_share is not None and max_share is not None and min_share > max_share:
        return {"error": f"min_share ({min_share}) is above max_share ({max_share}); "
                         f"no department can match."}

    cips = [ds.clean_text(c, 12) for c in (args.get("cip") or []) if ds.clean_text(c, 12)]
    raw_state = args.get("state")
    if isinstance(raw_state, str):
        raw_state = [raw_state]
    states = {ds.clean_text(s, 2).upper() for s in (raw_state or []) if ds.clean_text(s, 2)}

    insts = ds.institutions()
    if states:
        units_in_state = {u for u, (_n, st) in insts.items() if st.upper() in states}
        if not units_in_state:
            return {"error": f"No institution in hd_names.csv has state {sorted(states)}.",
                    "hint": "Use two-letter postal codes, e.g. ['TX']."}
    else:
        units_in_state = None

    agg = defaultdict(lambda: [0, 0])
    for year, uid, code, basis, total, nra in ds.load_index():
        if year not in years:
            continue
        if basis != _basis_for_year(year):
            continue
        if cips and not any(code.startswith(c) for c in cips):
            continue
        if units_in_state is not None and uid not in units_in_state:
            continue
        cell = agg[(uid, code)]
        cell[0] += total
        cell[1] += nra

    titles = ds.cip_titles()
    unit_to_key = {str(u.get("unitid")): (k, u.get("url") or f"/universities/{k}.html")
                   for k, u in ds.universities().items() if u.get("unitid")}

    rows, n_at_1, n_at_100_at_1 = [], 0, 0
    for (uid, code), (total, nra) in agg.items():
        if total <= 0:
            continue
        share = nra / total * 100
        if min_share is not None and share < min_share:
            continue
        if max_share is not None and share > max_share:
            continue
        n_at_1 += 1
        if nra == total:
            n_at_100_at_1 += 1
        if total < min_total:
            continue
        name, st = insts.get(uid, ("(unknown institution)", ""))
        rec = {"unitid": uid, "institution": name, "state": st,
               "cip": code, "subject": titles.get(code, "(title not in CIP2020 list)"),
               "total": total, "nra": nra, "nra_share": round(share, 1)}
        site = unit_to_key.get(uid)
        if site:
            rec["university_key"], rec["url"] = site[0], site[1]
        rows.append(rec)

    keyfn = {"share": lambda r: (-r["nra_share"], -r["total"]),
             "share_asc": lambda r: (r["nra_share"], -r["total"]),
             "total": lambda r: -r["total"],
             "nra": lambda r: -r["nra"]}
    rows.sort(key=keyfn.get(sort, keyfn["share"]))

    out = {
        "source": (f"IPEDS Completions via find_departments, {year_label} pooled, "
                   f"cohorts of {min_total}+"),
        "matched": len(rows),
        "returned": min(len(rows), limit),
        "departments": rows[:limit],
        "query": {"years": year_label, "pooling": "years pooled into one cohort per department",
                  "min_total": min_total, "min_share": min_share, "max_share": max_share,
                  "cip": cips or "all fields", "state": sorted(states) or "all states",
                  "sort": sort},
        "threshold": {
            "effective_min_total": min_total,
            "matched_at_this_threshold": len(rows),
            "matched_if_min_total_were_1": n_at_1,
            "at_100_percent_if_min_total_were_1": n_at_100_at_1,
            "note": ("The cohort floor decides the answer. Departments awarding one to "
                     "three doctorates in the window sit at 0% or 100% by arithmetic, not "
                     "by composition. Quote effective_min_total whenever you quote a row."),
        },
        "scope": ("A department is one institution x one 6-digit CIP code, all years in "
                  "the window pooled. `nra` counts non-resident-alien awardees: a visa "
                  "status at the time of the award, not ethnicity or country of birth."),
        "award_level": (
            "From 2010 this is IPEDS award level 17, doctor's degree - research/scholarship. "
            "Before 2010 it is award level 9, doctor's degree, which level 17 and level 18 "
            "(professional practice) were split out of in 2010; the pre-2010 years are "
            "therefore slightly broader than the years after. MD and JD sat in a separate "
            "pre-2010 category (first-professional) and are in neither. One basis is used "
            "per year, so the 2008 and 2009 rows that exist under both are not double-counted."),
        "_untrusted": UNTRUSTED,
    }
    if min_total < 10:
        out["warning"] = (f"min_total={min_total} is below 10. Shares on cohorts this small "
                          f"are arithmetic, not composition. Add a show_notice caveat.")
    if not rows:
        out["note"] = ("No department matched. Widen the year window, lower min_total, "
                       "loosen the share band, or drop the CIP/state filter. "
                       f"{n_at_1} departments match the share filters at min_total=1.")
    return out


# ---------------------------------------------------------------------------
# 2. search_records
# ---------------------------------------------------------------------------
def _search_scope(ix):
    return {
        "records_indexed": ix["records"],
        "universities": len(ix["universities"]),
        "departments": len(ix["departments"]),
        "year_range": [ix["year_min"], ix["year_max"]],
        "records_without_a_year": ix.get("records_without_year", 0),
        "vocabulary_terms": len(ix["vocab"]),
        "min_term_frequency": ix.get("min_df", MIN_DF),
        "grain": ix.get("grain", "institution x department x year"),
        "cells": ix["n_cells"],
    }


def _t_search_records(args):
    ix = load_search_index()
    if "error" in ix:
        return {"error": ix["error"],
                "hint": "Rebuild with scripts/build_chat_search_index.py and redeploy."}

    raw_query = ds.clean_text(args.get("query", ""), 120)
    terms = tokenize(raw_query)[:MAX_QUERY_TERMS]
    limit = _clamp(args.get("limit", 25), 1, 50, 25)

    searched = ("Title text of harvested dissertation and thesis records only. "
                "Author names, abstracts, repository URLs and full text are NOT indexed "
                "and NOT searched.")
    base = {
        "source": (f"Harvested repository titles via search_records "
                   f"({ix['records']:,} records, {len(ix['universities'])} universities)"),
        "searched": searched,
        "index": _search_scope(ix),
        "privacy": ("Returns counts by institution, department and year. It never returns "
                    "an individual record, title or author name. The records themselves are "
                    "published per university on the site and queryable at /query.html."),
        "_untrusted": UNTRUSTED,
    }

    if not terms:
        base["error"] = f"No searchable term in query {raw_query!r}."
        base["note"] = (f"Terms must be {MIN_TERM_LEN}+ characters, not a pure number, and not "
                        f"one of {len(STOPWORDS)} stopwords.")
        return base

    # department-label matches are a separate question from title matches
    qlow = raw_query.lower().strip()
    dept_label_hits = sorted(d for d in ix["departments"] if qlow and qlow in d.lower())

    posts, unknown = [], []
    for t in terms:
        p = _postings(ix, t)
        if not p:
            unknown.append(t)
        else:
            posts.append((t, p))
    if not posts:
        base["matched_records"] = 0
        base["terms"] = {"used": [], "not_in_index": unknown}
        base["by_university"], base["by_department"], base["by_year"] = [], [], []
        base["department_label_matches"] = dept_label_hits
        base["note"] = (f"None of {unknown} appears in {ix['records']:,} titles at least "
                        f"{ix.get('min_df', MIN_DF)} times, so no title matched. Terms below that "
                        f"frequency are not in the index and cannot be distinguished from terms "
                        f"that never occur.")
        return base

    # intersect at cell grain; count = min across terms (upper bound when >1 term)
    posts.sort(key=lambda tp: len(tp[1]))
    cells = dict(posts[0][1])
    for _t, p in posts[1:]:
        cells = {c: min(n, p[c]) for c, n in cells.items() if c in p}

    # filters
    uni_key = ds.clean_text(args.get("university", ""), 40).lower().replace(" ", "_")
    if uni_key and uni_key not in ix["universities"]:
        near = [k for k in ix["universities"] if uni_key in k or k in uni_key][:8]
        return {**base, "error": f"No indexed university with key '{uni_key}'.",
                "did_you_mean": near,
                "hint": "Call list_universities to find the right key."}
    field = ds.clean_text(args.get("field", ""), 60).lower()
    yr = args.get("year")
    if isinstance(yr, int):
        yr = [yr]
    yset, ylabel = (None, f"{ix['year_min']}-{ix['year_max']}")
    if yr:
        yset, ylabel = _year_window(yr, default=(ix["year_min"], ix["year_max"]),
                                    bounds=(ix["year_min"], ix["year_max"]))

    uni_i = ix["universities"].index(uni_key) if uni_key else None
    dept_ok = None
    if field:
        dept_ok = {i for i, d in enumerate(ix["departments"]) if field in d.lower()}
        if not dept_ok:
            return {**base, "error": f"No department label contains '{field}'.",
                    "hint": "Department labels come from the site's own department mapping; "
                            "call get_university_facts with fields=['departments'] to see them."}

    by_uni, by_dept, by_year = Counter(), Counter(), Counter()
    total = 0
    cu, cd, cy = ix["cell_u"], ix["cell_d"], ix["cell_y"]
    for cid, n in cells.items():
        u, d, y = cu[cid], cd[cid], cy[cid]
        if uni_i is not None and u != uni_i:
            continue
        if dept_ok is not None and d not in dept_ok:
            continue
        if yset is not None and y not in yset:
            continue
        total += n
        by_uni[u] += n
        by_dept[d] += n
        by_year[y] += n

    unis = ds.universities()
    uni_rows = []
    for u, n in by_uni.most_common(limit):
        key = ix["universities"][u]
        rec = unis.get(key) or {}
        uni_rows.append({"key": key, "name": rec.get("name", key), "records": n,
                         "url": rec.get("url", f"/universities/{key}.html")})
    dept_rows = [{"department": ix["departments"][d], "records": n}
                 for d, n in by_dept.most_common(limit)]

    out = {
        **base,
        "terms": {"used": [t for t, _ in posts], "not_in_index": unknown},
        "exact": len(posts) == 1,
        "matched_records": total,
        "share_of_indexed_corpus_pct": round(total / ix["records"] * 100, 3) if ix["records"] else None,
        "filters": {"university": uni_key or "all 105", "field": field or "all departments",
                    "years": ylabel},
        "by_university": uni_rows,
        "by_department": dept_rows,
        "by_year": sorted([y, n] for y, n in by_year.items()),
        "department_label_matches": dept_label_hits,
        "matching": (
            "Exact record count: one term, so every counted record is a title containing it."
            if len(posts) == 1 else
            "UPPER BOUND, not an exact count. Multiple terms are intersected at "
            "institution x department x year grain, so a match means that cell contains "
            "records with every term, not that one title contains them all. The count is "
            "the smallest per-term count in each cell. For an exact figure, search one term."),
    }
    if unknown:
        out["note"] = (f"Ignored {unknown}: below the index's {ix.get('min_df', MIN_DF)}-title "
                       f"frequency floor, or not present at all.")
    if total == 0:
        out["note"] = ("Terms are in the index but no record survives the filters. "
                       "Drop the university, field or year filter and retry.")
    return out


# ---------------------------------------------------------------------------
# 3. similar_to
# ---------------------------------------------------------------------------
def _origin_shares(u):
    o = u.get("name_origins") or {}
    tot = sum(v for v in o.values() if isinstance(v, (int, float)))
    if not tot:
        return None, None
    foreign = tot - (o.get("other") or 0)
    return {k: v / tot for k, v in o.items()}, (foreign / tot * 100, (o.get("chinese") or 0) / tot * 100)


def _recent_phd(u):
    ct = u.get("completions_trend") or {}
    years, tot = ct.get("years") or [], ct.get("phd_total") or []
    pairs = [(y, t) for y, t in zip(years, tot) if isinstance(t, (int, float))]
    if not pairs:
        return None
    pairs.sort()
    tail = [t for _y, t in pairs[-5:]]
    return sum(tail) / len(tail)


def _rd_recent(u):
    rd = ((u.get("funding") or {}).get("rd")) or {}
    vals = [(int(y), v) for y, v in rd.items() if isinstance(v, (int, float))]
    if not vals:
        return None
    vals.sort()
    return vals[-1][1]


# axis name -> (extractor, human label, unit)
_PROFILE_AXES = [
    ("nra_site_figure", lambda u: u.get("nra_site_figure"),
     "site non-resident share of doctorates", "%"),
    ("grad_enrolment_nra_pct", lambda u: (u.get("enrollment_ipeds") or {}).get("nra_pct"),
     "IPEDS non-resident share of graduate enrolment", "%"),
    ("faculty_nra_pct", lambda u: (u.get("faculty") or {}).get("nra_pct"),
     "IPEDS non-resident share of instructional staff", "%"),
    ("foreign_name_pct", lambda u: (_origin_shares(u)[1] or (None, None))[0],
     "share of classified author names that are not 'other'", "%"),
    ("chinese_name_pct", lambda u: (_origin_shares(u)[1] or (None, None))[1],
     "share of classified author names classed Chinese", "%"),
    ("log10_records", lambda u: (math.log10(u["records"]) if u.get("records") else None),
     "log10 of harvested dissertation records", "log10 count"),
]

_SCALE_AXES = [
    ("log10_records", lambda u: (math.log10(u["records"]) if u.get("records") else None),
     "log10 of harvested dissertation records", "log10 count"),
    ("log10_phd_per_year", lambda u: (math.log10(_recent_phd(u)) if (_recent_phd(u) or 0) > 0 else None),
     "log10 of mean IPEDS doctorates per year, last five reported years", "log10 count"),
    ("log10_rd_dollars", lambda u: (math.log10(_rd_recent(u)) if (_rd_recent(u) or 0) > 0 else None),
     "log10 of latest NSF HERD R&D expenditure", "log10 thousand USD"),
]


def _zscore_neighbours(key, unis, axes, limit):
    values = {}
    for k, u in unis.items():
        row = [fn(u) for _n, fn, _l, _un in axes]
        if all(v is not None for v in row):
            values[k] = row
    if key not in values:
        have = {n: fn(unis[key]) for n, fn, _l, _un in axes}
        missing = [n for n, v in have.items() if v is None]
        return None, {"error": f"'{key}' is missing {missing} in universities_compact.json, "
                               f"so it cannot be placed on these axes.",
                      "axes": [a[0] for a in axes]}
    n = len(axes)
    mean, sd = [0.0] * n, [0.0] * n
    for i in range(n):
        col = [v[i] for v in values.values()]
        mean[i] = sum(col) / len(col)
        var = sum((c - mean[i]) ** 2 for c in col) / len(col)
        sd[i] = math.sqrt(var) or 1.0
    me = values[key]
    mz = [(me[i] - mean[i]) / sd[i] for i in range(n)]
    out = []
    for k, row in values.items():
        if k == key:
            continue
        z = [(row[i] - mean[i]) / sd[i] for i in range(n)]
        d = math.sqrt(sum((z[i] - mz[i]) ** 2 for i in range(n)))
        out.append((d, k, row, z))
    out.sort(key=lambda r: r[0])
    neighbours = []
    for d, k, row, z in out[:limit]:
        neighbours.append({
            "key": k, "name": unis[k].get("name", k),
            "distance": round(d, 3),
            "url": unis[k].get("url", f"/universities/{k}.html"),
            "axes": {axes[i][0]: round(row[i], 3) for i in range(n)},
            "axis_gap_in_sd": {axes[i][0]: round(z[i] - mz[i], 2) for i in range(n)},
        })
    meta = {
        "compared_over": len(values),
        "excluded_for_missing_axes": sorted(set(unis) - set(values)),
        "target_axes": {axes[i][0]: round(me[i], 3) for i in range(n)},
        "axis_mean": {axes[i][0]: round(mean[i], 3) for i in range(n)},
        "axis_sd": {axes[i][0]: round(sd[i], 3) for i in range(n)},
    }
    return neighbours, meta


def _cosine_neighbours(key, unis, vecfn, limit):
    vecs = {}
    for k, u in unis.items():
        v = vecfn(u)
        if v:
            norm = math.sqrt(sum(x * x for x in v.values()))
            if norm > 0:
                vecs[k] = (v, norm)
    if key not in vecs:
        return None, {"error": f"'{key}' has no vector on this axis set in "
                               f"universities_compact.json."}
    mv, mn = vecs[key]
    out = []
    for k, (v, norm) in vecs.items():
        if k == key:
            continue
        dot = sum(x * v[t] for t, x in mv.items() if t in v)
        cos = dot / (mn * norm)
        out.append((1 - cos, k, v))
    out.sort(key=lambda r: r[0])
    neighbours = []
    for d, k, v in out[:limit]:
        tot = sum(v.values()) or 1.0
        top = sorted(v.items(), key=lambda kv: -kv[1])[:5]
        neighbours.append({
            "key": k, "name": unis[k].get("name", k), "distance": round(d, 4),
            "url": unis[k].get("url", f"/universities/{k}.html"),
            "top_components_pct": {t: round(x / tot * 100, 1) for t, x in top},
        })
    mtot = sum(mv.values()) or 1.0
    meta = {"compared_over": len(vecs),
            "excluded_for_missing_axes": sorted(set(unis) - set(vecs)),
            "target_top_components_pct": {t: round(x / mtot * 100, 1) for t, x in
                                          sorted(mv.items(), key=lambda kv: -kv[1])[:5]}}
    return neighbours, meta


def _t_similar_to(args):
    key = ds.clean_text(args.get("university", ""), 40).lower().replace(" ", "_")
    unis = ds.universities()
    if key not in unis:
        near = [k for k in unis if key and (key in k or k in key)][:8]
        return {"error": f"No university with key '{key}'.", "did_you_mean": near,
                "hint": "Call list_universities to find the right key."}
    by = args.get("by") or "profile"
    limit = _clamp(args.get("limit", 5), 1, 20, 5)

    if by == "field_mix":
        neigh, meta = _cosine_neighbours(
            key, unis,
            lambda u: {d["name"]: float(d.get("records") or 0)
                       for d in (u.get("departments") or []) if (d.get("records") or 0) > 0},
            limit)
        axes_desc = ("Department composition of the harvested record set: the site's top-25 "
                     "departments per university, as a record-count vector.")
        measure = "cosine distance (1 - cosine similarity) over the raw record-count vector"
    elif by == "origins":
        # The 'other' bucket is 52-90% of every university's names, so leaving it
        # in makes all 105 vectors near-parallel and the ranking is then decided
        # by rounding on a single dominant axis.  Compare the mix among the
        # classified origins instead; overall foreign-name share is already an
        # axis of `profile`.
        neigh, meta = _cosine_neighbours(
            key, unis,
            lambda u: {k2: float(v) for k2, v in (u.get("name_origins") or {}).items()
                       if k2 != "other" and isinstance(v, (int, float)) and v > 0},
            limit)
        axes_desc = ("Mix of the CLASSIFIED name origins of dissertation authors — chinese, "
                     "indian, korean, arabic, vietnamese, iranian, turkish — as shares of the "
                     "classified names only. The unclassified 'other' bucket is excluded "
                     "because it is 52-90% of every university and would swamp the comparison; "
                     "for overall foreign-name share use by='profile'. This is a surname-based "
                     "inference, not nationality or citizenship.")
        measure = "cosine distance (1 - cosine similarity) over the classified name-count vector"
    else:
        axes = _SCALE_AXES if by == "scale" else _PROFILE_AXES
        neigh, meta = _zscore_neighbours(key, unis, axes, limit)
        axes_desc = "; ".join(f"{a[0]} = {a[2]} ({a[3]})" for a in axes)
        measure = ("Euclidean distance in z-score space. Each axis is standardised over the "
                   "universities that have all axes, using the mean and standard deviation "
                   "reported below, so one distance unit is one standard deviation on one axis.")
        by = by if by in ("profile", "scale") else "profile"

    if neigh is None:
        return {**meta, "university": key, "by": by}

    flagged = sorted(k for k in [key] + [n["key"] for n in neigh]
                     if ((unis[k].get("faculty") or {}).get("nra_pct") == 0
                         and (unis[k].get("faculty") or {}).get("total")))
    out = {
        "source": "Site university digest (universities_compact.json) via similar_to",
        "university": {"key": key, "name": unis[key].get("name", key),
                       "url": unis[key].get("url", f"/universities/{key}.html")},
        "by": by,
        "axes": axes_desc,
        "distance_measure": measure,
        "neighbours": neigh,
        "scope": ("Nearest neighbours among the 105 universities that have a page on this "
                  "site, not among US universities generally. Distance is descriptive: it "
                  "says these profiles are close on the stated axes, nothing more."),
        "_untrusted": UNTRUSTED,
    }
    if flagged and by in ("profile",):
        out["data_quality"] = (
            f"{flagged} report exactly 0 non-resident instructional staff against a non-zero "
            f"staff total in IPEDS. Treat that as 'the category was not reported' rather than a "
            f"true zero: it pulls those universities together on the faculty_nra_pct axis, so "
            f"part of any closeness between them is a reporting artefact, not a real similarity.")
    out.update(meta)
    return out


# ---------------------------------------------------------------------------
# registry
# ---------------------------------------------------------------------------
IMPL = {
    "find_departments": _t_find_departments,
    "search_records": _t_search_records,
    "similar_to": _t_similar_to,
}
