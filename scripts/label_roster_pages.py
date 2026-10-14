#!/usr/bin/env python3
"""Does each stored roster page read like a TEAM or like a BIBLIOGRAPHY?

THE DISTINCTION THE AUTHOR NAMED, and it is the right one. A research
TEAM is a hiring decision: someone chose those people and pays them. A
CO-AUTHOR LIST is a record of who published together, and it carries
collaborators at other institutions, students who left a decade ago,
and the authors of any paper the page happens to host.

Reduced to a list of names the two are identical, and nothing
downstream can tell them apart. THE PAGE can be told apart, because a
roster labels its people and a bibliography labels its venues.

Seven of the 100 published labs were publication lists. The extraction
gave them away -- paper titles counted as members:

  eecis.udel.edu/~ruizhang    "IEEE CNS", "Rhythmic RFID
                              Authentication"            14 of 21
  cs.princeton.edu/~zhuangl   "Dropout Reduces Underfitting",
                              "Oral Presentation"        15 of 24
  pages.mtu.edu/~shene/NSF-2  "Graphics Gems IV", "The Computer
                              Journal"                   11 of 27
  cs.princeton.edu/~funk      Funkhouser's former students, now
                              faculty elsewhere          10 of 23
  cs.princeton.edu/~ravian    "Pensieve Website"          9 of 17

and graphics.stanford.edu/~maneesh was carrying 438 "members".

This records two numbers per page so the ranker can act on them. It
stores nothing about any person.

CITATION NETWORKS ARE WORTH HAVING and are not this. They answer who
works with whom, which is a different question from who is on the
payroll, and they belong in their own dataset.

Usage:
  python3 scripts/label_roster_pages.py            # resumes
  python3 scripts/label_roster_pages.py --restart
"""
from __future__ import annotations

import argparse
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import crawl_resume                                           # noqa: E402
import lab_store                                              # noqa: E402
from follow_lab_links import get                              # noqa: E402
from harvest_lab_rosters import page_signals                  # noqa: E402


def label(g: dict) -> dict:
    html = get(g["url"])
    if not html:
        #: Not judged, not cleared. A page that will not answer keeps
        #: whatever it had; saying "0 venue markers" because the fetch
        #: failed would clear it wrongly.
        return {}
    return {"url": g["url"], **page_signals(html)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--restart", action="store_true")
    a = ap.parse_args()

    resume = crawl_resume.Resume("roster_signals", why=(
        "Roster pages label_roster_pages.py has read. Re-reading is "
        "cheap to repeat when the role or venue vocabulary changes, so "
        "--restart clears this."))
    if a.restart:
        resume.reset()

    #: SELECTED BY THE DATA, NOT BY THE RESUME FILE. A row that carries
    #: role_markers has been read; one that does not has not, whatever
    #: any resume file says. That matters because a concurrent pass
    #: discarded 1,400 merged labels while this file said those pages
    #: were done -- a resume file running ahead of the data again, and
    #: the data is the one record that cannot drift from itself.
    #:
    #: The resume file now records only the pages that FAILED to fetch,
    #: so a permanently dead address is not refetched every run while a
    #: successful read is never skipped on the strength of a stale note.
    doc = lab_store.load()
    pool = [g for g in doc["groups"] if g.get("status") == "roster"]
    todo = [g for g in pool
            if "role_markers" not in g and g["url"] not in resume.done]
    if a.limit:
        todo = todo[: a.limit]
    print(f"Reading {len(todo)} roster pages for role and venue words "
          f"({len(pool)} rosters stored)")

    BATCH = 100
    rows: list = []
    failed: list = []
    bib = 0

    def flush() -> None:
        nonlocal rows, failed
        if rows:
            s = lab_store.merge(rows, source="roster-signals")
            print(f"   stored: {s['total']} rows", flush=True)
        resume.mark_many(failed)
        rows, failed = [], []

    try:
        with ThreadPoolExecutor(max_workers=a.workers) as ex:
            for i, (g, r) in enumerate(zip(todo, ex.map(label, todo)), 1):
                if not r:
                    failed.append(g["url"])
                else:
                    rows.append(r)
                    if r["venue_markers"] > r["role_markers"]:
                        bib += 1
                        print(f"  venues {r['venue_markers']:>3} vs roles "
                              f"{r['role_markers']:<3} {g['url'][:52]}",
                              flush=True)
                if len(rows) + len(failed) >= BATCH:
                    flush()
                    print(f"  ... {i}/{len(todo)}, {bib} read like a "
                          f"bibliography", flush=True)
                time.sleep(0.01)
    except KeyboardInterrupt:
        print("\n  interrupted; storing what is in hand", flush=True)
    finally:
        flush()
        print(f"\n  {bib} of {len(todo)} pages name more venues than roles")
        left = sum(1 for g in lab_store.load()["groups"]
                   if g.get("status") == "roster"
                   and "role_markers" not in g)
        print(f"  {left} roster pages still unlabelled; "
              f"{len(resume.done)} would not answer")
    return 0


if __name__ == "__main__":
    sys.exit(main())
