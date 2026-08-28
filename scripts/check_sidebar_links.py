#!/usr/bin/env python3
"""Verify every link the sidebar renders actually goes somewhere.

The sidebar is the site's whole navigation: ~30 page links, ~70 in-page
anchors and one entry per university, all declared in site/sidebar.js and
rendered by it at runtime. Nothing else checks them, and the failure is
quiet -- a renamed section id leaves a sidebar entry that scrolls nowhere,
and a renamed page leaves one that 404s. Both look fine until clicked.

Three things are checked, in the browser rather than by reading source,
because the ids the anchors point at are not all baked into the HTML:
anchors.js assigns the rest at load time from heading text. A static grep
would report those as broken and miss the ones that really are.

  1. page links   -- every href resolves to a file that exists and serves
  2. anchors      -- every #hash has an element with that id, once the page
                     has loaded and anchors.js has run
  3. universities -- every sidebar university selects a university when
                     followed, rather than landing on the empty state

Usage:
  python3 scripts/check_sidebar_links.py            # site/ over a local server
  python3 scripts/check_sidebar_links.py --live     # the deployed site
  python3 scripts/check_sidebar_links.py --external # also try external links
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
LIVE = "https://phd-demographics.andy-barr.com"

_results: list[tuple[bool, str, str]] = []


def check(ok: bool, name: str, detail: str = "") -> bool:
    _results.append((bool(ok), name, detail))
    return bool(ok)


# ---------------------------------------------------------------- sidebar.js

def parse_sidebar(js: str) -> tuple[list[dict], list[str]]:
    """Pull the declared items out of sidebar.js.

    Read from source rather than the DOM on purpose: this is the list the
    sidebar PROMISES to render, so comparing it against what actually renders
    catches a link that silently stopped being drawn at all.
    """
    start = js.index("const sections = [")
    depth, i = 0, start + len("const sections = ")
    for i in range(i, len(js)):
        if js[i] == "[":
            depth += 1
        elif js[i] == "]":
            depth -= 1
            if depth == 0:
                break
    block = js[start:i + 1]

    items: list[dict] = []
    # Each item is `{ href: '...', label: '...', ... }` with an optional
    # `anchors: [ { hash: '...' }, ... ]` running to the next `href:` or the
    # end of the enclosing list.
    for m in re.finditer(r"\{\s*href:\s*'([^']+)'\s*,\s*label:\s*([\"'])(.*?)\2", block):
        href, label = m.group(1), m.group(3)
        tail = block[m.end():]
        nxt = tail.find("href:")
        scope = tail[:nxt] if nxt != -1 else tail
        hashes = re.findall(r"hash:\s*'([^']+)'", scope)
        items.append({
            "href": href,
            "label": label,
            "hashes": hashes,
            "external": href.startswith("http"),
        })

    sections = re.findall(r"title:\s*'([^']+)'", block)
    return items, sections


# ------------------------------------------------------------- local serving

class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):  # silence the request log
        pass


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
    """Serve site/ so that root-absolute hrefs like /stem.html resolve.

    file:// cannot be used here: every sidebar href starts with '/', which
    under file:// points at the filesystem root, so every link would look
    broken for a reason that has nothing to do with the site.
    """
    handler = functools.partial(_Quiet, directory=str(directory))
    httpd = _Threaded(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}"


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--live", action="store_true",
                    help="check the deployed site instead of site/ on disk")
    ap.add_argument("--external", action="store_true",
                    help="also request the off-site links (needs network)")
    ap.add_argument("--universities", type=int, default=3,
                    help="how many university links to follow (0 for none)")
    args = ap.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright is required: pip install playwright && playwright install chromium")
        return 2

    js_path = SITE / "sidebar.js"
    if not js_path.exists():
        print(f"  {js_path} not found")
        return 2
    items, sections = parse_sidebar(js_path.read_text(encoding="utf-8"))
    check(len(items) > 10, "sidebar parsed", f"{len(items)} links, "
          f"{sum(len(i['hashes']) for i in items)} anchors, "
          f"{len(sections)} sections")

    httpd = None
    if args.live:
        base = LIVE
    else:
        httpd, base = serve(SITE)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            ctx = browser.new_context(viewport={"width": 1500, "height": 1000})
            page = ctx.new_page()
            _run(page, base, items, args)
            ctx.close()
            browser.close()
    finally:
        if httpd:
            httpd.shutdown()

    failed = [r for r in _results if not r[0]]
    print()
    for ok, name, detail in _results:
        print(f"  [{'ok  ' if ok else 'FAIL'}] {name}" + (f"  — {detail}" if detail else ""))
    print()
    if failed:
        print(f"  {len(failed)} of {len(_results)} checks FAILED")
        return 1
    print(f"  all {len(_results)} sidebar checks passed")
    return 0


def _dismiss_coach(page) -> None:
    """The first-visit coach mark covers the page and eats pointer events."""
    try:
        page.evaluate("localStorage.setItem('coach_done_v3','1')")
    except Exception:
        pass


def _nav_state(page) -> dict:
    """What navigation this page actually renders.

    There are THREE implementations, each with its own copy of the page list:

      sidebar.js   a.sb-item              23 pages, a fixed 220px rail
      generated    a.nav-item.nav-page    stem, non_stem and 208 uni pages
      nav.js       a.site-nav-link        3 pages, a drawer behind a button

    A checker that knows only some of them reports the rest as having no
    navigation at all. This one knew the first two, and duly reported
    submit.html as a dead end -- it is not; it carries the nav.js drawer with
    eleven working links. Wrong in the direction that wastes someone's time.
    """
    return page.evaluate("""() => {
      const shared = [...document.querySelectorAll('a.sb-item:not(.sb-sub)')];
      const baked  = [...document.querySelectorAll('a.nav-item.nav-page')];
      const drawer = [...document.querySelectorAll('a.site-nav-link')];
      const href = a => a.getAttribute('href') || '';
      return {
        impl: shared.length ? 'sidebar.js'
              : (baked.length ? 'generated'
              : (drawer.length ? 'nav.js' : 'none')),
        pages: [...shared, ...baked, ...drawer].map(href)
                 .filter(h => h && !h.startsWith('javascript:')),
        subs: [...document.querySelectorAll('a.sb-sub')]
                 .map(a => href(a).replace(/^#/, '')),
        unis: [...document.querySelectorAll('a.sb-uni, a.nav-item[data-key]')]
                 .map(a => a.dataset.key).filter(Boolean),
      };
    }""")


def _open(page, url: str) -> bool:
    """Load a page with the first-visit coach mark already dismissed."""
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.evaluate("localStorage.setItem('coach_done_v3','1')")
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(1500)
        return True
    except Exception as e:
        check(False, f"load {url}", str(e)[:80])
        return False


def _run(page, base: str, items: list[dict], args) -> None:
    internal = [i for i in items if not i["external"]]

    # 1. Every declared page link resolves to something that serves.
    for it in internal:
        try:
            resp = page.request.get(base + it["href"])
            ok = resp.status < 400
            check(ok, f"link {it['href']}", "" if ok else f"HTTP {resp.status}")
        except Exception as e:
            check(False, f"link {it['href']}", str(e)[:80])

    if args.external:
        for it in (i for i in items if i["external"]):
            try:
                resp = page.request.get(it["href"], timeout=15000)
                ok = resp.status < 400
                check(ok, f"external {it['href']}", "" if ok else f"HTTP {resp.status}")
            except Exception as e:
                check(False, f"external {it['href']}", str(e)[:80])

    # 2. Anchors: the target must exist, and the sidebar must still draw a
    #    link to it. Either half failing leaves the reader unable to get there.
    for it in (i for i in internal if i["hashes"]):
        if not _open(page, base + it["href"]):
            continue
        missing = page.evaluate(
            "hs => hs.filter(h => !document.getElementById(h))", it["hashes"])
        check(not missing, f"anchor targets on {it['href']}",
              f"{len(it['hashes'])} ok" if not missing
              else f"no element with id: {', '.join(missing)}")

        nav = _nav_state(page)
        if nav["impl"] == "sidebar.js":
            undrawn = [h for h in it["hashes"] if h not in nav["subs"]]
            check(not undrawn, f"sidebar draws anchors for {it['href']}",
                  "" if not undrawn else f"declared, not rendered: {', '.join(undrawn)}")

    # 3. Every page the sidebar links to must itself offer a way onward.
    #    A page with no navigation is a dead end: the sidebar sends readers
    #    there and nothing but the Back button brings them out.
    for it in internal:
        if not it["href"].endswith(".html"):
            continue
        if not _open(page, base + it["href"]):
            continue
        nav = _nav_state(page)
        check(nav["impl"] != "none", f"navigation present on {it['href']}",
              f"{nav['impl']}, {len(nav['pages'])} links"
              if nav["impl"] != "none" else "renders no navigation at all -- no sidebar.js, no nav.js drawer, and no baked-in nav, so a reader who lands here can only go back")

        # A baked-in sidebar keeps its own copy of the page list, so it can
        # drift from sidebar.js. Every link it draws still has to resolve.
        for href in dict.fromkeys(nav["pages"]):
            if href.startswith("http") or href.startswith("#"):
                continue
            target = href if href.startswith("/") else "/" + href
            try:
                resp = page.request.get(base + target)
                ok = resp.status < 400
                check(ok, f"{it['href']} -> {href}",
                      "" if ok else f"HTTP {resp.status}")
            except Exception as e:
                check(False, f"{it['href']} -> {href}", str(e)[:80])

    # 4. University links select a university instead of landing on the
    #    empty state, which is what an unknown key would do.
    if args.universities:
        if _open(page, base + "/stem.html"):
            page.wait_for_timeout(1500)
            keys = _nav_state(page)["unis"]
            check(bool(keys), "university links listed", f"{len(keys)} in the sidebar")
            for key in keys[:args.universities]:
                try:
                    page.goto(f"{base}/stem.html#{key}",
                              wait_until="domcontentloaded", timeout=60000)
                    page.wait_for_timeout(2500)
                    blocked = page.evaluate(
                        "() => document.body.classList.contains('no-uni')")
                    check(not blocked, f"#{key} selects a university",
                          "" if not blocked else "still on the empty state")
                except Exception as e:
                    check(False, f"#{key} selects a university", str(e)[:80])


if __name__ == "__main__":
    sys.exit(main())
