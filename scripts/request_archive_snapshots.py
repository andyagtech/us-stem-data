#!/usr/bin/env python3
"""Ask the Internet Archive to capture the pages it has not got.

WHY. The in-page viewer shows a university roster by framing either the
live page or the Archive's copy of it, because most university sites
send X-Frame-Options and refuse to be framed. Where neither works the
link just opens a new tab, which is the thing the viewer exists to
avoid. Save Page Now closes that gap: ask once, wait, and the page is
both viewable and -- more to the point -- fixed on a date.

SLOW AND POLITE. Save Page Now is a free service doing real work on
request. One page at a time, a pause between, and a single retry. If
it declines, that is a fine answer and the link keeps its new tab.

Usage:
  python3 scripts/request_archive_snapshots.py
  python3 scripts/request_archive_snapshots.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from atomic_write import write_text                            # noqa: E402

ROSTERS = ROOT / "data" / "labs" / "resolved_rosters.json"
UA = {"User-Agent": "phd-demographics research; archiving public roster pages"}


def save_now(url: str, timeout: int = 90) -> bool:
    """Ask for a capture. True if the request was accepted."""
    try:
        r = requests.get(f"https://web.archive.org/save/{url}",
                         headers=UA, timeout=timeout, allow_redirects=True)
        return r.status_code in (200, 302)
    except requests.RequestException:
        return False


def available(url: str) -> tuple[str, str]:
    try:
        r = requests.get("https://archive.org/wayback/available",
                         params={"url": url}, headers=UA, timeout=25)
        s = (r.json().get("archived_snapshots") or {}).get("closest") or {}
    except (requests.RequestException, ValueError):
        return "", ""
    if not s.get("available") or not s.get("url"):
        return "", ""
    return s["url"].replace("http://", "https://", 1), (s.get("timestamp") or "")[:8]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    doc = json.loads(ROSTERS.read_text())
    rows = doc.get("rows", [])
    need = sorted({r["url"] for r in rows if r.get("status") == "ok"
                   and not r.get("frameable") and not r.get("archive_url")})
    print(f"{len(need)} page(s) with neither live framing nor a snapshot")
    for u in need:
        print(f"  {u}")
    if a.dry_run or not need:
        return 0

    got = {}
    for u in need:
        print(f"\n  requesting {u[:60]}")
        ok = save_now(u)
        print(f"    accepted: {ok}")
        #: A capture is not instant. Wait, then ask the availability
        #: API rather than assuming it worked.
        for wait in (20, 40, 60):
            time.sleep(wait)
            url, ts = available(u)
            if url:
                got[u] = (url, ts)
                print(f"    captured {ts}")
                break
            print(f"    not there yet after {wait}s")
        else:
            print("    no snapshot; the link keeps its new tab")

    n = 0
    for r in rows:
        g = got.get(r.get("url"))
        if g:
            r["archive_url"], r["archive_date"] = g
            r["archive_requested"] = True
            n += 1
    doc["rows"] = rows
    doc["archive_fallback_count"] = sum(1 for r in rows if r.get("archive_url"))
    write_text(ROSTERS, json.dumps(doc, indent=2))
    print(f"\n  {n} newly captured; "
          f"{doc['archive_fallback_count']} rows now have a snapshot")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
