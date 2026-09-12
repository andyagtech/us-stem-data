#!/usr/bin/env python3
"""Tests for the analytics collector and dashboard.

Each test corresponds to one of the three faults found on 2026-09-12, or to a
trap in the fix. The Lambda lives in the private repo (infra/analytics) because
that is where it deploys from; these tests load it by path and give it a fake
table, so they need neither AWS nor credentials.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
from pathlib import Path

import pytest
from botocore.exceptions import ClientError

ROOT = Path(__file__).resolve().parents[1]
LAMBDA = Path.home() / "usds_china_private" / "infra" / "analytics" / "analytics_lambda.py"
TABLE = ROOT / "data" / "geo" / "ip_country.bin"


def _client_error(code: str, op: str, message: str = "") -> ClientError:
    """The exception boto3 raises, so the lambda's handling is exercised.

    The fake used to raise RuntimeError for a failed condition, which meant
    the lambda's `except ClientError` branches were never tested at all.
    """
    return ClientError({"Error": {"Code": code, "Message": message}}, op)


# One SET clause: a path, its if_not_exists default, and whether it adds one.
_CLAUSE = re.compile(r"([#\w.]+)\s*=\s*if_not_exists\(\s*[#\w.]+\s*,\s*"
                     r"(:\w+)\s*\)(\s*\+\s*:one)?")


class FakeTable:
    """Enough of a DynamoDB table to observe what the collector writes."""

    def __init__(self):
        self.items: dict[tuple, dict] = {}
        self.updates: list[dict] = []

    def put_item(self, Item=None, ConditionExpression=None):
        key = (Item["date"], Item["ts_session"])
        if ConditionExpression and key in self.items:
            raise _client_error("ConditionalCheckFailedException", "PutItem")
        self.items[key] = Item

    def update_item(self, Key=None, UpdateExpression="", ExpressionAttributeNames=None,
                    ExpressionAttributeValues=None, ReturnValues=None, **kw):
        self.updates.append({"key": Key, "expr": UpdateExpression,
                             "names": ExpressionAttributeNames or {}})
        rk = (Key["date"], Key["ts_session"])
        # An UpdateItem is atomic: if any path is invalid, NOTHING is applied.
        # Applying clause by clause onto the live row instead left the valid
        # counters incremented before the bad path raised, so _bump's retry
        # counted them twice -- a fake that fails differently from the real
        # table is as misleading as one that does not fail at all.
        import copy
        row = copy.deepcopy(self.items.get(rk) or dict(Key))
        names, values = ExpressionAttributeNames or {}, ExpressionAttributeValues or {}
        updated = {}
        # Two clause shapes, applied by hand:
        #   a.b.c = if_not_exists(a.b.c, :zero) + :one   -- add one
        #   a.b   = if_not_exists(a.b, :m0)              -- create a map
        #
        # This fake used to create every missing intermediate map with
        # setdefault, which DynamoDB does NOT do: setting human.referrers.x
        # when human.referrers is absent is a ValidationException that fails
        # the whole expression. Being more permissive than the real table is
        # how nineteen passing tests sat on top of a collector whose rollups
        # had never once incremented in production. The rule is enforced here
        # so the suite can only pass on writes DynamoDB would accept.
        # Clauses are matched, not split on ", " -- that separator also sits
        # inside if_not_exists(path, :default).
        for m in _CLAUSE.finditer(UpdateExpression):
            path, default, increment = m.group(1), m.group(2), m.group(3)
            parts = [names.get(p, p) for p in path.split(".")]
            cur = row
            for p in parts[:-1]:
                if not isinstance(cur, dict) or p not in cur:
                    raise _client_error(
                        "ValidationException", "UpdateItem",
                        "The document path provided in the update expression "
                        "is invalid for update")
                cur = cur[p]
            leaf = parts[-1]
            if increment:
                cur[leaf] = cur.get(leaf, 0) + 1
            elif leaf not in cur:                   # if_not_exists(p, :mN)
                cur[leaf] = values.get(default, {})
            updated[parts[0]] = row[parts[0]]
        self.items[rk] = row                        # commit, having validated
        # DynamoDB answers UPDATED_NEW with the new values under "Attributes";
        # without this the lambda's read-back of the session counter threw and
        # the engagement measure silently stayed at zero.
        return {"Attributes": updated} if ReturnValues else {}

    def get_item(self, Key=None):
        it = self.items.get((Key["date"], Key["ts_session"]))
        return {"Item": it} if it else {}

    def query(self, **kw):
        return {"Items": [v for k, v in sorted(self.items.items(), reverse=True)
                          if not k[1].startswith("@")]}


@pytest.fixture(scope="module")
def mod():
    if not LAMBDA.exists():
        pytest.skip("analytics lambda not present (private repo)")
    os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
    os.environ["ANALYTICS_PASSWORD"] = "test-password"
    spec = importlib.util.spec_from_file_location("analytics_lambda", LAMBDA)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    # The country table ships beside the lambda at deploy time; point at the source.
    m._IP_TABLE = TABLE.read_bytes() if TABLE.exists() else b""
    return m


@pytest.fixture
def table(mod, monkeypatch):
    t = FakeTable()
    monkeypatch.setattr(mod.dynamodb, "Table", lambda _name: t)
    return t


def post(mod, body, origin="https://phd-demographics.andy-barr.com", ip="8.8.8.8"):
    return mod.handler({
        "rawPath": "/collect",
        "requestContext": {"http": {"method": "POST", "sourceIp": ip}},
        "headers": {"origin": origin} if origin else {},
        "body": json.dumps(body)})


def get(mod, **params):
    params.setdefault("password", "test-password")
    return mod.handler({
        "rawPath": "/analytics",
        "requestContext": {"http": {"method": "GET"}},
        "queryStringParameters": {k: str(v) for k, v in params.items()}})


# --- fault 2: country ------------------------------------------------------
def test_country_comes_from_the_ip(mod, table):
    """It was read from a CloudFront header this endpoint never receives."""
    post(mod, {"type": "pageview", "sid": "s1", "page": "index",
               "ua": "Mozilla/5.0 (Macintosh) Safari/605"}, ip="8.8.8.8")
    raw = [i for k, i in table.items.items() if not k[1].startswith("@")]
    assert raw and raw[0]["country"] == "US"


def test_country_matches_the_build_script(mod):
    """Two copies of the lookup; they must not drift apart."""
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    from build_ip_country_table import lookup
    blob = TABLE.read_bytes()
    for ip in ("8.8.8.8", "1.1.1.1", "193.0.6.139", "196.25.1.1", "139.130.4.5",
               "0.0.0.1", "255.255.255.255"):
        assert mod.country_of(ip) == lookup(blob, ip), ip


def test_ipv6_and_junk_resolve_to_nothing_not_a_crash(mod):
    for ip in ("2001:db8::1", "", "not-an-ip", "1.2.3", "300.1.1.1"):
        assert mod.country_of(ip) == ""


# --- fault 3: bots and sites ----------------------------------------------
def test_headless_and_crawlers_are_marked(mod):
    for ua in ("Mozilla/5.0 HeadlessChrome/120", "Googlebot/2.1",
               "python-requests/2.31", "curl/8.4", ""):
        assert mod.looks_automated(ua), ua
    for ua in ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Safari/605.1.15",
               "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0) Version/17.0 Mobile Safari"):
        assert not mod.looks_automated(ua), ua


def test_bots_are_excluded_by_default_and_countable_on_request(mod, table):
    human = {"type": "pageview", "sid": "h1", "page": "index",
             "ua": "Mozilla/5.0 (Macintosh) Version/17 Safari/605"}
    bot = {"type": "pageview", "sid": "b1", "page": "index",
           "ua": "Mozilla/5.0 HeadlessChrome/120"}
    post(mod, human); post(mod, bot); post(mod, bot | {"sid": "b2"})
    d = json.loads(get(mod, days=1)["body"])
    assert d["total_views"] == 1 and d["bots"] == "excluded"
    d = json.loads(get(mod, days=1, bots="include")["body"])
    assert d["total_views"] == 3 and d["bots"] == "included"


def test_the_two_sites_are_kept_apart(mod, table):
    post(mod, {"type": "pageview", "sid": "a", "page": "index", "ua": "Safari/605"},
         origin="https://phd-demographics.andy-barr.com")
    post(mod, {"type": "pageview", "sid": "b", "page": "seattle-radicalism",
               "ua": "Safari/605"}, origin="https://seattle-radicalism.andy-barr.com")
    phd = json.loads(get(mod, days=1)["body"])
    other = json.loads(get(mod, days=1, site="seattle-radicalism")["body"])
    assert phd["total_views"] == 1 and other["total_views"] == 1
    assert "seattle-radicalism" in phd["sites"]


def test_a_foreign_origin_is_refused_but_a_missing_one_is_not(mod, table):
    r = post(mod, {"type": "pageview", "sid": "x", "ua": "Safari/605"},
             origin="https://example.com")
    assert r["statusCode"] == 403
    r = post(mod, {"type": "pageview", "sid": "y", "ua": "Safari/605"}, origin="")
    assert r["statusCode"] == 200, "a browser that omits Origin is still a visitor"


# --- fault 1: the undercount ----------------------------------------------
def test_totals_come_from_rollups_not_raw_events(mod, table):
    """The old reader queried raw events once per day and ignored the cursor,
    so it stopped at the first 1 MB -- about 2,400 events -- and said nothing."""
    for i in range(50):
        post(mod, {"type": "pageview", "sid": f"s{i}", "page": "index",
                   "ua": "Mozilla/5.0 (Macintosh) Safari/605"})
    d = json.loads(get(mod, days=1)["body"])
    assert d["total_views"] == 50
    assert d["total_sessions"] == 50
    rollups = [k for k in table.items if k[1].startswith("@rollup")]
    assert len(rollups) == 1, "one rollup row per site per day, whatever the traffic"


def test_sessions_are_counted_once_however_many_pages(mod, table):
    for page in ("index", "institutions", "briefing"):
        post(mod, {"type": "pageview", "sid": "same-session", "page": page,
                   "ua": "Mozilla/5.0 (Macintosh) Safari/605"})
    d = json.loads(get(mod, days=1)["body"])
    assert d["total_views"] == 3 and d["total_sessions"] == 1


def test_referrers_replace_the_cities_that_never_existed(mod, table):
    post(mod, {"type": "pageview", "sid": "r1", "page": "index", "ua": "Safari/605",
               "referrer": "https://news.ycombinator.com/item?id=1"})
    post(mod, {"type": "pageview", "sid": "r2", "page": "index", "ua": "Safari/605",
               "referrer": "https://news.ycombinator.com/"})
    d = json.loads(get(mod, days=1)["body"])
    assert d["top_referrers"].get("news_ycombinator_com") == 2
    assert "top_cities" not in d, "the registries publish no cities; do not imply any"


def test_internal_navigation_is_not_a_referrer_but_no_referrer_is_direct(mod, table):
    """Three cases that must not be pooled: another site sent them, nothing
    did, or they came from one of our own pages."""
    post(mod, {"type": "pageview", "sid": "i1", "page": "institutions", "ua": "Safari/605",
               "referrer": "https://phd-demographics.andy-barr.com/index.html"})
    d = json.loads(get(mod, days=1)["body"])
    assert d["top_referrers"] == {}, "a click from our own page is not a source"
    post(mod, {"type": "pageview", "sid": "i2", "page": "index", "ua": "Safari/605"})
    d = json.loads(get(mod, days=1)["body"])
    assert d["top_referrers"] == {"__direct": 1}


def test_clicks_and_errors_are_reported(mod, table):
    ua = "Mozilla/5.0 (Macintosh) Safari/605"
    post(mod, {"type": "pageview", "sid": "c1", "page": "briefing", "ua": ua})
    post(mod, {"type": "click", "sid": "c1", "target": "pdf.print", "ua": ua})
    post(mod, {"type": "error", "sid": "c1", "message": "boom", "ua": ua})
    d = json.loads(get(mod, days=1)["body"])
    assert d["total_clicks"] == 1 and d["total_errors"] == 1
    assert d["top_clicks"].get("pdf_print") == 1
    assert d["avg_clicks_per_session"] == 1.0


def test_the_password_still_guards_the_dashboard(mod, table):
    r = mod.handler({"rawPath": "/analytics",
                     "requestContext": {"http": {"method": "GET"}},
                     "queryStringParameters": {"password": "wrong"}})
    assert r["statusCode"] == 401


def test_the_full_ip_is_stored(mod, table):
    """Deliberate: geography depends on it and nothing here hashes it."""
    post(mod, {"type": "pageview", "sid": "ip1", "page": "index", "ua": "Safari/605"},
         ip="203.0.113.9")
    raw = [i for k, i in table.items.items() if not k[1].startswith("@")]
    assert raw[0]["ip"] == "203.0.113.9"



# --- the aggregations the dashboard is built on ----------------------------
def test_page_labels_are_one_per_page(mod, table):
    """The same page arrived as "stem", "/stem.html" and "/stem.html#njit" and
    split its own counter three ways."""
    ua = "Mozilla/5.0 (Macintosh) Safari/605"
    for page, path in (("stem", "/stem.html"), ("/stem.html", "/stem.html"),
                       ("/stem.html#njit", "/stem.html#njit")):
        post(mod, {"type": "pageview", "sid": f"p{page}", "page": page,
                   "path": path, "ua": ua})
    d = json.loads(get(mod, days=1)["body"])
    assert d["top_pages"] == {"stem": 3}, d["top_pages"]


def test_entry_pages_record_where_a_session_came_in(mod, table):
    ua = "Mozilla/5.0 (Macintosh) Safari/605"
    post(mod, {"type": "pageview", "sid": "e1", "page": "institutions", "ua": ua})
    post(mod, {"type": "pageview", "sid": "e1", "page": "briefing", "ua": ua})
    post(mod, {"type": "pageview", "sid": "e2", "page": "briefing", "ua": ua})
    d = json.loads(get(mod, days=1)["body"])
    assert d["top_entry_pages"] == {"institutions": 1, "briefing": 1}
    assert d["top_pages"] == {"briefing": 2, "institutions": 1}


def test_read_on_separates_a_bounce_from_a_session_that_continued(mod, table):
    ua = "Mozilla/5.0 (Macintosh) Safari/605"
    post(mod, {"type": "pageview", "sid": "b1", "page": "index", "ua": ua})
    post(mod, {"type": "pageview", "sid": "g1", "page": "index", "ua": ua})
    post(mod, {"type": "pageview", "sid": "g1", "page": "rankings", "ua": ua})
    post(mod, {"type": "pageview", "sid": "g1", "page": "briefing", "ua": ua})
    d = json.loads(get(mod, days=1)["body"])
    assert d["total_sessions"] == 2
    assert d["read_on_pct"] == 50.0, "one of two sessions went past its first page"
    assert d["views_per_session"] == 2.0


def test_devices_come_from_the_reported_screen_width(mod, table):
    ua = "Mozilla/5.0 (iPhone) Mobile Safari"
    post(mod, {"type": "pageview", "sid": "d1", "page": "index", "ua": ua, "screen": "390x844"})
    post(mod, {"type": "pageview", "sid": "d2", "page": "index", "ua": "Safari/605", "screen": "1512x982"})
    post(mod, {"type": "pageview", "sid": "d3", "page": "index", "ua": "Safari/605", "screen": "820x1180"})
    d = json.loads(get(mod, days=1)["body"])
    assert d["devices"] == {"phone": 1, "desktop": 1, "tablet": 1}


def test_errors_are_grouped_by_message_and_page(mod, table):
    ua = "Mozilla/5.0 (Macintosh) Safari/605"
    post(mod, {"type": "pageview", "sid": "x1", "page": "live", "ua": ua})
    post(mod, {"type": "error", "sid": "x1", "page": "live", "message": "chart failed", "ua": ua})
    post(mod, {"type": "rejection", "sid": "x1", "page": "live", "message": "chart failed", "ua": ua})
    d = json.loads(get(mod, days=1)["body"])
    assert d["total_errors"] == 2
    assert d["top_errors"] == {"chart_failed": 2}
    assert d["errors_by_page"] == {"live": 2}


# --------------------------------------------------------------------------
# The fault that shipped: DynamoDB will not create an intermediate map inside
# an UpdateExpression, so every counter of every event was being lost, and
# `except Exception: pass` meant nothing said so.
# --------------------------------------------------------------------------

def test_rollup_counters_survive_a_row_that_does_not_exist_yet(mod, table):
    """The first event of a day has no rollup row and no parent maps at all."""
    ua = "Mozilla/5.0 (Macintosh) Safari/605"
    post(mod, {"type": "pageview", "sid": "n1", "page": "index", "ua": ua,
               "referrer": "https://news.ycombinator.com/item?id=1",
               "screen": "1512x982"})
    d = json.loads(get(mod, days=1)["body"])
    assert d["total_views"] == 1
    assert d["total_sessions"] == 1
    assert d["top_referrers"] == {"news_ycombinator_com": 1}
    assert d["top_entry_pages"] == {"index": 1}
    assert d["devices"] == {"desktop": 1}


def test_a_new_counter_group_lands_on_a_row_written_before_it_existed(mod, table):
    """A rollup row missing one sub-map must not lose the other counters.

    This is the production state: rows existed with hours/pages/countries and
    no referrers/devices/entry_pages, so the referrer path failed validation
    and took the whole expression -- views, sessions, everything -- with it.
    """
    ua = "Mozilla/5.0 (Macintosh) Safari/605"
    key = ("2026-09-12", f"{mod.ROLLUP}#phd-demographics")
    table.items[key] = {"date": key[0], "ts_session": key[1],
                        "human": {"events": 7, "pageview": 7,
                                  "hours": {"12": 7}, "pages": {"index": 7}}}
    post(mod, {"type": "pageview", "sid": "p1", "page": "index", "ua": ua,
               "referrer": "https://example.org/post", "screen": "390x844"})
    human = table.items[key]["human"]
    assert human["events"] == 8, "the pre-existing counter still incremented"
    assert human["referrers"] == {"example_org": 1}, "the new group was created"
    assert human["devices"] == {"phone": 1}


def test_a_failed_counter_does_not_turn_a_new_session_into_a_returning_one(mod, table):
    """read_on must come from the session marker, not from a caught exception.

    The old code wrapped the conditional put and the counter bump in one
    `except Exception`, so a bump that failed after a SUCCESSFUL create ran
    the already-seen branch and counted a first visit as a session that read
    on. Bumps fail here; the session must still be new, and read_on zero.
    """
    ua = "Mozilla/5.0 (Macintosh) Safari/605"
    real = mod._bump

    def refuse(t, date_str, key, paths):
        if any(p.endswith("sessions") for p in paths):
            raise _client_error("ThrottlingException", "UpdateItem")
        return real(t, date_str, key, paths)

    mod._bump = refuse
    try:
        post(mod, {"type": "pageview", "sid": "s9", "page": "index", "ua": ua})
    finally:
        mod._bump = real
    d = json.loads(get(mod, days=1)["body"])
    assert d["read_on_pct"] == 0.0, "a first pageview never read on"
    marker = table.items[("2026-09-12", f"{mod.SESSION}#phd-demographics#s9")]
    assert "views" not in marker, "the already-seen branch must not have run"


def test_the_fake_table_refuses_a_write_dynamodb_would_refuse(mod, table):
    """Guard the guard: the fake must enforce the nested-path rule.

    If this passes trivially the fake has gone permissive again and the three
    tests above stop proving anything.
    """
    with pytest.raises(ClientError) as exc:
        table.update_item(
            Key={"date": "2026-09-12", "ts_session": "@rollup#x"},
            UpdateExpression="SET #a.#b = if_not_exists(#a.#b, :zero) + :one",
            ExpressionAttributeNames={"#a": "absent", "#b": "leaf"},
            ExpressionAttributeValues={":zero": 0, ":one": 1})
    assert exc.value.response["Error"]["Code"] == "ValidationException"
