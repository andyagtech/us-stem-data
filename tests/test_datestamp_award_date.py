"""Some repositories put the award date in the OAI header, not the metadata.

Penn State's ETDA publishes every dc:date as 2008 -- the date of a bulk
migration -- while its OAI <datestamp> runs from 1999 in chronological order.
22,098 records were being published under one wrong year. The datestamp is
normally a record modification time and useless for this, so it is opt-in per
repository rather than a general rule.
"""
import sys
sys.path.insert(0, "scripts")
from scrape_oai_etds import parse_records, DATESTAMP_IS_AWARD_DATE  # noqa: E402

XML = """<?xml version="1.0"?>
<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/"
         xmlns:oai_dc="http://www.openarchives.org/OAI/2.0/oai_dc/"
         xmlns:dc="http://purl.org/dc/elements/1.1/">
 <ListRecords><record>
  <header>
    <identifier>oai:etda.libraries.psu.edu:5801</identifier>
    <datestamp>1999-04-07T12:00:00Z</datestamp>
  </header>
  <metadata><oai_dc:dc>
    <dc:title>A thesis from 1999</dc:title>
    <dc:date>2008-10-14T13:54:03Z</dc:date>
  </oai_dc:dc></metadata>
 </record></ListRecords></OAI-PMH>"""


def test_opted_in_repo_takes_the_datestamp():
    rows, _tok, _n = parse_records(XML, "penn_state", "Penn State")
    assert rows and rows[0]["date"].startswith("1999"), rows[0]["date"]
    assert rows[0]["date_issued"].startswith("1999")


def test_other_repos_are_unaffected():
    """The datestamp is a modification time everywhere else; do not use it."""
    rows, _tok, _n = parse_records(XML, "some_other_repo", "Somewhere")
    assert rows and rows[0]["date"].startswith("2008"), rows[0]["date"]


def test_the_opt_in_list_is_deliberately_small():
    assert DATESTAMP_IS_AWARD_DATE == {"penn_state"}
