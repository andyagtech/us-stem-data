"""The employer-name formatter, including every case that shipped wrong."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from employer_name import pretty                              # noqa: E402


@pytest.mark.parametrize("raw,want", [
    #: The apostrophe bug: str.title() capitalises the letter after one.
    ("LOVE'S TRAVEL STOPS & COUNTRY STORES, INC.",
     "Love's Travel Stops & Country Stores"),
    ("JASANI'S INTERNATIONAL INC", "Jasani's International"),
    ("THE CLUB AT ADMIRAL'S COVE, INC.", "The Club at Admiral's Cove"),
    #: A real name particle keeps its capital.
    ("O'BRIEN & SONS LLC", "O'Brien & Sons"),
    #: Corporate suffixes are dropped, including mid-string before DBA.
    ("PILOT TRAVEL CENTERS LLC", "Pilot Travel Centers"),
    ("MAPCO EXPRESS, INC.", "Mapco Express"),
    ("JOC, INC. DBA HOT SPOT", "JOC DBA Hot Spot"),
    #: Initialisms stay in capitals; real short words do not.
    ("GDI SERVICES INC.", "GDI Services"),
    ("TFL INC.", "TFL"),
    ("HES FACILITIES, LLC", "HES Facilities"),
    ("SOUTHEASTERN JANITORIAL OF SC", "Southeastern Janitorial of SC"),
    ("K&G PETROLEUM LLC", "K&G Petroleum"),
    #: Double-escaped entities from the federal files.
    ("FRENCHMANS CREEK INC &AMP; SUBSIDIARY",
     "Frenchmans Creek Inc & Subsidiary"),
    #: Place-name particles are words, not initialisms.
    ("THE LOS ANGELES COUNTRY CLUB", "The Los Angeles Country Club"),
    ("LAS VEGAS SANDS CORP", "Las Vegas Sands"),
    ("SAN JOSE STATE UNIVERSITY", "San Jose State University"),
    #: A hyphen joins two words.
    ("T-TECH POWER SOLUTIONS", "T-Tech Power Solutions"),
    ("WAL-MART ASSOCIATES, INC.", "Wal-Mart Associates"),
    #: Ordinary public employers must survive untouched.
    ("UNIVERSITY OF WASHINGTON", "University of Washington"),
    ("CITY OF SEATTLE", "City of Seattle"),
])
def test_pretty(raw, want):
    assert pretty(raw) == want


@pytest.mark.parametrize("raw,want", [
    #: Found on the live page after the first version shipped. A short
    #: word with a trailing period escaped SHORT_WORDS and was treated as
    #: an initialism -- 70 names in this corpus.
    ("WASHINGTON UNIVERSITY IN ST. LOUIS",
     "Washington University in St. Louis"),
    ("MT. SINAI MEDICAL CENTER", "Mt. Sinai Medical Center"),
    ("SMITH JR. AND SONS", "Smith Jr. and Sons"),
    #: The suffix branch returned bare letters and ate the bracket.
    ("SOLAR ENERGY COMPANY, LLC. (D/B/A SEC FLORIDA LLC)",
     "Solar Energy Company, LLC. (D/B/A SEC Florida LLC)"),
    #: A word opening with a bracket kept its lower case, because
    #: upper() was applied to the bracket.
    ("ACME (HOLDINGS INC) GROUP", "Acme (Holdings INC) Group"),
])
def test_cases_found_after_shipping(raw, want):
    assert pretty(raw) == want


def test_never_strips_to_nothing():
    """A filer literally named for its suffix keeps its name.

    A suffix standing alone is the whole name, so it stays an
    initialism. The same token mid-name is an ordinary word -- see the
    Frenchmans Creek case above, which renders "Inc".
    """
    assert pretty("LLC") == "LLC"
    assert pretty("INC") == "INC"


def test_keep_suffix():
    assert pretty("PILOT TRAVEL CENTERS LLC", keep_suffix=True) == \
        "Pilot Travel Centers LLC"


def test_empty():
    assert pretty("") == ""
    assert pretty(None) == ""


def test_pretty_is_display_only_not_an_identity():
    """Two distinct federal rows may share one display form.

    This is the trap the formatter must never be used to work around:
    grouping on the pretty name would silently merge two employers the
    files keep apart.
    """
    a, b = "PILOT TRAVEL CENTERS LLC", "PILOT TRAVEL CENTERS, LLC"
    assert a != b
    assert pretty(a) == pretty(b)
