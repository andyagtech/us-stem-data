#!/usr/bin/env python3
"""One row per institution, so any two can be compared on the same measures.

This project's institution-level findings were scattered across a dozen files
that each answered one question on one basis: degrees here, enrolment there,
federal money somewhere else, each with its own key and its own floor. Nothing
let you take a university and read across, or add institutions up to a state.
This builds that table.

THE JOIN KEY IS UNITID, NOT THE NAME. IPEDS completions, enrolment, tuition
and finance all carry it, and the GSS carries it too. HERD and the Federal
Support Survey do not: NCSES publishes names only, in a house style of its own
('U. Pennsylvania', 'Johns Hopkins U.a'). Those are resolved by exact match on
a normalised token set, falling back to a hand-verified crosswalk. Subset
matching was tried and thrown out -- it maps Florida A&M onto the University of
Florida -- so a name that cannot be resolved is REPORTED UNMATCHED rather than
guessed at, and its dollars are counted in the coverage figures below.

WHAT A ROW DOES NOT MEAN. Nothing here is per-citizenship money. IPEDS reports
tuition revenue without regard to citizenship and NCSES reports obligations
without regard to who they train, so a high federal figure beside a high visa
share is a coincidence of location, not a payment. The per-doctorate column is
an intensity ratio for the same reason -- see federal_per_doctorate below.

SHARES ARE COMPUTED FROM SUMS. A state's foreign share is its foreign count
over its total, never the mean of its institutions' shares, which would let a
department of nine outvote a university of nine thousand.

Usage:
  python3 scripts/build_institution_profiles.py
  python3 scripts/build_institution_profiles.py --report   # match quality
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import statistics
import sys
import warnings
import zipfile
from pathlib import Path

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipeline.models import STEM_NARROW, bases_for           # noqa: E402
from scripts.atomic_write import write_json                  # noqa: E402

IPEDS = ROOT / "data" / "ipeds"
OUT = ROOT / "site" / "data" / "institution_profiles.json"
XWALK = ROOT / "pipeline" / "ncses_crosswalk.json"

# Degrees are counted over windows, not single years: a department that awards
# eleven doctorates swings by a third on one student's timing.
LATE = (2021, 2025)
EARLY = (2010, 2014)

# The per-doctorate ratio reproduces the basis already published on the funding
# page -- FY2023 obligations over the annual rate of core-STEM research
# doctorates 2015-2022 -- so the two figures can be compared directly.
COST_WINDOW = (2015, 2022)
COST_FLOOR = 100          # research doctorates in the window, as published

ENROL_YEAR = 2023
TUITION_YEAR = 2023

# Floors for the ranked lists. An institution with four foreign master's
# students out of five is not the country's most foreign-dependent programme.
FLOORS = {"masters": 100, "doctorate": 40, "graduate_enrolment": 500}

CONTROL = {"1": "public", "2": "private nonprofit", "3": "private for-profit"}


def norm(s: str) -> frozenset:
    """NCSES and IPEDS spellings of one institution, reduced to one token set."""
    s = s.lower().replace("&", " and ")
    s = re.sub(r"\bu\.s\.", "united states", s)
    s = re.sub(r"\bu\.", "university", s)
    s = re.sub(r"\bc\.(?=\s|$)", "college", s)
    s = re.sub(r"\bcoll\.", "college", s)
    s = re.sub(r"\binst\.", "institute", s)
    s = re.sub(r"\btech\.", "technology", s)
    s = re.sub(r"\bst\.", "saint", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    drop = {"of", "the", "at", "campus", "main", "and", "in"}
    return frozenset(("saint" if t == "st" else t)
                     for t in s.split() if t and t not in drop)


def directory() -> dict[str, dict]:
    """UNITID -> identity, from the most recent IPEDS directory file."""
    path = max((p for p in (IPEDS / f"hd{y}.csv" for y in range(2030, 2000, -1))
                if p.exists()), key=lambda p: p.name, default=None)
    if path is None:
        sys.exit("no IPEDS directory (hd*.csv) found")
    out = {}
    with open(path, newline="", encoding="latin-1") as fh:
        for r in csv.DictReader(fh):
            u = r[next(iter(r))].strip()
            out[u] = {"unitid": u, "institution": r["INSTNM"].strip(),
                      "state": r["STABBR"].strip(), "city": r["CITY"].strip(),
                      "control": CONTROL.get(r.get("CONTROL", "").strip(), "unknown")}
    return out, path.name


def completions_path(year: int) -> Path | None:
    """The revised file for a year if IPEDS has issued one, else provisional.

    Filenames mix case across download vintages (c2022_a.csv, C2023_a_RV.csv),
    so every spelling is probed rather than assumed.
    """
    for stem in (f"c{year}_a_rv", f"C{year}_a_RV", f"c{year}_a", f"C{year}_a",
                 f"C{year}_A"):
        p = IPEDS / f"{stem}.csv"
        if p.exists():
            return p
    return None


def degrees(lo: int, hi: int) -> tuple[dict, list[int]]:
    """UNITID -> core-STEM master's and research doctorates, summed over a window.

    MAJORNUM 1 only: IPEDS files a second row for each second major, and
    counting both would award two degrees to one graduate.
    """
    blank = {"masters": [0, 0], "doctorate": [0, 0],
             "all_research_doctorates": [0, 0],
             "all_professional_doctorates": [0, 0]}
    acc: dict[str, dict] = {}
    years = []
    for year in range(lo, hi + 1):
        path = completions_path(year)
        if path is None:
            continue
        years.append(year)
        # The research-doctorate award level is 17 from 2010 and 9 before it,
        # and 2008-09 needs both because institutions migrated one at a time.
        # pipeline.models owns that rule; re-deriving it here is how a window
        # that is moved back a couple of years silently loses a fifth of its
        # doctorates.
        doctoral = {b.removeprefix("aw").lstrip("0") for b in bases_for(year)}
        with open(path, newline="", encoding="utf-8-sig", errors="replace") as fh:
            for r in csv.DictReader(fh):
                if (r.get("MAJORNUM") or "").strip() != "1":
                    continue
                lvl = (r.get("AWLEVEL") or "").strip().lstrip("0")
                if lvl not in ({"7", "18"} | doctoral):
                    continue
                cip2 = (r.get("CIPCODE") or "").split(".")[0].zfill(2)
                # CIP 99 is the institution's own grand total, repeating every
                # detail row. The core-STEM filter happened to exclude it; a
                # count across all fields must exclude it explicitly or every
                # such total comes out exactly twice its true value.
                if cip2 == "99":
                    continue
                stem = cip2 in STEM_NARROW
                try:
                    tot = int(float(r.get("CTOTALT") or 0))
                    nra = int(float(r.get("CNRALT") or 0))
                except ValueError:
                    continue
                rec = acc.setdefault(r["UNITID"].strip(),
                                     {k: list(v) for k, v in blank.items()})
                # 17 is the research doctorate, 18 the professional practice
                # doctorate (MD, DDS, PharmD, JD). The all-field counts carry
                # both because federal obligations fund every field while the
                # per-doctorate denominator counts only core-STEM research
                # doctorates: an institution whose output is overwhelmingly
                # medical will show an enormous ratio without doing anything
                # unusual, and these two columns are what makes that visible.
                if lvl in doctoral:
                    rec["all_research_doctorates"][0] += tot
                    rec["all_research_doctorates"][1] += nra
                elif lvl == "18":
                    rec["all_professional_doctorates"][0] += tot
                    rec["all_professional_doctorates"][1] += nra
                if not stem:
                    continue
                key = "masters" if lvl == "7" else (
                    "doctorate" if lvl in doctoral else None)
                if key:
                    rec[key][0] += tot
                    rec[key][1] += nra
    return acc, years


def enrolment(year: int) -> dict[str, dict]:
    """UNITID -> graduate and total enrolment with non-resident counts.

    EFALEVEL 12 with LSTUDY 3 is the graduate total; EFALEVEL 1 is all
    students. Reading any other level double-counts, because the file carries
    full-time and part-time breakdowns of the same people.
    """
    src = IPEDS / "enrollment" / f"EF{year}A.zip"
    if not src.exists():
        return {}
    out: dict[str, dict] = {}
    with zipfile.ZipFile(src) as z:
        inner = next(n for n in z.namelist() if n.lower().endswith(".csv"))
        rd = csv.DictReader(io.TextIOWrapper(z.open(inner), encoding="latin-1"))
        for r in rd:
            lvl, study = r["EFALEVEL"].strip(), r["LSTUDY"].strip()
            if (lvl, study) not in (("12", "3"), ("1", "4")):
                continue
            try:
                tot = int(float(r.get("EFTOTLT") or 0))
                nra = int(float(r.get("EFNRALT") or 0))
            except ValueError:
                continue
            rec = out.setdefault(r["UNITID"].strip(), {})
            rec["graduate" if lvl == "12" else "total"] = (tot, nra)
    return out


def tuition(year: int) -> dict[str, int]:
    """UNITID -> published out-of-state graduate tuition.

    Out-of-state is the rate a foreign student pays; the in-state rate is not
    available to them at any public institution.
    """
    for name in (f"ic{year}_ay_rv.csv", f"ic{year}_ay.csv"):
        path = ROOT / "data" / "ipeds_tuition" / name
        if path.exists():
            break
    else:
        return {}
    out = {}
    with open(path, newline="", encoding="latin-1") as fh:
        for r in csv.DictReader(fh):
            try:
                v = int(float(r.get("TUITION7") or 0))
            except ValueError:
                continue
            if v > 0:
                out[r[next(iter(r))].strip()] = v
    return out


def gss_shares() -> dict[str, dict]:
    """UNITID -> foreign share of full-time S&E graduate enrolment, by level."""
    path = ROOT / "site" / "data" / "gss_institution_ranking.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    out = {}
    for rec in data.get("institutions", []):
        u = str(rec.get("unitid") or "")
        if not u.isdigit():
            continue
        out[u] = {lvl: rec[lvl]["share"] for lvl in ("doctoral", "master's")
                  if isinstance(rec.get(lvl), dict) and rec[lvl].get("total")}
    return out


def tuition_dependence() -> dict[str, float]:
    """UNITID -> tuition as a share of revenue, from the existing build.

    Public and private are never pooled there and are not pooled here; the
    figure is only ever compared within a sector.
    """
    path = ROOT / "site" / "data" / "tuition_dependence.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    out = {}
    for sector in data.get("sectors", {}).values():
        # That build publishes ranked extracts rather than the full sector, so
        # every list in it is scanned and only the institutions it names carry
        # a ratio here. Absent is absent, not zero.
        for value in sector.values():
            if not isinstance(value, list):
                continue
            for rec in value:
                if isinstance(rec, dict) and rec.get("unitid"):
                    out[str(rec["unitid"])] = rec.get("tuition_share_pct")
    return out


def ncses_table(path: Path, sheet: str, columns: dict[str, int]) -> list[dict]:
    """Rows of an NCSES ranked table, with the header and footnote furniture cut."""
    import openpyxl
    ws = openpyxl.load_workbook(path, read_only=True, data_only=True)[sheet]
    skip = ("table", "higher education", "federal obligations", "(dollars",
            "institution", "all institutions", "source:", "note")
    out = []
    for row in ws.iter_rows(values_only=True):
        name = row[0]
        if not isinstance(name, str) or not name.strip():
            continue
        name = name.strip()
        if name.lower().startswith(skip):
            continue
        rec = {"name": name}
        for key, idx in columns.items():
            v = row[idx] if idx < len(row) else None
            rec[key] = int(v) if isinstance(v, (int, float)) else None
        out.append(rec)
    return out


def resolve(rows: list[dict], names: dict[str, str], xwalk: dict) -> tuple[dict, list]:
    """NCSES rows -> UNITID, by exact normalised match then hand-verified alias.

    Two rows may legitimately resolve to one UNITID (IPEDS files Denver and
    Anschutz as a single unit while HERD files them separately). Those are
    summed, and the fact is recorded on the profile.
    """
    index: dict[frozenset, set] = {}
    for u, n in names.items():
        index.setdefault(norm(n), set()).add(u)

    resolved: dict[str, list] = {}
    unmatched = []
    for rec in rows:
        raw = rec["name"]
        stripped = re.sub(r"(?<=[.a-z])[a-z]$", "", raw)
        entry = xwalk.get(raw) or xwalk.get(stripped)
        if entry is not None:
            if entry.get("unitid"):
                resolved.setdefault(entry["unitid"], []).append((rec, entry))
            else:
                unmatched.append({"name": raw, "reason": entry["kind"],
                                  "value": rec.get("primary")})
            continue
        hit = None
        for cand in (raw, stripped):
            got = index.get(norm(cand), set())
            if len(got) == 1:
                hit = next(iter(got))
                break
        if hit:
            resolved.setdefault(hit, []).append((rec, {"kind": "campus"}))
        else:
            unmatched.append({"name": raw, "reason": "no exact match",
                              "value": rec.get("primary")})
    return resolved, unmatched


def pct(part: int, whole: int) -> float | None:
    return round(part / whole * 100, 1) if whole else None


def rank_lists(profiles: list[dict]) -> dict:
    """National rank on each measure, among institutions that clear its floor."""
    def deg(level, field):
        # share_change is absent where the early window has no degrees at all,
        # which is the common case for a programme founded since 2014.
        return lambda p: p[level].get(field)

    def grad(field):
        return lambda p: (p.get("graduate_enrolment") or {}).get(field)

    def fed(field):
        return lambda p: (p.get("federal") or {}).get(field)

    # (name, accessor, gate) -- the gate names which count must clear its floor
    # for the institution to be ranked at all. Ranking a share without one puts
    # a programme of five at the top of the country.
    specs = [
        ("stem_masters_awarded", deg("masters", "awarded"), "masters"),
        ("stem_masters_non_resident", deg("masters", "non_resident"), "masters"),
        ("stem_masters_non_resident_share", deg("masters", "share"), "masters"),
        ("stem_masters_share_change", deg("masters", "share_change"), "masters"),
        ("stem_doctorates_awarded", deg("doctorate", "awarded"), "doctorate"),
        ("stem_doctorates_non_resident", deg("doctorate", "non_resident"), "doctorate"),
        ("stem_doctorates_non_resident_share", deg("doctorate", "share"), "doctorate"),
        ("stem_doctorates_share_change", deg("doctorate", "share_change"), "doctorate"),
        ("graduate_non_resident", grad("non_resident"), None),
        ("graduate_non_resident_share", grad("share"), "graduate_enrolment"),
        ("federal_obligations", fed("obligations"), None),
        ("federal_rd", fed("rd_federal"), None),
        ("federal_training", fed("training"), None),
        ("federal_per_doctorate", lambda p: p.get("federal_per_doctorate"), None),
        ("graduate_tuition_out_of_state",
         lambda p: p.get("graduate_tuition_out_of_state"), None),
    ]
    gate_value = {
        "masters": lambda p: p["masters"]["awarded"],
        "doctorate": lambda p: p["doctorate"]["awarded"],
        "graduate_enrolment": lambda p: (p.get("graduate_enrolment") or {}).get("total") or 0,
    }
    out = {}
    for name, get, gate in specs:
        rows = []
        for p in profiles:
            v = get(p)
            if v is None:
                continue
            if gate and gate_value[gate](p) < FLOORS[gate]:
                continue
            rows.append((v, p))
        rows.sort(key=lambda t: -t[0])
        out[name] = [{"rank": i + 1, "unitid": p["unitid"],
                      "institution": p["institution"], "state": p["state"],
                      "value": v} for i, (v, p) in enumerate(rows[:50])]
        for i, (v, p) in enumerate(rows):
            p.setdefault("ranks", {})[name] = i + 1
        out[name + "__ranked"] = len(rows)
    return out


def by_state(profiles: list[dict]) -> list[dict]:
    """Institutions summed to their state. Shares recomputed from the sums."""
    acc: dict[str, dict] = {}
    for p in profiles:
        st = acc.setdefault(p["state"], {
            "state": p["state"], "institutions": 0,
            "masters_awarded": 0, "masters_non_resident": 0,
            "doctorates_awarded": 0, "doctorates_non_resident": 0,
            "graduate_enrolment": 0, "graduate_non_resident": 0,
            "federal_obligations": 0, "federal_rd": 0, "federal_training": 0,
            "institutions_with_federal": 0})
        st["institutions"] += 1
        st["masters_awarded"] += p["masters"]["awarded"]
        st["masters_non_resident"] += p["masters"]["non_resident"]
        st["doctorates_awarded"] += p["doctorate"]["awarded"]
        st["doctorates_non_resident"] += p["doctorate"]["non_resident"]
        ge = p.get("graduate_enrolment") or {}
        st["graduate_enrolment"] += ge.get("total") or 0
        st["graduate_non_resident"] += ge.get("non_resident") or 0
        fed = p.get("federal") or {}
        if fed:
            st["institutions_with_federal"] += 1
            for k, src in (("federal_obligations", "obligations"),
                           ("federal_rd", "rd_federal"),
                           ("federal_training", "training")):
                st[k] += fed.get(src) or 0
    out = []
    for st in acc.values():
        st["masters_non_resident_share"] = pct(st["masters_non_resident"], st["masters_awarded"])
        st["doctorates_non_resident_share"] = pct(st["doctorates_non_resident"], st["doctorates_awarded"])
        st["graduate_non_resident_share"] = pct(st["graduate_non_resident"], st["graduate_enrolment"])
        st["federal_per_doctorate"] = (
            round(st["federal_obligations"] / (st["doctorates_awarded"] / 5))
            if st["doctorates_awarded"] else None)
        out.append(st)
    out.sort(key=lambda s: -s["masters_awarded"])
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()

    ident, hd_name = directory()
    late, late_years = degrees(*LATE)
    early, _ = degrees(*EARLY)
    cost, cost_years = degrees(*COST_WINDOW)
    enrol = enrolment(ENROL_YEAR)
    tui = tuition(TUITION_YEAR)
    gss = gss_shares()
    dep = tuition_dependence()
    xwalk = json.loads(XWALK.read_text())["entries"]
    names = {u: v["institution"] for u, v in ident.items()}

    herd_rows = ncses_table(ROOT / "data" / "herd" / "herd_fy2024_table14.xlsx",
                            "Table 14", {"primary": 2, "federal": 4})
    fed_rows = ncses_table(ROOT / "data" / "federal_support" / "nsf25339-tab017.xlsx",
                           "Table 17", {"primary": 2, "rd": 3, "training": 6})
    herd_by_unit, herd_unmatched = resolve(herd_rows, names, xwalk)
    fed_by_unit, fed_unmatched = resolve(fed_rows, names, xwalk)

    profiles = []
    for u, base in ident.items():
        d_late = late.get(u)
        d_early = early.get(u)
        e = enrol.get(u, {})
        h = herd_by_unit.get(u)
        f = fed_by_unit.get(u)
        if not (d_late or e.get("graduate") or h or f):
            continue
        p = dict(base)
        for key, src in (("masters", "masters"), ("doctorate", "doctorate"),
                         ("all_research_doctorates", "all_research_doctorates"),
                         ("all_professional_doctorates", "all_professional_doctorates")):
            tot, nra = (d_late or {}).get(src, [0, 0])
            p[key] = {"awarded": tot, "non_resident": nra, "share": pct(nra, tot)}
            if d_early:
                et, en = d_early.get(src, [0, 0])
                p[key]["early_share"] = pct(en, et)
                p[key]["early_awarded"] = et
                if p[key]["share"] is not None and p[key]["early_share"] is not None:
                    p[key]["share_change"] = round(p[key]["share"] - p[key]["early_share"], 1)
        if e.get("graduate"):
            t, n = e["graduate"]
            p["graduate_enrolment"] = {"total": t, "non_resident": n, "share": pct(n, t)}
        if e.get("total"):
            t, n = e["total"]
            p["total_enrolment"] = {"total": t, "non_resident": n, "share": pct(n, t)}
        if u in gss:
            p["gss_foreign_share"] = gss[u]
        if u in tui:
            p["graduate_tuition_out_of_state"] = tui[u]
        if u in dep and dep[u] is not None:
            p["tuition_share_of_revenue"] = dep[u]

        fed_rec = {}
        kinds = set()
        if h:
            fed_rec["rd_total"] = sum((r["primary"] or 0) * 1000 for r, _ in h)
            fed_rec["rd_federal"] = sum((r["federal"] or 0) * 1000 for r, _ in h)
            kinds |= {e_["kind"] for _, e_ in h}
            if len(h) > 1:
                fed_rec["herd_rows_summed"] = [r["name"] for r, _ in h]
        if f:
            fed_rec["obligations"] = sum((r["primary"] or 0) * 1000 for r, _ in f)
            fed_rec["training"] = sum((r["training"] or 0) * 1000 for r, _ in f)
            kinds |= {e_["kind"] for _, e_ in f}
            if len(f) > 1:
                fed_rec["federal_support_rows_summed"] = [r["name"] for r, _ in f]
        if fed_rec:
            fed_rec["match_kind"] = sorted(kinds)
            p["federal"] = fed_rec

        c = (cost.get(u) or {}).get("doctorate", [0, 0])
        if fed_rec.get("obligations") and c[0] >= COST_FLOOR:
            per_year = c[0] / (COST_WINDOW[1] - COST_WINDOW[0] + 1)
            p["federal_per_doctorate"] = round(fed_rec["obligations"] / per_year)
            p["cost_basis_doctorates"] = c[0]
            allr = (cost.get(u) or {}).get("all_research_doctorates", [0, 0])[0]
            allp = (cost.get(u) or {}).get("all_professional_doctorates", [0, 0])[0]
            p["cost_basis_share_of_all_doctorates"] = pct(c[0], allr)
            p["cost_basis_professional_doctorates"] = allp
        profiles.append(p)

    ranks = rank_lists(profiles)
    states = by_state(profiles)

    per_doc = [p["federal_per_doctorate"] for p in profiles
               if p.get("federal_per_doctorate")]
    herd_total = sum(r["primary"] or 0 for r in herd_rows)
    fed_total = sum(r["primary"] or 0 for r in fed_rows)

    out = {
        "_comment": [
            "One row per institution, keyed on IPEDS UNITID, so any two can be",
            "compared and any group can be added up to a state.",
            "",
            "COVERAGE IS UNEVEN AND THE ROW SAYS SO. An institution appears if it",
            "has any of: core-STEM graduate degrees in the late window, graduate",
            "enrolment, or federal money. Fields it has no data for are absent",
            "rather than zero, because a missing HERD row means an institution was",
            "not surveyed, not that it spent nothing on research.",
            "",
            "federal_per_doctorate IS AN INTENSITY RATIO, NOT A PRICE. Federal",
            "obligations fund research whose outputs include papers, instruments,",
            "facilities and staff, not only degrees. It shows the scale of public",
            "research money moving through an institution relative to the",
            "doctorates it produces; it does not establish that the public paid",
            "that sum for any particular degree.",
            "",
            "NON-RESIDENT IS A VISA CATEGORY, NOT A BIRTHPLACE. A naturalised",
            "citizen or permanent resident is counted as domestic throughout, so",
            "every share here is a floor on the foreign-born proportion.",
            "",
            "match_kind ON THE FEDERAL BLOCK SAYS WHAT THE MONEY COVERS.",
            "campus_plus_affiliate folds in a hospital that enrols nobody;",
            "multi_campus spans units that report degrees separately;",
            "system_office rows have no students at all. Per-doctorate ratios on",
            "those rows are correspondingly loose.",
        ],
        "sources": {
            "degrees": f"IPEDS Completions {late_years[0]}-{late_years[-1]}, "
                       f"CIP {', '.join(STEM_NARROW)}, MAJORNUM 1",
            "enrolment": f"IPEDS Fall Enrollment {ENROL_YEAR}",
            "tuition": f"IPEDS IC {TUITION_YEAR} academic-year charges (TUITION7)",
            "directory": f"IPEDS {hd_name}",
            "federal_rd": "NSF HERD FY2024 Table 14",
            "federal_obligations": "NSF Federal Support Survey FY2023 (NSF 25-339 Table 17)",
            "gss": "NSF GSS 2024",
        },
        "windows": {"late": list(LATE), "late_years_present": late_years,
                    "early": list(EARLY), "cost_basis": list(COST_WINDOW)},
        "floors": FLOORS,
        "coverage": {
            "institutions": len(profiles),
            "with_late_degrees": sum(1 for p in profiles if p["masters"]["awarded"]
                                     or p["doctorate"]["awarded"]),
            "with_graduate_enrolment": sum(1 for p in profiles if p.get("graduate_enrolment")),
            "with_federal": sum(1 for p in profiles if p.get("federal")),
            "with_per_doctorate": len(per_doc),
            "with_gss": sum(1 for p in profiles if p.get("gss_foreign_share")),
            "with_tuition": sum(1 for p in profiles if p.get("graduate_tuition_out_of_state")),
        },
        "crosswalk": {
            "herd_rows": len(herd_rows), "herd_resolved": sum(len(v) for v in herd_by_unit.values()),
            "herd_unmatched": len(herd_unmatched),
            "herd_unmatched_dollars_pct": round(
                sum(u["value"] or 0 for u in herd_unmatched) / herd_total * 100, 1) if herd_total else None,
            "federal_support_rows": len(fed_rows),
            "federal_support_resolved": sum(len(v) for v in fed_by_unit.values()),
            "federal_support_unmatched": len(fed_unmatched),
            "federal_support_unmatched_dollars_pct": round(
                sum(u["value"] or 0 for u in fed_unmatched) / fed_total * 100, 1) if fed_total else None,
            "largest_unmatched": sorted(
                [u for u in herd_unmatched + fed_unmatched if u["value"]],
                key=lambda u: -u["value"])[:15],
        },
        "national_per_doctorate": {
            "count": len(per_doc),
            "median": round(statistics.median(per_doc)) if per_doc else None,
            "note": "Every institution nationally that clears the floor, so this "
                    "is a wider population than the figure quoted on the funding "
                    "page, which covers this project's own university set.",
        },
        "rankings": {k: v for k, v in ranks.items() if not k.endswith("__ranked")},
        "ranked_counts": {k[:-len("__ranked")]: v for k, v in ranks.items()
                          if k.endswith("__ranked")},
        "states": states,
        "institutions": sorted(profiles, key=lambda p: p["institution"]),
    }
    write_json(OUT, out)
    print(f"  wrote {OUT.relative_to(ROOT)}: {len(profiles):,} institutions, "
          f"{len(states)} states")
    print(f"  federal matched: HERD {out['crosswalk']['herd_unmatched_dollars_pct']}% "
          f"of dollars unmatched, Federal Support "
          f"{out['crosswalk']['federal_support_unmatched_dollars_pct']}%")
    if args.report:
        for u in out["crosswalk"]["largest_unmatched"]:
            print(f"    ${(u['value'] or 0)/1000:,.0f}M  {u['name']}  [{u['reason']}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
