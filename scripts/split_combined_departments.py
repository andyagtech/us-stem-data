#!/usr/bin/env python3
"""Recover the real degree from a repository record page.

THE PROBLEM. Missouri S&T awards through a department it calls
"Geosciences and Geological and Petroleum Engineering". The harvest
recorded that name, so 413 dissertations sit in one bucket and the site
cannot say how many are petroleum and how many are earth science. The
same shape appears 69 times across the corpus: "Mechanical & Aerospace
Eng", "Mining & Nuclear Eng", "Electrical Engineering and Computer
Science".

THE FIX IS NOT A KEYWORD GUESS AT THE TITLE. "Fabrication of
micro-/nanofluidic models and their applications for enhanced oil
recovery" reads as petroleum to a person and would read as materials
science to a regular expression, and guessing would put a number on
the page that nobody could check.

The university already publishes the answer. Every Scholars' Mine
record carries a Degree Name field -- "Ph. D. in Petroleum
Engineering" -- which is the degree conferred, not the department that
houses it. This fetches that field for each record and reports the
split. It is slow because it is one request per dissertation, and it
is exact because it is the registrar's own words.

Usage:
  python3 scripts/split_combined_departments.py --university missouri_st \
      --department "Geosciences & Geo/Petroleum Eng"
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import duckdb
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from atomic_write import write_text                            # noqa: E402

OUT = ROOT / "data" / "labs" / "degree_splits.json"
PARQUET = ROOT / "site" / "data" / "exports" / "stem_records.parquet"
UA = {"User-Agent": "phd-demographics research; one request per record"}

#: bepress repositories label it this way; a few sites vary the wording
DEGREE = [
    re.compile(r"Degree Name</[^>]*>\s*<[^>]*>\s*([^<]{4,90})", re.I | re.S),
    re.compile(r"Degree\s*Name[^<]*</\w+>\s*([^<]{4,90})", re.I | re.S),
    re.compile(r'name="bepress_citation_dissertation_name"[^>]*'
               r'content="([^"]{4,90})"', re.I),
]


def degree_of(url: str) -> str | None:
    try:
        r = requests.get(url, headers=UA, timeout=25)
    except requests.RequestException:
        return None
    if r.status_code != 200:
        return None
    for pat in DEGREE:
        m = pat.search(r.text)
        if m:
            d = " ".join(m.group(1).split())
            #: "Ph. D. in Petroleum Engineering" -> "Petroleum Engineering"
            d = re.sub(r"^.*?\bin\s+", "", d).strip(" .")
            if 3 < len(d) < 70:
                return d
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--university", required=True)
    ap.add_argument("--department", required=True)
    ap.add_argument("--limit", type=int, default=450)
    ap.add_argument("--workers", type=int, default=5)
    a = ap.parse_args()

    rows = duckdb.sql(f"""
        SELECT year, name, title, url FROM '{PARQUET}'
        WHERE university = '{a.university}'
          AND department = '{a.department.replace("'", "''")}'
          AND url IS NOT NULL AND url <> ''
        ORDER BY year DESC""").fetchall()
    rows = rows[: a.limit]
    print(f"Reading the degree field from {len(rows)} record pages")
    print("  one request each, so this is slow on purpose\n")

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        degrees = list(ex.map(lambda r: degree_of(r[3]), rows))

    got = [d for d in degrees if d]
    counts = Counter(got)
    print(f"  {len(got)} of {len(rows)} records carried a degree name "
          f"in {time.time() - t0:.0f}s\n")
    for d, n in counts.most_common(14):
        print(f"    {n:>4}  {d}")

    payload = {
        "university": a.university,
        "department_as_harvested": a.department,
        "why": ("The department name bundles several fields. This is the "
                "DEGREE CONFERRED, taken one record at a time from the "
                "university's own repository, so the split is the "
                "registrar's and not an inference from the title."),
        "records": len(rows),
        "with_degree": len(got),
        "coverage_pct": round(len(got) / max(len(rows), 1) * 100, 1),
        "degrees": dict(counts.most_common()),
        "rows": [{"year": r[0], "name": r[1], "url": r[3], "degree": d}
                 for r, d in zip(rows, degrees) if d],
    }
    existing = {}
    if OUT.exists():
        existing = json.loads(OUT.read_text())
    existing[f"{a.university}|{a.department}"] = payload
    write_text(OUT, json.dumps(existing, indent=1))
    print(f"\n  wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
