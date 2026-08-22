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


def test_soc_code_normalisation():
    """Only the .00 base suffix collapses; detail codes stay distinct."""
    from pipeline.step3_parse_federal import _normalize_soc
    assert _normalize_soc("25-1032.00", "Engineering Teachers")[0] == "25-1032"
    assert _normalize_soc("25-1032", "ENGINEERING TEACHERS")[0] == "25-1032"
    assert _normalize_soc("25-1032.01", "X")[0] == "25-1032.01"
    assert _normalize_soc('="25-1032.00"', '="X Y"') == ("25-1032", "X Y")


def test_one_soc_code_yields_one_row(lca_dir):
    """The same occupation spelled three ways must not appear three times.

    Case rules cannot fix this: 'Biochemists and Biophysicists' and
    'Biochemists And Biophysicists' both occur in DOL's own files, alongside
    truncations. Counting is keyed on the code.
    """
    rows = [_row(f"I-200-{i}", soc=c) for i, c in
            enumerate(["19-1021.00", "19-1021", "19-1021.00"])]
    header = MODERN
    recs = []
    for r, nm in zip(rows, ["Biochemists and Biophysicists",
                            "BIOCHEMISTS AND BIOPHYSICISTS",
                            "Biochemists and Biophysicists"]):
        r = list(r); r[5] = nm; recs.append(r)
    _write(lca_dir, "modern", header, recs)
    out = _parse_lca_duckdb(lca_dir, EMAP)
    soc = out["stanford"]["top_soc"]
    assert len(soc) == 1, soc
    assert soc[0] == ["19-1021 Biochemists and Biophysicists", 3], soc


def test_truncated_soc_name_loses_to_the_full_one():
    """The short variant is usually a truncation, so length breaks ties."""
    from collections import Counter
    from pipeline.step3_parse_federal import _best_soc_name
    names = {"25-1124": Counter({"Foreign Language And Literature Teachers,": 8,
                                 "Foreign Language and Literature Teachers, Postsecondary": 8})}
    assert _best_soc_name(names, "25-1124").endswith("Postsecondary")


def test_all_caps_soc_names_are_cased_for_display():
    from collections import Counter
    from pipeline.step3_parse_federal import _best_soc_name, _display_case
    assert _display_case("BIOCHEMISTS AND BIOPHYSICISTS") == "Biochemists and Biophysicists"
    assert _display_case("CHEMISTS") == "Chemists"
    # Mixed-case input is left alone; re-casing would corrupt forms like R&D.
    assert _display_case("Mechanical Engineers, R&D") == "Mechanical Engineers, R&D"
    names = {"19-2031": Counter({"CHEMISTS": 5})}
    assert _best_soc_name(names, "19-2031") == "Chemists"


# --- legal representation -------------------------------------------------

LEGAL = MODERN + ["LAWFIRM_NAME_BUSINESS_NAME", "AGENT_ATTORNEY_LAST_NAME",
                  "AGENT_ATTORNEY_FIRST_NAME", "AGENT_ATTORNEY_STATE",
                  "AGENT_REPRESENTING_EMPLOYER"]


def _legal_row(case, firm="Fragomen LLP", last="Ng", first="Alice",
               state="NY", agent="Y"):
    return _row(case) + [firm, last, first, state, agent]


def test_legal_fields_are_optional_not_fatal(lca_dir):
    """FY2013 has no legal columns at all; that must not fail the build."""
    _write(lca_dir, "legacy", LEGACY, [_row("I-200-A")])
    out = _parse_lca_duckdb(lca_dir, EMAP)
    assert out["stanford"]["total_lcas"] == 1
    assert out["_legal"]["_meta"]["distinct_firms"] == 0


def test_firms_and_attorneys_are_counted(lca_dir):
    _write(lca_dir, "modern", LEGAL, [
        _legal_row("I-200-A"),
        _legal_row("I-200-B"),
        _legal_row("I-200-C", firm="Ogletree PC", last="Diaz", first="Luis"),
    ])
    L = _parse_lca_duckdb(lca_dir, EMAP)["_legal"]
    u = L["universities"]["stanford"]
    assert u["top_firms"][0] == ["FRAGOMEN LLP", 2], u["top_firms"]
    assert u["with_named_firm"] == 3
    assert ["Ng, Alice", 2] in u["top_attorneys"]


def test_firm_suffix_punctuation_is_folded(lca_dir):
    """'Fragomen L.L.P.' and 'Fragomen LLP' are one firm, not two."""
    _write(lca_dir, "modern", LEGAL, [
        _legal_row("I-200-A", firm="Fragomen LLP"),
        _legal_row("I-200-B", firm="Fragomen L.L.P."),
        _legal_row("I-200-C", firm="Fragomen LLP,"),
    ])
    L = _parse_lca_duckdb(lca_dir, EMAP)["_legal"]
    assert L["universities"]["stanford"]["top_firms"] == [["FRAGOMEN LLP", 3]]


def test_placeholder_firm_names_are_dropped(lca_dir):
    _write(lca_dir, "modern", LEGAL, [
        _legal_row("I-200-A", firm="N/A"),
        _legal_row("I-200-B", firm="  "),
        _legal_row("I-200-C", firm="Real Firm LLP"),
    ])
    L = _parse_lca_duckdb(lca_dir, EMAP)["_legal"]
    assert L["universities"]["stanford"]["with_named_firm"] == 1


def test_self_filed_is_counted(lca_dir):
    _write(lca_dir, "modern", LEGAL, [
        _legal_row("I-200-A", firm="", last="", first="", agent="N"),
        _legal_row("I-200-B", agent="Y"),
    ])
    u = _parse_lca_duckdb(lca_dir, EMAP)["_legal"]["universities"]["stanford"]
    assert u["self_filed"] == 1, u


def test_attorney_contact_details_are_never_collected(lca_dir):
    """Email and phone exist in the source and must not reach the output."""
    header = LEGAL + ["AGENT_ATTORNEY_EMAIL_ADDRESS", "AGENT_ATTORNEY_PHONE"]
    _write(lca_dir, "modern", header,
           [_legal_row("I-200-A") + ["alice@firm.com", "212-555-0100"]])
    blob = json.dumps(_parse_lca_duckdb(lca_dir, EMAP)["_legal"])
    assert "alice@firm.com" not in blob and "212-555-0100" not in blob


def test_legal_aggregate_is_split_out_of_the_university_dict(lca_dir, tmp_path):
    """_parse_lca_files must return only universities; _legal goes to a file."""
    from pipeline.step3_parse_federal import _parse_lca_files
    _write(lca_dir, "modern", LEGAL, [_legal_row("I-200-A")])
    base = lca_dir.parent.parent.parent
    out = _parse_lca_files(base, EMAP)
    assert "_legal" not in out, list(out)
    written = base / "data" / "h1b" / "lca_legal_by_university.json"
    assert written.exists()
    assert json.loads(written.read_text())["universities"]["stanford"]
