#!/usr/bin/env python3
"""A local cache of the names read off each roster page.

WHY. A composition is a set of totals, and the names behind it are
deliberately not published. That is right for the site and wrong for
the workbench: every change to the classifier meant re-fetching 140
pages over several minutes, so each adjustment cost a crawl, and
adjustments are the point.

The cache sits OUTSIDE the published data and is not committed. It
holds what the extractor read, so re-scoring a classifier change is
a pass over local files -- about a second -- and the published
figures still carry totals only.

A page is re-fetched when it is not cached, or with --refresh.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / ".cache" / "lab_names"


def _key(url: str) -> Path:
    h = hashlib.sha256(url.encode()).hexdigest()[:20]
    return CACHE / f"{h}.json"


def get(url: str) -> list[str] | None:
    """The names last read from this page, or None."""
    f = _key(url)
    if not f.exists():
        return None
    try:
        return json.loads(f.read_text())["names"]
    except Exception:                                         # noqa: BLE001
        return None


def put(url: str, names: list[str]) -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    _key(url).write_text(json.dumps({"url": url, "names": names}))


def urls() -> list[str]:
    """Every cached page."""
    if not CACHE.exists():
        return []
    out = []
    for f in CACHE.glob("*.json"):
        try:
            out.append(json.loads(f.read_text())["url"])
        except Exception:                                     # noqa: BLE001
            continue
    return out


def count() -> int:
    return len(list(CACHE.glob("*.json"))) if CACHE.exists() else 0
