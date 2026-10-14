"""Every hand-supplied lab must reach the ranker.

research_labs.json holds the labs the author named himself -- the two
that started this work, Mo Li's LIGHT and Jenq-Neng Hwang's IPL at
Washington. rank_research_labs reads discovered_labs.json and nothing
else, so for as long as the two files stayed separate those two were
measured, written down, and never once considered for the table.

Nobody noticed because the table filled up with labs found by
crawling. The author asked where his own examples had gone.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

DECLARED = ROOT / "data" / "labs" / "research_labs.json"
DISCOVERED = ROOT / "data" / "labs" / "discovered_labs.json"


def test_every_declared_lab_is_in_the_ranked_pool():
    if not DECLARED.exists():
        return
    declared = json.loads(DECLARED.read_text()).get("labs", [])
    if not declared:
        return
    known = {g["url"] for g in json.loads(DISCOVERED.read_text())["groups"]}
    missing = []
    for lab in declared:
        urls = {lab.get("roster_url"), lab.get("home_url")} - {None, ""}
        if urls and not (urls & known):
            missing.append(lab.get("name") or next(iter(urls)))
    assert not missing, (
        "hand-supplied labs absent from the ranked pool, so they can "
        f"never appear in the table: {missing}")


# --- one name per university ----------------------------------------------

def test_no_university_appears_under_two_names():
    """The directory was assembled by four crawlers that learned an
    institution's name from different places, so the same university arrived
    twice and the published count counted both. "94 labs at 39 universities"
    was really 36: Stanford, Georgia Tech and the University of Washington
    were each in the list twice."""
    import json
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    from lab_overrides import apply, CANONICAL_INSTITUTION

    rows = apply(list(json.loads(
        (root / "data" / "labs" / "lab_outliers.json").read_text())["outliers"]))
    names = {r["institution"] for r in rows if r.get("institution")}
    leaked = sorted(names & set(CANONICAL_INSTITUTION))
    assert leaked == [], leaked


def test_the_canonical_map_points_at_names_the_data_uses():
    """A target nobody uses would silently create a 37th university."""
    import json
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    from lab_overrides import apply, CANONICAL_INSTITUTION

    rows = apply(list(json.loads(
        (root / "data" / "labs" / "lab_outliers.json").read_text())["outliers"]))
    names = {r["institution"] for r in rows}
    unused = sorted(set(CANONICAL_INSTITUTION.values()) - names)
    assert unused == [], unused
