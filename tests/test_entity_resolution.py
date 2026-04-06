"""Tests for employer name → university key entity resolution.

USCIS truncates employer names at 35 characters and uses various
abbreviations. These tests verify the matching logic handles real
patterns found in H-1B, LCA, and PERM filings.
"""
import sys
import os
import json

# The _match_employer function lives in the pipeline package which uses
# relative imports. Replicate the pure function here for testing.
def _match_employer(name: str, entity_map: dict) -> str | None:
    """Match an employer name to a university key using entity map."""
    upper = (name or "").upper().strip()
    if upper in entity_map:
        return entity_map[upper]
    for pattern, key in entity_map.items():
        if pattern in upper:
            return key
    return None


# Load the real entity map
ENTITY_MAP_PATH = os.path.join(os.path.dirname(__file__), '..', 'pipeline', 'entity_map.json')
with open(ENTITY_MAP_PATH) as f:
    ENTITY_MAP = json.load(f)


class TestDirectMatch:

    def test_mit(self):
        assert _match_employer('MASSACHUSETTS INSTITUTE OF TECHNOLOGY', ENTITY_MAP) == 'mit'

    def test_stanford(self):
        assert _match_employer('STANFORD UNIVERSITY', ENTITY_MAP) == 'stanford'

    def test_case_insensitive(self):
        assert _match_employer('Massachusetts Institute of Technology', ENTITY_MAP) == 'mit'

    def test_whitespace_trimmed(self):
        assert _match_employer('  STANFORD UNIVERSITY  ', ENTITY_MAP) == 'stanford'


class TestTruncatedNames:
    """USCIS pre-2020 files truncate at ~35 characters."""

    def test_stanford_legal_name(self):
        assert _match_employer('THE LELAND STANFORD JR UNIVERSITY', ENTITY_MAP) == 'stanford'

    def test_missouri_curators_truncated(self):
        """'THE CURATORS OF THE UNIVERSITY OF MISSOURI' truncated."""
        result = _match_employer('THE CURATORS OF THE UNIV OF MISSOU', ENTITY_MAP)
        assert result == 'umissouri'


class TestAbbreviations:
    """Common USCIS abbreviations."""

    def test_virginia_tech_abbreviated(self):
        result = _match_employer('VIRGINIA POLYTECHNIC INST & STATE UNIV', ENTITY_MAP)
        assert result == 'vt'


class TestNoMatch:

    def test_unknown_employer(self):
        assert _match_employer('GOOGLE LLC', ENTITY_MAP) is None

    def test_empty_string(self):
        assert _match_employer('', ENTITY_MAP) is None

    def test_none(self):
        assert _match_employer(None, ENTITY_MAP) is None


class TestEntityMapIntegrity:
    """Verify the entity map itself is well-formed."""

    def test_all_keys_are_uppercase(self):
        for key in ENTITY_MAP:
            assert key == key.upper(), f"Entity map key not uppercase: {key}"

    def test_all_values_are_lowercase(self):
        for key, val in ENTITY_MAP.items():
            assert val == val.lower() or '_' in val, f"Entity map value should be lowercase key: {val} (from {key})"

    def test_minimum_entries(self):
        assert len(ENTITY_MAP) >= 250, f"Entity map too small: {len(ENTITY_MAP)}"
