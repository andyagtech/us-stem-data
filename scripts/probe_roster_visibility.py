#!/usr/bin/env python3
"""Can you see who is in a federally funded lab? Sector by sector.

THE FINDING THIS WAS WRITTEN TO TEST. Harvesting rosters for the
access-regime sectors kept coming back with faculty and no students, while
the same harvester pulled 82 members off a computer-vision lab at
Washington without trouble. Either that is four unlucky pages or it is a
property of those fields, and the difference matters: if a nuclear
programme's doctoral body is 72% non-resident by IPEDS and the department
publishes no student roster, the composition of an access-controlled
programme is not auditable from the outside at all.

WHAT IT MEASURES. For each institution, whether a page exists that names
graduate students, and whether anything on the department's site does. It
does not count people and does not classify anyone. It answers one
question: is the roster visible?

Usage:
  python3 scripts/probe_roster_visibility.py
  python3 scripts/probe_roster_visibility.py --sector nuclear
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from atomic_write import write_text                            # noqa: E402

OUT = ROOT / "data" / "labs" / "roster_visibility.json"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0 Safari/537.36")

#: Department sites per sector. Hand-declared, because guessing a
#: university's department hostname produces 404s at scale and a 404 would
#: be scored as "no roster" when it only means "wrong URL".
SITES = {
    "nuclear": [
        ("Missouri S&T", "https://nuclear.mst.edu"),
        ("UIUC", "https://npre.illinois.edu"),
        ("NC State", "https://ne.ncsu.edu"),
        ("Texas A&M", "https://engineering.tamu.edu/nuclear"),
        ("Michigan", "https://ners.engin.umich.edu"),
        ("Wisconsin", "https://ep.wisc.edu"),
    ],
    "aerospace": [
        ("Iowa State", "https://www.aere.iastate.edu"),
        ("Georgia Tech", "https://ae.gatech.edu"),
        ("Minnesota", "https://cse.umn.edu/aem"),
        ("Colorado", "https://www.colorado.edu/aerospace"),
        ("Maryland", "https://aero.umd.edu"),
    ],
    "ai_cs": [
        ("UW", "https://www.cs.washington.edu"),
        ("UIUC", "https://cs.illinois.edu"),
        ("UCLA", "https://www.cs.ucla.edu"),
        ("Rice", "https://csweb.rice.edu"),
        ("Stony Brook", "https://www.cs.stonybrook.edu"),
    ],
}

PATHS = ["/people", "/people/", "/directory", "/directory/",
         "/people/graduate-students", "/people/students", "/grad-students",
         "/students", "/people/phd-students", "/graduate-students",
         "/people/grad-students", "/phd-students"]

STUDENT_WORDS = re.compile(
    r"(graduate students?|ph\.?\s?d\.?\s+students?|doctoral students?|"
    r"grad students?|current students?)", re.I)


def get(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read()
            if (r.headers.get("Content-Encoding") or "").lower() == "gzip":
                import gzip
                raw = gzip.decompress(raw)
            return r.status, raw.decode("utf-8", "replace"), r.url
    except urllib.error.HTTPError as e:
        return e.code, "", url
    except Exception:                                          # noqa: BLE001
        return 0, "", url


def strip(html: str) -> str:
    s = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.S)
    return re.sub(r"<[^>]+>", " ", s)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sector")
    a = ap.parse_args()

    out = {"note": ("Whether a department publishes a page naming its "
                    "graduate students. Counts nobody and classifies "
                    "nobody."), "sectors": {}}
    for sector, sites in SITES.items():
        if a.sector and sector != a.sector:
            continue
        rows = []
        print(f"\n  {sector}")
        for name, base in sites:
            found, hits = None, 0
            for path in PATHS:
                code, html, final = get(base.rstrip("/") + path)
                if code != 200 or len(html) < 2000:
                    continue
                body = strip(html)
                n = len(STUDENT_WORDS.findall(body))
                if n > hits:
                    hits, found = n, final
                if n >= 3:
                    break
                time.sleep(0.4)
            rows.append({"institution": name, "site": base,
                         "student_page": found if hits >= 2 else None,
                         "student_word_hits": hits})
            flag = "lists students" if hits >= 2 else "no student roster found"
            print(f"    {name:16} {flag:26} {(found or '')[:52]}")
        out["sectors"][sector] = rows

    write_text(OUT, json.dumps(out, indent=2))
    print()
    for sector, rows in out["sectors"].items():
        vis = sum(1 for r in rows if r["student_page"])
        print(f"  {sector:10} {vis}/{len(rows)} departments publish a student roster")
    print(f"\n  wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
