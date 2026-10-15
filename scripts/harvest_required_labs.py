#!/usr/bin/env python3
"""Measure the labs the author requires, and put them in the pool.

WHY THIS EXISTS. The author sends laboratories he wants in the table.
Some are below a threshold; some the crawl has never reached at all,
because they sit on a personal page no department links to. Declaring
one used to take two edits in two files, and a URL that was never
crawled could not be forced in at all -- lab_overrides.ALWAYS_INCLUDE
pulls a row from the TESTED set, and an uncrawled page is not in it.

So this reads that one list, fetches anything missing, and merges the
measurement through lab_store like every other harvester. One list,
one script.

WHAT IT DOES NOT DO. It does not invent a figure and it does not lower
a bar for the page itself. The roster is read by the same extractor,
scored by the same classifier, counted against the same denominator.
If the page carries no readable roster, nothing is merged and this
says so: a lab cannot be published by asserting it exists.

Usage:
    python3 scripts/harvest_required_labs.py
    python3 scripts/harvest_required_labs.py --refresh
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lab_store                                              # noqa: E402
from follow_lab_links import get                              # noqa: E402
from harvest_lab_rosters import best_names, composition       # noqa: E402
from lab_overrides import ALWAYS_INCLUDE                      # noqa: E402
from lab_page_filter import is_a_research_group               # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true",
                    help="re-read a lab already in the pool")
    a = ap.parse_args()

    have = {g["url"]: g for g in lab_store.load()["groups"]}
    rows, skipped = [], 0
    for url, (institution, field, why) in ALWAYS_INCLUDE.items():
        cur = have.get(url)
        if cur and (cur.get("composition") or {}).get("dominance") is not None \
                and not a.refresh:
            skipped += 1
            continue
        html = get(url)
        if not html:
            print(f"  UNREACHABLE  {url}")
            continue
        m = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
        title = " ".join(m.group(1).split())[:110] if m else ""
        keep, no = is_a_research_group(url, title)
        if not keep:
            #: THE ONE JUDGEMENT THE OVERRIDE DOES NOT OVERRIDE. A
            #: share read off a page that is not a team is not a
            #: finding about anyone's hiring, so this is reported and
            #: not merged.
            print(f"  NOT A TEAM PAGE  {url}\n      {no}")
            continue
        names = best_names(html)
        if not names:
            print(f"  NO READABLE ROSTER  {url}")
            continue
        comp = composition(names)
        rows.append({
            "url": url, "title": title, "institution": institution,
            "department_field": field, "status": "roster",
            "members": len(names), "members_detected": len(names),
            "composition": comp, "found_from": "required",
            "required_by_author": True,
        })
        print(f"  {len(names):>3} members  {comp['dominance']:>5}% "
              f"{comp['dominant_group'] or '-':<14} "
              f"non-European {comp['non_european_share']:>5}%  {url[:46]}")

    if rows:
        s = lab_store.merge(rows, source="required",
                            correct=("members", "members_detected",
                                     "composition"))
        print(f"\n  merged {len(rows)}: +{s['added']} new, "
              f"{s['improved']} improved")
    print(f"  {skipped} already measured; {len(ALWAYS_INCLUDE)} required "
          f"in all")
    return 0


if __name__ == "__main__":
    sys.exit(main())
