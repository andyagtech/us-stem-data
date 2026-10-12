"""A laboratory abroad is not a finding about American programmes.

The table's top entry was the Cheng group at 91.4% from one origin,
credited to Illinois. It is at Westlake University in Hangzhou: the
crawl found Jianjun Cheng through an Illinois faculty directory,
because he taught there until 2021, and followed his research link
to the laboratory he now runs in China.

These cases are the ones that were actually wrong, in both
directions, and they are kept because each one broke a different
rule.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from us_affiliation import check  # noqa: E402


def test_a_foreign_domain_is_conclusive():
    ok, why = check("https://www.math.pku.edu.cn/", "", "University of Chicago")
    assert not ok and "foreign domain" in why


def test_an_edu_host_is_conclusive_even_with_a_short_institution():
    #: www-math.mit.edu was rejected because "MIT" is too short for
    #: the name matcher, so the test that should have passed it never
    #: ran. A .edu host needs no corroboration.
    ok, _ = check("http://www-math.mit.edu/~stevenj/group.html",
                  "<html>ETH Zurich Hebrew University</html>", "MIT")
    assert ok


def test_foreign_contact_addresses_outweigh_the_page():
    html = "<html>" + " ".join(
        f"a{i}@westlake.edu.cn" for i in range(20)) + "</html>"
    ok, why = check("https://www.cheng-lab.com/group", html,
                    "University of Illinois Urbana-Champaign")
    assert not ok and "foreign domains" in why


def test_edu_addresses_are_positive_evidence():
    #: skotheimlab.com carries four .edu addresses and no foreign
    #: ones, and was rejected anyway because its alumni list names
    #: Munich: the marker test ran on a page that had already proved
    #: where it lives.
    html = ("<html>Technical University of Munich. "
            "a@stanford.edu b@stanford.edu c@stanford.edu "
            "d@stanford.edu</html>")
    ok, _ = check("http://skotheimlab.com/people", html,
                  "Stanford University")
    assert ok


def test_alumni_abroad_do_not_move_the_lab():
    #: dabirilab.com is Caltech's. Its alumni went to the Technion and
    #: ETH, and naming them is not evidence the laboratory moved.
    html = ("<html>Caltech. California Institute of Technology. "
            "Alumni: Technion, ETH Zurich, Universidad.</html>")
    ok, _ = check("http://www.dabirilab.com/people", html,
                  "California Institute of Technology")
    assert ok


@pytest.mark.parametrize("host", [
    "https://lab.tsinghua.edu.cn/x", "https://g.ac.uk/people",
    "https://x.univ-mlv.fr/team", "https://y.mpg.de/members",
])
def test_country_domains(host):
    ok, _ = check(host, "", "Duke University")
    assert not ok
