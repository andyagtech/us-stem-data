#!/usr/bin/env python3
"""Which federal agency pays for graduate study, and through what mechanism.

The project could say that 76% of visa-holding doctorate recipients were on
an assistantship and 53% of citizens were. It could not say whose money that
was. NSF's Graduate Students and Postdoctorates survey reports, per
institution, full-time graduate support split by mechanism -- fellowship,
traineeship, research assistantship, teaching assistantship -- and, within
federal support, by the agency funding it.

WHAT THIS DOES NOT CLOSE. GSS reports support by mechanism and agency, and
enrolment by citizenship, but never the two together: no published field says
which agency funded a foreign national. The link from an award to a student's
citizenship remains the ask on the data-needs page. This narrows the gap from
"whose money" to "whose money, and separately how many foreign students that
institution enrols".

Usage:
  python3 scripts/build_grad_support.py
"""
from __future__ import annotations

import json
import sys
import warnings
import zipfile
from collections import defaultdict
from pathlib import Path

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "nsf_gss" / "graduate_students_postdocs_2024.zip"
MEMBER = "gss2024_Code.xlsx"
OUT = ROOT / "site" / "data" / "grad_support.json"

AGENCY = {"dod": "Defense", "nih": "NIH", "hhs": "HHS (excl. NIH)",
          "nsf": "NSF", "doa": "Agriculture", "nasa": "NASA",
          "doe": "Energy", "oth": "Other federal"}
MECH = {"fel": "Fellowship", "trn": "Traineeship",
        "ra": "Research assistantship", "ta": "Teaching assistantship",
        "ots": "Other support"}


def sheet_rows(name):
    import openpyxl
    with zipfile.ZipFile(SRC) as z:
        with z.open(MEMBER) as fh:
            data = fh.read()
    import io
    wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True)
    ws = wb[name]
    it = ws.iter_rows(values_only=True)
    hdr = [str(c) if c is not None else "" for c in next(it)]
    for row in it:
        yield dict(zip(hdr, row))


def num(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


def main() -> int:
    if not SRC.exists():
        print(f"  {SRC.relative_to(ROOT)} not found")
        return 1

    # Doctorate-level, full-time. dr_ft_<mech>_fed_<agency>_v
    by_agency = defaultdict(int)
    by_mech = defaultdict(lambda: {"federal": 0, "nonfederal": 0, "self": 0})
    agency_by_mech = defaultdict(lambda: defaultdict(int))
    inst_fed = defaultdict(int)
    inst_name = {}
    n_rows = 0

    for r in sheet_rows("Support"):
        n_rows += 1
        uid = str(r.get("UNITID") or "").strip()
        if uid:
            inst_name[uid] = (r.get("Institution_Name") or "").strip()
            inst_fed[uid] += num(r.get("dr_ft_tot_fed_all_v"))
        for m in MECH:
            by_mech[m]["federal"] += num(r.get(f"dr_ft_{m}_fed_all_v"))
            by_mech[m]["nonfederal"] += num(r.get(f"dr_ft_{m}_nfed_all_v"))
            if m == "ots":
                by_mech[m]["self"] += num(r.get(f"dr_ft_{m}_self_sup_v"))
            for a in AGENCY:
                v = num(r.get(f"dr_ft_{m}_fed_{a}_v"))
                if v:
                    by_agency[a] += v
                    agency_by_mech[m][a] += v

    if not n_rows:
        print("  no rows read")
        return 1

    fed_total = sum(by_agency.values())
    doc = {
        "_comment": ("Full-time doctoral graduate support by mechanism and, "
                     "within federal support, by funding agency. Counts are "
                     "STUDENTS SUPPORTED, not dollars. GSS reports support by "
                     "agency and enrolment by citizenship but NEVER TOGETHER: "
                     "no published field links an award to a student's "
                     "citizenship, which remains the outstanding ask."),
        "source": ("NSF NCSES, Survey of Graduate Students and Postdoctorates "
                   "in Science and Engineering, 2024"),
        "unit": "full-time doctoral students supported",
        "institutions": len(inst_name),
        "federal_supported_total": fed_total,
        "by_agency": {AGENCY[a]: n for a, n in
                      sorted(by_agency.items(), key=lambda kv: -kv[1])},
        "by_agency_pct": {AGENCY[a]: round(100 * n / fed_total, 1) for a, n in
                          sorted(by_agency.items(), key=lambda kv: -kv[1])} if fed_total else {},
        "by_mechanism": {MECH[m]: v for m, v in by_mech.items()},
        "agency_by_mechanism": {
            MECH[m]: {AGENCY[a]: n for a, n in sorted(d.items(), key=lambda kv: -kv[1])}
            for m, d in agency_by_mech.items()},
        "top_institutions_by_federal_support": [
            {"unitid": u, "institution": inst_name.get(u, u), "federally_supported": n}
            for u, n in sorted(inst_fed.items(), key=lambda kv: -kv[1])[:15]],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=1) + "\n")

    print(f"  {n_rows:,} institution-programme rows, {len(inst_name):,} institutions")
    print(f"  federally supported full-time doctoral students: {fed_total:,}")
    for a, n in list(doc["by_agency"].items())[:6]:
        print(f"    {a:18} {n:>8,}  {doc['by_agency_pct'][a]:>5.1f}%")
    print("  by mechanism (federal / non-federal):")
    for m, v in doc["by_mechanism"].items():
        print(f"    {m:24} {v['federal']:>8,} / {v['nonfederal']:>8,}")
    print(f"  wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
