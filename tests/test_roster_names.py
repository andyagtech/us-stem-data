"""The roster extractor must count people, not page furniture.

A lab page carries navigation, research topics, awards and the
university's own name. Counting those inflates a roster's size and
halves its measured concentration: a group of seven read as fourteen.

The fixture is a hand-labelled random sample of what the extractor
actually pulled off real lab pages. A change to the filter may not
lose a person to gain a rejection.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from harvest_lab_rosters import clean_member  # noqa: E402

FIXTURE = json.loads(
    (ROOT / "tests" / "fixtures" / "roster_name_labels.json").read_text())


@pytest.mark.parametrize("name", FIXTURE["person"])
def test_a_person_is_kept(name):
    assert clean_member(name), f"{name!r} is a person and was dropped"


@pytest.mark.parametrize("name", FIXTURE["furniture"])
def test_furniture_is_rejected(name):
    assert not clean_member(name), f"{name!r} is not a person and was kept"


def test_the_sample_is_not_trivially_one_sided():
    #: a filter that keeps everything, or nothing, would pass half of
    #: the cases above by accident. The sample must hold both.
    assert len(FIXTURE["person"]) >= 20
    assert len(FIXTURE["furniture"]) >= 10
