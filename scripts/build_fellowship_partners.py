#!/usr/bin/env python3
"""The Build Fellowship's published university partners, joined to IPEDS.

Open Avenues Foundation runs the Build Fellowship and is the clearest public
example of the cap-exempt affiliated-nonprofit route: a nonprofit whose
affiliation with institutions of higher education confers exemption from the
H-1B numerical cap. Its own impact page names the universities involved.

This joins that published partner list to IPEDS, so each partner carries its
actual graduate STEM figures rather than only a student-participation count.
The partner list is the organisation's own claim about where it operates; the
IPEDS columns are independent.

WHAT A PARTNERSHIP IS NOT. Appearing here means the Build Fellowship reports
training students at that institution. It does not mean the university
sponsors anyone, employs a fellow, or is party to any petition. The
affiliation that matters for the cap exemption is the nonprofit's, and no
published source records cap status against a named employer.

Usage:
  python3 scripts/build_fellowship_partners.py
"""
from __future__ import annotations

import csv
import io
import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipeline.models import STEM_NARROW  # noqa: E402

RAW = ROOT / "data" / "h1b" / "build_fellowship_partners_raw.json"
IPEDS = ROOT / "data" / "ipeds"
OUT = ROOT / "data" / "h1b" / "build_fellowship_partners.json"
WINDOW = (2021, 2025)
SOURCE = "https://www.buildfellowship.com/impact"


def norm(s: str) -> str:
    s = s.upper().replace("&", " AND ")
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    s = re.sub(r"\b(THE|AT|OF|IN|MAIN|CAMPUS)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def hd_rows(year: int):
    # utf-8-sig, not latin-1: the file carries a BOM, and reading it as
    # latin-1 turns the first header into "\ufeffUNITID" so every UNITID
    # comes back None. Every partner then collapsed onto the same None key
    # and 54 institutions became one.
    for name in (f"hd{year}.csv", f"HD{year}.csv"):
        p = IPEDS / name
        if p.exists():
            with open(p, newline="", encoding="utf-8-sig", errors="replace") as fh:
                yield from csv.DictReader(fh)
            return
    p = IPEDS / f"HD{year}.zip"
    if p.exists():
        with zipfile.ZipFile(p) as z:
            inner = next(n for n in z.namelist() if n.lower().endswith(".csv"))
            with z.open(inner) as fh:
                yield from csv.DictReader(io.TextIOWrapper(fh, encoding="latin-1"))


def completions(year: int):
    for name in (f"c{year}_a.csv", f"C{year}_a.csv", f"C{year}_A.csv"):
        p = IPEDS / name
        if p.exists():
            with open(p, newline="", encoding="utf-8-sig", errors="replace") as fh:
                yield from csv.DictReader(fh)
            return
    for name in (f"C{year}_A.zip", f"c{year}_a.zip"):
        p = IPEDS / name
        if p.exists():
            with zipfile.ZipFile(p) as z:
                inner = next(n for n in z.namelist() if n.lower().endswith(".csv"))
                with z.open(inner) as fh:
                    yield from csv.DictReader(
                        io.TextIOWrapper(fh, encoding="utf-8-sig", errors="replace"))
            return


def main() -> int:
    if not RAW.exists():
        print(f"  {RAW.relative_to(ROOT)} not found")
        return 1
    partners = json.loads(RAW.read_text())

    # Directory: normalised institution name -> (unitid, official name, state)
    directory = {}
    for year in (2024, 2025, 2023):
        rows = list(hd_rows(year))
        if not rows:
            continue
        for r in rows:
            nm = (r.get("INSTNM") or "").strip()
            if nm:
                directory.setdefault(norm(nm), (r.get("UNITID"), nm, r.get("STABBR")))
        break

    wanted, unmatched = {}, []
    for state, rows in partners.items():
        for row in rows:
            hit = directory.get(norm(row["institution"]))
            if not hit:
                unmatched.append(row["institution"])
                continue
            unitid, official, stabbr = hit
            if not unitid:
                unmatched.append(row["institution"])
                continue
            wanted[unitid] = {
                "partner_name": row["institution"], "ipeds_name": official,
                "unitid": unitid, "state": stabbr or state,
                "students_reported": row["students"],
            }

    # Graduate STEM completions for the matched partners.
    tally = {u: {"masters": [0, 0], "doctorate": [0, 0]} for u in wanted}
    for year in range(WINDOW[0], WINDOW[1] + 1):
        for r in completions(year):
            u = (r.get("UNITID") or "").strip()
            if u not in tally:
                continue
            cip = (r.get("CIPCODE") or "").strip()
            if cip.split(".")[0].zfill(2) not in set(STEM_NARROW):
                continue
            # IPEDS carries no family rollup rows -- codes are six digits
            # (11.0101) -- so the detail rows ARE the data. Only CIPCODE 99,
            # the institution grand total, must be excluded. An earlier
            # version kept rollups instead and summed nothing at all.
            if cip.startswith("99"):
                continue
            try:
                lvl = int(r.get("AWLEVEL") or 0)
                if int(r.get("MAJORNUM") or 1) != 1:
                    continue
                tot, nra = int(r.get("CTOTALT") or 0), int(r.get("CNRALT") or 0)
            except ValueError:
                continue
            key = "masters" if lvl == 7 else "doctorate" if lvl == 17 else None
            if key:
                tally[u][key][0] += tot
                tally[u][key][1] += nra

    out = []
    for u, meta in wanted.items():
        rec = dict(meta)
        for level in ("masters", "doctorate"):
            tot, nra = tally[u][level]
            rec[level] = {"total": tot, "nra": nra,
                          "share": round(100 * nra / tot, 1) if tot else None}
        out.append(rec)
    out.sort(key=lambda r: -(r["masters"]["nra"] + r["doctorate"]["nra"]))

    OUT.write_text(json.dumps({
        "_comment": ("University partners the Build Fellowship publishes on its "
                     "impact page, joined to IPEDS graduate STEM completions. "
                     "A partnership is the organisation's own claim that it "
                     "trains students there. It does NOT mean the university "
                     "sponsors anyone, employs a fellow, or is party to any "
                     "petition -- the affiliation that confers cap exemption is "
                     "the nonprofit's. The IPEDS columns are independent of the "
                     "partner list."),
        "partner_source": SOURCE,
        "ipeds_window": list(WINDOW),
        "partners_published": sum(len(v) for v in partners.values()),
        "partners_matched": len(out),
        "unmatched": unmatched,
        "partners": out,
    }, indent=1) + "\n")

    print(f"  {sum(len(v) for v in partners.values())} published partners, "
          f"{len(out)} matched to IPEDS, {len(unmatched)} unmatched")
    print(f"  {'institution':44} {'st':>3} {'M share':>8} {'D share':>8} {'grad NRA':>9}")
    for r in out[:14]:
        m, d = r["masters"], r["doctorate"]
        print(f"  {r['ipeds_name'][:44]:44} {r['state']:>3} "
              f"{(str(m['share']) + '%') if m['share'] is not None else '—':>8} "
              f"{(str(d['share']) + '%') if d['share'] is not None else '—':>8} "
              f"{m['nra'] + d['nra']:>9,}")
    for u in unmatched:
        print(f"  unmatched: {u}")
    print(f"  wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
