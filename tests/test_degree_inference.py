"""Tests for the 8-step degree inference chain (infer_degree_type).

This is the most critical function in the pipeline — it determines
PhD vs Master's for 294K records. Each test case documents a real
pattern encountered from a specific university.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from generate_name_lists import infer_degree_type


# ── Step 1: Config override ──

def test_config_override_phd():
    """Caltech, UC System: entire collection is PhD-only."""
    row = {'title': 'Some thesis', 'type': '', 'oai_set': '', 'description': ''}
    assert infer_degree_type(row, {'degree_label': 'phd'}) == 'phd'


def test_config_override_ms():
    """Missouri S&T master's collection."""
    row = {'title': 'Some thesis', 'type': '', 'oai_set': '', 'description': ''}
    assert infer_degree_type(row, {'degree_label': 'ms'}) == 'ms'


# ── Step 2: Explicit degree fields ──

def test_degree_name_phd():
    """Binghamton oai_etdms: degree_name = 'Doctor of Philosophy (PhD)'."""
    row = {'degree_name': 'Doctor of Philosophy (PhD)', 'oai_set': '', 'type': '', 'description': ''}
    assert infer_degree_type(row, {}) == 'phd'


def test_degree_name_ms():
    """BYU oai_etdms: degree_name = 'MS'."""
    row = {'degree_name': 'MS', 'oai_set': '', 'type': '', 'description': ''}
    assert infer_degree_type(row, {}) == 'ms'


def test_degree_name_ma():
    """Binghamton: degree_name = 'Master of Arts (MA)'."""
    row = {'degree_name': 'Master of Arts (MA)', 'oai_set': '', 'type': '', 'description': ''}
    assert infer_degree_type(row, {}) == 'ms'


def test_degree_name_edd():
    """EdD is a doctoral degree."""
    row = {'degree_name': 'EdD', 'oai_set': '', 'type': '', 'description': ''}
    assert infer_degree_type(row, {}) == 'phd'


def test_degree_name_mfa():
    """MFA is a master's degree."""
    row = {'degree_name': 'MFA', 'oai_set': '', 'type': '', 'description': ''}
    assert infer_degree_type(row, {}) == 'ms'


def test_degree_type_dissertation():
    """Generic degree_type = 'dissertation'."""
    row = {'degree_type': 'dissertation', 'oai_set': '', 'type': '', 'description': ''}
    assert infer_degree_type(row, {}) == 'phd'


def test_skip_bachelors():
    """Bachelor's theses should be filtered out."""
    row = {'degree_name': 'B.S.', 'oai_set': '', 'type': '', 'description': ''}
    assert infer_degree_type(row, {}) == 'bs'


# ── Step 3: ETD degree_level ──

def test_degree_level_dissertation():
    """Mississippi State: degree_level = 'Dissertation - Open Access'."""
    row = {'degree_level': 'Dissertation - Open Access', 'oai_set': '', 'type': '', 'description': ''}
    assert infer_degree_type(row, {}) == 'phd'


def test_degree_level_thesis():
    """Binghamton: degree_level = 'Thesis' means Master's in etdms context."""
    row = {'degree_level': 'Thesis', 'oai_set': '', 'type': '', 'description': ''}
    assert infer_degree_type(row, {}) == 'ms'


def test_degree_level_graduate_thesis():
    """Mississippi State: 'Graduate Thesis - Open Access'."""
    row = {'degree_level': 'Graduate Thesis - Open Access', 'oai_set': '', 'type': '', 'description': ''}
    assert infer_degree_type(row, {}) == 'ms'


# ── Step 4: OAI set membership ──

def test_oai_set_dissertations():
    """UC bepress: publication:dissertations → PhD."""
    row = {'oai_set': 'publication:dissertations', 'type': '', 'description': ''}
    assert infer_degree_type(row, {}) == 'phd'


def test_oai_set_degree_level_doctoral():
    """Columbia: degree_level:doctoral set."""
    row = {'oai_set': 'degree_level:doctoral', 'type': '', 'description': ''}
    assert infer_degree_type(row, {}) == 'phd'


def test_oai_set_degree_level_master():
    """Columbia: degree_level:master set."""
    row = {'oai_set': 'degree_level:master', 'type': '', 'description': ''}
    assert infer_degree_type(row, {}) == 'ms'


def test_oai_set_ambiguous_theses_dissertations():
    """Combined set like 'publication:theses-dissertations' should NOT match."""
    row = {'oai_set': 'publication:theses-dissertations', 'type': '', 'description': ''}
    # Should return empty — ambiguous set doesn't tell us PhD vs MS
    assert infer_degree_type(row, {}) == ''


# ── Step 5: Type field ──

def test_type_doctoral():
    row = {'type': 'Doctoral Dissertation', 'oai_set': '', 'description': ''}
    assert infer_degree_type(row, {}) == 'phd'


def test_type_masters():
    row = {'type': "Master's Thesis", 'oai_set': '', 'description': ''}
    assert infer_degree_type(row, {}) == 'ms'


def test_type_generic_thesis_is_ambiguous():
    """Generic 'Thesis' alone does NOT mean master's — many universities use it for all grad work."""
    row = {'type': 'Thesis', 'oai_set': '', 'description': ''}
    assert infer_degree_type(row, {}) == ''


# ── Step 6: Relation field ──

def test_relation_phd():
    """Penn State stores degree type in relation field."""
    row = {'relation': 'PHD', 'type': '', 'oai_set': '', 'description': ''}
    assert infer_degree_type(row, {}) == 'phd'


def test_relation_masters():
    row = {'relation': 'MASTERS', 'type': '', 'oai_set': '', 'description': ''}
    assert infer_degree_type(row, {}) == 'ms'


# ── Step 7: Description regex ──

def test_description_phd():
    """MIT: degree type embedded in description."""
    row = {'type': '', 'oai_set': '', 'description': 'Thesis (Ph.D.)--Massachusetts Institute of Technology'}
    assert infer_degree_type(row, {}) == 'phd'


def test_description_sm():
    """MIT: S.M. degree."""
    row = {'type': '', 'oai_set': '', 'description': 'Thesis (S.M.)--Massachusetts Institute of Technology'}
    assert infer_degree_type(row, {}) == 'ms'


def test_description_meng():
    """MIT: M.Eng degree."""
    row = {'type': '', 'oai_set': '', 'description': 'Thesis (M.Eng.)--Massachusetts Institute of Technology'}
    assert infer_degree_type(row, {}) == 'ms'


def test_description_scd():
    """MIT: Sc.D. (Doctor of Science)."""
    row = {'type': '', 'oai_set': '', 'description': 'Thesis (Sc.D.)--Massachusetts Institute of Technology'}
    assert infer_degree_type(row, {}) == 'phd'


def test_description_skip_sb():
    """MIT: S.B. (Bachelor of Science) should be filtered."""
    row = {'type': '', 'oai_set': '', 'description': 'Thesis (S.B.)--Massachusetts Institute of Technology'}
    assert infer_degree_type(row, {}) == 'bs'


# ── Step 8: Late OAI fallback ──

def test_late_oai_theses_only():
    """If only 'publication:theses' exists (no dissertations set), assume MS."""
    row = {'oai_set': 'publication:theses', 'type': '', 'description': ''}
    assert infer_degree_type(row, {}) == 'ms'


def test_late_oai_theses_with_dissertations():
    """If both theses AND dissertations sets exist, theses alone is NOT enough for MS."""
    row = {'oai_set': 'publication:theses; publication:dissertations', 'type': '', 'description': ''}
    # The dissertations set match in step 4 should catch PhD;
    # but a record in BOTH sets is ambiguous — step 4 catches dissertations → phd
    assert infer_degree_type(row, {}) == 'phd'


# ── Empty / missing fields ──

def test_all_empty_returns_unlabeled():
    """No metadata at all → unlabeled."""
    row = {'type': '', 'oai_set': '', 'description': ''}
    assert infer_degree_type(row, {}) == ''


def test_none_values():
    """Fields can be None (from CSV DictReader for missing columns)."""
    row = {'type': None, 'oai_set': None, 'description': None}
    assert infer_degree_type(row, {}) == ''
