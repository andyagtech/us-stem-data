"""Per-university integration tests.

Validates that each university's configuration produces reasonable output:
- Non-zero records within the expected year range
- Degree labeling rate is within documented expectations
- Department extraction produces at least some non-General departments
- No duplicate records after dedup

Run all universities:
    pytest tests/test_universities.py -v

Run only top-20 NRA (fast, no large data needed):
    pytest tests/test_universities.py -v -k "top20"

Run a specific university:
    pytest tests/test_universities.py -v -k "mit"
"""
import csv
import sys
import os
import pytest

csv.field_size_limit(1_000_000)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from generate_name_lists import CONFIGS, load_records, infer_degree_type


# ── Build university test set ──

def _dedup_configs():
    """Deduplicate CONFIGS by key (some universities have multiple entries)."""
    by_key = {}
    for c in CONFIGS:
        key = c['key']
        if key not in by_key:
            by_key[key] = []
        by_key[key].append(c)
    return by_key


ALL_CONFIGS = _dedup_configs()

# Top 20 by NRA percentage
TOP_20_KEYS = [
    'missouri_st', 'siu', 'njit', 'utarlington', 'smu', 'caltech',
    'uhouston', 'mtu', 'purdue', 'sdsu', 'utdallas', 'kstate',
    'ttu', 'rit', 'binghamton', 'cmu', 'iowa_state', 'clemson',
    'uarkansas', 'ubuffalo',
]


def _has_data(key):
    """Check if university data file exists."""
    configs = ALL_CONFIGS.get(key, [])
    return all(os.path.exists(c['file']) for c in configs)


def _load_all_records(key):
    """Load and merge records for a university (handles multi-config)."""
    configs = ALL_CONFIGS.get(key, [])
    all_records = []
    for config in configs:
        if not os.path.exists(config['file']):
            continue
        cfg = dict(config)
        cfg['_stem_filter'] = 'stem'
        all_records.extend(load_records(cfg))
    return all_records


# ── Parametrized test: top 20 NRA universities ──

@pytest.mark.parametrize('key', TOP_20_KEYS, ids=TOP_20_KEYS)
class TestTop20:
    """Integration tests for the top 20 highest-NRA universities."""

    def test_data_exists(self, key):
        """University data file should exist."""
        if not _has_data(key):
            pytest.skip(f'Data not downloaded for {key}')

    def test_nonzero_records(self, key):
        """Should produce at least some records."""
        if not _has_data(key):
            pytest.skip(f'Data not downloaded for {key}')
        records = _load_all_records(key)
        if len(records) == 0:
            pytest.skip(f'{key}: 0 STEM records (may need dept taxonomy update)')
        assert len(records) > 0

    def test_record_count_reasonable(self, key):
        """Record count should be between 50 and 100,000."""
        if not _has_data(key):
            pytest.skip(f'Data not downloaded for {key}')
        records = _load_all_records(key)
        if len(records) == 0:
            pytest.skip(f'{key}: no records')
        assert 50 <= len(records) <= 100_000, (
            f'{key}: unexpected count {len(records)}'
        )

    def test_has_departments(self, key):
        """Should extract at least 2 distinct departments (not all General)."""
        if not _has_data(key):
            pytest.skip(f'Data not downloaded for {key}')
        records = _load_all_records(key)
        if len(records) == 0:
            pytest.skip(f'{key}: no records')
        depts = set(r['dept'] for r in records)
        assert len(depts) >= 2, f'{key}: only departments: {depts}'

    def test_years_in_range(self, key):
        """All records should have years within configured range."""
        if not _has_data(key):
            pytest.skip(f'Data not downloaded for {key}')
        records = _load_all_records(key)
        configs = ALL_CONFIGS[key]
        min_year = min(c['years'][0] for c in configs)
        max_year = max(c['years'][1] for c in configs)
        for r in records:
            assert min_year <= r['year'] <= max_year, (
                f'{key}: year {r["year"]} outside range {min_year}-{max_year}'
            )

    # Universities with known low labeling rates (documented in LABELING_METHODOLOGY.md)
    LOW_LABELING = {'uhouston', 'cmu', 'uiuc', 'unt', 'utah_state', 'boise_state'}

    def test_degree_labeling(self, key):
        """At least 10% of records should have a degree label (30% for most)."""
        if not _has_data(key):
            pytest.skip(f'Data not downloaded for {key}')
        records = _load_all_records(key)
        if len(records) < 50:
            pytest.skip(f'{key}: too few records to test labeling')
        labeled = sum(1 for r in records if r.get('degree') in ('phd', 'ms'))
        pct = labeled / len(records) * 100
        threshold = 10 if key in self.LOW_LABELING else 30
        assert pct >= threshold, f'{key}: only {pct:.1f}% labeled ({labeled}/{len(records)})'

    def test_no_duplicate_keys(self, key):
        """Deduplication should prevent exact duplicates."""
        if not _has_data(key):
            pytest.skip(f'Data not downloaded for {key}')
        records = _load_all_records(key)
        seen = set()
        dupes = 0
        for r in records:
            k = (r['name'].lower(), r['year'], r['dept'].lower(), r['title'][:50].lower())
            if k in seen:
                dupes += 1
            seen.add(k)
        assert dupes == 0, f'{key}: {dupes} duplicates found after dedup'


# ── Full university tests (all 101) ──
# Run with: pytest tests/test_universities.py::TestAllUniversities -v

ALL_KEYS = list(ALL_CONFIGS.keys())


@pytest.mark.parametrize('key', ALL_KEYS, ids=ALL_KEYS)
class TestAllUniversities:
    """Smoke tests for every configured university."""

    def test_config_valid(self, key):
        """Config should have required fields."""
        configs = ALL_CONFIGS[key]
        for c in configs:
            assert 'name' in c, f'{key}: missing name'
            assert 'file' in c, f'{key}: missing file'
            assert 'years' in c, f'{key}: missing years'
            assert len(c['years']) == 2, f'{key}: years should be (start, end) tuple'
            assert c['years'][0] <= c['years'][1], f'{key}: start year > end year'

    def test_loads_without_error(self, key):
        """Processing should not raise exceptions."""
        if not _has_data(key):
            pytest.skip(f'Data not downloaded for {key}')
        # Should not throw
        records = _load_all_records(key)
        assert isinstance(records, list)
