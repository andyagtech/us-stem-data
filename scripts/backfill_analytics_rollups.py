#!/usr/bin/env python3
"""Rebuild the analytics daily rollups from the raw events already stored.

The dashboard reads daily rollup rows rather than raw events, because reading
a spike's worth of raw events cannot be done inside the Lambda's timeout and
the previous reader silently truncated at the first 1 MB of each day. Rollups
are written going forward by the collector; the events recorded before that
change -- 1,088 of them, from 24 July -- have none, so this builds theirs.

It also backfills the three fields those events never carried: the site they
came from, whether the agent looked automated, and the country the IP was
allocated to. Without them the old events cannot be filtered the way new ones
can, and the history would read as one undifferentiated pile.

IDEMPOTENT BY CONSTRUCTION. Each rollup row is computed in full from the raw
events and written with put_item, not incremented, so running this twice gives
the same answer. The collector's own increments land on top of whatever is
there, so a backfill and live traffic do not fight.

Usage:
  python3 scripts/backfill_analytics_rollups.py --dry-run
  python3 scripts/backfill_analytics_rollups.py
"""
from __future__ import annotations

import argparse
import collections
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from build_ip_country_table import lookup                    # noqa: E402

TABLE_NAME = os.environ.get("TABLE_NAME", "phd-demographics-analytics")
IP_TABLE = ROOT / "data" / "geo" / "ip_country.bin"
RETENTION_DAYS = 90
LAMBDA = (Path.home() / "usds_china_private" / "infra" / "analytics"
          / "analytics_lambda.py")


def _collector():
    """The deployed collector, loaded by path.

    Its aggregation is reused rather than reimplemented. This script used to
    carry its own BOT_MARKERS, host_of, safe and counter-path logic, and they
    had drifted: it counted pages under the raw data-page value, so
    /stem.html#njit and stem were two pages in a backfilled row and one page
    in a live one, and it wrote no devices, entry pages, read-on or errors at
    all. Since it overwrites rows with put_item, running it was a way to
    delete counters the collector had correctly recorded.
    """
    import importlib.util
    if not LAMBDA.exists():
        raise SystemExit(f"  collector not found at {LAMBDA}")
    # The collector demands its password at import time, deliberately: it must
    # not start up unauthenticated. Nothing here serves a request, so a
    # placeholder is enough -- and must not be the real one.
    os.environ.setdefault("ANALYTICS_PASSWORD", "not-used-by-the-backfill")
    os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
    spec = importlib.util.spec_from_file_location("analytics_lambda", LAMBDA)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m._IP_TABLE = IP_TABLE.read_bytes()
    return m


MOD = None                                  # set in main(), after argv parsing


def host_of(url: str) -> str:
    return MOD.host_of(url)


def safe(s: str) -> str:
    return MOD._safe(s)


def site_of(item: dict) -> str:
    """Which site an old event came from.

    Old events carry no site. The page label is the only reliable signal: the
    other site sets data-page="seattle-radicalism" on every page. A referrer
    from localhost marks this project's own test runs.
    """
    if item.get("site"):
        return item["site"]
    page = str(item.get("page", ""))
    if "radicalism" in page:
        return "seattle-radicalism"
    ref_host = host_of(item.get("referrer", ""))
    if ref_host in ("localhost", "127.0.0.1"):
        return "local"
    return "phd-demographics"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    import boto3

    global MOD
    MOD = _collector()

    blob = IP_TABLE.read_bytes() if IP_TABLE.exists() else b""
    if not blob:
        print(f"  missing {IP_TABLE.relative_to(ROOT)}; run "
              "scripts/build_ip_country_table.py")
        return 1
    table = boto3.resource("dynamodb").Table(TABLE_NAME)

    raw, kw = [], {}
    while True:
        r = table.scan(**kw)
        raw += [i for i in r["Items"] if not str(i["ts_session"]).startswith("@")]
        if "LastEvaluatedKey" not in r:
            break
        kw["ExclusiveStartKey"] = r["LastEvaluatedKey"]
    print(f"  {len(raw):,} raw events")

    rollups: dict[tuple, dict] = collections.defaultdict(dict)
    # Pageviews per session, in time order, so the first one gives the entry
    # page and a second one makes the session a read-on rather than a bounce.
    # These two cannot be derived from a single event, which is why the
    # collector counts them against a session marker and this counts them here.
    seen: dict[tuple, list] = collections.defaultdict(list)
    patched = 0
    for it in raw:
        date, site = it["date"], site_of(it)
        cc = lookup(blob, it.get("ip", ""))
        et = it.get("event_type", "pageview")
        bot = MOD.looks_automated(it.get("user_agent", ""))
        who = "bot" if bot else "human"
        r = rollups[(date, site)].setdefault(who, {})

        def bump(path: str, n: int = 1, into=None):
            cur = into if into is not None else r
            parts = path.split(".")
            for p in parts[:-1]:
                cur = cur.setdefault(p, {})
            cur[parts[-1]] = cur.get(parts[-1], 0) + n

        # The collector's own path list, minus its "who." prefix -- the rollup
        # body here is already scoped to one of human/bot.
        item = dict(it, country=it.get("country") or cc)
        for path in MOD.rollup_paths(who, et, item):
            bump(path.split(".", 1)[1])
        if it.get("session_id") and et == "pageview":
            seen[(date, site, who)].append((it.get("timestamp", ""), it, item))

        if not args.dry_run and (it.get("site") != site
                                 or "bot" not in it
                                 or (cc and not it.get("country"))):
            table.update_item(
                Key={"date": date, "ts_session": it["ts_session"]},
                UpdateExpression="SET #s = :s, #b = :b" + (", #c = :c" if cc else ""),
                ExpressionAttributeNames={"#s": "site", "#b": "bot",
                                          **({"#c": "country"} if cc else {})},
                ExpressionAttributeValues={":s": site, ":b": bot,
                                           **({":c": cc} if cc else {})})
            patched += 1

    # Sessions, entry pages and read-on, from the pageviews of each session.
    for (date, site, who), views in seen.items():
        body = rollups[(date, site)].setdefault(who, {})
        by_sid: dict[str, list] = collections.defaultdict(list)
        for ts, it, item in views:
            by_sid[it["session_id"]].append((ts, item))
        body["sessions"] = len(by_sid)
        read_on = 0
        for sid, rows in by_sid.items():
            rows.sort(key=lambda r: r[0])
            path = MOD.entry_path(who, rows[0][1])
            parts = path.split(".", 1)[1].split(".")
            cur = body
            for p in parts[:-1]:
                cur = cur.setdefault(p, {})
            cur[parts[-1]] = cur.get(parts[-1], 0) + 1
            if len(rows) > 1:
                read_on += 1
        if read_on:
            body["read_on_sessions"] = read_on

    print(f"  {len(rollups)} rollup rows over {len({d for d, _s in rollups})} days, "
          f"{len({s for _d, s in rollups})} sites")
    for (date, site), body in sorted(rollups.items())[-6:]:
        h, b = body.get("human", {}), body.get("bot", {})
        print(f"    {date} {site:20} human {h.get('pageview', 0):>4} views / "
              f"{h.get('sessions', 0):>3} sessions   bot {b.get('pageview', 0):>4}")
    if args.dry_run:
        print("  dry run: nothing written")
        return 0
    for (date, site), body in rollups.items():
        table.put_item(Item={"date": date, "ts_session": f"@rollup#{site}",
                             "ttl": int(time.time()) + RETENTION_DAYS * 86400,
                             **body})
    print(f"  wrote {len(rollups)} rollup rows; patched {patched} raw events")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
