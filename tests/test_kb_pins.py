"""The pinned knowledge figures, and the path resolver that reads them."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "cloud" / "chat"))

from knowledge_pins import (NOT_DATA, PINS, PathError, resolve,   # noqa: E402
                            split_path, stated_value)

DATA = ROOT / "site" / "data"
KB = ROOT / "cloud" / "chat" / "knowledge"


def _load(stem: str):
    return json.loads((DATA / f"{stem}.json").read_text())


def test_there_are_pins():
    assert len(PINS) > 150, "the pin table looks truncated"


@pytest.mark.parametrize("name,written,stem,path", PINS,
                         ids=[f"{n}:{w}" for n, w, _, _ in PINS])
def test_each_pin_still_matches_its_field(name, written, stem, path):
    """The figure in the prose still equals the field it was taken from."""
    actual = resolve(_load(stem), path)
    assert isinstance(actual, (int, float)), f"{stem}.{path} is not a number"
    want = stated_value(written)
    tol = max(0.051, abs(float(actual)) * 0.0005)
    assert any(abs(c - float(actual)) <= tol
               for c in (want, want / 100.0, want * 100.0)), (
        f"{name} says {written}; {stem}.{path} is {actual}")


def test_no_pin_covers_a_definition():
    """A threshold or an industry code must never be pinned to a measured field."""
    for name, written, _, _ in PINS:
        assert (name, written) not in NOT_DATA


def test_selectors_identify_exactly_one_row():
    """A selector that matches two rows is not an identifier.

    With "state" ahead of "employer" in the generator's key order, an employer
    list was once keyed [state=CA] -- several employers are in CA, so the pin
    read whichever row came first and would have passed regardless.
    """
    for _, _, stem, path in PINS:
        data = _load(stem)
        node = data
        for part in split_path(path):
            if "[" in part and part.endswith("]"):
                field, _, rest = part.partition("[")
                key, _, want = rest[:-1].partition("=")
                rows = node[field]
                hits = [r for r in rows
                        if isinstance(r, dict) and str(r.get(key)) == want]
                assert len(hits) == 1, (
                    f"{stem}.{field}[{key}={want}] matches {len(hits)} rows")
                node = hits[0]
            else:
                node = node[int(part)] if isinstance(node, list) else node[part]


def test_split_path_keeps_dots_inside_a_selector():
    """Employer names carry dots; splitting on every dot tore the selector apart."""
    assert split_path("largest_filers[employer=AMAZON.COM SERVICES LLC].filings") == [
        "largest_filers[employer=AMAZON.COM SERVICES LLC]", "filings"]
    assert split_path("a[employer=ERNST & YOUNG U.S. LLP].b.c") == [
        "a[employer=ERNST & YOUNG U.S. LLP]", "b", "c"]


def test_resolver_refuses_a_row_that_is_not_there():
    data = _load("local_wage_comparison")
    assert resolve(data, "by_state[state=CA].priced") > 0
    with pytest.raises(PathError):
        resolve(data, "by_state[state=Atlantis].priced")
    with pytest.raises(PathError):
        resolve(data, "no_such_field")


def test_each_pinned_figure_appears_in_the_file_it_names():
    """The pin's value is actually written in that knowledge file.

    A pin compares the pin table with the data, not with the prose. That
    catches the data moving under a figure, which is what it is for. It does
    NOT catch the prose being edited away from its pin: change 58.3 to 57.9 in
    the markdown and every pin still passes, because nothing had read the
    markdown.

    So the drift alarm guarded one end of the pair and not the other. This
    closes it. The pin is only evidence about the prose if the prose still
    says the pinned number.
    """
    import re
    missing = []
    for name, written, stem, path in PINS:
        f = KB / name
        if not f.exists():
            missing.append(f"{name}: no such knowledge file")
            continue
        text = f.read_text()
        #: Match the figure as written, and also without thousands separators,
        #: because prose may carry either and both are the same claim.
        forms = {written, written.replace(",", "")}
        if not any(re.search(rf"(?<![\d.]){re.escape(v)}(?![\d])", text)
                   for v in forms):
            missing.append(f"{name} is pinned to {written} "
                           f"({stem}.{path}) but does not contain it")
    assert not missing, "\n".join(missing)
