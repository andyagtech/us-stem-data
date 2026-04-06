"""Tests for department extraction from heterogeneous metadata fields.

Each university stores department information differently. These tests
verify the generic extractor and the STEM/non-STEM taxonomy.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from generate_name_lists import (
    extract_dept_from_subject_generic,
    extract_year,
    get_dept_from_oai,
    NON_STEM_DEPTS,
)


# ── Generic subject extraction ──

class TestGenericDeptExtraction:

    def test_computer_science(self):
        assert extract_dept_from_subject_generic('Computer Science') == 'Computer Science'

    def test_electrical_engineering(self):
        assert extract_dept_from_subject_generic('Electrical Engineering') == 'Electrical & Computer Eng'

    def test_mechanical_engineering(self):
        assert extract_dept_from_subject_generic('Mechanical Engineering') == 'Mechanical Eng'

    def test_physics(self):
        assert extract_dept_from_subject_generic('Physics') == 'Physics'

    def test_chemistry(self):
        assert extract_dept_from_subject_generic('Chemistry') == 'Chemistry'

    def test_biochemistry(self):
        assert extract_dept_from_subject_generic('Biochemistry') == 'Biochemistry'

    def test_biology(self):
        assert extract_dept_from_subject_generic('Biology') == 'Biology'

    def test_mathematics(self):
        assert extract_dept_from_subject_generic('Mathematics') == 'Mathematics/Statistics'

    def test_statistics(self):
        assert extract_dept_from_subject_generic('Statistics') == 'Mathematics/Statistics'

    def test_civil_engineering(self):
        assert extract_dept_from_subject_generic('Civil and Environmental Engineering') == 'Civil & Environmental Eng'

    def test_materials_science(self):
        assert extract_dept_from_subject_generic('Materials Science and Engineering') == 'Materials Science & Eng'

    def test_neuroscience(self):
        assert extract_dept_from_subject_generic('Neuroscience') == 'Neuroscience'

    def test_education(self):
        assert extract_dept_from_subject_generic('Education') == 'Education'

    def test_psychology(self):
        assert extract_dept_from_subject_generic('Psychology') == 'Psychology'

    def test_economics(self):
        assert extract_dept_from_subject_generic('Economics') == 'Economics'

    def test_data_science(self):
        assert extract_dept_from_subject_generic('Data Science and Machine Learning') == 'Data Science'

    def test_empty_returns_none(self):
        assert extract_dept_from_subject_generic('') is None
        assert extract_dept_from_subject_generic(None) is None

    def test_no_match_returns_none(self):
        assert extract_dept_from_subject_generic('Underwater Basket Weaving') is None

    def test_case_insensitive(self):
        assert extract_dept_from_subject_generic('COMPUTER SCIENCE') == 'Computer Science'
        assert extract_dept_from_subject_generic('mechanical engineering') == 'Mechanical Eng'

    def test_specificity_ordering(self):
        """More specific patterns should match before broad ones."""
        # "Electrical and Computer Engineering" should match ECE, not generic Engineering
        assert extract_dept_from_subject_generic('Electrical and Computer Engineering') == 'Electrical & Computer Eng'
        # "Biomedical Engineering" should match BME, not generic Biology
        assert extract_dept_from_subject_generic('Biomedical Engineering') == 'Biomedical Eng'

    def test_physics_not_physical_education(self):
        """'Physics' regex should not match 'Physical Education'."""
        assert extract_dept_from_subject_generic('Physical Education') != 'Physics'


# ── OAI set mapping ──

class TestOAISetMapping:

    MISSOURI_MAP = {
        'Computer Science': ['comsci', 'comsci_dissert', 'compsci-tds'],
        'Chemistry': ['chem', 'chem_dissert', 'chem-tds'],
    }

    def test_direct_match(self):
        assert get_dept_from_oai('publication:comsci', self.MISSOURI_MAP) == 'Computer Science'

    def test_dissert_variant(self):
        assert get_dept_from_oai('publication:chem_dissert', self.MISSOURI_MAP) == 'Chemistry'

    def test_no_match(self):
        assert get_dept_from_oai('publication:unknown', self.MISSOURI_MAP) is None

    def test_multiple_sets(self):
        assert get_dept_from_oai('publication:comsci; publication:etd', self.MISSOURI_MAP) == 'Computer Science'


# ── Year extraction ──

class TestExtractYear:

    def test_standard_date(self):
        assert extract_year('2023-05-15') == 2023

    def test_year_only(self):
        assert extract_year('2020') == 2020

    def test_iso_datetime(self):
        assert extract_year('2019-01-01T00:00:00Z') == 2019

    def test_empty(self):
        assert extract_year('') is None
        assert extract_year(None) is None

    def test_no_year(self):
        assert extract_year('no date here') is None


# ── STEM taxonomy ──

class TestSTEMTaxonomy:

    def test_education_is_non_stem(self):
        assert 'Education' in NON_STEM_DEPTS

    def test_history_is_non_stem(self):
        assert 'History' in NON_STEM_DEPTS

    def test_business_is_non_stem(self):
        assert 'Business' in NON_STEM_DEPTS

    def test_psychology_is_non_stem(self):
        assert 'Psychology' in NON_STEM_DEPTS

    def test_computer_science_is_not_non_stem(self):
        assert 'Computer Science' not in NON_STEM_DEPTS

    def test_physics_is_not_non_stem(self):
        assert 'Physics' not in NON_STEM_DEPTS

    def test_taxonomy_has_reasonable_size(self):
        """Should have between 40 and 100 non-STEM departments."""
        assert 40 <= len(NON_STEM_DEPTS) <= 100
