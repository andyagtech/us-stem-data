#!/usr/bin/env python3
"""Pre-warm the assistant's answer cache with the questions people actually ask.

WHY

A cold cache means the first person to ask each common question waits for a
full model turn - several seconds, several tool calls. On a page built to
attract attention, that first person is thousands of people arriving at once,
each hitting a cold entry. Warming ahead of time turns the common path into a
lookup.

It also caps cost at the moment cost is most likely to run away: the twenty or
thirty questions below will be the overwhelming majority of traffic, and each
is paid for once rather than once per visitor.

HOW

Each question is sent to the live endpoint exactly as a browser would send it,
with no conversation history so the answer qualifies for caching. The handler
does the work and stores the result. This does not write to the cache directly
-- going through the real path means the warmed entries are byte-identical to
what a visitor would get, rather than something assembled by a different code
path that might drift.

WHEN TO RE-RUN

After any data rebuild. The cache key includes the data version, so a rebuild
invalidates every entry and the first visitor after it pays full price again
unless this is re-run.

Usage:
    python3 scripts/warm_chat_cache.py --dry-run
    python3 scripts/warm_chat_cache.py
    python3 scripts/warm_chat_cache.py --endpoint https://... --delay 2
"""
from __future__ import annotations

import argparse
from pathlib import Path
import json
import sys
import time
import urllib.error
import urllib.request

def _widget_endpoint() -> str:
    """The endpoint the site's chat widget calls, read from the widget itself.

    This was a hard-coded URL for the OLD `phd-chat` function, retired in
    April, so every warming run since then filled the cache of a function no
    visitor reaches -- while the one they do reach, phd-chat-prod, stayed
    cold. tests/test_chat_assistant.py had the same bug and was fixed; this
    one was missed. Reading the widget means the two cannot disagree again.
    """
    import re
    widget = Path(__file__).resolve().parents[1] / "site" / "chat-widget.js"
    m = re.search(r"CHAT_ENDPOINT\s*=\s*'([^']+)'", widget.read_text()) if widget.exists() else None
    if not m:
        raise SystemExit("could not read CHAT_ENDPOINT from site/chat-widget.js; pass --endpoint")
    return m.group(1)


DEFAULT_ENDPOINT = _widget_endpoint()
ORIGIN = "https://phd-demographics.andy-barr.com"

# Drawn from the knowledge base's "questions readers actually ask", the site's
# own suggestion chips, and the shape of the argument the landing page makes.
# Grouped so it is obvious what is covered and what is missing.
QUESTIONS: list[tuple[str, str]] = [
    # The finding itself
    ("finding", "What is the main finding of this site?"),
    ("finding", "Is the share of foreign students in US PhD programs rising?"),
    ("finding", "What is the concentration effect?"),
    ("finding", "How many departments are majority non-resident?"),
    ("finding", "Which departments have the highest non-resident share?"),

    # Money - the landing page's lead
    ("cost", "How much do taxpayers spend per STEM doctorate?"),
    ("cost", "How much federal funding goes to these programs?"),
    ("cost", "Which universities get the most federal research funding?"),

    # Level and field
    ("fields", "Which field has the highest non-resident share?"),
    ("fields", "What share of computer science master's degrees go to foreign students?"),
    ("fields", "How does engineering compare to biology?"),
    ("fields", "What is the difference between master's and doctorate programs?"),
    ("fields", "Show me the trend in STEM doctorates over time"),

    # Institutions
    ("schools", "What is the NRA share at MIT?"),
    ("schools", "Which university has the highest non-resident share?"),
    ("schools", "How does Purdue compare to other universities?"),
    ("schools", "Show me data for Stony Brook"),

    # The hard questions - these must be answered carefully every time
    ("hard", "Are American students being displaced?"),
    ("hard", "Did domestic enrollment go down?"),
    ("hard", "Does this prove foreign students are prioritized?"),
    ("hard", "Which university is the worst offender?"),
    ("hard", "What about Chinese students specifically?"),

    # Visas and the pipeline
    ("visas", "How many F-1 student visas are issued each year?"),
    ("visas", "What happened to F-1 visa numbers after 2015?"),
    ("visas", "What is OPT?"),
    ("visas", "How does the student visa to green card pipeline work?"),

    # Method and provenance - asked by the people most worth convincing
    ("method", "Where does this data come from?"),
    ("method", "What does non-resident alien mean?"),
    ("method", "How is STEM defined here?"),
    ("method", "Can I download the raw data?"),
    ("method", "What are the limitations of this data?"),

    # Comparison between institutions. The per-institution table is the only
    # place degrees, enrolment and federal money sit on one row, and these are
    # the shapes people reach for once they know they can compare at all.
    ("compare", "Compare Purdue and Michigan"),
    ("compare", "Which institutions award the most foreign STEM master's degrees?"),
    ("compare", "Which universities receive the most federal obligations?"),
    ("compare", "Which states have the highest non-resident share?"),
    ("compare", "How much federal money goes to each state?"),
    ("compare", "Where has the foreign master's share risen the most?"),
    ("compare", "What does my state look like?"),

    # The wage comparison, which is the finding most often quoted at the wrong
    # geography: the national figure understates it by 13 points.
    ("wages", "Do H-1B employers pay below market rates?"),
    ("wages", "What wage level do most H-1B filings use?"),
]


def ask(endpoint: str, question: str, timeout: int = 60) -> tuple[bool, str, int]:
    payload = {"v": 2, "message": question, "page": {"path": "/"}}
    req = urllib.request.Request(
        endpoint, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Origin": ORIGIN},
        method="POST")
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return False, f"HTTP {e.code}", int((time.time() - t0) * 1000)
    except Exception as e:                                  # noqa: BLE001
        return False, str(e)[:60], int((time.time() - t0) * 1000)
    ms = int((time.time() - t0) * 1000)
    cached = (body.get("meta") or {}).get("cache")
    nblocks = len(body.get("blocks") or [])
    note = f"cache={cached}" if cached else f"{nblocks} blocks"
    return True, note, ms


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    ap.add_argument("--delay", type=float, default=1.5,
                    help="seconds between questions; the endpoint rate-limits "
                         "at 10/min/IP, so keep this above 6 for a full run "
                         "from one address")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--group", help="warm only one group")
    args = ap.parse_args()

    qs = [q for q in QUESTIONS if not args.group or q[0] == args.group]
    groups = sorted({g for g, _ in QUESTIONS})

    if args.dry_run:
        print(f"{len(qs)} questions across {len(groups)} groups: "
              f"{', '.join(groups)}\n")
        for g, q in qs:
            print(f"  [{g:<8}] {q}")
        print(f"\nAt --delay {args.delay}s that is roughly "
              f"{len(qs) * args.delay / 60:.1f} minutes.")
        return 0

    print(f"Warming {len(qs)} questions against {args.endpoint}\n")
    ok = fail = 0
    for i, (group, q) in enumerate(qs, 1):
        good, note, ms = ask(args.endpoint, q)
        ok, fail = (ok + 1, fail) if good else (ok, fail + 1)
        print(f"  {i:>2}/{len(qs)}  [{group:<8}] {ms:>6} ms  "
              f"{'ok ' if good else 'FAIL'}  {note:<14} {q[:44]}")
        if i < len(qs):
            time.sleep(args.delay)

    print(f"\n{ok} warmed, {fail} failed.")
    if fail:
        print("Failures leave those questions cold; re-run for just that group "
              "with --group.")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
