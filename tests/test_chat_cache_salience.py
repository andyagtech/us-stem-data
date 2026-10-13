#!/usr/bin/env python3
"""The semantic cache must not answer a question nobody asked.

On 2026-10-13 the live assistant was asked which CIVIL engineering programmes
lean hardest on foreign students and returned the MECHANICAL engineering
answer, word for word, with its stored latency. The two questions differ by
one word out of thirty, so they embed far above the 0.82 threshold -- higher
than the real paraphrases the semantic layer exists to catch. No threshold
separates them.

So similarity is necessary and no longer sufficient: a hit must also name the
same things. These tests hold the gate and, just as important, hold the
paraphrases open.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cloud"))
from chat import cache as C                                         # noqa: E402


# --- the bug ---------------------------------------------------------------

def test_two_fields_are_not_the_same_question():
    a = C.salient("Rank the five mechanical engineering doctoral programmes "
                  "with the largest foreign-student share")
    b = C.salient("Which civil engineering doctoral programmes lean most "
                  "heavily on foreign students?")
    assert a != b
    assert "mechanical" in a and "civil" in b


def test_two_institutions_are_not_the_same_question():
    assert C.salient("what is the nra share at mit") != \
           C.salient("what is the nra share at stanford")


def test_two_years_are_not_the_same_question():
    assert C.salient("how has the share moved since 2015") != \
           C.salient("how has the share moved since 2020")


# --- what must still match -------------------------------------------------

@pytest.mark.parametrize("a,b", [
    ("what is the main finding of this site",
     "whats the main finding of this website"),
    ("how much do taxpayers spend per stem doctorate",
     "what do taxpayers pay for each stem phd"),
    ("which field has the highest non resident share",
     "what field has the largest foreign student share"),
])
def test_a_paraphrase_that_names_nothing_still_matches(a, b):
    """The gate only fires on questions that name a particular thing. These
    are the pairs the semantic layer was built for and it keeps them."""
    assert C.salient(a) == C.salient(b)


def test_the_same_field_in_different_words_still_matches():
    """The site writes "programme", readers type "program". That spelling
    must not split one question into two."""
    assert C.salient("show me mechanical engineering programmes with the "
                     "highest foreign share") == \
           C.salient("which mechanical engineering programs lean most on "
                     "foreign students")


def test_case_and_punctuation_do_not_matter():
    assert C.salient("what is the nra share at MIT?") == \
           C.salient("what is the nra share at mit")


# --- the vocabulary itself -------------------------------------------------

def test_a_category_word_is_not_an_entity():
    """"engineering" sits in 94 CIP titles and "university" in 827 institution
    names. A word that broad distinguishes nothing, and treating it as an
    entity would gate every pair that phrased the same question differently."""
    vocab = C.salient_vocab()
    for word in ("engineering", "university", "studies", "sciences",
                 "general", "technology", "management"):
        assert word not in vocab, word


def test_this_sites_everyday_words_are_not_entities():
    """Read from the knowledge base, not a hand-written list: a word in more
    than KB_MAX_DF of the knowledge files is this site's own register."""
    vocab = C.salient_vocab()
    for word in ("foreign", "student", "share", "doctorate", "with"):
        assert word not in vocab, word


def test_the_entities_that_matter_survive():
    vocab = C.salient_vocab()
    for word in ("mechanical", "civil", "electrical", "chemistry",
                 "stanford", "mit"):
        assert word in vocab, word


def test_the_vocabulary_is_not_empty_or_everything():
    n = len(C.salient_vocab())
    assert 400 < n < 4000, n


def test_stats_reports_the_vocabulary_size():
    assert C.stats()["salient_vocab"] == len(C.salient_vocab())
