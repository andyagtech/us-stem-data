#!/usr/bin/env python3
"""Schools where foreign students are the majority of graduate enrolment.

WHAT IT COUNTS. Every US institution with at least 100 graduate students where
non-resident aliens are 50% or more of them, in IPEDS Fall Enrollment for 2022,
2023 and 2024; plus, for the schools that qualify in 2024, their three-year
enrolment trend, sector, whether they take part in federal student aid, the
federal aid they took in, and -- for the nonprofits, which file IRS Form 990 --
what they reported paying firms for student recruitment.

WHAT THE FIGURES ARE, EXACTLY.
  * Graduate enrolment is IPEDS EF part A, EFALEVEL 12 with LSTUDY 3 (all
    graduate students); "non-resident" is EFNRALT. Any other level
    double-counts, because the file also carries full- and part-time splits.
  * "Takes part in federal student aid" is the IPEDS directory's OPEFLAG = 1:
    the institution has a Program Participation Agreement for Title IV.
  * Pell grants and federal loans are IPEDS Student Financial Aid 2022-23, and
    they are UNDERGRADUATE: IPEDS does not report graduate federal loans. The
    money is paid to the institution and credited to students' accounts
    against tuition and fees first. Non-resident aliens are not eligible for
    either programme, so these dollars were awarded to the school's eligible
    students -- the school is what receives them.
  * Recruitment payments are as filed on each nonprofit's Form 990 (Part VII
    Section B contractors, or the same table filed in Schedule O, and Part IX
    expense lines naming recruitment). A return filed by a larger parent under
    the same EIN is flagged and not attributed to the campus.

Usage:
  python3 scripts/build_visa_schools.py
"""
from __future__ import annotations

import csv
import io
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from atomic_write import write_json                          # noqa: E402

IPEDS = ROOT / "data" / "ipeds"
HD = IPEDS / "HD2024.csv"
EF = {2022: IPEDS / "enrollment" / "EF2022A.zip",
      2023: IPEDS / "enrollment" / "EF2023A.zip",
      2024: IPEDS / "enrollment" / "EF2024A.zip"}
SFA = IPEDS / "sfa" / "SFA2223.zip"
RECRUIT = ROOT / "data" / "irs990" / "recruitment_990.json"
OUT = ROOT / "site" / "data" / "visa_schools.json"

MIN_GRAD = 100                       # smaller programmes swing on a handful of students
THRESHOLDS = (50, 80, 90)
CONTROL = {"1": "public", "2": "private nonprofit", "3": "for-profit"}


def _reader(path: Path):
    """Rows of an IPEDS csv, zipped or not, as uppercase-keyed dicts."""
    if path.suffix.lower() == ".zip":
        z = zipfile.ZipFile(path)
        inner = next(n for n in z.namelist() if n.lower().endswith(".csv")
                     and "_rv" not in n.lower())
        fh = io.TextIOWrapper(z.open(inner), encoding="utf-8-sig", errors="replace")
    else:
        fh = open(path, encoding="utf-8-sig", errors="replace")
    for r in csv.DictReader(fh):
        yield {k.strip().upper(): (v or "").strip() for k, v in r.items() if k}


def _int(v: str) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


def directory() -> dict[str, dict]:
    out = {}
    for r in _reader(HD):
        out[r["UNITID"]] = {"unitid": r["UNITID"], "name": r["INSTNM"], "city": r["CITY"],
                            "state": r["STABBR"], "control": CONTROL.get(r["CONTROL"], "unknown"),
                            "ein": r.get("EIN", ""), "title_iv": r.get("OPEFLAG") == "1",
                            "web": r.get("WEBADDR", "")}
    return out


def enrolment(year: int) -> dict[str, dict]:
    """UNITID -> {grad, grad_nra, total, total_nra} for one fall."""
    out: dict[str, dict] = {}
    for r in _reader(EF[year]):
        key = (r["EFALEVEL"], r["LSTUDY"])
        if key not in (("12", "3"), ("1", "4")):
            continue
        rec = out.setdefault(r["UNITID"], {})
        if key == ("12", "3"):
            rec["grad"], rec["grad_nra"] = _int(r["EFTOTLT"]), _int(r["EFNRALT"])
        else:
            rec["total"], rec["total_nra"] = _int(r["EFTOTLT"]), _int(r["EFNRALT"])
    return out


def federal_aid() -> dict[str, dict]:
    """UNITID -> undergraduate Pell and federal loan recipients and dollars, 2022-23."""
    out = {}
    for r in _reader(SFA):
        out[r["UNITID"]] = {"pell_recipients": _int(r.get("UPGRNTN")),
                            "pell_dollars": _int(r.get("UPGRNTT")),
                            "federal_loan_recipients": _int(r.get("UFLOANN")),
                            "federal_loan_dollars": _int(r.get("UFLOANT"))}
    return out


def recruitment() -> dict[str, dict]:
    """UNITID -> recruitment payments per tax year, from the 990 extract.

    Two bases, never added together because they can overlap: payments to
    named contractors whose filed services are recruitment (Part VII Section
    B), and expense lines whose filed description names recruitment (Part IX).
    Only contractors the extract marked recruitment_related count: the same
    return also lists course developers and consultants, and summing every
    listed contractor would have overstated Harrisburg by about $2.2 million.

    A return filed under a larger parent's EIN is kept, not zeroed, and
    flagged: for Trine's regional record the parent IS Trine University, and
    the page says the amount is the whole university's.
    """
    if not RECRUIT.exists():
        return {}
    out = {}
    for s in json.loads(RECRUIT.read_text()):
        years = []
        for ret in s.get("returns") or []:
            firms = [c for c in ret.get("recruitment_contractors") or []
                     if c.get("recruitment_related") is True and isinstance(c.get("amount"), int)]
            lines = [x for x in ret.get("recruitment_expense_lines") or []
                     if isinstance(x.get("amount"), int) and x["amount"] > 0]
            if not firms and not lines:
                continue
            years.append({"tax_period_end": ret.get("tax_period_end"),
                          "object_id": ret.get("object_id"),
                          "firms": [{"name": c["name"], "services": c.get("services"),
                                     "amount": c["amount"]} for c in firms if c["amount"] > 0],
                          "firms_total": sum(c["amount"] for c in firms),
                          "expense_lines": [{"desc": x["desc"], "amount": x["amount"]} for x in lines],
                          "expense_lines_total": sum(x["amount"] for x in lines),
                          "total_revenue": ret.get("total_revenue")})
        years.sort(key=lambda y: y["tax_period_end"] or "")
        firms_total = sum(y["firms_total"] for y in years)
        lines_total = sum(y["expense_lines_total"] for y in years)
        out[str(s["unitid"])] = {
            "filer_name": s.get("filer_name"),
            "filer_is_parent": bool(s.get("filer_is_parent")),
            "returns_checked": len(s.get("returns") or []),
            "years": years,
            "firms_total": firms_total,
            "expense_lines_total": lines_total,
            # What the table shows: named recruiting firms when the school lists
            # any, otherwise its recruitment expense lines, labelled as such.
            "headline": ({"basis": "firms", "amount": firms_total} if firms_total else
                         {"basis": "expense_lines", "amount": lines_total,
                          "label": "; ".join(sorted({x["desc"] for y in years for x in y["expense_lines"]}))}
                         if lines_total else None)}
    return out


def main() -> int:
    missing = [p for p in [HD, SFA, *EF.values()] if not p.exists()]
    if missing:
        print("  missing inputs: " + ", ".join(str(p.relative_to(ROOT)) for p in missing))
        return 1
    hd, aid, rec = directory(), federal_aid(), recruitment()
    ef = {y: enrolment(y) for y in EF}

    summary = {}
    for y, rows in ef.items():
        grads = [v for v in rows.values() if v.get("grad")]
        nat_grad = sum(v["grad"] for v in grads)
        nat_nra = sum(v["grad_nra"] for v in grads)
        by = {}
        for t in THRESHOLDS:
            sel = [u for u, v in rows.items() if v.get("grad", 0) >= MIN_GRAD
                   and v["grad_nra"] * 100 >= t * v["grad"]]
            by[str(t)] = {
                "schools": len(sel),
                "nonresident_grad_students": sum(rows[u]["grad_nra"] for u in sel),
                "grad_students": sum(rows[u]["grad"] for u in sel),
                "take_federal_student_aid": sum(1 for u in sel if hd.get(u, {}).get("title_iv")),
                "by_sector": {c: sum(1 for u in sel if hd.get(u, {}).get("control") == c)
                              for c in CONTROL.values()},
            }
        summary[str(y)] = {"national_grad_students": nat_grad,
                           "national_nonresident_grad_students": nat_nra,
                           "national_nonresident_share_pct": round(100 * nat_nra / nat_grad, 1),
                           "at_or_above": by}

    latest = max(ef)
    schools = []
    for u, v in ef[latest].items():
        if v.get("grad", 0) < MIN_GRAD or v["grad_nra"] * 2 < v["grad"]:
            continue
        d = hd.get(u, {"unitid": u, "name": f"UNITID {u}", "control": "unknown"})
        trend = {str(y): ({"grad": ef[y][u]["grad"], "grad_nra": ef[y][u]["grad_nra"]}
                          if u in ef[y] and ef[y][u].get("grad") else None) for y in EF}
        rr = rec.get(u)
        schools.append({**d,
                        "grad": v["grad"], "grad_nra": v["grad_nra"],
                        "grad_nra_share_pct": round(100 * v["grad_nra"] / v["grad"], 1),
                        "total": v.get("total"), "total_nra": v.get("total_nra"),
                        "trend": trend,
                        "federal_aid_2022_23": aid.get(u),
                        "recruitment_990": rr})
    schools.sort(key=lambda s: (-s["grad_nra_share_pct"], -s["grad_nra"]))

    maj = summary[str(latest)]["at_or_above"]["50"]
    aid_rows = [s["federal_aid_2022_23"] for s in schools if s["federal_aid_2022_23"]]
    totals = {"schools": len(schools),
              "pell_dollars": sum(a["pell_dollars"] for a in aid_rows),
              "pell_recipients": sum(a["pell_recipients"] for a in aid_rows),
              "federal_loan_dollars": sum(a["federal_loan_dollars"] for a in aid_rows),
              "take_federal_student_aid": maj["take_federal_student_aid"],
              "recruitment_filers_checked": sum(1 for s in schools if s["recruitment_990"]),
              "schools_reporting_recruitment": sum(1 for s in schools
                                                   if (s["recruitment_990"] or {}).get("headline")),
              "recruiting_firm_dollars": sum((s["recruitment_990"] or {}).get("firms_total", 0)
                                             for s in schools)}
    out = {
        "_comment": __doc__.split("Usage:")[0].strip(),
        "sources": {
            "enrolment": "NCES IPEDS Fall Enrollment, part A, fall 2022-2024",
            "directory": "NCES IPEDS Institutional Characteristics directory, 2024",
            "federal_aid": "NCES IPEDS Student Financial Aid, 2022-23 (undergraduate)",
            "recruitment": "IRS Form 990 e-file returns (IRS bulk release)",
            "urls": ["https://nces.ed.gov/ipeds/use-the-data",
                     "https://www.irs.gov/charities-non-profits/form-990-series-downloads"]},
        "rules": {"min_grad_students": MIN_GRAD, "majority_threshold_pct": 50,
                  "graduate": "EFALEVEL 12, LSTUDY 3", "nonresident": "EFNRALT",
                  "federal_aid_participation": "OPEFLAG = 1"},
        "latest_fall": latest,
        "summary": summary,
        "totals": totals,
        "schools": schools,
    }
    write_json(OUT, out, indent=1)
    s = summary[str(latest)]["at_or_above"]
    print(f"  wrote {OUT.relative_to(ROOT)}: {len(schools)} majority-foreign schools in fall {latest} "
          f"(>=80%: {s['80']['schools']}, >=90%: {s['90']['schools']}); "
          f"Pell ${totals['pell_dollars']:,}, federal loans ${totals['federal_loan_dollars']:,}; "
          f"990s checked for {totals['recruitment_filers_checked']}, "
          f"{totals['schools_reporting_recruitment']} report recruitment, "
          f"firms paid ${totals['recruiting_firm_dollars']:,}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
