#!/usr/bin/env python3
"""
Build the compact data artifacts that get bundled into the chat Lambda zip.

Outputs (into cloud/chat/chat_data/ by default):

  universities_compact.json  per-university scalars + short series + a top-N
                             department digest, distilled from
                             site/data/{stem,nonstem}/{key}.json
  national_series.json       the national series that today live only as
                             `const` arrays inside site/departments-stem.html and
                             site/pipeline.html
  hd_names.csv               unitid,name,state for every institution that
                             appears in data/ipeds/nra_index.csv.gz

WHY A DIGEST AND NOT THE FULL PAYLOADS
--------------------------------------
site/data/stem/ is ~216 MB.  95%+ of each per-university file is its `records`
array (one row per dissertation: department, year, author name, name-origin
class, confidence, title, repository URL, degree).  Three reasons not to ship
it:

  1. Size.  mit.json alone is 2.9 MB and _search.json is 20 MB; the whole
     directory would not fit a Lambda zip, let alone a warm-start budget.
  2. It is the wrong shape.  A chat answer needs aggregates, not 14,203 rows.
     The raw rows already have a first-class home: query.html runs SQL over
     them in the browser, which is what suggest_query points at.
  3. Safety.  Titles and author names are scraped repository metadata — the
     largest untrusted-text surface in the project, and the one place a
     prompt-injection string could be sitting today.  Aggregating to
     (department, count, share) discards the free text entirely.

So: scalars, short series, and the top 25 departments by record count.  Roughly
0.3 MB for all 106 universities.

Usage:
    python3 scripts/build_chat_facts.py
    python3 scripts/build_chat_facts.py --out-dir /some/where
"""
from __future__ import annotations

import argparse
import collections
import csv
import gzip
import json
import os
import re
import sys
from atomic_write import write_json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")
IPEDS = os.path.join(ROOT, "data", "ipeds")
DEFAULT_OUT = os.path.join(ROOT, "cloud", "chat", "chat_data")

sys.path.insert(0, os.path.join(ROOT, "scripts"))

TOP_DEPARTMENTS = 25
TOP_LCA_TITLES = 10
# Name-origin classes that are neither "American-sounding" nor a usable signal.
NOT_CLASSIFIED = {"excluded_ambiguous", "unknown", ""}
DOMESTIC_CLASS = "other"


# ---------------------------------------------------------------------------
# key -> UNITID
# ---------------------------------------------------------------------------
def key_to_unitid() -> dict:
    """Reuse the mapping that pipeline step 4 uses; never redefine it here."""
    src = os.path.join(ROOT, "scripts", "enrich_university_json.py")
    text = open(src, encoding="utf-8").read()
    m = re.search(r"KEY_TO_UNITID\s*=\s*\{(.*?)\n\}", text, re.S)
    if not m:
        raise SystemExit("could not find KEY_TO_UNITID in enrich_university_json.py")
    out = {}
    for k, v in re.findall(r"'([a-z0-9_]+)'\s*:\s*(\d+)", m.group(1)):
        out[k] = str(v)
    return out


# ---------------------------------------------------------------------------
# per-university digest
# ---------------------------------------------------------------------------
def _departments(records: list) -> list:
    """(department, n, foreign_name_pct, top foreign-origin class)."""
    agg = collections.defaultdict(lambda: collections.Counter())
    for r in records:
        if not r:
            continue
        dept = str(r[0])[:60] if r[0] else "(unspecified)"
        cls = str(r[3]) if len(r) > 3 and r[3] else ""
        agg[dept][cls] += 1
    out = []
    for dept, counter in agg.items():
        classified = sum(n for c, n in counter.items() if c not in NOT_CLASSIFIED)
        foreign = sum(n for c, n in counter.items()
                      if c not in NOT_CLASSIFIED and c != DOMESTIC_CLASS)
        total = sum(counter.values())
        top = [c for c, _ in counter.most_common()
               if c not in NOT_CLASSIFIED and c != DOMESTIC_CLASS]
        out.append({
            "name": dept,
            "records": total,
            "classified": classified,
            "foreign_name_pct": round(foreign / classified * 100, 1) if classified else None,
            "top_origin": top[0] if top else None,
        })
    out.sort(key=lambda d: -d["records"])
    return out[:TOP_DEPARTMENTS]


def _origins(records: list) -> dict:
    c = collections.Counter(
        str(r[3]) for r in records if len(r) > 3 and r[3] and str(r[3]) not in NOT_CLASSIFIED
    )
    return dict(c.most_common(12))


def _year_range(records: list):
    years = [r[1] for r in records if len(r) > 1 and isinstance(r[1], int)]
    return (min(years), max(years)) if years else (None, None)


def digest_university(key: str, stem: dict, nonstem: dict | None, unitid: str | None) -> dict:
    recs = stem.get("records") or []
    lo, hi = _year_range(recs)
    d = {
        "key": key,
        "name": stem.get("name", key),
        "url": f"/universities/{key}.html",
        "records": len(recs),
        "record_years": [lo, hi],
        "nra_site_figure": stem.get("nra"),
        "departments": _departments(recs),
        "name_origins": _origins(recs),
    }
    if unitid:
        d["unitid"] = unitid
    if nonstem:
        d["nonstem_records"] = len(nonstem.get("records") or [])

    ct = stem.get("completions_trend")
    if ct and ct.get("years"):
        d["completions_trend"] = {
            "years": ct["years"],
            "phd_total": ct.get("phd_total"),
            "phd_nra": ct.get("phd_nra"),
            "phd_stem_total": ct.get("phd_stem_total"),
            "phd_stem_nra": ct.get("phd_stem_nra"),
            "phd_nra_share": [
                round(n / t * 100, 1) if t else None
                for n, t in zip(ct.get("phd_nra") or [], ct.get("phd_total") or [])
            ],
        }

    opt = stem.get("opt")
    if opt:
        d["opt"] = {
            y: {
                "opt_students": (v.get("opt") or {}).get("students_employed"),
                "stem_opt_students": (v.get("stem_opt") or {}).get("students_employed"),
                "opt_rank": (v.get("opt") or {}).get("rank"),
            }
            for y, v in sorted(opt.items())
        }

    h1b = stem.get("h1b")
    if h1b:
        d["h1b"] = [{"year": r[0], "petitions": r[1], "approvals": r[2]}
                    for r in h1b if isinstance(r, list) and len(r) >= 3]

    lca = stem.get("lca")
    if lca:
        # title_wages is kept whole (~0.8 MB across all universities): the
        # wages_for tool answers "what does this university pay a <title>",
        # and a trimmed top-N list cannot answer for a title outside it.
        d["lca"] = {
            "total_lcas": lca.get("total_lcas"),
            "wage_median": lca.get("wage_median"),
            "wage_25th": lca.get("wage_25th"),
            "wage_75th": lca.get("wage_75th"),
            "yearly": lca.get("yearly"),
            "top_titles": (lca.get("top_titles") or [])[:TOP_LCA_TITLES],
            "top_soc": (lca.get("top_soc") or [])[:TOP_LCA_TITLES],
            "title_wages": lca.get("title_wages") or {},
        }

    for src, dst in (("perm", "perm"), ("enrollment_ipeds", "enrollment_ipeds"),
                     ("faculty", "faculty"), ("tuition", "tuition")):
        v = stem.get(src)
        if v:
            keep = {k: x for k, x in v.items() if not isinstance(x, (list, dict))}
            d[dst] = keep

    perm = stem.get("perm")
    if perm and perm.get("top_titles"):
        d["perm"]["top_titles"] = perm["top_titles"][:TOP_LCA_TITLES]

    enr = stem.get("enrollment")
    if enr:
        d["enrollment_gss"] = {k: v for k, v in enr.items() if not isinstance(v, (list, dict))}
        if enr.get("by_field"):
            d["enrollment_gss"]["by_field"] = enr["by_field"][:10]

    fund = stem.get("funding")
    if fund:
        d["funding"] = {"rank": fund.get("rank"), "rd": fund.get("rd")}

    fed = stem.get("federal_support")
    if fed:
        d["federal_support"] = {
            k: fed.get(k) for k in
            ("fiscal_year", "rank", "all_federal_obligations", "rd",
             "fellowships_traineeships_training")
        }

    nsf, nih = stem.get("nsf_awards"), stem.get("nih")
    if nsf:
        d["nsf_awards"] = {"total_awards": nsf.get("total_awards"),
                           "total_obligated": nsf.get("total_obligated")}
    if nih:
        d["nih"] = {"total_grants": nih.get("total_grants"),
                    "total_dollars": nih.get("total_dollars")}
    return d


def build_universities(out_dir: str) -> str:
    k2u = key_to_unitid()
    stem_dir = os.path.join(SITE, "data", "stem")
    nonstem_dir = os.path.join(SITE, "data", "nonstem")
    out = {}
    for name in sorted(os.listdir(stem_dir)):
        if not name.endswith(".json") or name.startswith("_"):
            continue
        key = name[:-5]
        with open(os.path.join(stem_dir, name), encoding="utf-8") as fh:
            stem = json.load(fh)
        ns = None
        ns_path = os.path.join(nonstem_dir, name)
        if os.path.exists(ns_path):
            with open(ns_path, encoding="utf-8") as fh:
                ns = json.load(fh)
        out[key] = digest_university(key, stem, ns, k2u.get(key))
    path = os.path.join(out_dir, "universities_compact.json")
    write_json(path, out, separators=(",", ":"), ensure_ascii=False)
    print(f"universities_compact.json: {len(out)} universities, "
          f"{os.path.getsize(path)/1024:.0f} KB")
    return path


# ---------------------------------------------------------------------------
# national series, lifted out of the pages that currently own them
# ---------------------------------------------------------------------------
def _js_array(html: str, name: str) -> list:
    """Pull `const NAME = [ ... ];` out of a page.  Raises if absent."""
    m = re.search(r"\bconst\s+" + re.escape(name) + r"\s*=\s*(\[.*?\])\s*;", html, re.S)
    if not m:
        raise SystemExit(f"national series: {name} not found — the page changed shape")
    return json.loads(m.group(1).replace("'", '"'))


def build_national(out_dir: str) -> str:
    stem_html = open(os.path.join(SITE, "departments-stem.html"), encoding="utf-8").read()
    pipe_html = open(os.path.join(SITE, "pipeline.html"), encoding="utf-8").read()

    phd_years = _js_array(stem_html, "phdYears")
    phd_total = _js_array(stem_html, "phdTotal")
    phd_nra = _js_array(stem_html, "phdNRA")
    opt_years = [int(y) for y in _js_array(stem_html, "optYears")]
    visa_years = _js_array(stem_html, "visaYears")

    series = {
        "phd_completions": {
            "title": "STEM PhD completions by citizenship status",
            "unit": "doctorates",
            "years": phd_years,
            "values": {
                "total": phd_total,
                "nra": phd_nra,
                "american": [t - n for t, n in zip(phd_total, phd_nra)],
            },
            "source": "IPEDS Completions (C-series), via departments-stem.html national panel",
        },
        "phd_nra_share": {
            "title": "Non-resident alien share of STEM PhD completions",
            "unit": "percent",
            "years": phd_years,
            "values": {"nra_share": [round(n / t * 100, 1) for n, t in zip(phd_nra, phd_total)]},
            "source": "IPEDS Completions (C-series), via departments-stem.html national panel",
        },
        "opt": {
            "title": "OPT / STEM-OPT / CPT authorisations",
            "unit": "authorisations",
            "years": opt_years,
            "values": {
                "opt": _js_array(stem_html, "optData"),
                "stem_opt": _js_array(stem_html, "stemOpt"),
                "cpt": _js_array(stem_html, "cptData"),
            },
            "source": "ICE/SEVP SEVIS by the Numbers, via departments-stem.html national panel",
        },
        "visa_issuances": {
            "title": "Non-immigrant visa issuances by class",
            "unit": "visas",
            "years": visa_years,
            "values": {
                "f1": _js_array(stem_html, "f1Data"),
                "j1": _js_array(stem_html, "j1Data"),
                "h1b": _js_array(stem_html, "h1bIss"),
                "l1": _js_array(stem_html, "l1Data"),
                "o1": _js_array(stem_html, "o1Data"),
            },
            "source": "US State Department visa statistics, via departments-stem.html national panel",
        },
        "rd_funding": {
            "title": "University R&D spending vs American STEM PhDs",
            "unit": "USD billions / doctorates",
            "years": _js_array(stem_html, "fundYears"),
            "values": {
                "rd_billions": _js_array(stem_html, "rdBillions"),
                "american_phds": [t - n for t, n in zip(phd_total, phd_nra)],
            },
            "source": "NSF HERD + IPEDS Completions, via departments-stem.html national panel",
        },
        "nra_by_field": {
            "title": "NRA share of doctorates by broad field",
            "unit": "percent",
            "categories": _js_array(stem_html, "fieldLabels"),
            "values": {"nra_share": _js_array(stem_html, "fieldPct")},
            "source": "IPEDS Completions, via departments-stem.html national panel",
        },
        "eb_by_country": {
            "title": "Employment-based green cards vs US doctorates, FY2024",
            "unit": "people",
            "categories": _js_array(pipe_html, "ebLabels"),
            "values": {
                "us_phds": _js_array(pipe_html, "ebPhds"),
                "eb_green_cards": _js_array(pipe_html, "ebGreen"),
            },
            "source": "State Department FY2024 + NSF SED, via pipeline.html",
        },
    }
    series["stem_opt"] = {
        "title": "STEM-OPT extensions",
        "unit": "authorisations",
        "years": opt_years,
        "values": {"stem_opt": series["opt"]["values"]["stem_opt"]},
        "source": series["opt"]["source"],
    }
    series["cpt"] = {
        "title": "CPT authorisations",
        "unit": "authorisations",
        "years": opt_years,
        "values": {"cpt": series["opt"]["values"]["cpt"]},
        "source": series["opt"]["source"],
    }

    path = os.path.join(out_dir, "national_series.json")
    write_json(path, series, separators=(",", ":"), ensure_ascii=False)
    print(f"national_series.json: {len(series)} series, {os.path.getsize(path)/1024:.0f} KB")
    return path


# ---------------------------------------------------------------------------
# institution names for the unitids that actually occur in the NRA index
# ---------------------------------------------------------------------------
def _hd_files() -> list:
    out = []
    for name in os.listdir(IPEDS):
        low = name.lower()
        if low.startswith("hd") and low.endswith(".csv") and low[2:6].isdigit():
            out.append((int(low[2:6]), name))
    out.sort(key=lambda t: -t[0])
    return [n for _, n in out]


def build_hd_names(out_dir: str) -> str:
    needed = set()
    with gzip.open(os.path.join(IPEDS, "nra_index.csv.gz"), "rt", encoding="utf-8") as fh:
        for r in csv.reader(fh):
            if r and r[0] != "year":
                needed.add(r[1])
    found = {}
    for fname in _hd_files():
        if not (needed - found.keys()):
            break
        path = os.path.join(IPEDS, fname)
        # The first column header carries a UTF-8 BOM in every IPEDS CSV, so
        # utf-8-sig plus an explicit header normalisation is mandatory here;
        # row.get("UNITID") on a plain DictReader returns None.
        with open(path, encoding="utf-8-sig", errors="replace") as fh:
            reader = csv.reader(fh)
            header = [c.strip().strip('"').upper() for c in next(reader)]
            idx = {c: n for n, c in enumerate(header)}
            iu, ins, ist = idx.get("UNITID"), idx.get("INSTNM"), idx.get("STABBR")
            if iu is None or ins is None:
                continue
            for row in reader:
                if len(row) <= max(iu, ins):
                    continue
                uid = row[iu].strip().strip('"')
                if uid in needed and uid not in found:
                    found[uid] = (
                        row[ins].strip().strip('"'),
                        row[ist].strip().strip('"') if ist is not None and len(row) > ist else "",
                    )
    path = os.path.join(out_dir, "hd_names.csv")
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["unitid", "name", "state"])
        for uid in sorted(found):
            w.writerow([uid, found[uid][0], found[uid][1]])
    print(f"hd_names.csv: {len(found)}/{len(needed)} unitids resolved, "
          f"{os.path.getsize(path)/1024:.0f} KB")
    return path


# ---------------------------------------------------------------------------
# national federal-support context
#
# federal_support_by_university.json gives each university its own FY2023
# obligations but no denominator, so a chat answer can print "$4.4 M of
# training grants" with nothing to compare it against.  The national row and
# the full ranked column live in NSF 25-339 Table 17 itself, so read them
# straight out of the workbook.  Parsed with the standard library (xlsx is a
# zip of XML) so the build does not need openpyxl.
# ---------------------------------------------------------------------------
FED_TAB17 = os.path.join(ROOT, "data", "federal_support", "nsf25339-tab017.xlsx")
FED_COLUMNS = [
    ("all_federal_obligations", "C"),
    ("rd", "D"),
    ("rd_plant", "E"),
    ("facilities_equipment_instruction", "F"),
    ("fellowships_traineeships_training", "G"),
    ("other_general_support", "H"),
]


def _xlsx_rows(path: str) -> list:
    """[{column_letter: value}] for the first worksheet, stdlib only."""
    import zipfile
    from xml.etree import ElementTree as ET

    ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    with zipfile.ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")):
                shared.append("".join(t.text or "" for t in si.iter(ns + "t")))
        sheet = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
    rows = []
    for r in sheet.iter(ns + "row"):
        cells = {}
        for c in r.iter(ns + "c"):
            col = re.match(r"[A-Z]+", c.get("r") or "A").group(0)
            v, t = c.find(ns + "v"), c.get("t")
            if v is None:
                inline = c.find(ns + "is")
                val = ("".join(x.text or "" for x in inline.iter(ns + "t"))
                       if inline is not None else None)
            elif t == "s":
                val = shared[int(v.text)]
            else:
                val = v.text
            cells[col] = val
        rows.append(cells)
    return rows


def _thousands_to_dollars(raw):
    try:
        return int(round(float(raw) * 1000))
    except (TypeError, ValueError):
        return None


def build_federal_context(out_dir: str) -> str | None:
    if not os.path.exists(FED_TAB17):
        print(f"  MISSING {FED_TAB17} — federal_context.json not rebuilt", file=sys.stderr)
        return None
    rows = _xlsx_rows(FED_TAB17)
    national, ranked = None, []
    for cells in rows:
        name = (cells.get("A") or "").strip()
        if name == "All institutions":
            national = {k: _thousands_to_dollars(cells.get(col)) for k, col in FED_COLUMNS}
            continue
        rank = (cells.get("B") or "").strip()
        try:
            rank = int(float(rank))
        except ValueError:
            continue
        ranked.append({
            "rank": rank,
            "institution": name,
            "all_federal_obligations": _thousands_to_dollars(cells.get("C")),
            "fellowships_traineeships_training": _thousands_to_dollars(cells.get("G")),
        })
    if national is None:
        raise SystemExit("Table 17: no 'All institutions' row found")

    fttt = sorted((r["fellowships_traineeships_training"] or 0) for r in ranked)
    fttt.reverse()
    recipients = [v for v in fttt if v > 0]

    def pct(seq, p):
        return seq[int(round((len(seq) - 1) * p))] if seq else None

    top = sorted(ranked, key=lambda r: -(r["fellowships_traineeships_training"] or 0))[:10]
    out = {
        "source": ("NSF NCSES Federal Support Survey, NSF 25-339 Table 17 "
                   "(federal obligations for S&E to universities and colleges, FY 2023)"),
        "source_url": "https://ncses.nsf.gov/pubs/nsf25339",
        "fiscal_year": 2023,
        "units": "US dollars (source reports thousands; converted here)",
        "institutions_ranked": len(ranked),
        "national": national,
        "fttt": {
            "institutions_with_any": len(recipients),
            "median_of_recipients": pct(sorted(recipients), 0.5),
            "p75_of_recipients": pct(sorted(recipients), 0.75),
            "p90_of_recipients": pct(sorted(recipients), 0.90),
            "sorted_desc": fttt,
            "top10": [{"institution": r["institution"],
                       "fellowships_traineeships_training":
                           r["fellowships_traineeships_training"]} for r in top],
        },
    }
    path = os.path.join(out_dir, "federal_context.json")
    write_json(path, out, separators=(",", ":"), ensure_ascii=False)
    print(f"federal_context.json: {len(ranked)} institutions, "
          f"{os.path.getsize(path)/1024:.0f} KB")
    return path


# ---------------------------------------------------------------------------
# straight copies (no transformation, so they stay byte-identical to source)
# ---------------------------------------------------------------------------
COPIES = [
    (os.path.join(IPEDS, "nra_index.csv.gz"), "nra_index.csv.gz"),
    (os.path.join(IPEDS, "cip_titles.csv"), "cip_titles.csv"),
    (os.path.join(SITE, "data", "chat", "site_map.json"), "site_map.json"),
]


def copy_artifacts(out_dir: str):
    import shutil
    for src, name in COPIES:
        if not os.path.exists(src):
            print(f"  MISSING {src} — run scripts/build_site_map.py first?", file=sys.stderr)
            continue
        dst = os.path.join(out_dir, name)
        shutil.copyfile(src, dst)
        print(f"copied {name}: {os.path.getsize(dst)/1024:.0f} KB")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=DEFAULT_OUT)
    ap.add_argument("--only", choices=["universities", "national", "federal", "hd", "copies"],
                    action="append")
    args = ap.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    only = set(args.only or ["universities", "national", "federal", "hd", "copies"])
    if "universities" in only:
        build_universities(args.out_dir)
    if "national" in only:
        build_national(args.out_dir)
    if "federal" in only:
        build_federal_context(args.out_dir)
    if "hd" in only:
        build_hd_names(args.out_dir)
    if "copies" in only:
        copy_artifacts(args.out_dir)
    total = sum(os.path.getsize(os.path.join(args.out_dir, f))
                for f in os.listdir(args.out_dir) if not f.startswith("."))
    print(f"chat_data total: {total/1024/1024:.2f} MB in {args.out_dir}")


if __name__ == "__main__":
    main()
