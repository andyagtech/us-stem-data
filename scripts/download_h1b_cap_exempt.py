#!/usr/bin/env python3
"""Extract cap-exempt H-1B employer counts from the USCIS reports to Congress.

Neither of the H-1B sources already in this project can answer "how many
petitions came from cap-exempt employers":

  DOL LCA          the form never asks. An LCA is filed before the petition,
                   when the cap has not been engaged at all.
  USCIS Data Hub   employer-level counts with a NAICS code, but no cap flag.

The answer is published, but not under that name. The annual Report on H-1B
Petitions to Congress carries a table of exemptions from the ACWIA FEE, and
its employer rows are the same statutory categories that make an employer
exempt from the numerical cap under INA 214(g)(5):

  institutions of higher education
  nonprofits related to or affiliated with one
  nonprofit research organisations and government research organisations

TWO THINGS THIS IS NOT. Fee exemption is broader than cap exemption -- the
same table counts primary and secondary schools and procedural exemptions
(a second extension, an amended petition, correcting a USCIS error) that say
nothing about the cap. And the report's own footnote warns a petition may be
counted in more than one row, so the rows must not be summed into a total.

Usage:
  python3 scripts/download_h1b_cap_exempt.py            # download and parse
  python3 scripts/download_h1b_cap_exempt.py --offline  # parse what is cached
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "h1b" / "uscis_reports"
OUT = ROOT / "data" / "h1b" / "h1b_cap_exempt.json"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120 Safari/537.36")

BASE = "https://www.uscis.gov/sites/default/files/document"
REPORTS = {
    2018: f"{BASE}/reports/FY-2018-Annual-Report-H-1B-Petitions.pdf",
    2019: f"{BASE}/reports/H-1B_Petitions_FY19_Annual_Report.pdf",
    2020: f"{BASE}/reports/FY-2020-Annual-Report-H-1B-Petitions.pdf",
    2021: f"{BASE}/reports/%5BOLA%20Signed%5D_Congressional_Report_on_H-1B_Petitions_FY2021_2.9.22.pdf",
    2022: f"{BASE}/reports/FY-2022-Annual-Report-H-1B-Petitions.pdf",
    2023: f"{BASE}/reports/FY-2023-Annual-Report-H-1B-Petitions.pdf",
    2024: f"{BASE}/legal-docs/ola_signed_fy2024_h1b_petitions.pdf",
    2025: f"{BASE}/legal-docs/fy25_h1b_petitions_021126_v1.0.pdf",
}

# Anchors are matched against the label text with whitespace collapsed,
# because the same row wraps differently in each year's typesetting.
CATEGORIES = [
    ("higher_education", "institution of higher education",
     r"employer is an institution of higher"),
    ("affiliated_nonprofit", "Nonprofit related to or affiliated with an institution of higher education",
     r"employer is a nonprofit organization"),
    ("research_organization", "Nonprofit research organisation or government research organisation",
     r"employer is a nonprofit research"),
    ("primary_secondary", "Primary or secondary education institution (fee-exempt, NOT cap-exempt)",
     r"employer is a primary or secondary"),
    ("clinical_training", "Nonprofit engaged in clinical training (fee-exempt, cap status varies)",
     r"employer is a nonprofit entity"),
]
CAP_EXEMPT_KEYS = ("higher_education", "affiliated_nonprofit", "research_organization")


def fetch(year: int, url: str) -> Path | None:
    dest = CACHE / f"h1b_petitions_fy{year}.pdf"
    if dest.exists() and dest.stat().st_size > 20_000:
        return dest
    CACHE.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["curl", "-sL", "--max-time", "90", "-A", UA, "-o", str(dest), url],
                       capture_output=True, text=True)
    if r.returncode != 0 or not dest.exists() or dest.stat().st_size < 20_000:
        print(f"  FY{year}: download failed")
        dest.unlink(missing_ok=True)
        return None
    if not dest.read_bytes()[:5].startswith(b"%PDF"):
        print(f"  FY{year}: not a PDF (probably an error page)")
        dest.unlink(missing_ok=True)
        return None
    return dest


def pdftext(path: Path) -> str:
    r = subprocess.run(["pdftotext", "-layout", str(path), "-"],
                       capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else ""


def parse_table(lines: list[str]) -> tuple[dict, list[str]]:
    """Label -> fiscal-year total for one exemption table, plus any rejections.

    Two things make this harder than it looks.

    The narrative before the table names all the same categories, so an
    anchor match outside the table would run forward and pick up whichever
    row happened to have five numbers next -- which is how FY2021's research
    organisations came out as 78,848 instead of 5,932. The search therefore
    starts at "REASONS FOR EXEMPTION" and a row's figures must sit within two
    lines of its label.

    The older reports are scanned, and pdftotext returns "1.330" for 1,330
    and "4.45 1" for 4,451. Those parse without complaint into numbers that
    are simply wrong. Every row is reconciled instead: four quarters must sum
    to the stated total, or the row is dropped and reported.
    """
    def repair(line: str) -> str:
        """Undo the scan artefacts in the older reports, checkably.

        pdftotext returns "1.330" for 1,330 and "4.45 1" for 4,451 in the
        FY2018 and FY2019 scans. The ANNUAL total on the same row comes out
        clean, so a repair can be verified rather than trusted: fix the
        separators, then require the four quarters to sum to that total. A
        repair that does not reconcile is discarded with the row.
        """
        line = re.sub(r"(?<=\d)\s+(?=,\d{3})", "", line)           # 4 ,654 -> 4,654
        line = re.sub(r"(?<=\d)\.(?=\d{3}\b)", ",", line)          # 1.330  -> 1,330
        line = re.sub(r"(?<=\d)\s(?=\d\b)", "", line)              # 4.45 1 -> 4.451
        return re.sub(r"(?<=\d)\.(?=\d{3}\b)", ",", line)

    start = next((i for i, ln in enumerate(lines)
                  if re.search(r"REASONS FOR EXEMPTION", ln, re.I)), None)
    if start is None:
        return {}, ["no 'reasons for exemption' block"]
    window = lines[start:start + 80]
    joined = [re.sub(r"\s+", " ", ln).strip().lower() for ln in window]
    out: dict[str, int] = {}
    rejected: list[str] = []
    for key, _label, anchor in CATEGORIES:
        for i, ln in enumerate(joined):
            if not re.search(anchor, ln):
                continue
            # The label may wrap over up to three lines before the figures,
            # so scan forward for the first line carrying five numbers --
            # four quarters and a total -- rather than stopping at the label.
            for j in range(i, min(i + 4, len(window))):
                # Try the line as extracted, then repaired. A scan artefact
                # can still yield five parseable numbers -- "1,561 2,444
                # 4 ,654" reads as 1561, 2444, 654 -- so a failed
                # reconciliation must fall through to the repair rather than
                # consume the attempt.
                best = None
                for candidate in (window[j], repair(window[j])):
                    nums = re.findall(r"\d{1,3}(?:,\d{3})+|\b\d{3,7}\b", candidate)
                    if len(nums) < 5:
                        continue
                    vals = [int(v.replace(",", "")) for v in nums[-5:]]
                    best = vals
                    if abs(sum(vals[:4]) - vals[4]) <= max(2, 0.005 * vals[4]):
                        out[key] = vals[4]
                        break
                if key in out:
                    break
                if best is not None:
                    rejected.append(f"{key}: {best[:4]} do not sum to {best[4]}")
                    break
            break

    return out, rejected


def parse_report(text: str) -> dict:
    """Both tables: petitions filed, and petitions approved."""
    lines = text.splitlines()
    # Table 3 repeats the same row labels for approvals, so split on it.
    cut = next((i for i, ln in enumerate(lines) if re.match(r"\s*Table 3\b", ln)), len(lines))
    filed, rej_f = parse_table(lines[:cut])
    approved, rej_a = parse_table(lines[cut:])
    totals = {}
    # The label carries a footnote marker and the figures sit on the next
    # line, so both have to be considered -- and the footnote text itself
    # matches the label, which is what produced a total of zero for FY2024.
    for label, pat in (("filed", r"TOTAL PETITIONS FILED"),
                       ("approved", r"TOTAL PETITIONS APPROVED")):
        for i, ln in enumerate(lines):
            if not re.search(pat, ln, re.I) or ln.strip().startswith("12"):
                continue
            for j in (i, i + 1, i + 2):
                if j >= len(lines):
                    break
                nums = re.findall(r"\d{1,3}(?:,\d{3})+|\b\d{4,7}\b", lines[j])
                if len(nums) >= 5:
                    vals = [int(v.replace(",", "")) for v in nums[-5:]]
                    if abs(sum(vals[:4]) - vals[4]) <= max(2, 0.005 * vals[4]):
                        totals[label] = vals[4]
                    break
            if label in totals:
                break
    return {"filed": filed, "approved": approved, "totals": totals,
            "rejected": rej_f + rej_a}


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--offline", action="store_true", help="parse the cache only")
    args = ap.parse_args()

    series: dict[str, dict] = {}
    for year, url in sorted(REPORTS.items()):
        pdf = (CACHE / f"h1b_petitions_fy{year}.pdf") if args.offline else fetch(year, url)
        if not pdf or not pdf.exists():
            continue
        got = parse_report(pdftext(pdf))
        if not got["filed"]:
            print(f"  FY{year}: no usable exemption table "
                  f"({'; '.join(got['rejected'][:2]) or 'no table found'})")
            continue
        for why in got["rejected"]:
            print(f"  FY{year}: dropped {why}")
        f = got["filed"]
        series[str(year)] = got | {"source_url": url}
        print(f"  FY{year}: higher-ed {f.get('higher_education', 0):>7,}  "
              f"affiliated nonprofit {f.get('affiliated_nonprofit', 0):>7,}  "
              f"research org {f.get('research_organization', 0):>6,}  "
              f"(all petitions {got['totals'].get('filed', 0):,})")

    if not series:
        print("  nothing parsed")
        return 1

    OUT.write_text(json.dumps({
        "_comment": ("H-1B petitions by exempt employer category, from the USCIS "
                     "annual Report on H-1B Petitions to Congress, Section 2.2. "
                     "These are ACWIA FEE exemptions; the first three categories "
                     "are also the statutory cap-exempt employer types under INA "
                     "214(g)(5). Rows may double-count a petition qualifying "
                     "under more than one heading, so they must not be summed. "
                     "Primary/secondary schools are fee-exempt but NOT cap-exempt."),
        "cap_exempt_categories": list(CAP_EXEMPT_KEYS),
        "labels": {k: label for k, label, _a in CATEGORIES},
        "series": series,
    }, indent=1) + "\n")
    print(f"  wrote {OUT.relative_to(ROOT)} ({len(series)} years)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
