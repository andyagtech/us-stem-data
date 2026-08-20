#!/usr/bin/env python3
"""Read chat analytics from DynamoDB, locally, over IAM.

WHY THIS REPLACED A WEB DASHBOARD

`chat-admin.html` read its data from a Lambda Function URL configured with
`AuthType: NONE`. Anyone who viewed source on that publicly served page got the
URL, and the URL returned every log entry -- including each visitor's full IP
address alongside the question they asked. CORS was set, which restricts
browsers and does nothing to curl.

The exposure was small in practice (eleven entries, one address, almost all of
it test traffic) but it was about to stop being small, on a politically
contentious site where the pairing of an IP with a question about immigration
data is exactly the sort of thing that should never be public.

The durable fix is not authentication on that endpoint. It is noticing that a
single-operator admin tool has no business being a public web page. This script
reads the table directly with the operator's own AWS credentials:

  secure       no public endpoint exists to find, probe or leak. Access is IAM,
               through a profile that already exists. No shared secret ships to
               a browser, and there is none to rotate or accidentally commit.
  reliable     no Lambda, no cold start, no CORS, no Function URL to
               misconfigure. Fewer moving parts than the thing it replaces.
  sustainable  nothing new to run or pay for. The table was already there.

FULL IPS ARE DELIBERATE

The logs record complete addresses on purpose, for geo-analysis. That decision
is unchanged. What changed is that reading them now requires credentials, and
`--anonymise` is offered for when output is going to be pasted somewhere.

Usage:
    python3 scripts/chat_logs.py                    # last 7 days
    python3 scripts/chat_logs.py --days 30
    python3 scripts/chat_logs.py --anonymise        # mask the last two octets
    python3 scripts/chat_logs.py --json             # raw, for further analysis
    python3 scripts/chat_logs.py --summary          # counts, no message bodies
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter

TABLE = os.environ.get("CHAT_LOGS_TABLE", "phd-chat-logs")
REGION = os.environ.get("AWS_REGION", "us-east-1")


def _mask(ip: str) -> str:
    parts = (ip or "").split(".")
    return ".".join(parts[:2] + ["x", "x"]) if len(parts) == 4 else "?"


def fetch(days: int) -> list[dict]:
    try:
        import boto3
    except ImportError:
        sys.exit("boto3 required: pip install boto3")
    cutoff = int(time.time()) - days * 86400
    table = boto3.resource("dynamodb", region_name=REGION).Table(TABLE)

    items, kwargs = [], {}
    while True:
        # A scan is right here: the table is small, TTL-bounded, and this runs
        # interactively a few times a week. An index would be more machinery
        # than the access pattern justifies.
        resp = table.scan(**kwargs)
        items.extend(resp.get("Items", []))
        if "LastEvaluatedKey" not in resp:
            break
        kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]

    rows = [i for i in items if int(i.get("epoch", 0) or 0) >= cutoff]
    rows.sort(key=lambda r: int(r.get("epoch", 0) or 0), reverse=True)
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--anonymise", action="store_true",
                    help="mask the last two octets of every IP")
    ap.add_argument("--json", action="store_true", help="raw JSON output")
    ap.add_argument("--summary", action="store_true",
                    help="counts only, no message bodies")
    ap.add_argument("--limit", type=int, default=60)
    args = ap.parse_args()

    rows = fetch(args.days)
    if not rows:
        print(f"No chat activity in the last {args.days} days.")
        return 0

    if args.json:
        out = []
        for r in rows:
            d = {k: (float(v) if hasattr(v, "as_tuple") else v)
                 for k, v in r.items()}
            if args.anonymise:
                d["ip"] = _mask(str(d.get("ip", "")))
            out.append(d)
        print(json.dumps(out, indent=2, default=str))
        return 0

    ips = Counter(str(r.get("ip", "")) for r in rows)
    tools = Counter(t for r in rows for t in (r.get("tools_used") or []))
    lat = [int(r.get("latency_ms", 0) or 0) for r in rows
           if r.get("latency_ms")]
    lat.sort()

    print(f"Chat analytics — last {args.days} days, table {TABLE}\n")
    print(f"  turns:            {len(rows)}")
    print(f"  distinct IPs:     {len(ips)}")
    if lat:
        print(f"  latency p50/p95:  {lat[len(lat)//2]:,} ms / "
              f"{lat[int(len(lat)*0.95)]:,} ms")
    if tools:
        print(f"  tools used:       "
              + ", ".join(f"{t}×{n}" for t, n in tools.most_common(6)))
    busiest = ips.most_common(3)
    if busiest:
        print("  busiest callers:  "
              + ", ".join(f"{(_mask(i) if args.anonymise else i)}×{n}"
                          for i, n in busiest))

    if args.summary:
        return 0

    print(f"\n  {'when':<21}{'ip':<17}message")
    print("  " + "-" * 76)
    for r in rows[:args.limit]:
        ip = str(r.get("ip", ""))
        shown = _mask(ip) if args.anonymise else ip
        msg = str(r.get("message", ""))[:44]
        print(f"  {str(r.get('timestamp',''))[:19]:<21}{shown:<17}{msg}")
    if len(rows) > args.limit:
        print(f"  … {len(rows) - args.limit} more (raise --limit)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
