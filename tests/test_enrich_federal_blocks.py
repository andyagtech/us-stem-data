"""The federal blocks in a university JSON are owned by step4_enrich.

They used to be merged additively -- `if key in lca: enriched["lca"] = ...`
with no delete -- so a block written by an older build was never removed. It
survived every subsequent run because the branch that would overwrite it only
fires for keys the CURRENT source still has. Three universities were shipping
LCA totals older than any lca_by_university.json on disk, and no rebuild could
dislodge them.
"""
from pipeline.step4_enrich import _enrich_university


def test_stale_block_is_dropped_when_the_source_loses_the_key():
    stale = {"name": "Rice", "lca": {"total_lcas": 1121}}
    out = _enrich_university(stale, "rice", h1b={}, opt={}, lca={}, perm={})
    assert "lca" not in out, out


def test_current_source_still_populates():
    out = _enrich_university({"name": "MIT"}, "mit", h1b={}, opt={},
                             lca={"mit": {"total_lcas": 2401}}, perm={})
    assert out["lca"]["total_lcas"] == 2401


def test_stale_block_is_replaced_not_merged():
    stale = {"lca": {"total_lcas": 999, "wage_median": 1}}
    out = _enrich_university(stale, "mit", h1b={}, opt={},
                             lca={"mit": {"total_lcas": 2401}}, perm={})
    assert out["lca"] == {"total_lcas": 2401}, out


def test_all_four_federal_blocks_are_cleared():
    stale = {"h1b": {"a": 1}, "opt": {"b": 2}, "lca": {"c": 3}, "perm": {"d": 4},
             "name": "keep me"}
    out = _enrich_university(stale, "nobody", h1b={}, opt={}, lca={}, perm={})
    assert set(out) == {"name"}, out


def test_non_federal_fields_are_untouched():
    d = {"name": "X", "records": [1, 2, 3], "nra": 29.8, "lca": {"total_lcas": 1}}
    out = _enrich_university(d, "x", h1b={}, opt={}, lca={}, perm={})
    assert out["records"] == [1, 2, 3] and out["nra"] == 29.8


def test_a_newly_processed_university_is_not_skipped(tmp_path):
    """The union of both directories, not just this step's previous output.

    Reading only site/data/ meant a university processed for the first time
    was invisible until a second identical run.
    """
    from pipeline.step4_enrich import _keys_to_enrich
    proc, site = tmp_path / "processed", tmp_path / "site"
    proc.mkdir(); site.mkdir()
    (proc / "old.json").write_text("{}")
    (site / "old.json").write_text("{}")
    (proc / "new.json").write_text("{}")      # only in the fresh output
    (site / "retired.json").write_text("{}")  # only in the previous output
    assert _keys_to_enrich(proc, site) == {"old", "new", "retired"}


def test_underscore_and_non_json_files_are_ignored(tmp_path):
    from pipeline.step4_enrich import _keys_to_enrich
    d = tmp_path / "p"; d.mkdir()
    (d / "_index.json").write_text("{}")
    (d / "notes.txt").write_text("x")
    (d / "real.json").write_text("{}")
    assert _keys_to_enrich(d, tmp_path / "missing") == {"real"}
