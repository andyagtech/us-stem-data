#!/usr/bin/env python3
"""Mark every stored roster that is not at a US university.

The table's top entry was a Chinese laboratory credited to Illinois.
A Chinese lab staffed by Chinese students is not a finding, and the
crawl had no way to tell: it reached the professor through an
Illinois directory, because he used to be there, and followed his
research link abroad.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import crawl_resume                                           # noqa: E402
import lab_name_cache as cache                                # noqa: E402
import lab_store                                              # noqa: E402
from follow_lab_links import get                              # noqa: E402
from us_affiliation import check                              # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
LABS = ROOT / "data" / "labs" / "discovered_labs.json"


#: Set by main() so judge() can run without the network. The TLD test
#: needs no page at all, and 6,484 stored rows had never been judged --
#: the ranker only excludes a lab it KNOWS is foreign, so an unjudged
#: one passes, which is the Cheng Lab failure waiting to happen again.
TLD_ONLY = False


def judge(g: dict) -> dict:
    url = g["url"]
    #: a foreign domain needs no fetch
    ok, why = check(url, "", g.get("institution", ""))
    if not ok:
        return {**g, "us_affiliated": False, "not_us_because": why}
    if TLD_ONLY:
        #: Not judged, not cleared. Saying True here on the strength of
        #: a .com would be the original bug: cheng-lab.com looks
        #: American and is in Hangzhou.
        return {}
    html = get(url)
    ok, why = check(url, html, g.get("institution", ""))
    return {**g, "us_affiliated": bool(ok),
            **({"not_us_because": why} if not ok else {})}


def main() -> int:
    global TLD_ONLY
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--tld-only", action="store_true",
                    help="judge on the domain alone, no fetches. Marks the "
                         "clearly foreign and leaves everything else "
                         "unjudged.")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--restart", action="store_true",
                    help="ignore the resume file and re-read every page")
    a = ap.parse_args()
    TLD_ONLY = a.tld_only

    resume = crawl_resume.Resume("us_affiliation", why=(
        "Rosters flag_non_us_labs.py has read a page for. The domain test "
        "needs no page and is cheap to repeat, so only the full check is "
        "recorded here."))
    if a.restart:
        resume.reset()

    doc = lab_store.load()
    pool = [g for g in doc["groups"] if g.get("status") == "roster"]
    if a.tld_only:
        todo = pool
    else:
        todo = [g for g in pool
                if g.get("us_affiliated") is None
                and g["url"] not in resume.done]
    if a.limit:
        todo = todo[: a.limit]
    print(f"Checking {len(todo)} rosters for a US affiliation"
          + (" (domain only, no fetches)" if a.tld_only else "")
          + f"; {len(pool)} rosters stored")

    BATCH = 1 if a.tld_only else 200
    pending_rows: list = []
    pending_tried: list = []
    flagged = 0

    def flush() -> None:
        nonlocal pending_rows, pending_tried
        if pending_rows:
            lab_store.merge(pending_rows, source="us-affiliation")
        if not TLD_ONLY:
            resume.mark_many(pending_tried)
        pending_rows, pending_tried = [], []

    try:
        if a.tld_only:
            for g in todo:
                r = judge(g)
                if r:
                    pending_rows.append(r)
                    flagged += 1
                    print(f"  NOT US  {g['url'][:52]}")
                    print(f"          {r.get('not_us_because', '')[:68]}")
            flush()
        else:
            with ThreadPoolExecutor(max_workers=a.workers) as ex:
                for i, (g, r) in enumerate(zip(todo, ex.map(judge, todo)), 1):
                    pending_tried.append(g["url"])
                    if r:
                        pending_rows.append(r)
                        if not r.get("us_affiliated"):
                            flagged += 1
                            print(f"  NOT US  {g['url'][:52]}")
                            print(f"          "
                                  f"{r.get('not_us_because', '')[:68]}")
                    if len(pending_tried) >= BATCH:
                        flush()
                        print(f"  ... {i}/{len(todo)}", flush=True)
                    time.sleep(0.005)
    except KeyboardInterrupt:
        print("\n  interrupted; storing what is in hand", flush=True)
    finally:
        flush()
        doc = lab_store.load()
        n = sum(1 for g in doc["groups"] if g.get("us_affiliated") is False)
        unjudged = sum(1 for g in doc["groups"]
                       if g.get("status") == "roster"
                       and g.get("us_affiliated") is None)
        lab_store.merge([], source="us-affiliation",
                        meta={"non_us_rosters": n})
        print(f"\n  {flagged} flagged this run; {n} rosters are not at a "
              f"US university; {unjudged} rosters still unjudged")
    return 0


if __name__ == "__main__":
    sys.exit(main())
