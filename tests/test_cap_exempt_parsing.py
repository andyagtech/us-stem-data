"""The cap-exempt tables are scanned PDFs; the numbers must be checked.

USCIS publishes these counts as an ACWIA FEE exemption table in its annual
Report on H-1B Petitions. The employer rows are the same statutory categories
that make an employer exempt from the numerical cap, which is the only reason
the figures are usable for that question at all.

The older reports are scans. pdftotext returns "1.330" for 1,330 and
"4 ,654" for 4,654, and those parse into numbers that are simply wrong
without raising anything. Every row therefore reconciles four quarters
against the printed annual total before it is accepted.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import download_h1b_cap_exempt as M  # noqa: E402


CLEAN = """
 REASONS FOR EXEMPTION 8
      Employer is an institution of higher
      education
                                         4,837    6,055    9,306    6,751    26,949
      Employer is a nonprofit organization
      or entity related to, or affiliated with 3,772  5,274  8,975  6,052    24,073
      an institution of higher education
      Employer is a nonprofit research
      organization or a government             1,675  1,857  2,162  1,866     7,560
      organization
"""


def test_the_three_cap_exempt_categories_are_read():
    got, rejected = M.parse_table(CLEAN.splitlines())
    assert got["higher_education"] == 26949
    assert got["affiliated_nonprofit"] == 24073
    assert got["research_organization"] == 7560
    assert rejected == []


def test_a_row_whose_quarters_do_not_sum_is_rejected():
    bad = CLEAN.replace("4,837    6,055    9,306    6,751    26,949",
                        "4,837    6,055    9,306    6,751    99,999")
    got, rejected = M.parse_table(bad.splitlines())
    assert "higher_education" not in got
    assert any(r.startswith("higher_education") for r in rejected)


# --- the scan artefacts, which reconcile only after repair ---------------

SCANNED_FY2018 = """
 REASONS FOR EXEMPTION 11
      Employer is a nonprofit organization
      or entity related to, or affiliated with 1.330   2.397   4.45 1   2,556   10,734
      an institution ofhigher education
"""

SCANNED_FY2019 = """
 REASONS FOR EXEMPTION 11
      Employer is a nonprofit organization
      or entity related to, or affiliated with
      1,561   2,444   4 ,654   2,983   11,642
"""


@pytest.mark.parametrize("text,want", [(SCANNED_FY2018, 10734),
                                       (SCANNED_FY2019, 11642)])
def test_scan_artefacts_are_repaired_and_then_verified(text, want):
    """The repair is accepted only because the quarters then sum correctly.

    1,330 + 2,397 + 4,451 + 2,556 = 10,734, exactly the printed figure. That
    checksum is what makes the repair a correction rather than a guess.
    """
    got, _rejected = M.parse_table(text.splitlines())
    assert got["affiliated_nonprofit"] == want


def test_the_raw_line_failing_does_not_consume_the_repair_attempt():
    """"4 ,654" parses to 654, giving five numbers that do not reconcile.

    An early exit there left FY2019 with no value at all rather than falling
    through to the repaired line.
    """
    got, _ = M.parse_table(SCANNED_FY2019.splitlines())
    assert got.get("affiliated_nonprofit") == 11642


def test_narrative_text_outside_the_table_is_not_scanned():
    """The prose before the table names every category too.

    Searching the whole document matched there and then ran forward to the
    next row with five numbers, which reported FY2021's research
    organisations as 78,848 instead of 5,932.
    """
    prose = ("The exemptions apply to employers that are: an institution of higher "
             "education; a nonprofit research organization.\n") * 3
    got, rejected = M.parse_table(prose.splitlines())
    assert got == {} and rejected == ["no 'reasons for exemption' block"]


# --- the published dataset ---------------------------------------------

def test_every_published_year_has_the_three_categories():
    import json
    p = ROOT / "data" / "h1b" / "h1b_cap_exempt.json"
    if not p.exists():
        pytest.skip("dataset not built")
    doc = json.loads(p.read_text())
    assert doc["cap_exempt_categories"] == [
        "higher_education", "affiliated_nonprofit", "research_organization"]
    for year, rec in doc["series"].items():
        for key in doc["cap_exempt_categories"]:
            assert rec["filed"].get(key), f"FY{year} missing {key}"


def test_primary_secondary_is_not_counted_as_cap_exempt():
    """It is fee-exempt but NOT cap-exempt, and the two must not be merged."""
    import json
    p = ROOT / "data" / "h1b" / "h1b_cap_exempt.json"
    if not p.exists():
        pytest.skip("dataset not built")
    doc = json.loads(p.read_text())
    assert "primary_secondary" not in doc["cap_exempt_categories"]
    assert "NOT cap-exempt" in doc["labels"]["primary_secondary"]
