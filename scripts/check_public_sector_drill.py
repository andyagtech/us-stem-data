#!/usr/bin/env python3
"""Does the public-sector page's state drill-down actually work for a reader?

WHY THIS EXISTS SEPARATELY FROM THE UNIT TESTS

tests/test_public_sector_drill.py proves the data: every employer row in the
page resolves to an employer in its state's file, every filing is there once,
and the totals match the figures the page already prints. It cannot prove any
of what a reader does, because all of that is JavaScript:

  a row opens and loads ten filings      the row is a button, the filings are
                                         fetched, and neither happens in Python
  "Show 50" and "Show All" work          251 rows is the case that matters and
                                         the author asked for it by name
  one fetch per state, not per row       230 employers in Florida share one file
  closing and reopening resets to ten    the default is the point of the default
  sorting keeps a detail row with its
  employer                               the shared sorter in states.js moves
                                         rows, and it used to move the rows of
                                         tables NESTED inside them
  the fragment opens the row             this is what stands in for a page per
                                         employer, so it has to work cold

So this drives a real browser over site/ on a local server, the way
check_anchor_ids.py does. It needs no network and no credentials.

Usage:
  python3 scripts/check_public_sector_drill.py
  python3 scripts/check_public_sector_drill.py --live
  python3 scripts/check_public_sector_drill.py --host https://h1b.andy-barr.com
"""
from __future__ import annotations

import argparse
import functools
import http.server
import json
import re
import socketserver
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
PAGE = "public-sector-visas.html"
LIVE = "https://phd-demographics.andy-barr.com"

_results: list[tuple[bool, str, str]] = []


def check(ok: bool, name: str, detail: str = "") -> bool:
    _results.append((bool(ok), name, detail))
    return bool(ok)


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def handle_one_request(self):
        # The browser abandons requests it no longer needs, which arrives here
        # as a broken pipe and a traceback that looks like a failure.
        try:
            super().handle_one_request()
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True


class _Threaded(socketserver.ThreadingTCPServer):
    """Serve concurrently: this page is 1.2 MB and then fetches a JSON."""
    daemon_threads = True
    allow_reuse_address = True


def serve(directory: Path):
    handler = functools.partial(_Quiet, directory=str(directory))
    httpd = _Threaded(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}"


def biggest_employer() -> tuple[str, str, int, str]:
    """The busiest employer in any state the page features, from the built
    files rather than from a name typed in here. 251 filings today; whatever
    it is after the next rebuild, tomorrow."""
    best = None
    for f in sorted((SITE / "data" / "public_sector_filings").glob("*.json")):
        j = json.loads(f.read_text())
        for e in j["employers"]:
            if best is None or e["filings"] > best[2]:
                best = (f.stem, e["name"], e["filings"], j["state"])
    if best is None:
        sys.exit("no state filing files: run scripts/build_public_sector_page.py")
    return best


def row_id(page_html: str, slug: str, name: str) -> str | None:
    """The id the builder gave that employer's row, read off the page."""
    want = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:60].strip("-")
    for rid in re.findall(r'<tr class="emp" id="(emp-[^"]+)"', page_html):
        if rid == f"emp-{slug}--{want}":
            return rid
    return None


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--host")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright is required: pip install playwright && "
              "playwright install chromium")
        return 2

    slug, emp_name, filings, state = biggest_employer()
    rid = row_id((SITE / PAGE).read_text(), slug, emp_name)
    if not check(bool(rid), "the busiest employer has a row id",
                 f"{emp_name} ({state}), {filings:,} filings"):
        return report(args.verbose)

    httpd = None
    base = args.host or (LIVE if args.live else None)
    if base is None:
        httpd, base = serve(SITE)
    url = f"{base}/{PAGE}"
    det = f"#d-{rid}"

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            ctx = browser.new_context(viewport={"width": 1400, "height": 1000})
            pg = ctx.new_page()
            errors, fetches = [], []
            pg.on("pageerror", lambda e: errors.append(str(e)))
            pg.on("console",
                  lambda m: errors.append(m.text) if m.type == "error" else None)
            pg.on("request", lambda r: fetches.append(r.url)
                  if "public_sector_filings" in r.url else None)

            pg.goto(url, wait_until="load", timeout=60000)
            pg.wait_for_timeout(800)
            check(not errors, "the page loads with no script errors",
                  "; ".join(errors[:2]))
            check(not fetches, "no filings are fetched until a row is opened",
                  f"{len(fetches)} fetched")

            # Every state section is a drill-down, not only the first.
            sections = pg.evaluate("""() =>
              [...document.querySelectorAll('section[id^="state-"]')].map(s => ({
                id: s.id,
                rows: s.querySelectorAll('table.drill tr.emp').length,
              }))""")
            check(bool(sections), "the page has state sections")
            for s in sections:
                check(s["rows"] > 0, f"{s['id']} drills down",
                      f"{s['rows']} employers")

            # The three depths, on the biggest employer there is.
            pg.locator(f"#{rid}").scroll_into_view_if_needed()
            pg.locator(f"#{rid}").click()
            pg.wait_for_selector(f"{det} table.filed tbody tr", timeout=30000)
            pg.wait_for_timeout(300)
            n = pg.locator(f"{det} table.filed tbody tr").count()
            check(n == 10, "an opened row shows ten filings", str(n))
            said = pg.evaluate(
                f"document.querySelector('{det} .showing span').textContent")
            check(said == f"Showing 10 of {filings:,} filings.",
                  "the row says what it is showing", repr(said))
            btns = pg.locator(f"{det} .showing button").all_inner_texts()
            check(btns == ["Show 50", "Show All"],
                  "the two buttons the author asked for", str(btns))

            pg.locator(f"{det} .showing button", has_text="Show 50").click()
            pg.wait_for_timeout(250)
            n = pg.locator(f"{det} table.filed tbody tr").count()
            check(n == 50, "Show 50 shows fifty", str(n))

            pg.locator(f"{det} .showing button", has_text="Show All").click()
            pg.wait_for_timeout(600)
            n = pg.locator(f"{det} table.filed tbody tr").count()
            check(n == filings, f"Show All shows all {filings:,}", str(n))

            # Closing and reopening comes back to the default.
            pg.locator(f"#{rid}").click()
            pg.wait_for_timeout(200)
            check(pg.locator(det).is_hidden(), "the row closes")
            pg.locator(f"#{rid}").click()
            pg.wait_for_timeout(500)
            n = pg.locator(f"{det} table.filed tbody tr").count()
            check(n == 10, "reopening comes back to ten", str(n))

            # One file per state, however many rows are opened in it.
            before = len(fetches)
            opened = pg.evaluate(f"""() => {{
              const rows = [...document.querySelectorAll(
                'tr.emp[data-state="{slug}"]')].slice(0, 4);
              rows.forEach(r => r.click());
              return rows.length;
            }}""")
            pg.wait_for_timeout(700)
            check(len(fetches) == before,
                  f"{opened} more rows in one state fetch nothing new",
                  f"{len(fetches)} fetches in total")

            # Sorting must not separate a row from what it opened.
            pg.locator(f"#{rid}").scroll_into_view_if_needed()
            if pg.locator(f"#{rid}").get_attribute("aria-expanded") != "true":
                pg.locator(f"#{rid}").click()
                pg.wait_for_timeout(400)
            pg.evaluate(f"""() => {{
              const r = document.getElementById('{rid}');
              r.closest('table').querySelector('thead th').click();
            }}""")
            pg.wait_for_timeout(400)
            stuck = pg.evaluate(f"""() => {{
              const r = document.getElementById('{rid}');
              return !!r.nextElementSibling
                && r.nextElementSibling.id === 'd-' + r.id;
            }}""")
            check(stuck, "sorting keeps a detail row with its employer")
            check(pg.locator(f"{det} table.filed tbody tr").count() > 0,
                  "sorting does not empty an open row")

            # The fragment is what stands in for a page per employer.
            pg2 = ctx.new_page()
            err2 = []
            pg2.on("pageerror", lambda e: err2.append(str(e)))
            pg2.goto(f"{url}#{rid}", wait_until="load", timeout=60000)
            pg2.wait_for_timeout(1500)
            n = pg2.locator(f"{det} table.filed tbody tr").count()
            check(n == 10, "the fragment opens that row on a cold load", str(n))
            check(not err2, "no script errors on the deep-linked load",
                  "; ".join(err2[:2]))

            check(not errors, "no script errors through the whole run",
                  "; ".join(errors[:2]))
            ctx.close()
            browser.close()
    finally:
        if httpd:
            httpd.shutdown()

    return report(args.verbose)


def report(verbose: bool) -> int:
    failed = [r for r in _results if not r[0]]
    print()
    for ok, nm, detail in _results:
        if ok and not verbose:
            continue
        print(f"  [{'ok  ' if ok else 'FAIL'}] {nm}"
              + (f"  -- {detail}" if detail else ""))
    print()
    if failed:
        print(f"  {len(failed)} of {len(_results)} drill-down checks FAILED")
        return 1
    print(f"  all {len(_results)} drill-down checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
