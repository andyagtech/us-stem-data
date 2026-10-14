#!/usr/bin/env python3
"""One place that turns a crawled institution name into a record key.

WHY THIS EXISTS. The lab crawlers learn an institution's name from
whatever the page gave them -- an IPEDS registered name from the sector
lists, a short house name from the thesis record, sometimes a banner.
The ranker then needs the thesis-record key so it can take that
department's own doctorates as the baseline. It did that by scoring
token overlap against the record's SHORT display names, and the short
names are abbreviations, so the scoring went wrong in the worst
direction: it answered confidently and it answered wrongly.

Measured on 2026-10-14, against the 106 keys in the record:

  University of California-Berkeley     -> caltech
  University of Arizona                 -> nau        (Northern Arizona)
  University of Texas at Austin         -> unt        (U North Texas)
  Florida State University              -> uf         (U Florida)
  Michigan Technological University     -> msu        (Michigan State)
  Washington University in St Louis     -> uw_seattle (UW Seattle)
  University of Connecticut             -> ""         (no match at all)

"UC Berkeley" tokenises to {berkeley}; "Caltech" to {caltech}; the full
name "California Institute of Technology" to {california}, which is a
subset of "university of california berkeley". Every one of those rows
is a laboratory measured against a department three states away, and
the resulting percentage looks exactly as real as a right one.
CLAUDE.md states the rule it breaks: a false baseline is worse than no
baseline.

HOW IT RESOLVES NOW. pipeline/universities.json carries each key's
IPEDS UNITID, and chat_data/hd_names.csv carries each UNITID's
registered name. That join is exact and it is the authority. A name
resolves if it matches, after normalisation, one of:

  * the registered IPEDS name for the key's UNITID
  * the same with a leading "The" dropped, which is the whole
    difference between "University of Texas at Austin" and the
    registered "The University of Texas at Austin"
  * the key's short display name, which is what the thesis record and
    some crawler rows use
  * the key itself
  * an entry in ALIAS below

Anything else returns "", which means no baseline. Two keys have no
UNITID in the catalogue and are reached through ALIAS alone.

NOTHING HERE GUESSES. A name this file does not know is a name it says
it does not know.
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOGUE = ROOT / "pipeline" / "universities.json"
HD_NAMES = ROOT / "cloud" / "chat" / "chat_data" / "hd_names.csv"

#: Names no join reaches. Each one is here because a person checked it.
ALIAS = {
    #: mines and cuny carry no UNITID in the catalogue.
    "colorado school of mines": "mines",
    "co school of mines": "mines",
    "cuny graduate center": "cuny",
    "city university of new york": "cuny",
    "cuny grad center": "cuny",
    #: Spellings the crawlers produced that are not the registered name.
    "stanford": "stanford",
    "uw seattle": "uw_seattle",
    "georgia tech": "gatech",
    "mit": "mit",
    "uc santa barbara": "ucsb",
    "uc san diego": "ucsd",
    "u delaware": "udel",
}

_MAP: dict = {}


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def _drop_the(s: str) -> str:
    return s[4:] if s.startswith("the ") else s


def _build() -> dict:
    hd: dict = {}
    if HD_NAMES.exists():
        with HD_NAMES.open() as f:
            for row in csv.DictReader(f):
                try:
                    hd[int(row["unitid"])] = row["name"]
                except (KeyError, TypeError, ValueError):
                    continue
    out: dict = {}
    cat = json.loads(CATALOGUE.read_text())
    for key, meta in cat.items():
        unitid = meta.get("unitid")
        official = hd.get(int(unitid)) if unitid else None
        for cand in (official, _drop_the(_norm(official or "")),
                     meta.get("name"), key.replace("_", " ")):
            n = _norm(cand)
            if n:
                out.setdefault(n, key)
    for name, key in ALIAS.items():
        if key in cat:
            out[_norm(name)] = key
    return out


def key_for(name: str, keys: set | None = None) -> str:
    """The record key for an institution name, or "" if unknown.

    `keys` is the set actually present in the dataset being measured; a
    key the catalogue knows but the dataset does not is still no
    baseline.
    """
    global _MAP
    if not _MAP:
        _MAP = _build()
    n = _norm(name)
    k = _MAP.get(n) or _MAP.get(_drop_the(n)) or ""
    if k and keys is not None and k not in keys:
        return ""
    return k


def known() -> dict:
    """The whole table, for a test or a report to walk."""
    global _MAP
    if not _MAP:
        _MAP = _build()
    return dict(_MAP)


_OFFICIAL: dict = {}


def official_name(key: str) -> str:
    """The registered IPEDS name for a record key, or "".

    This is the spelling the published list uses, so that two crawled
    spellings of one university cannot be counted as two.
    """
    global _OFFICIAL
    if not _OFFICIAL:
        hd: dict = {}
        if HD_NAMES.exists():
            with HD_NAMES.open() as f:
                for row in csv.DictReader(f):
                    try:
                        hd[int(row["unitid"])] = row["name"]
                    except (KeyError, TypeError, ValueError):
                        continue
        for k, meta in json.loads(CATALOGUE.read_text()).items():
            unitid = meta.get("unitid")
            name = hd.get(int(unitid)) if unitid else None
            _OFFICIAL[k] = name or meta.get("name") or k
    return _OFFICIAL.get(key, "")
