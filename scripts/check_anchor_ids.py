#!/usr/bin/env python3
"""Verify every section on every page is addressable from the URL bar.

The site already has the machinery for this: add_section_anchors.py bakes
descriptive ids into the hand-written pages, generate_name_lists_html.py
bakes its own into the generated ones, and anchors.js assigns the rest at
load time from heading text. What nothing checked is whether the result
actually holds on every page.

Three ways a section stops being addressable, none of which are visible by
looking at the page:

  no id          nothing to put after the '#'
  duplicate id   the browser resolves the FIRST match, so the second block
                 is unreachable and the first one hijacks its link
  opaque id      'section-3' or 'div_17' is technically addressable but no
                 reader would ever guess or trust it, and it moves whenever
                 the page is reordered

Checked in a real browser, after anchors.js has run: a static grep would
report every runtime-assigned id as missing.

Usage:
  python3 scripts/check_anchor_ids.py           # site/ over a local server
  python3 scripts/check_anchor_ids.py --live    # the deployed site
  python3 scripts/check_anchor_ids.py --verbose # list every id found
"""
from __future__ import annotations

import argparse
import functools
import http.server
import re
import socketserver
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
LIVE = "https://phd-demographics.andy-barr.com"

# Pages that are not part of the reader-facing site.
SKIP = {"chat-admin.html", "analytics.html", "webmcp.html", "quality.html"}

# Pages add_section_anchors.py deliberately does not rewrite, because they are
# produced by some other generator. Their headings genuinely have no ids, but
# that is a decision rather than a defect, so they are reported and not failed.
# Read from the baker itself so the two lists cannot drift apart.
def _excluded() -> set[str]:
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        from add_section_anchors import SKIP as baked
        return set(baked)
    except Exception:
        return set()

# An id a reader could not guess, or that moves when the page is reordered.
OPAQUE = re.compile(r"^(?:section|panel|block|div|item|chart|tab|el)[-_]?\d+$|^[a-z]?\d+$", re.I)

_results: list[tuple[bool, str, str]] = []


def check(ok: bool, name: str, detail: str = "") -> bool:
    _results.append((bool(ok), name, detail))
    return bool(ok)


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):  # silence the request log
        pass

    def handle_one_request(self):
        # The browser abandons requests it no longer needs (a navigation
        # supersedes an in-flight fetch), which surfaces here as a broken
        # pipe and a traceback that looks like a failure but is not one.
        try:
            super().handle_one_request()
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True


class _Threaded(socketserver.ThreadingTCPServer):
    """Serve concurrently.

    A single-threaded server serialises requests, and the browser opens
    several at once for a 1 MB page and its JSON. The later ones queue behind
    the first until the navigation times out, which reads as a broken page
    rather than a slow test harness.
    """
    daemon_threads = True
    allow_reuse_address = True


def serve(directory: Path):
    handler = functools.partial(_Quiet, directory=str(directory))
    httpd = _Threaded(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}"


# Collected after anchors.js has run. Headings inside the sidebar, nav and
# footer are chrome, not content, and are not meant to be linkable.
PROBE = """() => {
  const CHROME = 'nav, aside, footer, .sidebar, #sidebar, .sb-group, .coach-overlay';
  const inChrome = el => !!el.closest(CHROME);
  const heads = [...document.querySelectorAll('h1, h2, h3')].filter(h =>
      !inChrome(h) && h.offsetParent !== null && h.textContent.trim());

  // The id that addresses a heading is its own, or the enclosing block's
  // when the block carries one -- that is what add_section_anchors.py does
  // so that :target frames the whole card rather than the text alone.
  const idFor = h => {
    if (h.id) return h.id;
    const holder = h.closest('[id]');
    return holder ? holder.id : '';
  };

  const all = [...document.querySelectorAll('[id]')].map(e => e.id);
  const dupes = [...new Set(all.filter((id, i) => all.indexOf(id) !== i))];

  return {
    headings: heads.map(h => ({
      text: h.textContent.trim().slice(0, 60),
      tag: h.tagName,
      id: idFor(h),
    })),
    duplicates: dupes,
    total: all.length,
  };
}"""


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--pages", nargs="*", help="limit to these page names")
    args = ap.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright is required: pip install playwright && playwright install chromium")
        return 2

    # A redirect stub has no sections of its own, and following it here lands
    # on the local static server's 404 -- it cannot serve /presentation without
    # the .html the way CloudFront does, so the check read an H1 of "Error
    # response" and failed a page that is fine in production.
    def is_redirect(path):
        head = path.read_text(encoding="utf-8", errors="replace")[:1500]
        return 'http-equiv="refresh"' in head.lower()

    pages = sorted(p.name for p in SITE.glob("*.html")
                   if p.name not in SKIP and not is_redirect(p))
    if args.pages:
        pages = [p for p in pages if p in set(args.pages)]

    httpd = None
    base = LIVE if args.live else None
    if not args.live:
        httpd, base = serve(SITE)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            ctx = browser.new_context(viewport={"width": 1500, "height": 1000})
            page = ctx.new_page()
            for name in pages:
                _audit(page, base, name, args.verbose)
            ctx.close()
            browser.close()
    finally:
        if httpd:
            httpd.shutdown()

    failed = [r for r in _results if not r[0]]
    print()
    for ok, nm, detail in _results:
        if ok and not args.verbose:
            continue
        print(f"  [{'ok  ' if ok else 'FAIL'}] {nm}" + (f"  — {detail}" if detail else ""))
    print()
    if failed:
        print(f"  {len(failed)} of {len(_results)} checks FAILED")
        return 1
    print(f"  all {len(_results)} anchor-id checks passed across {len(pages)} pages")
    return 0


def _audit(page, base: str, name: str, verbose: bool) -> None:
    url = f"{base}/{name}"
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.evaluate("localStorage.setItem('coach_done_v3','1')")
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(1500)
        data = page.evaluate(PROBE)
    except Exception as e:
        check(False, f"{name}: loads", str(e)[:90])
        return

    heads = data["headings"]
    if not heads:
        check(True, f"{name}: no linkable sections", "nothing to address")
        return

    unnamed = [h for h in heads if not h["id"]]
    if unnamed and name in _excluded():
        check(True, f"{name}: not anchored (generated elsewhere)",
              f"{len(unnamed)} of {len(heads)} sections; excluded by "
              f"add_section_anchors.py")
        unnamed = []
    check(not unnamed, f"{name}: every section has an id",
          f"{len(heads)} sections" if not unnamed else
          "; ".join(f"{h['tag']} {h['text']!r}" for h in unnamed[:4]))

    opaque = [h for h in heads if h["id"] and OPAQUE.match(h["id"])]
    check(not opaque, f"{name}: ids are descriptive",
          "" if not opaque else
          "; ".join(f"{h['id']} ({h['text']!r})" for h in opaque[:4]))

    check(not data["duplicates"], f"{name}: ids are unique",
          f"{data['total']} ids" if not data["duplicates"] else
          f"repeated, so only the first is reachable: "
          f"{', '.join(data['duplicates'][:5])}")

    if verbose:
        for h in heads:
            print(f"      {name}#{h['id']}  {h['tag']}  {h['text']!r}")


if __name__ == "__main__":
    sys.exit(main())
