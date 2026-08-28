#!/usr/bin/env python3
"""EB-2 immigrant petitions with and without a National Interest Waiver.

The O-1 story on the briefing's cap page has an immigrant-visa counterpart.
An EB-2 petition normally needs an employer and a labour certification; the
National Interest Waiver removes both, letting the beneficiary self-petition.
USCIS clarified the STEM criteria for it in January 2022, and the effect is
visible in the next two years of filings.

Source: USCIS, "STEM-Related Petition Trends: EB-2 and O-1A Categories",
Table 1 -- receipts, completions and approvals split by NIW and non-NIW,
FY2018-FY2023.

Every row is reconciled: non-NIW plus NIW must equal the printed total, or
the row is dropped and named. The figures elsewhere in the fact sheet are
chart labels scattered across the page layout and are deliberately not read.

Usage:
  python3 scripts/build_eb2_niw.py
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "h1b" / "uscis_reports"
PDF = CACHE / "stem_eb2_o1a_fy23.pdf"
OUT = ROOT / "data" / "h1b" / "eb2_niw.json"
URL = ("https://www.uscis.gov/sites/default/files/document/reports/"
       "stem_related_petition_trends_eb2_and_o1a_categories_factsheet_fy23.pdf")
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"

# Receipts, completions, approvals -- each a (non-NIW, NIW, total) triple.
MEASURES = ("receipts", "completions", "approvals")


def fetch() -> bool:
    if PDF.exists() and PDF.stat().st_size > 50_000:
        return True
    CACHE.mkdir(parents=True, exist_ok=True)
    subprocess.run(["curl", "-sL", "--max-time", "90", "-A", UA,
                    "-o", str(PDF), URL], capture_output=True)
    return PDF.exists() and PDF.read_bytes()[:5].startswith(b"%PDF")


def main() -> int:
    if not fetch():
        print("  could not obtain the fact sheet")
        return 1
    text = subprocess.run(["pdftotext", "-layout", str(PDF), "-"],
                          capture_output=True, text=True).stdout
    lines = text.splitlines()
    start = next((i for i, ln in enumerate(lines)
                  if re.search(r"Table 1\.\s*EB-2", ln)), None)
    if start is None:
        print("  Table 1 not found")
        return 1

    series: dict[str, dict] = {}
    rejected: list[str] = []
    # Bound the table. Table 2 repeats the same row shape for STEM job
    # categories only; running past the heading mixed the two and produced
    # rows whose columns did not correspond to their labels.
    end = next((i for i, ln in enumerate(lines[start + 1:start + 60], start + 1)
                if re.search(r"(Table 2|Figure \d)", ln)), start + 40)
    for ln in lines[start:end]:
        m = re.match(r"\s*(20\d{2})\s+((?:[\d,]+\s+){8}[\d,]+)", ln)
        if not m:
            continue
        year = m.group(1)
        vals = [int(v.replace(",", "")) for v in m.group(2).split()]
        rec: dict[str, dict] = {}
        ok = True
        for i, measure in enumerate(MEASURES):
            non_niw, niw, total = vals[i * 3:i * 3 + 3]
            # USCIS rounds every figure to the nearest 10, so two rounded
            # parts need not sum exactly to a rounded total -- 62,490 +
            # 21,990 against a printed 84,470 is correct, not corrupt.
            # Demanding exact equality rejected most of the table.
            if abs(non_niw + niw - total) > 10:
                rejected.append(f"FY{year} {measure}: {non_niw:,}+{niw:,} != {total:,}")
                ok = False
                break
            rec[measure] = {"non_niw": non_niw, "niw": niw, "total": total,
                            "niw_share": round(100 * niw / total, 1) if total else 0.0}
        if ok:
            series[year] = rec

    if not series:
        print("  no rows reconciled")
        for r in rejected[:4]:
            print(f"   {r}")
        return 1

    years = sorted(series)
    first, last = series[years[0]], series[years[-1]]
    OUT.write_text(json.dumps({
        "_comment": ("EB-2 immigrant petitions with and without a National "
                     "Interest Waiver. The NIW removes the employer and labour "
                     "certification requirements, so the beneficiary "
                     "self-petitions. USCIS clarified the STEM criteria in "
                     "January 2022. Receipts are filings, not people, and an "
                     "approval is not an admission -- a visa number must still "
                     "be available."),
        "source": ("USCIS, STEM-Related Petition Trends: EB-2 and O-1A "
                   "Categories, Table 1"),
        "source_url": URL,
        "series": series,
        "rejected_rows": rejected,
    }, indent=1) + "\n")

    print(f"  {'FY':6} {'receipts':>10} {'NIW':>9} {'NIW share':>10} {'approvals':>10}")
    for y in years:
        r, a = series[y]["receipts"], series[y]["approvals"]
        print(f"  {y:6} {r['total']:>10,} {r['niw']:>9,} {r['niw_share']:>9.1f}% "
              f"{a['total']:>10,}")
    print(f"  NIW receipts FY{years[0]}->FY{years[-1]}: "
          f"{first['receipts']['niw']:,} -> {last['receipts']['niw']:,} "
          f"({100*(last['receipts']['niw']/first['receipts']['niw']-1):+.0f}%)")
    for r in rejected:
        print(f"  dropped {r}")
    print(f"  wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
