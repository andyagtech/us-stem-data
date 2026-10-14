#!/usr/bin/env python3
"""Pre-share checklist. Tests the LIVE site, not the working copy.

WHY A SEPARATE SCRIPT FROM check_consistency. That gate compares the repo
with itself and is the right thing to run before a deploy. This runs AFTER
one and asks a different question: does the thing a reader will open
actually work? Those differ, and the ways they differ have bitten this
project before -- a page live and linked while the assistant could not
mention it, a homepage that lost its sidebar because only /index.html was
ever checked, a footer two months stale on every page.

So every check here loads a URL over the network, as a reader would.

Usage:
  python3 scripts/preflight.py
  python3 scripts/preflight.py --host https://h1b.andy-barr.com
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor

DEFAULT_HOST = "https://phd-demographics.andy-barr.com"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 Chrome/131.0 Safari/537.36"}

results: list[tuple[bool, str, str]] = []


def check(ok: bool, name: str, detail: str = "") -> bool:
    results.append((bool(ok), name, detail))
    return bool(ok)


def get(url: str, timeout: int = 30):
    """Fetch and DECOMPRESS. The site is deployed pre-compressed and
    CloudFront returns Content-Encoding: gzip for the larger objects whether
    or not the client asked for it. urllib does not decompress, so the first
    version of this script read gzip bytes as text and reported that the two
    university pages -- the only ones big enough to be compressed -- had no
    stylesheet, no sidebar and no OpenGraph tags. They had all three. A
    checker that lies about the two biggest pages is worse than no checker.
    """
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        enc = (r.headers.get("Content-Encoding") or "").lower()
        if enc == "gzip":
            import gzip
            raw = gzip.decompress(raw)
        elif enc == "br":
            try:
                import brotli
                raw = brotli.decompress(raw)
            except ImportError:
                raise RuntimeError("brotli response but no brotli module")
        return r.status, raw.decode("utf-8", "replace"), dict(r.headers)


#: The pages a reader is most likely to open first, plus the two that have
#: been broken before. "/" and "/index.html" are BOTH here on purpose: they
#: take different code paths and the homepage lost its sidebar once because
#: only the second was ever checked.
KEY_PAGES = ["/", "/index.html", "/overview", "/postdocs", "/name-lists",
             "/departments-stem", "/departments-nonstem", "/data_requests", "/data_sources",
             "/query", "/presentation", "/visa-schools", "/bodyshops",
             "/public-sector-visas", "/contents",
             "/universities/missouri_st.html", "/universities/mit.html",
             "/states/mt", "/industries/petroleum"]


def check_pages_load(host: str) -> dict[str, str]:
    bodies = {}

    def one(path):
        try:
            s, b, _ = get(host + path)
            return path, s, b
        except Exception as e:                                # noqa: BLE001
            return path, 0, str(e)

    with ThreadPoolExecutor(max_workers=8) as ex:
        for path, status, body in ex.map(one, KEY_PAGES):
            if status == 200:
                bodies[path] = body
    bad = [p for p in KEY_PAGES if p not in bodies]
    check(not bad, "every key page returns 200",
          f"{len(bodies)}/{len(KEY_PAGES)} ok" + (f"; FAILED {bad}" if bad else ""))
    return bodies


def check_design(bodies: dict[str, str]) -> None:
    """One stylesheet, one theme, one sidebar, on every page."""
    no_css = [p for p, b in bodies.items() if 'href="/style.css"' not in b]
    check(not no_css, "every page loads the shared stylesheet",
          f"{len(bodies) - len(no_css)}/{len(bodies)}"
          + (f"; missing on {no_css}" if no_css else ""))

    no_sb = [p for p, b in bodies.items()
             if "sidebar.js" not in b and "shared-sidebar" not in b]
    check(not no_sb, "every page loads the sidebar",
          f"{len(bodies) - len(no_sb)}/{len(bodies)}"
          + (f"; missing on {no_sb}" if no_sb else ""))

    no_theme = [p for p, b in bodies.items() if "phd-theme-boot" not in b]
    check(not no_theme, "every page boots the theme before paint",
          f"{len(bodies) - len(no_theme)}/{len(bodies)}"
          + (f"; missing on {no_theme}" if no_theme else ""))

    #: A token defined in terms of itself resolves to nothing and the element
    #: renders invisible. This shipped once.
    self_ref = [p for p, b in bodies.items()
                if re.search(r"--([a-z0-9-]+)\s*:\s*var\(\s*--\1\s*\)", b)]
    check(not self_ref, "no self-referencing CSS tokens",
          f"checked {len(bodies)}" + (f"; FOUND on {self_ref}" if self_ref else ""))


def check_freshness(host: str, bodies: dict[str, str]) -> None:
    try:
        _, sb, _ = get(host + "/sidebar.js")
    except Exception as e:                                    # noqa: BLE001
        check(False, "the footer date is current", str(e)[:60]); return
    # The date is wrapped in an <!--auto:...--> marker so sync_docs owns it,
    # and the marker sits between the label and the value. Skip anything
    # that is not the date itself.
    m = re.search(r"Last updated:(?:\s|<!--[^>]*-->)*([A-Z][a-z]+ \d{4})", sb)
    if not m:
        check(False, "the footer date is current", "no date found in sidebar.js")
        return
    import datetime as dt
    now = dt.date.today()
    try:
        shown = dt.datetime.strptime(m.group(1), "%B %Y").date()
    except ValueError:
        check(False, "the footer date is current", f"unparseable: {m.group(1)}")
        return
    months = (now.year - shown.year) * 12 + now.month - shown.month
    check(months <= 1, "the footer date is current",
          f"says {m.group(1)}, today is {now:%B %Y}"
          + (f" -- {months} months stale" if months > 1 else ""))


def check_catalog(host: str) -> None:
    try:
        _, raw, _ = get(host + "/catalog.json")
        cat = json.loads(raw)
    except Exception as e:                                    # noqa: BLE001
        check(False, "catalog.json is served and current", str(e)[:60]); return
    import datetime as dt
    upd = cat.get("last_updated", "")
    try:
        when = dt.datetime.fromisoformat(upd.replace("Z", "+00:00")).date()
        age = (dt.date.today() - when).days
    except Exception:                                         # noqa: BLE001
        age = 9999
    t = cat.get("totals", {})
    check(age <= 7, "catalog.json is served and current",
          f"updated {upd[:10]} ({age}d ago), "
          f"{t.get('universities')} universities, "
          f"{t.get('stem_records'):,} STEM records"
          if age != 9999 else f"unparseable date {upd!r}")


def check_anchors(host: str, bodies: dict[str, str]) -> None:
    """Every plain in-page link must resolve to an id on the same page.

    TWO KINDS OF ANCHOR, AND ONLY ONE IS TESTABLE THIS WAY. A plain
    <a href="#method"> must match an id="method" or the reader goes nowhere.
    But the record pages also carry share buttons -- the small # beside a
    department or a panel -- whose href is a fallback and whose real target
    is computed in the click handler against a hash router. Those cannot be
    checked by matching ids, and treating them as broken made this check cry
    wolf on four pages at once, which is how a check gets ignored.

    So they are counted and reported separately rather than failed.
    """
    broken, checked, routed = [], 0, 0
    link = re.compile(r'<a\b[^>]*href="#([^"]+)"[^>]*>')
    for path, body in bodies.items():
        ids = set(re.findall(r'\sid="([^"]+)"', body))
        for m in link.finditer(body):
            href, tag = m.group(1), m.group(0)
            if not href or href == "top":
                continue
            # A handler that computes its own destination owns the link.
            if "onclick=" in tag:
                routed += 1
                continue
            checked += 1
            if href not in ids:
                broken.append(f"{path}#{href}")
    check(not broken, "plain in-page anchors resolve",
          f"{checked} checked, {routed} script-routed (not testable here)"
          + (f"; BROKEN {broken[:6]}" if broken else ""))


def check_opengraph(host: str, bodies: dict[str, str]) -> None:
    missing, imgs = [], {}
    for path, body in bodies.items():
        t = re.search(r'<meta property="og:title" content="([^"]*)"', body)
        d = re.search(r'<meta property="og:description" content="([^"]*)"', body)
        i = re.search(r'<meta property="og:image" content="([^"]*)"', body)
        if not (t and t.group(1).strip()) or not (d and d.group(1).strip()):
            missing.append(path)
        if i and i.group(1).strip():
            imgs[path] = i.group(1).strip()
    check(not missing, "every page has an og:title and og:description",
          f"{len(bodies) - len(missing)}/{len(bodies)}"
          + (f"; missing on {missing[:6]}" if missing else ""))

    #: An og:image that 404s is worse than none: the card renders blank.
    urls = {u if u.startswith("http") else host + u for u in imgs.values()}
    dead = []
    def head(u):
        try:
            s, _, h = get(u, timeout=20)
            return u, s, int(h.get("Content-Length") or 0)
        except Exception:                                     # noqa: BLE001
            return u, 0, 0
    if urls:
        with ThreadPoolExecutor(max_workers=6) as ex:
            for u, s, n in ex.map(head, urls):
                if s != 200 or n < 1000:
                    dead.append(f"{u.rsplit('/', 1)[-1]} ({s}, {n}B)")
    check(not dead, "every og:image actually loads",
          f"{len(urls)} distinct image(s), {len(imgs)} page(s) carry one"
          + (f"; BROKEN {dead}" if dead else ""))


def check_assistant(host: str) -> None:
    try:
        _, raw, _ = get(host + "/data/chat/site_map.json")
        sm = json.loads(raw)
    except Exception as e:                                    # noqa: BLE001
        check(False, "the assistant's site map is live", str(e)[:60]); return
    pages = sm.get("pages") or sm
    n = len(pages) if hasattr(pages, "__len__") else 0
    want = ["postdocs", "name-lists", "data_requests"]
    have = json.dumps(sm)
    absent = [w for w in want if w not in have]
    check(not absent, "the assistant's site map is live",
          f"{n} entries" + (f"; ABSENT {absent}" if absent else ""))


def check_indexable(host: str) -> None:
    try:
        _, robots, _ = get(host + "/robots.txt")
        _, smap, _ = get(host + "/sitemap.xml")
    except Exception as e:                                    # noqa: BLE001
        check(False, "robots.txt and sitemap.xml are served", str(e)[:60]); return
    urls = smap.count("<loc>")
    blocks_all = re.search(r"Disallow:\s*/\s*$", robots, re.M)
    check(urls > 50 and not blocks_all,
          "robots.txt and sitemap.xml are served",
          f"{urls} urls in the sitemap"
          + ("; ROBOTS BLOCKS EVERYTHING" if blocks_all else ""))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default=DEFAULT_HOST)
    a = ap.parse_args()
    host = a.host.rstrip("/")

    print(f"Pre-share checklist against {host}\n")
    bodies = check_pages_load(host)
    if bodies:
        check_design(bodies)
        check_anchors(host, bodies)
        check_opengraph(host, bodies)
    check_freshness(host, bodies)
    check_catalog(host)
    check_assistant(host)
    check_indexable(host)

    print()
    for ok, name, detail in results:
        print(f"  {'pass' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail else ""))
    bad = sum(1 for ok, _, _ in results if not ok)
    print(f"\n{len(results) - bad}/{len(results)} checks pass")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
