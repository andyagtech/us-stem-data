#!/usr/bin/env python3
"""What a crawler has already tried, so a restart is cheap and honest.

THE SHAPE OF THE BUG THIS REMOVES. Every crawler here recorded its
work by what it FOUND. follow_lab_links skipped a profile only if that
profile had produced a group site; discover_research_labs had no record
at all, and the only trace of a visited department was `found_from` on
the rows it produced. So the two outcomes that matter most were
indistinguishable from never having looked:

  a department that yielded nothing
  a page that was tried and failed

The first is re-walked for ever -- forty fetches against a
university's own servers every run. The second never gets a second
chance that anyone can see.

MARK AFTER STORING, NEVER BEFORE. A resume file that runs ahead of the
data is worse than none: the rows are gone and nothing will ever look
there again. Every caller here stores its results first and marks
second, so a crash costs one batch and a kill costs nothing that was
already written.

A resume file is a cache of effort, not a finding. Deleting one costs
time and loses no data, which is why --restart is safe to offer.

Usage:
    r = crawl_resume.Resume("discover")
    todo = [u for u in candidates if u not in r.done]
    ...
    r.mark_many(batch)
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "data" / "labs"


class Resume:
    """A set of addresses already attempted, on disk, written atomically."""

    def __init__(self, name: str, why: str = "") -> None:
        self.name = name
        self.path = DIR / f".{name}_done.json"
        self.why = why or (
            f"Addresses {name} has already attempted, successfully or not. "
            "Delete this file, or pass --restart, to try them all again.")
        self.done: set = set()
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            doc = json.loads(self.path.read_text())
        except (OSError, ValueError):
            #: A truncated resume file must not stop a crawl. The cost of
            #: ignoring it is repeated work; the cost of trusting half of
            #: it is a permanent gap.
            return
        for key in ("tried", "departments", "urls"):
            if isinstance(doc.get(key), list):
                self.done |= {u for u in doc[key] if isinstance(u, str)}

    def seed(self, urls) -> int:
        """Pre-fill from evidence, when a run predates the resume file.

        Only addresses that can be PROVEN attempted belong here -- a row
        naming the page it came from, for instance. Anything unprovable
        is left out and tried once more, because an unprovable skip is
        how a gap becomes permanent.
        """
        if self.path.exists():
            return 0
        before = len(self.done)
        self.done |= {u for u in urls if isinstance(u, str) and u}
        if len(self.done) != before:
            self._write()
        return len(self.done) - before

    def mark(self, url: str) -> None:
        self.mark_many([url])

    def mark_many(self, urls) -> None:
        new = {u for u in urls if isinstance(u, str) and u} - self.done
        if not new:
            return
        self.done |= new
        self._write()

    def reset(self) -> None:
        self.done = set()
        if self.path.exists():
            self.path.unlink()

    def _write(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"why": self.why, "count": len(self.done),
                              "tried": sorted(self.done)}, indent=2)
        fd, tmp = tempfile.mkstemp(dir=str(self.path.parent), suffix=".tmp")
        with os.fdopen(fd, "w") as fh:
            fh.write(payload + "\n")
        os.replace(tmp, self.path)

    def __len__(self) -> int:
        return len(self.done)

    def __contains__(self, url: str) -> bool:
        return url in self.done
