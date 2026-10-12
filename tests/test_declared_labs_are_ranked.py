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
