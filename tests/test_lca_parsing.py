"""Tests for the LCA read path.

These exist because of a specific silent failure: reading all DOL CSVs through
one read_csv() glob with union_by_name + auto_detect made DuckDB mis-sniff the
header on the older layouts. The union came back with 506 columns whose names
were data values, five files had a NULL case number for every row, and the
dedup dropped them wholesale -- 1.6M rows gone, no error, a published total
that was simply wrong. The guard tested here turns that into a hard failure.
"""
import csv
import json
from pathlib import Path

import pytest

from pipeline.step3_parse_federal import _parse_lca_duckdb, _top_n, _strip_excel_formula

pytest.importorskip("duckdb")

MODERN = ["CASE_NUMBER", "CASE_STATUS", "EMPLOYER_NAME", "JOB_TITLE",
          "SOC_CODE", "SOC_TITLE", "WAGE_RATE_OF_PAY_FROM",
          "WAGE_UNIT_OF_PAY", "DECISION_DATE"]
# FY2013's layout: every field carries an LCA_ prefix and there is no
# DECISION_DATE at all.
LEGACY = ["LCA_CASE_NUMBER", "STATUS", "LCA_CASE_EMPLOYER_NAME",
          "LCA_CASE_JOB_TITLE", "LCA_CASE_SOC_CODE", "LCA_CASE_SOC_NAME",
          "LCA_CASE_WAGE_RATE_FROM", "LCA_CASE_WAGE_RATE_UNIT",
          "LCA_CASE_SUBMIT"]


def _row(case, employer="STANFORD UNIVERSITY", title="Postdoctoral Scholar",
         soc="19-1042", wage="70000", date="2021-03-04"):
    return [case, "CERTIFIED", employer, title, soc, "Medical Scientists",
            wage, "Year", date]


def _write(lca_dir: Path, name: str, header: list[str], rows: list[list[str]]):
    (lca_dir / f"{name}.xlsx").write_bytes(b"")   # presence only; never opened
    cache = lca_dir / "csv_cache"
    cache.mkdir(exist_ok=True)
    with open(cache / f"{name}.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)


@pytest.fixture
def lca_dir(tmp_path):
    d = tmp_path / "data" / "h1b" / "lca"
    d.mkdir(parents=True)
    return d


EMAP = {"STANFORD UNIVERSITY": "stanford"}


def test_legacy_and_modern_layouts_both_contribute(lca_dir):
    """A 2013-style file and a modern one must both reach the aggregate."""
    _write(lca_dir, "modern", MODERN, [_row("I-200-A")])
    _write(lca_dir, "legacy", LEGACY, [_row("I-200-B")])
    out = _parse_lca_duckdb(lca_dir, EMAP)
    assert out["stanford"]["total_lcas"] == 2, out


def test_overlapping_quarters_are_deduplicated(lca_dir):
    """The same case in two files counts once, not twice."""
    _write(lca_dir, "q1", MODERN, [_row("I-200-A"), _row("I-200-B")])
    _write(lca_dir, "q3", MODERN, [_row("I-200-A"), _row("I-200-B"), _row("I-200-C")])
    out = _parse_lca_duckdb(lca_dir, EMAP)
    assert out["stanford"]["total_lcas"] == 3, out


def test_unrecognised_case_column_raises(lca_dir):
    """The exact defect: a layout whose key column we do not know.

    It must fail loudly. Silently dropping the file produces a plausible
    smaller number that nothing downstream can detect.
    """
    _write(lca_dir, "modern", MODERN, [_row("I-200-A")])
    weird = ["MYSTERY_ID"] + MODERN[1:]
    _write(lca_dir, "weird", weird, [_row("I-200-B")])
    with pytest.raises(RuntimeError, match="weird"):
        _parse_lca_duckdb(lca_dir, EMAP)


def test_employer_match_is_exact_not_substring(lca_dir):
    """'MIT' must not sweep in INFOSYS LIMITED."""
    _write(lca_dir, "modern", MODERN, [
        _row("I-200-A", employer="MIT"),
        _row("I-200-B", employer="INFOSYS LIMITED"),
        _row("I-200-C", employer="SUMMIT HEALTH"),
    ])
    out = _parse_lca_duckdb(lca_dir, {"MIT": "mit"})
    assert out["mit"]["total_lcas"] == 1, out


def test_contact_job_title_is_not_mistaken_for_the_worker_title(lca_dir):
    """EMPLOYER_POC_JOB_TITLE must never win over JOB_TITLE."""
    header = MODERN + ["EMPLOYER_POC_JOB_TITLE"]
    _write(lca_dir, "modern", header, [_row("I-200-A") + ["HR Manager"]])
    out = _parse_lca_duckdb(lca_dir, EMAP)
    titles = [t[0] for t in out["stanford"]["top_titles"]]
    assert "Hr Manager" not in titles, titles
    assert "Postdoctoral Scholar" in titles, titles


def test_top_n_breaks_ties_deterministically():
    from collections import Counter
    assert _top_n(Counter({"b": 5, "a": 5, "c": 9})) == [["c", 9], ["a", 5], ["b", 5]]


def test_excel_formula_artifact_is_stripped():
    assert _strip_excel_formula('="25-1032.00"') == "25-1032.00"
    assert _strip_excel_formula("25-1032.00 ") == "25-1032.00"


def test_guard_is_not_swallowed_by_a_fallback(lca_dir):
    """The guard must reach the caller of _parse_lca_files, not just _duckdb.

    _parse_lca_files() used to wrap the DuckDB parser in `except Exception`
    and fall back to an openpyxl parser that did NO deduplication. That path
    would have caught the dropped-file guard and answered with an inflated,
    double-counted total -- the worst possible response to "this data is
    wrong". There is no fallback now, so the guard has to propagate.
    """
    from pipeline.step3_parse_federal import _parse_lca_files
    _write(lca_dir, "modern", MODERN, [_row("I-200-A")])
    _write(lca_dir, "weird", ["MYSTERY_ID"] + MODERN[1:], [_row("I-200-B")])
    base = lca_dir.parent.parent.parent          # <tmp>/data/h1b/lca -> <tmp>
    with pytest.raises(RuntimeError, match="weird"):
        _parse_lca_files(base, EMAP)


def test_parse_lca_files_returns_the_deduplicated_aggregate(lca_dir):
    """Happy path through the public entry point, with overlap."""
    from pipeline.step3_parse_federal import _parse_lca_files
    _write(lca_dir, "q1", MODERN, [_row("I-200-A")])
    _write(lca_dir, "q3", MODERN, [_row("I-200-A"), _row("I-200-B")])
    out = _parse_lca_files(lca_dir.parent.parent.parent, EMAP)
    assert out["stanford"]["total_lcas"] == 2, out


def test_a_missing_wage_column_is_not_tolerated(lca_dir):
    """FY2019 names its wage columns WAGE_RATE_OF_PAY_FROM_1.

    Before that alias existed the file matched on case number and employer,
    passed the key check, and silently contributed no wages -- the same loss
    as a dropped file, just harder to see. Every canonical field must resolve.
    """
    header = [h for h in MODERN if h != "WAGE_RATE_OF_PAY_FROM"] + ["WAGE_MYSTERY"]
    _write(lca_dir, "odd", header, [[
        "I-200-A", "CERTIFIED", "STANFORD UNIVERSITY", "Postdoc",
        "19-1042", "Medical Scientists", "Year", "2021-03-04", "70000"]])
    with pytest.raises(RuntimeError, match="wage_from"):
        _parse_lca_duckdb(lca_dir, EMAP)


def test_fy2019_numbered_worksite_wage_columns_resolve(lca_dir):
    """The _1 suffix is the primary worksite and must be picked up."""
    header = ["CASE_NUMBER", "CASE_STATUS", "EMPLOYER_NAME", "JOB_TITLE",
              "SOC_CODE", "SOC_TITLE", "WAGE_RATE_OF_PAY_FROM_1",
              "WAGE_UNIT_OF_PAY_1", "DECISION_DATE"]
    _write(lca_dir, "fy2019", header, [_row("I-200-A")])
    out = _parse_lca_duckdb(lca_dir, EMAP)
    assert out["stanford"]["wage_median"] == 70000, out
