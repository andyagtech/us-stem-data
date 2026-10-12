#!/usr/bin/env python3
"""The one writer to discovered_labs.json.

WHY. Four scripts add rosters to this file, each by reading it,
changing it and writing it back. Run two at once and the second
overwrites what the first added: a crawl of 399 rosters was lost
exactly that way, and its own summary printed a count that had
already been clobbered.

Every write now goes through merge(), which holds an exclusive lock
across the whole read-modify-write and replaces the file atomically.
Concurrent crawlers queue instead of racing.
"""
from __future__ import annotations

import fcntl
import json
import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LABS = ROOT / "data" / "labs" / "discovered_labs.json"
LOCK = ROOT / "data" / "labs" / ".discovered_labs.lock"


def merge(rows: list[dict], *, source: str = "") -> dict:
    """Add or improve rows. Returns a summary of what changed.

    A row already carrying a composition is never replaced by one
    without -- retrieved data is append-only, and a later crawl that
    failed to parse a page must not erase the read that worked.
    """
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    with open(LOCK, "w") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            doc = json.loads(LABS.read_text()) if LABS.exists() else {
                "why": "Research groups found by crawling departments.",
                "groups": [],
            }
            by = {g["url"]: g for g in doc.get("groups", [])}
            added = improved = 0
            for r in rows:
                url = r.get("url")
                if not url:
                    continue
                cur = by.get(url)
                if cur is None:
                    by[url] = dict(r)
                    added += 1
                    continue
                has = bool((cur.get("composition") or {}).get("dominance"))
                brings = bool((r.get("composition") or {}).get("dominance"))
                if brings and not has:
                    cur.update(r)
                    improved += 1
                elif not has and not brings:
                    #: fill empty fields without dropping any
                    for k, v in r.items():
                        cur.setdefault(k, v)
            doc["groups"] = sorted(by.values(), key=lambda g: g["url"])
            doc["candidate_urls"] = len(doc["groups"])
            doc["groups_found"] = sum(
                1 for g in doc["groups"] if g.get("status") == "roster")

            #: atomic replace, so a reader never sees half a file
            fd, tmp = tempfile.mkstemp(dir=str(LABS.parent), suffix=".tmp")
            with os.fdopen(fd, "w") as fh:
                json.dump(doc, fh, indent=2)
                fh.write("\n")
            os.replace(tmp, LABS)
            return {"added": added, "improved": improved,
                    "rosters": doc["groups_found"],
                    "total": len(doc["groups"]), "source": source}
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)


def load() -> dict:
    return json.loads(LABS.read_text())
