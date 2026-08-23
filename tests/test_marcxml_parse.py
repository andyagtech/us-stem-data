"""MARC21 XML, for repositories that publish an award date nowhere else.

George Mason's oai_dc gives one dc:date per record and it is a bulk-load
timestamp -- identical across every record, so every thesis published under
the same wrong day. Its MARC carries the real date.
"""
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, "scripts")
from scrape_oai_etds import _parse_marcxml  # noqa: E402

def _xml(fields):
    return ET.fromstring(
        '<collection xmlns="http://www.loc.gov/MARC21/slim"><record>'
        + fields + '</record></collection>')

DF = ('<datafield tag="{t}"><subfield code="{c}">{v}</subfield></datafield>')
TITLE = DF.format(t="245", c="a", v="A thesis")


def test_the_explicit_issued_date_wins():
    x = _xml(TITLE
             + DF.format(t="911", c="a", v="[date: issued] 2013-10-31")
             + DF.format(t="264", c="c", v="2014-01-01")
             + DF.format(t="269", c="a", v="2015")
             + DF.format(t="307", c="a", v="2020-05-05T00:00:00Z"))
    rows, _, _ = _parse_marcxml(x, "gmu", "George Mason")
    assert rows[0]["date_issued"] == "2013-10-31", rows[0]


def test_falls_back_to_264c_then_269a():
    x = _xml(TITLE + DF.format(t="264", c="c", v="2014-01-01"))
    assert _parse_marcxml(x, "g", "G")[0][0]["date_issued"] == "2014-01-01"
    x = _xml(TITLE + DF.format(t="269", c="a", v="2015"))
    assert _parse_marcxml(x, "g", "G")[0][0]["date_issued"] == "2015"


def test_the_deposit_stamp_is_never_used():
    """307$a is the very field that made the oai_dc dates useless."""
    x = _xml(TITLE + DF.format(t="307", c="a", v="2020-05-05T00:00:00Z"))
    rows, _, _ = _parse_marcxml(x, "g", "G")
    assert rows[0]["date_issued"] == "", rows[0]["date_issued"]


def test_a_record_with_no_title_is_skipped():
    x = _xml(DF.format(t="264", c="c", v="2014"))
    assert _parse_marcxml(x, "g", "G")[0] == []


def test_creators_and_subjects_are_collected():
    x = _xml(TITLE
             + '<datafield tag="700"><subfield code="a">Ng, Alice</subfield></datafield>'
             + '<datafield tag="700"><subfield code="a">Diaz, Luis</subfield></datafield>'
             + '<datafield tag="650"><subfield code="a">Physics</subfield></datafield>')
    r = _parse_marcxml(x, "g", "G")[0][0]
    assert r["creator"] == "Ng, Alice; Diaz, Luis"
    assert r["subject"] == "Physics"


def test_the_resumption_token_is_returned():
    """It lives in the OAI envelope, not the MARC.

    Returning None told the harvester the set was finished after one page:
    the first GMU run stopped at 100 of 13,493 records and reported success.
    """
    x = ET.fromstring(
        '<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/">'
        '<ListRecords>'
        '<collection xmlns="http://www.loc.gov/MARC21/slim"><record>'
        + TITLE + '</record></collection>'
        '<resumptionToken completeListSize="8127">tok123</resumptionToken>'
        '</ListRecords></OAI-PMH>')
    rows, token, total = _parse_marcxml(x, "gmu", "George Mason")
    assert token == "tok123", token
    assert total == "8127", total


def test_the_last_page_returns_no_token():
    x = ET.fromstring(
        '<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/"><ListRecords>'
        '<collection xmlns="http://www.loc.gov/MARC21/slim"><record>'
        + TITLE + '</record></collection>'
        '<resumptionToken completeListSize="8127"></resumptionToken>'
        '</ListRecords></OAI-PMH>')
    _rows, token, _total = _parse_marcxml(x, "gmu", "George Mason")
    assert token is None, token
