#!/usr/bin/env python3
"""Give every page and every interactive element a stable analytics identity.

WHY NOT JUST USE `id`. `id` already has three jobs on this site: URL anchors
(#same-campus, #who-pays), ARIA relationships, and JS/CSS hooks. Overloading it
with a fourth -- analytics -- couples them: rename an anchor to improve a
shareable link and you silently break the metric that has been collecting for
months, with nothing to warn you. So analytics gets a dedicated attribute:

    <body data-page="index">                     page identity
    <a data-track="nav.expansion">               element identity

`id` keeps doing what it already does, and the two can change independently.

WHAT THIS REPLACES. The collector derived its click label from the element's
VISIBLE TEXT:

    var lbl = t.dataset.key || t.textContent.trim().substr(0,40)

so rewording a button split its time series in two, retroactively and silently.
It also only listened to four hardcoded classes -- .nav-item, .dept-header,
.toggle-wrap, a.name-link -- none of which exist on index.html, so the landing
page would have recorded zero clicks even once instrumented.

Naming: `<area>.<thing>`, lowercase, dot-separated, derived from structure
rather than copy. nav.expansion, cta.method, chart.masters-toggle.

Usage:
    python3 scripts/add_tracking_ids.py --report     # what would change
    python3 scripts/add_tracking_ids.py --write
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"

# Pages whose reception actually matters. University pages are handled
# separately: they share one template and are identified by their key.
ARGUMENT_PAGES = ["index", "expansion", "rankings", "distributions",
                  "concentration", "query", "live", "data_sources"]


def slug(text: str) -> str:
    # Decode entities FIRST: without it "master&rsquo;s" became the permanent
    # metric key "master-rsquo-s". These names outlive the copy they came from,
    # so a bad one is a bad column header forever.
    import html as _html
    s = _html.unescape(re.sub(r"<[^>]+>", " ", text))
    s = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return s[:34]


def track_name(tag: str, attrs: str, inner: str, href: str | None) -> str:
    """Derive a stable name from STRUCTURE, never from prose."""
    if href:
        h = href.strip()
        if h.startswith("#"):
            return f"anchor.{h[1:]}"
        if h.startswith("/"):
            return "nav." + slug(h.strip("/").replace(".html", "")) or "nav.home"
        if h.startswith(("http://", "https://")):
            host = re.sub(r"^https?://(www\.)?", "", h).split("/")[0]
            return f"out.{slug(host)}"
        if h.startswith("mailto:"):
            return "out.email"
    if tag == "button":
        m = re.search(r'id="([^"]+)"', attrs)
        if m:
            return f"btn.{m.group(1)}"
        return f"btn.{slug(inner)}"
    if tag == "select":
        m = re.search(r'id="([^"]+)"', attrs)
        return f"select.{m.group(1) if m else slug(inner)}"
    if tag == "details":
        return f"disclose.{slug(inner)}"
    return f"{tag}.{slug(inner)}"


TAG_RE = re.compile(r'<(a|button|select|details)\b([^>]*)>(.{0,120}?)</\1>',
                    re.S | re.I)


def process(path: Path, write: bool) -> tuple[int, int, list[str]]:
    s = path.read_text(errors="replace")
    orig = s
    added_body = 0

    # 1. page identity on <body>
    if "data-page=" not in s:
        page = path.stem
        s = re.sub(r"<body(\s[^>]*)?>",
                   lambda m: f'<body data-page="{page}"{m.group(1) or ""}>',
                   s, count=1)
        added_body = 1

    # 2. element identity, only where absent
    names: list[str] = []
    seen: dict[str, int] = {}
    unnamed: list[str] = []

    def repl(m):
        tag, attrs, inner = m.group(1).lower(), m.group(2), m.group(3)
        if "data-track=" in attrs:
            return m.group(0)
        href_m = re.search(r'href="([^"]*)"', attrs)
        name = track_name(tag, attrs, inner, href_m.group(1) if href_m else None)
        # uniqueness within the page, so a metric maps to one element
        if name.endswith("."):
            # No href, no id, no text. Naming it "unnamed" would produce a
            # metric nobody can act on; flag it so a human gives it one.
            unnamed.append(f"{path.name}: <{tag}> with no derivable name")
            return m.group(0)
        seen[name] = seen.get(name, 0) + 1
        if seen[name] > 1:
            name = f"{name}-{seen[name]}"
        names.append(name)
        return f'<{m.group(1)}{attrs} data-track="{name}">{inner}</{m.group(1)}>'

    s = TAG_RE.sub(repl, s)
    if write and s != orig:
        path.write_text(s)
    if unnamed:
        for u in unnamed:
            print(f"    SKIPPED (needs a hand-written name): {u}")
    return added_body, len(names), names


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--all", action="store_true",
                    help="include the 230 per-university pages")
    args = ap.parse_args()
    if not (args.write or args.report):
        args.report = True

    targets = [SITE / f"{n}.html" for n in ARGUMENT_PAGES]
    if args.all:
        targets += sorted((SITE / "universities").glob("*.html"))
    targets = [p for p in targets if p.exists()]

    tot_body = tot_el = 0
    for p in targets:
        b, n, names = process(p, args.write)
        tot_body += b
        tot_el += n
        if n or b:
            print(f"  {p.name:<24} page-id:{'+' if b else '.'}  elements:+{n}")
            if args.report and names:
                print(f"       e.g. {', '.join(names[:5])}")
    verb = "wrote" if args.write else "would add"
    print(f"\n  {verb}: {tot_body} page identities, {tot_el} element identities, "
          f"across {len(targets)} page(s)")
    if not args.write:
        print("  Re-run with --write to apply.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
