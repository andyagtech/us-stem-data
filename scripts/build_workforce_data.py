#!/usr/bin/env python3
"""
Extract NSF SDR (Survey of Doctorate Recipients) 2023 citizenship and field
data into a single JSON for the STEM workforce dashboard page.

Output: data/nsf_workforce/workforce_dashboard.json
"""
import json
import warnings
import openpyxl
from pathlib import Path

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent
SDR = ROOT / "data" / "nsf_workforce" / "sdr_2023_tables"
OUT = ROOT / "data" / "nsf_workforce" / "workforce_dashboard.json"


def load_table9_citizenship_by_field():
    """Table 9: U.S. residing employed doctoral S&E by field × citizenship status."""
    wb = openpyxl.load_workbook(SDR / "nsf25321-tab009.xlsx", data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))

    # Header layout (row indices 3-5):
    # Row 3: Field of study | All employed |   | U.S. citizen ... | Non-U.S. citizen ...
    # Row 4: blank | blank | blank | Total | blank | Native born | blank | Naturalized | blank | Total | blank | Permanent resident | blank | Temporary resident | blank
    # Row 5: numeric column headers

    # We want broad fields and a few key fine fields
    broad_fields = {
        "All fields": "All Fields",
        "Science": "Science (all)",
        "Engineering": "Engineering (all)",
        "Health": "Health Sciences",
        "Biological, agricultural, and environmental life sciences": "Life Sciences",
        "Computer and information sciences": "Computer & Information Sciences",
        "Computer science": "Computer Science",
        "Mathematics and statistics": "Mathematics & Statistics",
        "Physics": "Physics",
        "Chemistry, except biochemistry": "Chemistry",
        "Psychology": "Psychology",
        "Social sciences": "Social Sciences",
        "Aerospace, aeronautical, and astronautical engineering": "Aerospace Eng",
        "Chemical engineering": "Chemical Eng",
        "Civil engineering": "Civil Eng",
        "Electrical and computer engineering": "Electrical & Computer Eng",
        "Mechanical engineering": "Mechanical Eng",
        "Bioengineering and biomedical engineering": "Biomedical Eng",
    }
    out = []
    for r in rows:
        if not r or not r[0] or not isinstance(r[0], str):
            continue
        label = r[0].strip()
        if label not in broad_fields:
            continue
        try:
            total = int(r[1] or 0)
            us_total = int(r[3] or 0)
            native = int(r[5] or 0)
            naturalized = int(r[7] or 0)
            non_us_total = int(r[9] or 0)
            perm_res = int(r[11] or 0)
            temp_res = int(r[13] or 0)
        except (TypeError, ValueError):
            continue
        out.append({
            "field": broad_fields[label],
            "total": total,
            "native_born": native,
            "naturalized": naturalized,
            "permanent_resident": perm_res,
            "temporary_resident": temp_res,
            # Derived: foreign-born share = (naturalized + perm_res + temp_res) / total
            "foreign_born_pct": round(100 * (naturalized + perm_res + temp_res) / total, 1) if total else 0,
            "non_citizen_pct": round(100 * non_us_total / total, 1) if total else 0,
        })
    return out


def load_existing_findings():
    """Load the pre-computed sdr_citizenship_findings.json (national topline)."""
    fp = ROOT / "data" / "nsf_workforce" / "sdr_citizenship_findings.json"
    if not fp.exists():
        return None
    return json.loads(fp.read_text())


def main():
    out = {
        "source": "NSF Survey of Doctorate Recipients (SDR) 2023",
        "url": "https://ncses.nsf.gov/surveys/doctorate-recipients",
        "national_topline": load_existing_findings(),
        "by_field": load_table9_citizenship_by_field(),
    }
    OUT.write_text(json.dumps(out, indent=2))
    print(f"Wrote {OUT}")
    print(f"  by_field rows: {len(out['by_field'])}")
    for f in out["by_field"]:
        print(f"    {f['field']:<32} {f['total']:>10,} ({f['foreign_born_pct']}% foreign-born)")


if __name__ == "__main__":
    main()
