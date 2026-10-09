"""Identifiers become clickable URLs, and nothing unknown is guessed at."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from resolve_record_url import resolve_record_url as r        # noqa: E402

#: Each of these was probed against the live repository and returned 200.
RESOLVES = [
    ("10.1184/R1/12755750.v1", "https://doi.org/10.1184/R1/12755750.v1"),
    ("10.1184/R1/31019845.v1", "https://doi.org/10.1184/R1/31019845.v1"),
    ("oai:pdxscholar.library.pdx.edu:open_access_etds-1015",
     "https://pdxscholar.library.pdx.edu/open_access_etds/1015"),
    ("etd:1079", "https://d.lib.msu.edu/etd/1079"),
]

PASSES_THROUGH = [
    "https://dspace.mit.edu/handle/1721.1/12345",
    "http://example.edu/thesis/1",
    "/data/stem/mit.json",
]

#: No safe mapping exists. These must come back None so the page renders the
#: name unlinked rather than inventing a URL that 404s.
NO_GUESS = [
    "oai:figshare.com:article/6719894",      # different host convention
    "oai:open.bu.edu:2144/45624",            # DSpace handle, not bepress
    "oai:ttu-ir.tdl.org:2346/12345",
    "1121263553",                            # a bare number
    "Best practices for short-term study abroad",
    "Dijkstra, Paul and Heinrich, Paul L (2010) Position paper",
    "", "   ", None, 42,
]


def test_known_identifiers_resolve():
    for raw, want in RESOLVES:
        assert r(raw) == want, raw


def test_real_urls_pass_through_untouched():
    for u in PASSES_THROUGH:
        assert r(u) == u


def test_unknown_shapes_are_not_guessed():
    for u in NO_GUESS:
        assert r(u) is None, f"invented a URL for {u!r}: {r(u)!r}"


def test_it_never_returns_a_relative_url():
    """A scheme-less return value is the bug this module exists to fix."""
    for raw, _ in RESOLVES:
        out = r(raw)
        assert out.startswith(("http://", "https://")), out
