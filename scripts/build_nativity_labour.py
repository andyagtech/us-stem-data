#!/usr/bin/env python3
"""The domestic side of the ledger.

Every other dataset in this project measures the foreign population --
degrees to non-residents, visas issued, petitions approved. None of them
measures what happened to workers already here, which makes the displacement
argument one-sided and is the most attackable feature of the work.

This is the counterpart: employment by occupation and median weekly earnings,
split by nativity, from the Current Population Survey.

NATIVITY IS NOT VISA STATUS. "Foreign born" here includes naturalised
citizens, permanent residents and people on temporary visas together, and
"native born" includes anyone born in the United States regardless of
parentage. It is a much broader cut than the visa categories used elsewhere
and the two must not be treated as the same population.

THE EARNINGS GAP IS NOT A LIKE-FOR-LIKE COMPARISON. The two groups differ in
age, education, occupation, region and language, and none of that is
controlled here. A raw gap describes the two populations as they are, not
what an employer pays for the same work.

Usage:
  python3 scripts/build_nativity_labour.py
"""
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "bls_nativity"
OUT = ROOT / "site" / "data" / "nativity_labour.json"
sys.path.insert(0, str(ROOT / "scripts"))
from atomic_write import write_json                          # noqa: E402

SECTION = re.compile(r"^[A-Z][A-Z \-,]{3,}$")   # "AGE", "OCCUPATION" headings


def rows_of(path: Path) -> tuple[str, list[list[str]]]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    title = ""
    m = re.search(r"Table \d+\.\s*([^<]{10,200})", raw)
    if m:
        title = re.sub(r"\s+", " ", html.unescape(m.group(1))).strip()
    t = re.search(r"<table[^>]*>(.*?)</table>", raw, re.S | re.I)
    if not t:
        return title, []
    out = []
    for r in re.findall(r"<tr[^>]*>(.*?)</tr>", t.group(1), re.S | re.I):
        cells = [re.sub(r"\s+", " ",
                        html.unescape(re.sub(r"<[^>]+>", " ", c))).strip()
                 for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", r, re.S | re.I)]
        cells = [c for c in cells if c]
        if cells:
            out.append(cells)
    return title, out


def num(s: str) -> float | None:
    s = str(s or "").replace(",", "").replace("$", "").strip()
    if not s or s in ("-", "–", "(1)", "(2)"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def main() -> int:
    t4, t5 = SRC / "forbrn.t04.htm", SRC / "forbrn.t05.htm"
    for p in (t4, t5):
        if not p.exists():
            print(f"  missing {p.relative_to(ROOT)}")
            return 1

    warns = []

    # --- Table 5: earnings by nativity ---------------------------------
    title5, rows5 = rows_of(t5)
    year = None
    m = re.search(r"(20\d\d)\s*annual averages", title5)
    if m:
        year = int(m.group(1))
    earnings, section = {}, None
    for cells in rows5:
        label = cells[0]
        if len(cells) == 1:
            if SECTION.match(label):
                section = label.title()
            continue
        vals = [num(c) for c in cells[1:]]
        # Layout: two years side by side, each
        # [foreign n, foreign median, native n, native median, ratio].
        if len(vals) < 10 or any(v is None for v in vals[5:10]):
            continue
        fb_n, fb_med, nb_n, nb_med, ratio = vals[5:10]
        earnings[label] = {
            "section": section,
            "foreign_born_thousands": fb_n,
            "foreign_born_median_weekly": fb_med,
            "native_born_thousands": nb_n,
            "native_born_median_weekly": nb_med,
            "foreign_as_pct_of_native": ratio,
        }
        if nb_med and abs(100 * fb_med / nb_med - ratio) > 1.5:
            warns.append(f"{label}: published ratio {ratio} against "
                         f"{100 * fb_med / nb_med:.1f} computed")

    # --- Table 4: employment by occupation ------------------------------
    # Columns are foreign born (total, men, women) then native born (total,
    # men, women), so the native total is the FOURTH value and not the
    # second. And every row after the totals is a PERCENT OF ITS OWN GROUP,
    # not a headcount: the occupation shares must be rebuilt from the group
    # totals or a 25% occupation reads as 61%.
    title4, rows4 = rows_of(t4)
    occupations, section = {}, None
    fb_total = nb_total = None
    for cells in rows4:
        label = cells[0]
        if len(cells) == 1:
            if SECTION.match(label):
                section = label.title()
            continue
        vals = [num(c) for c in cells[1:]]
        if len(vals) < 4 or vals[0] is None or vals[3] is None:
            continue
        if fb_total is None and label.lower().startswith("total employed"):
            fb_total, nb_total = vals[0], vals[3]
            continue
        if fb_total is None:
            continue
        fb_pct, nb_pct = vals[0], vals[3]
        if not (0 <= fb_pct <= 100 and 0 <= nb_pct <= 100):
            warns.append(f"{label}: values {fb_pct}, {nb_pct} are not percents")
            continue
        fb = fb_total * fb_pct / 100
        nb = nb_total * nb_pct / 100
        tot = fb + nb
        occupations[label] = {
            "section": section,
            "pct_of_foreign_born_workers": fb_pct,
            "pct_of_native_born_workers": nb_pct,
            "foreign_born_thousands": round(fb, 1),
            "native_born_thousands": round(nb, 1),
            "foreign_born_share_pct": round(100 * fb / tot, 1) if tot else None,
        }
    if fb_total:
        occupations["_totals"] = {"foreign_born_thousands": fb_total,
                                  "native_born_thousands": nb_total,
                                  "foreign_born_share_pct": round(
                                      100 * fb_total / (fb_total + nb_total), 1)}

    if not earnings:
        print("  no earnings rows parsed")
        for w in warns[:4]:
            print(f"  WARN {w}")
        return 1

    total = earnings.get("Total, 16 years and over")
    prof = {k: v for k, v in occupations.items()
            if not k.startswith("_")
            and re.search(r"computer|engineering|science|professional", k, re.I)}

    doc = {
        "_comment": (
            "Employment by occupation and median usual weekly earnings, split "
            "by NATIVITY, from the CPS via the BLS foreign-born news release. "
            "Held because every other dataset here measures the foreign "
            "population and none measured the workers already present, which "
            "made the displacement argument one-sided. NATIVITY IS NOT VISA "
            "STATUS: 'foreign born' pools naturalised citizens, permanent "
            "residents and temporary-visa holders, and 'native born' includes "
            "anyone born in the US whatever their parentage. It is far "
            "broader than the visa categories used elsewhere and the two must "
            "not be treated as one population. THE EARNINGS GAP IS NOT "
            "LIKE-FOR-LIKE -- the groups differ in age, education, "
            "occupation, region and language and none of it is controlled, so "
            "a raw gap describes two populations rather than what an employer "
            "pays for the same work. Earnings are MEDIAN USUAL WEEKLY for "
            "full-time wage and salary workers, not annual and not including "
            "the self-employed."),
        "source": "BLS Current Population Survey, foreign-born workers news release",
        "source_url": "https://www.bls.gov/news.release/forbrn.nr0.htm",
        "year": year,
        "earnings_table": title5,
        "occupation_table": title4,
        "headline": total,
        "earnings_by_characteristic": earnings,
        "employment_by_occupation": occupations,
        "professional_occupations": prof,
        "warnings": warns,
    }
    write_json(OUT, doc)

    print(f"  {year} annual averages; {len(earnings)} earnings rows, "
          f"{len(occupations)} occupation rows")
    if total:
        print(f"\n  median usual weekly earnings, full-time:")
        print(f"   foreign born  ${total['foreign_born_median_weekly']:,.0f}"
              f"  ({total['foreign_born_thousands']:,.0f}k workers)")
        print(f"   native born   ${total['native_born_median_weekly']:,.0f}"
              f"  ({total['native_born_thousands']:,.0f}k workers)")
        print(f"   foreign as % of native: {total['foreign_as_pct_of_native']}")
    if prof:
        print(f"\n  foreign-born share of employment, professional occupations:")
        for k, v in list(prof.items())[:8]:
            print(f"   {k[:46]:48}{v['foreign_born_share_pct']:>6.1f}%")
    for w in warns[:5]:
        print(f"  WARN {w}")
    print(f"\n  wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
