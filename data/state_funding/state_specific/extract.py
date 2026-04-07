#!/usr/bin/env python3
"""
Extract per-institution state appropriations data from downloaded PDFs
for California, Texas, and Florida. Produces JSON matched to our
university keys in site/data/stem/.
"""
import json
import re
import subprocess
from pathlib import Path

BASE = Path(__file__).resolve().parent


def pdftotext(pdf_path: Path) -> str:
    return subprocess.run(
        ["pdftotext", "-layout", str(pdf_path), "-"],
        capture_output=True, text=True, check=False,
    ).stdout


def parse_money(s: str) -> float:
    """Parse '$1,023.4' or '$ 784,363,608' -> float (in raw $)."""
    s = s.replace("$", "").replace(",", "").strip()
    if s in ("", "-"):
        return 0.0
    return float(s)


# ------------------------------------------------------------------
# FLORIDA: per-university E&G Summary Schedule I — General Revenue
# Each university has its own schedule with a "4 General Revenue" row.
# Format: "4 General Revenue  $ <E&G> $ <IFAS/SchoolA> ..."
# The first $ column after "General Revenue" is the main-campus E&G GR.
# ------------------------------------------------------------------
FL_UNI_ORDER = [
    # Order they appear in FY2024-25 summary book (1 GR row per uni)
    ("uf",   "UNIVERSITY OF FLORIDA"),
    ("fsu",  "FLORIDA STATE UNIVERSITY"),
    ("famu", "FLORIDA A&M UNIVERSITY"),
    ("usf",  "UNIVERSITY OF SOUTH FLORIDA"),
    ("fau",  "FLORIDA ATLANTIC UNIVERSITY"),
    ("uwf",  "UNIVERSITY OF WEST FLORIDA"),
    ("ucf",  "UNIVERSITY OF CENTRAL FLORIDA"),
    ("fiu",  "FLORIDA INTERNATIONAL UNIVERSITY"),
    ("unf",  "UNIVERSITY OF NORTH FLORIDA"),
    ("fgcu", "FLORIDA GULF COAST UNIVERSITY"),
    ("ncf",  "NEW COLLEGE OF FLORIDA"),
    ("fpu",  "FLORIDA POLYTECHNIC UNIVERSITY"),
]


def parse_fl_sus_pdf(pdf_path: Path, fy_label: str) -> dict:
    """
    Extract per-university General Revenue, Lottery, Student Tuition,
    and total E&G revenue for a given Florida SUS Operating Budget PDF.
    Strategy: Find the main table (TOTAL POSITIONS AND EXPENDITURES)
    to get total E&G expenditures per uni. Then find each uni's
    Summary Schedule I block and the "4 General Revenue" row inside it.
    """
    text = pdftotext(pdf_path)
    lines = text.splitlines()

    # Locate each university's Schedule I section header line then
    # find the first "General Revenue" row after it.
    result = {}
    # Build list of (line_idx, key) anchors for each uni header appearing
    # as a stand-alone centered header (not a table row).
    anchors = []
    for key, display in FL_UNI_ORDER:
        # Look for the *section header* occurrence (centered, no dollars
        # on the same line). Then the first GR line after that.
        for i, ln in enumerate(lines):
            if display in ln and "$" not in ln and "OPERATING BUDGET" not in ln and "POSITIONS" not in ln:
                # Section headers for Schedule I are typically followed
                # within ~3 lines by "OPERATING BUDGET".
                lookahead = "\n".join(lines[i : i + 5]).lower()
                if "operating budget" in lookahead and "summary schedule" in lookahead:
                    anchors.append((i, key))
                    break

    for idx, (line_idx, key) in enumerate(anchors):
        end_idx = anchors[idx + 1][0] if idx + 1 < len(anchors) else min(line_idx + 200, len(lines))
        block = lines[line_idx:end_idx]
        rec = {"general_revenue": None, "lottery": None, "student_tuition": None}
        for ln in block:
            s = ln.strip()
            if s.startswith("4 General Revenue"):
                m = re.search(r"\$\s*([\d,]+)", ln)
                if m:
                    rec["general_revenue"] = parse_money(m.group(1))
            elif s.startswith("5 Lottery"):
                m = re.search(r"\$\s*([\d,]+)", ln)
                if m:
                    rec["lottery"] = parse_money(m.group(1))
            elif s.startswith("6 Student Tuition"):
                m = re.search(r"\$\s*([\d,]+)", ln)
                if m:
                    rec["student_tuition"] = parse_money(m.group(1))
        rec["fiscal_year"] = fy_label
        rec["source"] = pdf_path.name
        rec["currency"] = "USD"
        result[key] = rec
    return result


def extract_florida():
    fl_dir = BASE / "fl"
    out = {}  # {fy: {key: rec}}
    for pdf in sorted(fl_dir.glob("sus_operating_budget_20*.pdf")):
        # FY label from filename
        m = re.search(r"(20\d{2}-\d{2})", pdf.name)
        if not m:
            continue
        fy = m.group(1)
        print(f"[FL] Parsing {pdf.name}...")
        try:
            out[fy] = parse_fl_sus_pdf(pdf, fy)
            print(f"     Found {len(out[fy])} universities")
        except Exception as e:
            print(f"     ERROR: {e}")
            out[fy] = {}
    return out


# ------------------------------------------------------------------
# TEXAS: LBB Fiscal Size-Up -- All Funds Appropriations by institution
# Figure 193 gives All Funds Appropriations; Figure 194 gives GR I&O
# formula funding. Both for the 2026-27 biennium.
# ------------------------------------------------------------------
TX_UNIVERSITIES = {
    "utaustin":    "University of Texas at Austin",
    "utdallas":    "University of Texas at Dallas",
    "utarlington": "University of Texas at Arlington",
    "uhouston":    "University of Houston",
    "ttu":         "Texas Tech University",
}

def parse_tx_sizeup(pdf_path: Path) -> dict:
    text = pdftotext(pdf_path)
    lines = text.splitlines()

    # Find Figure 193 (All Funds) and Figure 194 (GR I&O + Infrastructure)
    def find_figure(fig_num: int):
        # Match the stand-alone figure header (strip whitespace, exact)
        target = f"FIGURE {fig_num}"
        for i, ln in enumerate(lines):
            if ln.strip().upper() == target:
                return i
        return None

    def parse_region(start_idx: int, end_idx: int) -> dict:
        # Each line has 0,1, or 2 institution/amount pairs (two-column layout).
        rows = {}
        # Regex: name .... $amount
        pat = re.compile(r"([A-Za-z][A-Za-z &\-\u2013\u2014\.\'\(\)]+?)\s+\$\s*([\d,]+\.\d+|[\d,]+)")
        for ln in lines[start_idx:end_idx]:
            for m in pat.finditer(ln):
                name = m.group(1).strip().rstrip(".")
                amount = parse_money(m.group(2))
                rows[name] = amount
        return rows

    fig193 = find_figure(193)
    fig194 = find_figure(194)
    fig195 = find_figure(195)
    result = {"all_funds_2026_27_biennium_millions": {}, "gr_formula_2026_27_biennium_millions": {}}

    if fig193 is not None:
        all_funds = parse_region(fig193, fig194 or fig193 + 80)
        for key, canonical in TX_UNIVERSITIES.items():
            for name, amt in all_funds.items():
                if canonical.lower() == name.lower():
                    result["all_funds_2026_27_biennium_millions"][key] = amt
                    break

    if fig194 is not None:
        gr_form = parse_region(fig194, fig195 or fig194 + 80)
        for key, canonical in TX_UNIVERSITIES.items():
            for name, amt in gr_form.items():
                if canonical.lower() == name.lower():
                    result["gr_formula_2026_27_biennium_millions"][key] = amt
                    break

    return result


# ------------------------------------------------------------------
# CALIFORNIA: UC does not publish per-campus state appropriations in
# its public budget documents (allocations are made internally). We
# record the UC systemwide State General Fund total time series by
# parsing the budget-summary PDFs.
# ------------------------------------------------------------------
def parse_ca_uc(pdf_path: Path) -> dict:
    text = pdftotext(pdf_path)
    # Collapse whitespace for tolerant matching.
    flat = re.sub(r"\s+", " ", text)
    # Variations:
    #   "State General Fund support for UC totals $4.91 billion in 2024-25"
    #   "State General Fund support for the University totals $X billion"
    patterns = [
        r"State General Fund support for UC totals\s*\$([\d,\.]+)\s*(billion|million)",
        r"State General Fund support for the University totals\s*\$([\d,\.]+)\s*(billion|million)",
        r"State General Fund support(?:[^$]{0,60})totals\s*\$([\d,\.]+)\s*(billion|million)",
    ]
    for pat in patterns:
        m = re.search(pat, flat, re.IGNORECASE)
        if m:
            val = float(m.group(1).replace(",", ""))
            val *= 1_000_000_000 if m.group(2).lower() == "billion" else 1_000_000
            return {"uc_systemwide_state_general_fund_usd": val,
                    "matched_phrase": m.group(0)}
    return {}


def extract_california():
    ca_dir = BASE / "ca"
    out = {}
    # Prefer detail PDFs which contain the headline "$X billion" phrase.
    for pdf in sorted(ca_dir.glob("uc_budget_20*_detail.pdf")):
        m = re.search(r"(20\d{2}-\d{2})", pdf.name)
        if not m:
            continue
        fy = m.group(1)
        print(f"[CA] Parsing {pdf.name}...")
        out[fy] = parse_ca_uc(pdf)
    return out


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------
def main():
    # FL
    fl_data = extract_florida()
    (BASE / "fl" / "florida_sus_general_revenue_timeseries.json").write_text(
        json.dumps(fl_data, indent=2, sort_keys=True)
    )

    # TX
    tx_data = parse_tx_sizeup(BASE / "tx" / "tx_fiscal_sizeup_2026-27.pdf")
    (BASE / "tx" / "texas_appropriations_2026-27_biennium.json").write_text(
        json.dumps(tx_data, indent=2, sort_keys=True)
    )

    # CA
    ca_data = extract_california()
    (BASE / "ca" / "uc_systemwide_state_funds_timeseries.json").write_text(
        json.dumps(ca_data, indent=2, sort_keys=True)
    )

    # Unified: per-university matched to our 101-university keys
    unified = {}

    # Florida: map to keys we care about (uf, ucf, usf; also include fsu etc.)
    our_fl_keys = {"uf", "ucf", "usf", "fiu", "fsu", "fau", "famu"}
    for fy, uni_map in fl_data.items():
        for key, rec in uni_map.items():
            if key in our_fl_keys and rec.get("general_revenue"):
                unified.setdefault(key, {"state": "FL", "series": {}})
                unified[key]["series"][fy] = {
                    "state_general_revenue_usd": rec["general_revenue"],
                    "lottery_usd": rec.get("lottery"),
                    "tuition_usd": rec.get("student_tuition"),
                    "source_file": rec.get("source"),
                }

    # Texas: one snapshot for the 2026-27 biennium
    for key in TX_UNIVERSITIES:
        all_f = tx_data.get("all_funds_2026_27_biennium_millions", {}).get(key)
        gr_f = tx_data.get("gr_formula_2026_27_biennium_millions", {}).get(key)
        if all_f or gr_f:
            unified.setdefault(key, {"state": "TX", "series": {}})
            unified[key]["series"]["2026-27_biennium"] = {
                "all_funds_appropriations_usd": (all_f or 0) * 1_000_000 if all_f else None,
                "gr_formula_funding_usd":       (gr_f or 0) * 1_000_000 if gr_f else None,
                "source_file": "tx_fiscal_sizeup_2026-27.pdf",
            }

    # California: systemwide only; apply same total to all UC campus keys
    ca_campus_keys = [
        "ucberkeley", "ucla", "ucsd", "ucsf", "ucdavis",
        "ucirvine", "ucsb", "ucsc", "ucriverside", "ucmerced",
    ]
    for key in ca_campus_keys:
        unified.setdefault(key, {"state": "CA", "series": {}})
        unified[key]["_note"] = (
            "UC Office of the President does not publish per-campus state "
            "general fund appropriations. The series below reflects the UC "
            "systemwide State General Fund total. Campus-level allocation "
            "is determined internally by UCOP."
        )
        for fy, rec in ca_data.items():
            if rec:
                unified[key]["series"][fy] = {
                    "uc_systemwide_state_general_fund_usd":
                        rec.get("uc_systemwide_state_general_fund_usd"),
                    "source_file": f"uc_budget_{fy}_summary.pdf",
                }

    (BASE / "state_specific_funding_by_university.json").write_text(
        json.dumps(unified, indent=2, sort_keys=True)
    )
    print(f"\nWrote unified file with {len(unified)} universities")
    for k, v in sorted(unified.items()):
        print(f"  {k} ({v.get('state')}): {len(v.get('series', {}))} data points")


if __name__ == "__main__":
    main()
