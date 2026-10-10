#!/usr/bin/env python3
"""Re-check every URL stored in program_urls.json and strip the dead ones.

WHY THIS IS SEPARATE FROM THE RESOLVER. The resolver checks a URL once, at
the moment it finds it, and then the answer is frozen in the JSON. University
sites move constantly. uwyo.edu/petroleum/people/faculty returned a page when
it was resolved and returns "404 - PAGE NOT FOUND" now.

AND A 200 IS NOT PROOF. Several universities serve their not-found page with
status 200, so the status line alone would have kept that Wyoming link. This
checks the body for not-found wording as well, and only then believes it.

A dead URL is cleared rather than left in place, because a link that 404s in
front of a reader is worse than an honest "not resolved".

Usage:
  python3 scripts/verify_program_urls.py            # report only
  python3 scripts/verify_program_urls.py --write    # clear the dead ones
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from atomic_write import write_text                            # noqa: E402

OUT = ROOT / "data" / "labs" / "program_urls.json"
FIELDS = ("url", "students_url", "faculty_url", "directory_url")

#: Wording that means not-found even when the status line says 200.
SOFT_404 = re.compile(
    r"(404\s*[-–]?\s*page not found|page not found|"
    r"page you (are looking for|requested) (has moved|cannot be found)|"
    r"no longer exists|this page (is )?(unavailable|does not exist)|"
    r"we can.t find (that|the) page)", re.I)

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0 Safari/537.36"}


def check(url: str) -> tuple[str, bool, str]:
    """(url, alive, why). A timeout is NOT a death sentence -- a slow or
    WAF-guarded page is still a real page, and clearing it would lose a
    good link to a transient failure."""
    try:
        r = requests.get(url, headers=UA, timeout=20, allow_redirects=True)
    except requests.RequestException as e:
        return url, True, f"unreachable, kept ({type(e).__name__})"
    if r.status_code == 404:
        return url, False, "404"
    #: 403 and 429 are a firewall refusing a robot, not a missing page.
    #: ece.ucdavis.edu serves 403 to this script and a real department
    #: page to a browser. Clearing it would delete a good link because a
    #: WAF did not like us.
    if r.status_code in (401, 403, 406, 429) or r.status_code >= 500:
        return url, True, f"blocked or erroring ({r.status_code}), kept"
    if r.status_code != 200:
        return url, False, f"status {r.status_code}"
    body = re.sub(r"<[^>]+>", " ", r.text[:60000])
    if SOFT_404.search(body):
        return url, False, "soft 404 (200 with a not-found page)"
    return url, True, "ok"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()

    doc = json.loads(OUT.read_text())
    rows = doc["rows"]
    urls = sorted({r[f] for r in rows for f in FIELDS if r.get(f)})
    print(f"Checking {len(urls)} stored URLs")

    with ThreadPoolExecutor(max_workers=12) as ex:
        results = dict((u, (alive, why)) for u, alive, why in ex.map(check, urls))

    dead = {u: why for u, (alive, why) in results.items() if not alive}
    for u, why in sorted(dead.items()):
        print(f"  DEAD  {why:<42} {u}")
    print(f"\n  {len(urls) - len(dead)} alive, {len(dead)} dead")

    if not a.write:
        print("  (report only; pass --write to clear the dead ones)")
        return 0

    cleared = 0
    for r in rows:
        for f in FIELDS:
            if r.get(f) and r[f] in dead:
                r[f] = None
                cleared += 1
        #: A row whose main URL DIED is no longer resolved. A row that
        #: never had one is still merely unresolved -- marking those
        #: "dead_link" too relabelled 97 rows that had never been
        #: reached as if their pages had been taken down.
        if r.get("status") == "ok" and not r.get("url"):
            r["status"] = "dead_link"
    doc["rows"] = rows
    doc["verified_links"] = {"checked": len(urls), "dead": len(dead)}
    write_text(OUT, json.dumps(doc, indent=1))
    print(f"  cleared {cleared} dead links, wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
