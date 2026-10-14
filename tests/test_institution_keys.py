"""A lab is measured against its own university or against nothing.

The ranker takes a laboratory's baseline from the surrounding
department's doctorates in this site's thesis record, which means it
has to turn a crawled institution name into a record key. It used to do
that by scoring token overlap against the record's display names, and
those names are abbreviations, so the scoring resolved confidently and
wrongly: "University of California-Berkeley" became caltech because
"California Institute of Technology" tokenises to {california};
"University of Missouri-Columbia" became columbia, the one in New York.

CLAUDE.md states the rule: a false baseline is worse than no baseline,
because it tests a group against a department it has nothing to do with
and the number looks exactly as real as a right one.

Each pair below was measured on 2026-10-14 against the 106 keys in the
record. The WRONG map is what the old resolver returned.
"""
import csv
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from institution_keys import key_for, known                   # noqa: E402

#: crawled name -> the key it must resolve to
RIGHT = {
    "University of California-Berkeley": "ucberkeley",
    "University of Arizona": "uarizona",
    "University of Texas at Austin": "utaustin",
    "The University of Texas at Austin": "utaustin",
    "Michigan Technological University": "mtu",
    "Washington University in St Louis": "washu",
    "University of Missouri-Columbia": "umissouri",
    "University of Pennsylvania": "upenn",
    "Virginia Polytechnic Institute and State University": "vt",
    "University of Central Florida": "ucf",
    "University of Kansas": "ukansas",
    "University of Utah": "uutah",
    "University of Connecticut": "uconn",
    "North Carolina State University at Raleigh": "ncstate",
    "Louisiana State University and Agricultural & Mechanical College": "lsu",
    "Pennsylvania State University-Main Campus": "penn_state",
    "University of Tennessee-Knoxville": "utk",
    "Colorado School of Mines": "mines",
    #: short house spellings the crawlers also produce
    "Stanford": "stanford",
    "UW Seattle": "uw_seattle",
    "Georgia Tech": "gatech",
    "MIT": "mit",
}

#: crawled name -> the key the old resolver guessed. These universities
#: are not in the thesis record at all, so the only honest answer is
#: no baseline.
WAS_A_GUESS = {
    "Florida State University": "uf",
    "Florida Atlantic University": "uf",
    "Florida International University": "uf",
    "Oregon State University": "uoregon",
    "Illinois Institute of Technology": "niu",
    "Georgia State University": "gatech",
    "Texas A&M University-College Station": "unt",
    "Texas A & M University-College Station": "unt",
    "University of Southern California": "caltech",
    "University of Georgia": "gatech",
    "Ohio University-Main Campus": "osu",
    "North Dakota State University-Main Campus": "und",
    "Western Michigan University": "msu",
    "Brown University": "",
    "Lehigh University": "",
    "Princeton University": "",
}


@pytest.mark.parametrize("name,key", sorted(RIGHT.items()))
def test_resolves_to_its_own_university(name, key):
    assert key_for(name) == key, f"{name!r} resolved to the wrong university"


@pytest.mark.parametrize("name,guess", sorted(WAS_A_GUESS.items()))
def test_an_unknown_university_gets_no_baseline(name, guess):
    got = key_for(name)
    assert got == "", (
        f"{name!r} is not in the thesis record, so it must resolve to "
        f'"" and be reported without a baseline; got {got!r}'
    )
    if guess:
        assert got != guess, f"{name!r} resolved to {guess!r} again"


def test_keys_filter_is_applied():
    """A key the catalogue knows but the dataset does not is no baseline."""
    assert key_for("Stanford University", {"stanford"}) == "stanford"
    assert key_for("Stanford University", {"mit"}) == ""


def test_every_key_in_the_catalogue_is_reachable_by_some_name():
    """A key nothing maps to can never supply a baseline."""
    cat = json.loads((ROOT / "pipeline" / "universities.json").read_text())
    reachable = set(known().values())
    missing = sorted(set(cat) - reachable)
    assert not missing, f"no name resolves to: {missing}"


def test_the_registered_name_of_every_key_resolves_to_it():
    """The UNITID join is the authority; prove it holds for all 106."""
    hd = {}
    with (ROOT / "cloud" / "chat" / "chat_data" / "hd_names.csv").open() as f:
        for row in csv.DictReader(f):
            hd[int(row["unitid"])] = row["name"]
    cat = json.loads((ROOT / "pipeline" / "universities.json").read_text())
    wrong = []
    for key, meta in cat.items():
        unitid = meta.get("unitid")
        if not unitid or int(unitid) not in hd:
            continue
        got = key_for(hd[int(unitid)])
        if got != key:
            wrong.append((hd[int(unitid)], key, got))
    assert not wrong, f"registered name did not resolve to its own key: {wrong}"
