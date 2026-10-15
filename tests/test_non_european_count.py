"""Every origin the classifier knows counts as non-European.

The author asked twice for this, and the second time about Iranian and
Turkish names specifically. They already counted -- both are merged
into a middle_eastern group and that group is summed into the
non-European total -- but "already true" is not a guarantee, and the
file that computes it builds its groups from a dict literal that a
future edit could quietly drop an origin from.

THE REAL FAILURE THIS GUARDS IS SILENT. non_european_share is used as
a publication threshold: a lab is listed when 55 per cent or more of
its roster is from outside Europe. An origin missing from the GROUPS
map is not an error, a crash or a visible zero. It is a roster scored
lower than it is, and a lab that should be in the table quietly absent
from it.

A Virginia roster of nine, every one from outside Europe, scored 44
per cent before Japanese and Bengali names were classified at all.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from harvest_lab_rosters import composition                   # noqa: E402
from name_classifier import classify                          # noqa: E402

#: category -> generic surnames that must land in it. These are
#: surnames, not people: the point is the classifier's coverage.
ORIGINS = {
    "iranian": ("Hosseini", "Razavi", "Sharifpour", "Mousavi", "Karimi"),
    "turkish": ("Yilmaz", "Ozdemir", "Yalcin", "Kaya", "Demir"),
    "japanese": ("Tanaka", "Suzuki", "Yamamoto", "Nakamura", "Watanabe"),
    "bengali": ("Chowdhury", "Mullick", "Zaman", "Shahnewaz", "Hossain"),
    "chinese": ("Wang", "Zhang", "Liu", "Chen"),
    "korean": ("Kim", "Park", "Jeong"),
    "vietnamese": ("Nguyen", "Tran"),
    "indian": ("Patel", "Sharma", "Gupta"),
    "arabic": ("Alghamdi", "Hariri"),
    "african": ("Adeyemi", "Okafor"),
}


@pytest.mark.parametrize("origin,surnames", sorted(ORIGINS.items()))
def test_the_classifier_knows_this_origin(origin, surnames):
    wrong = [s for s in surnames if classify(f"Testgiven {s}")[0] != origin]
    assert not wrong, f"{wrong} did not classify as {origin}"


@pytest.mark.parametrize("origin,surnames", sorted(ORIGINS.items()))
def test_this_origin_counts_as_non_european(origin, surnames):
    """The threshold test. A roster of one origin must score 100%."""
    roster = [f"Testgiven{i} {s}" for i, s in enumerate(surnames)]
    c = composition(roster)
    assert c["non_european_share"] == 100.0, (
        f"a roster of {len(roster)} {origin} names scored "
        f"{c['non_european_share']}% non-European, not 100%. "
        f"by_origin={c['by_origin']} by_group={c['by_group']}")


def test_a_european_roster_scores_zero():
    """The rule has to be able to say no, or it proves nothing."""
    c = composition(["Alice Smith", "Bob Johnson", "Carol Miller",
                     "Dave Anderson", "Erin Williams"])
    assert c["non_european_share"] == 0.0, c["by_origin"]


def test_every_classifier_category_is_in_a_group():
    """A category the grouping forgets is scored as European."""
    import harvest_lab_rosters as h
    import inspect
    src = inspect.getsource(h.composition)
    known = {"chinese", "japanese", "korean", "vietnamese", "indian",
             "bengali", "iranian", "turkish", "arabic", "african"}
    missing = [k for k in known if f'"{k}"' not in src]
    assert not missing, (
        f"the classifier can return {missing} and composition() does not "
        f"group them, so every such name is counted as European")


#: SURNAMES THAT ARE ALSO ORDINARY WORDS. Each of these was thrown out
#: as page furniture by a blocklist entry that looked harmless, and each
#: is a real person's name. The lesson has had to be learnt three times
#: -- "Ram", then publisher words, then university short-names -- so it
#: is pinned here rather than left to a fourth.
A_WORD_THAT_IS_ALSO_A_NAME = [
    "Ram Devireddy", "Rajeev Ram", "Ashwin Ram", "Ram Seshadri",
    "Roxanne P. Springer", "Thomas Cover",
    "John Duke", "Sarah Berkeley", "Michael Stanford", "Anne Cornell",
    "David Emory", "Lisa Amherst", "Mary Clemson",
    "V. Kumar", "I. David Taylor", "J. Smith",
]

#: and the furniture those entries exist to catch, which must still go.
PAGE_FURNITURE = [
    "Job Opportunities", "Profile Type", "Super Nav",
    "UMass Amherst", "Manning CICS", "NSF CAREER", "Secure Edge AI",
    "Journal Cover Art", "Spin-Transfer Torque Ram",
    "Comm. Math. Phys.", "J. Algebra", "Trans. AMS",
]


@pytest.mark.parametrize("name", A_WORD_THAT_IS_ALSO_A_NAME)
def test_a_word_that_is_also_a_surname_keeps_the_person(name):
    from harvest_lab_rosters import clean_member
    assert clean_member(name) == name, (
        f"{name!r} is a real person thrown out by a blocklist entry. A "
        f"word that is also a name cannot go in a list that rejects "
        f"names.")


@pytest.mark.parametrize("junk", PAGE_FURNITURE)
def test_page_furniture_is_not_a_member(junk):
    from harvest_lab_rosters import clean_member
    assert clean_member(junk) == "", (
        f"{junk!r} was counted as a member. On a group of seven, three "
        f"such strings are 43 per cent of the denominator.")
