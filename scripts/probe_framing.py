#!/usr/bin/env python3
"""Record which roster pages can be shown inside the page.

WHY MEASURE IT AHEAD OF TIME. A browser gives almost no usable signal
when a frame is refused: the load event fires either way in some
browsers and not at all in others, so a viewer that waits to find out
shows a blank rectangle and then guesses. The servers say so plainly in
a header, and there are only a few dozen pages, so the honest thing is
to ask them once at build time and route each link to where it will
actually work.

Most of them refuse. Of 31 roster pages, 9 allow framing and 22 send
X-Frame-Options or a frame-ancestors policy. A "view in page" control
that ignored this would be broken on seven links in ten.

Usage:
  python3 scripts/probe_framing.py
"""
from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from atomic_write import write_text                            # noqa: E402

ROSTERS = ROOT / "data" / "labs" / "resolved_rosters.json"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 Chrome/124.0 Safari/537.36"}


def frameable(url: str) -> tuple[bool, str]:
    """(can be framed, why not)."""
    try:
        r = requests.get(url, headers=UA, timeout=20, allow_redirects=True,
                         stream=True)
        h = {k.lower(): v for k, v in r.headers.items()}
        r.close()
    except requests.RequestException as e:
        #: Unreachable from here is not the same as refusing to be
        #: framed, but either way the in-page view cannot be trusted.
        return False, f"unreachable ({type(e).__name__})"
    xfo = h.get("x-frame-options", "").strip()
    if xfo:
        return False, f"X-Frame-Options: {xfo}"
    csp = h.get("content-security-policy", "")
    if "frame-ancestors" in csp:
        fa = csp.split("frame-ancestors", 1)[1].split(";")[0].strip()
        if "*" not in fa:
            return False, f"frame-ancestors {fa[:40]}"
    return True, ""


def archived(url: str) -> tuple[str, str]:
    """(wayback url, yyyymmdd) for the closest snapshot, or ("", "").

    THE ARCHIVE CAN BE FRAMED AND THE ORIGINAL USUALLY CANNOT. Purdue
    sends X-Frame-Options: DENY; Caltech, Stanford and UCR send
    SAMEORIGIN. web.archive.org sends neither, so a snapshot shows
    inside the page where the live roster will not.

    It is also the better thing to show. A snapshot is the page as it
    stood on a date, which is what this site wants to point at -- the
    live page can change between a reader following a link and anyone
    checking it.
    """
    try:
        r = requests.get("https://archive.org/wayback/available",
                         params={"url": url}, headers=UA, timeout=25)
        snap = (r.json().get("archived_snapshots") or {}).get("closest") or {}
    except (requests.RequestException, ValueError):
        return "", ""
    if not snap.get("available") or not snap.get("url"):
        return "", ""
    #: force https, and id_ gives the page without the archive's own
    #: toolbar, which otherwise eats sixty pixels of a small frame
    u = snap["url"].replace("http://", "https://", 1)
    return u, (snap.get("timestamp") or "")[:8]


def main() -> int:
    doc = json.loads(ROSTERS.read_text())
    rows = doc.get("rows", [])
    urls = sorted({r["url"] for r in rows if r.get("status") == "ok"})
    print(f"Asking {len(urls)} roster pages whether they can be framed")

    with ThreadPoolExecutor(max_workers=8) as ex:
        results = dict(zip(urls, ex.map(frameable, urls)))

    ok = [u for u, (f, _) in results.items() if f]
    for u, (f, why) in sorted(results.items()):
        print(f"  {'IN PAGE ' if f else 'new tab '} {why[:34]:36} {u[:48]}")
    print(f"\n  {len(ok)} of {len(urls)} can be shown in the page")

    #: For anything that refuses, ask the archive. One request each,
    #: paced, because the availability API rate-limits.
    import time
    need = [u for u, (f, _) in results.items() if not f]
    print(f"\n  looking for snapshots of {len(need)} refused pages")
    arch: dict = {}
    for u in need:
        a, ts = archived(u)
        if a:
            arch[u] = (a, ts)
        time.sleep(0.5)
    print(f"  {len(arch)} of {len(need)} have one")

    for r in rows:
        u = r.get("url")
        f, why = results.get(u, (False, "not probed"))
        r["frameable"] = f
        if not f:
            r["frame_refused"] = why
            a = arch.get(u)
            if a:
                r["archive_url"], r["archive_date"] = a
    doc["rows"] = rows
    doc["frameable_count"] = len(ok)
    doc["archive_fallback_count"] = sum(
        1 for r in rows if r.get("archive_url"))
    doc["frame_probed"] = len(urls)
    write_text(ROSTERS, json.dumps(doc, indent=2))
    print(f"  wrote {ROSTERS.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
