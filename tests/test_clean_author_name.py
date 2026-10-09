"""The author-name cleaner removes catalogue junk and never a real name.

The second half matters more than the first. These names appear on the pages
the author shares, so a name mangled by over-cleaning is worse than the junk.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from clean_author_name import clean_author_name                 # noqa: E402

JUNK = [
    ("Chen, Hongge,Ph. D.Massachusetts Institute of Technology.", "Chen, Hongge"),
    ("Zhu, Rong, Ph. D. Massachusetts Institute of Technology", "Zhu, Rong"),
    ("Dai, Siyu(Scientist in mechanical engineering) Massachusetts "
     "Institute of Technology", "Dai, Siyu"),
    ("Holloway, Jack Wade,1980-", "Holloway, Jack Wade"),
    ("Chen, Wei,1942-2011.", "Chen, Wei"),
    ("Markham, Lauren Elizabeth, Ph.D.", "Markham, Lauren Elizabeth"),
    ("Yang, Yang,Ph. D. Department of Electrical Engineering and "
     "Computer Science.", "Yang, Yang"),
    ("Sun, Xin, Ph. D. Department of Mathematics", "Sun, Xin"),
]

#: S. M. is a given name in Bangladeshi and other South Asian naming, and
#: 'Meng' is a common Chinese given name that a careless degree pattern reads
#: as 'M.Eng'. An earlier cleaner turned 'Mahmud, S. M. Naziur' into 'Mahmud
#: Naziur'. These must come back byte-identical.
UNTOUCHED = [
    "Mahmud, S. M. Naziur",
    # M.S. / M.A. / B.S. at the end of a name are indistinguishable from
    # middle initials. A cleaner that stripped them produced 'Moussa,
    # Alfred' and 'Oteafy, Ahmed'. They are deliberately not in the pattern.
    "Moussa, Alfred M. S.",
    "Oteafy, Ahmed M. A.",
    "Whitfield, James B. S.",
    "Nakamura, Yuki M.A.",
    "Islam, S. M. Zakirul",
    "Sadati, S.M. Sajed",
    "Samarakoon, S. M. Disna Priyadarsani",
    "Mofidian, S. M. Mahdi",
    "Huang, Mengchen",
    "Meng, Xianglin",
    "Zhong, Mengqi",
    "Smith, John A.",
    "O'Brien, Seán",
    "García-López, María José",
]


def test_junk_is_removed():
    for raw, want in JUNK:
        assert clean_author_name(raw) == want, raw


def test_real_names_are_untouched():
    for name in UNTOUCHED:
        assert clean_author_name(name) == name, (
            f"the cleaner altered a real name: {name!r} -> "
            f"{clean_author_name(name)!r}")


def test_it_never_empties_a_name_that_had_one():
    """A name made entirely of junk comes back unchanged, not blank.

    An empty row is worse than an odd one: the page would show a title with
    no author and the reader would assume the harvest lost it.
    """
    for raw in ("Ph.D.", ",", "Massachusetts Institute of Technology"):
        assert clean_author_name(raw) == raw, raw


def test_it_passes_through_what_is_not_a_name():
    for raw in ("", "   "):
        assert clean_author_name(raw) == raw


def test_collapsing_whitespace_is_the_only_change_to_a_clean_name():
    """A double space is tidied. Nothing else about a clean name moves."""
    assert clean_author_name("Schingo, Victor  A.") == "Schingo, Victor A."
    assert clean_author_name("Tran, Katherine  Anh-Trang") == \
        "Tran, Katherine Anh-Trang"


def test_it_is_idempotent():
    for raw, _ in JUNK:
        once = clean_author_name(raw)
        assert clean_author_name(once) == once, raw
