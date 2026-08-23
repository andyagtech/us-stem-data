"""Offline geocoding of the immigration firms.

No hosted geocoder is used: coordinates come from a vendored 0.6 MB GeoNames
postal table. These tests pin the behaviour that matters -- that a postcode
beats a city, that a city centroid is still returned when no postcode is
present, and that an unmatchable address returns None rather than a guess.
"""
import pytest

pytest.importorskip("requests")
from scripts.geocode_legal import OfflineGeocoder, GEO      # noqa: E402

pytestmark = pytest.mark.skipif(
    not GEO.exists(), reason="gazetteer not vendored; run download_geonames.py")


@pytest.fixture(scope="module")
def geo():
    return OfflineGeocoder()


def test_postcode_wins_over_city(geo):
    """The address ends in a ZIP, so the ZIP centroid is used."""
    r = geo.locate("800 NW 62nd Avenue, Suite 590, Miami, FL, 33126")
    assert r["matched_on"] == "postal" and r["zip"] == "33126"
    assert r["state"] == "FL"
    assert 25.0 < r["lat"] < 26.5 and -81 < r["lon"] < -80


def test_city_and_state_when_there_is_no_postcode(geo):
    r = geo.locate("CORAL GABLES, FL")
    assert r["matched_on"] == "city" and r["state"] == "FL"
    assert 25.0 < r["lat"] < 26.5


def test_zip_plus_four_still_resolves(geo):
    r = geo.locate("195 Church Street, New Haven, CT, 06510-1839")
    assert r["matched_on"] == "postal" and r["zip"] == "06510"


def test_unmatchable_address_returns_none_not_a_guess(geo):
    assert geo.locate("Somewhere, ZZ, 00000") is None
    assert geo.locate("") is None
    assert geo.locate(None) is None


def test_a_city_centroid_reports_how_many_postcodes_it_averaged(geo):
    r = geo.locate("HOUSTON, TX")
    assert r["matched_on"] == "city" and r["postcodes_averaged"] > 1


def test_matched_on_is_always_present(geo):
    """A reader must be able to tell a rooftop-ish match from a city blob."""
    for addr in ("800 NW 62nd Avenue, Miami, FL, 33126", "ST. LOUIS, MO"):
        assert geo.locate(addr)["matched_on"] in ("postal", "city")


def test_abbreviated_city_names_resolve(geo):
    """Filers write "ST. LOUIS"; GeoNames writes "Saint Louis"."""
    for addr, state in (("ST. LOUIS, MO", "MO"), ("FT. WORTH, TX", "TX"),
                        ("MT. PLEASANT, SC", "SC")):
        r = geo.locate(addr)
        assert r is not None, addr
        assert r["state"] == state and r["matched_on"] == "city"


def test_normalisation_does_not_invent_matches():
    """Expanding abbreviations must not make unrelated names collide."""
    from scripts.geocode_legal import _city_key
    assert _city_key("ST. LOUIS") == _city_key("Saint Louis")
    assert _city_key("N. CHARLESTON") == _city_key("North Charleston")
    assert _city_key("SPRINGFIELD") != _city_key("SPRINGDALE")
