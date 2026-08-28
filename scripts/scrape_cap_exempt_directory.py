#!/usr/bin/env python3
"""Harvest a third-party cap-exempt employer directory.

USCIS records cap status on the I-129 and does not publish it, so every
public "cap-exempt employer list" is somebody's inference -- usually from
employer type or industry code. This directory claims 2,396 employers, which
is a far better candidate list than NAICS 61 alone: that code sweeps in
school districts and for-profit colleges and misses affiliated nonprofits
filing under other codes.

USE IT AS A SELECTION, NOT AS A SOURCE. The names are worth having; the cap
status attached to them is not authoritative and is not stored as though it
were. Anything published from this should carry USCIS figures, with the
directory credited only for choosing which employers to look at.

robots.txt was checked: Allow: / with a single exclusion for a favicon.
Fetches are rate-limited and cached.

Usage:
  python3 scripts/scrape_cap_exempt_directory.py
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "cap_exempt" / "pages"
OUT = ROOT / "data" / "cap_exempt" / "directory.json"
BASE = "https://www.ellis.com/visa-sponsors/cap-exempt"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120 Safari/537.36")
DELAY = 0.6
MAX_PAGES = 120

# The anchor wraps a whole card -- city, headcount, logo, filing counts -- so
# taking its text as the employer name produced entries like "ABERDEEN, SD NS
# Northern State University H-1B Filings 1 PERM...". The slug is the clean
# identifier; the card is mined separately for the fields worth having.
# Not anchored on </a>: the card's closing tag sits well beyond any sane
# window, so a fixed look-ahead is used and the fields are picked out of it.
ROW = re.compile(r'href="/visa-sponsors/([a-z0-9\-]{3,})"(.{0,400})', re.S)
CITY = re.compile(r"^([A-Z][A-Za-z .'\-]{2,40}),\s*([A-Z]{2})$")
SIZE = re.compile(r"^([\d.]+K?|\d{1,3}(?:,\d{3})*)$")


def card_fields(inner: str) -> dict:
    """City, state and headcount out of one directory card."""
    parts = [x.strip() for x in re.sub(r"<[^>]+>", "|", inner).split("|")]
    parts = [x for x in parts if x]
    out: dict = {}
    for i, x in enumerate(parts):
        m = CITY.match(x)
        if m and "city" not in out:
            out["city"], out["state"] = m.group(1), m.group(2)
        if x == "employees" and i and SIZE.match(parts[i - 1]):
            out["employees_label"] = parts[i - 1]
    return out


def name_from_slug(slug: str) -> str:
    """Title-case the slug, keeping the initialisms readable."""
    SMALL = {"of", "the", "and", "at", "for", "in", "on"}
    UPPER = {"usa", "us", "uc", "suny", "cuny", "mit", "nyu", "ucla", "ut", "va"}
    words = slug.split("-")
    out = []
    for i, w in enumerate(words):
        if w in UPPER:
            out.append(w.upper())
        elif w in SMALL and i:
            out.append(w)
        else:
            out.append(w.capitalize())
    return " ".join(out)


def fetch(page: int) -> str | None:
    dest = CACHE / f"page_{page:03d}.html"
    if dest.exists() and dest.stat().st_size > 5000:
        return dest.read_text(errors="replace")
    CACHE.mkdir(parents=True, exist_ok=True)
    url = BASE if page == 1 else f"{BASE}?page={page}"
    r = subprocess.run(["curl", "-sL", "--max-time", "45", "-A", UA,
                        "-o", str(dest), url], capture_output=True)
    if r.returncode != 0 or not dest.exists() or dest.stat().st_size < 5000:
        dest.unlink(missing_ok=True)
        return None
    time.sleep(DELAY)
    return dest.read_text(errors="replace")


def parse(html: str) -> list[dict]:
    out, seen = [], set()
    for slug, inner in ROW.findall(html):
        if slug == "cap-exempt" or slug in seen:
            continue
        seen.add(slug)
        rec = {"slug": slug, "name": name_from_slug(slug),
               "url": f"https://www.ellis.com/visa-sponsors/{slug}"}
        rec.update(card_fields(inner))
        out.append(rec)
    return out


def main() -> int:
    employers: dict[str, dict] = {}
    empty_runs = 0
    for page in range(1, MAX_PAGES + 1):
        html = fetch(page)
        if html is None:
            print(f"  page {page}: fetch failed")
            break
        rows = parse(html)
        new = [r for r in rows if r["slug"] not in employers]
        for r in rows:
            employers.setdefault(r["slug"], r)
        if not new:
            empty_runs += 1
            if empty_runs >= 3:
                print(f"  no new employers for 3 pages; stopping at {page}")
                break
        else:
            empty_runs = 0
        if page % 20 == 0:
            print(f"    page {page}: {len(employers):,} employers so far")

    claimed = None
    first = (CACHE / "page_001.html")
    if first.exists():
        m = re.search(r"([\d,]{3,8})\s*\+?\s*(?:verified\s*)?cap",
                      first.read_text(errors="replace"), re.I)
        claimed = m.group(1) if m else None

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "_comment": ("A third-party directory's list of employers it treats as "
                     "cap-exempt. USCIS does not publish cap status, so this "
                     "is the directory's inference and is NOT authoritative. "
                     "Use it to choose which employers to look up in USCIS "
                     "data; never publish its cap status as a finding."),
        "source": BASE,
        "captured": time.strftime("%Y-%m-%d"),
        "claimed_total": claimed,
        "captured_total": len(employers),
        "employers": sorted(employers.values(), key=lambda e: e["name"]),
    }, indent=1) + "\n")
    print(f"  directory claims {claimed}; captured {len(employers):,}")
    print(f"  wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
