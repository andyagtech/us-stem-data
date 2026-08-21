#!/usr/bin/env python3
"""Master's versus doctoral funding, from the NSF GSS 2024 institution file.

Why this exists: the site's funding argument rests on NSF SED Table 4-1, which
covers RESEARCH DOCTORATE RECIPIENTS ONLY. The master's expansion is the site's
strongest composition finding (60.3% of new core-STEM places), so the obvious
next question is whether the funding argument extends to it. It does not, and
the reason is worth stating precisely rather than leaving as a gap.

The GSS institution file carries support broken out by degree level:
    ma_ft_*   master's, full-time
    dr_ft_*   doctoral, full-time
and, in a separate sheet, enrolment by citizenship at each level
(ma_ft_tot_forgn_v / dr_ft_tot_forgn_v).

THE LIMIT, which is the whole point:
    Support lives in the 'Support' sheet. Citizenship lives in the 'Race' sheet.
    They are NOT crossed. GSS never publishes support-by-citizenship at either
    level, and SED -- which does cross them -- has no master's population at
    all. So "what share of non-resident master's students are federally
    funded" is NOT ANSWERABLE from public federal data. Do not estimate it by
    multiplying the two margins; that assumes the funding mix is identical for
    both groups, which nothing measures.

What IS answerable, and is the finding: master's study is overwhelmingly
self-financed at BOTH citizenships combined, in a way doctoral study is not.
That reframes the master's expansion as tuition revenue rather than as federal
training money, which is a different argument and needs different evidence.

Usage:
    python3 scripts/analyze_masters_support.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GSS = ROOT / "data" / "nsf_gss" / "gss2024_Code.xlsx"

SUPPORT_KEYS = ("tot_all", "tot_fed_all", "tot_nfed_all", "tot_self_sup",
                "ra_all", "ta_all", "fel_all", "trn_all")


def _sum(ws, cols):
    it = ws.iter_rows(values_only=True)
    hdr = list(next(it))
    idx = {c: hdr.index(c) for c in cols if c in hdr}
    missing = [c for c in cols if c not in idx]
    if missing:
        sys.exit(f"GSS file is missing expected columns: {missing}")
    out = dict.fromkeys(idx, 0)
    for row in it:
        for c, i in idx.items():
            v = row[i]
            if isinstance(v, (int, float)):
                out[c] += v
    return out


def main() -> int:
    try:
        import openpyxl
    except ModuleNotFoundError:
        sys.exit("openpyxl required -- see requirements.txt")
    if not GSS.exists():
        sys.exit(f"missing {GSS}")

    wb = openpyxl.load_workbook(GSS, read_only=True, data_only=True)
    sup = _sum(wb["Support"],
               [f"{lv}_ft_{k}_v" for lv in ("ma", "dr") for k in SUPPORT_KEYS])
    race = _sum(wb["Race"],
                [f"{lv}_ft_tot_{k}_v" for lv in ("ma", "dr")
                 for k in ("forgn", "all_races")])

    mt, dt = sup["ma_ft_tot_all_v"], sup["dr_ft_tot_all_v"]
    print("NSF GSS 2024 -- full-time graduate students, science/engineering/health\n")
    print(f"{'':<28}{chr(39).join(['MASTER', 'S']):>18}{'DOCTORAL':>18}")

    def row(label, key):
        a, b = sup[f"ma_ft_{key}_v"], sup[f"dr_ft_{key}_v"]
        print(f"  {label:<26}{a:>9,} ({100*a/mt:>4.1f}%){b:>9,} ({100*b/dt:>4.1f}%)")

    print(f"  {'full-time enrolled':<26}{mt:>17,}{dt:>18,}")
    print()
    row("federally supported", "tot_fed_all")
    row("institutional / other", "tot_nfed_all")
    row("SELF-SUPPORTING", "tot_self_sup")
    print()
    row("research assistantship", "ra_all")
    row("teaching assistantship", "ta_all")
    row("fellowship", "fel_all")
    row("traineeship", "trn_all")

    mf, ma = race["ma_ft_tot_forgn_v"], race["ma_ft_tot_all_races_v"]
    df, da = race["dr_ft_tot_forgn_v"], race["dr_ft_tot_all_races_v"]
    print("\nEnrolment by citizenship (Race sheet -- NOT crossed with support):")
    print(f"  {'temporary visa holders':<26}{mf:>9,} ({100*mf/ma:>4.1f}%)"
          f"{df:>9,} ({100*df/da:>4.1f}%)")
    print(f"\n  Temporary-visa master's students outnumber temporary-visa")
    print(f"  doctoral students {mf/df:.2f}x ({mf:,} vs {df:,}).")
    print("\nNOT ANSWERABLE from public federal data: the federal-support rate of")
    print("non-resident master's students specifically. Support and citizenship")
    print("are never crossed at master's level in GSS, and SED has no master's")
    print("population. Multiplying the two margins would invent the number.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
