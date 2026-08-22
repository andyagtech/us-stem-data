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
