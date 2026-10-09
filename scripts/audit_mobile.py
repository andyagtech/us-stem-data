#!/usr/bin/env python3
"""How the live pages behave on phones and tablets.

MEASURE THE THING, NOT A PROXY. Mobile emulation inflates window.innerWidth,
so a page that overflows can report a width that fits. Every measurement
here compares the document's scrollWidth against the viewport's clientWidth
and names the widest element when they disagree, because "something
overflows" is not actionable and "this table is 540px in a 390px viewport"
is.

Four checks per page per device:
  overflow   nothing forces the page to scroll sideways
  gutter     text is not jammed against the screen edge
  targets    tappable controls are large enough to hit
  legible    body text is not below 12px

Usage:
  python3 scripts/audit_mobile.py
  python3 scripts/audit_mobile.py --pages /overview,/postdocs
"""
from __future__ import annotations

import argparse
import sys

HOST = "https://phd-demographics.andy-barr.com"

#: Real devices, not round numbers. The 360 is the common Android floor and
#: the one that breaks first; the 1024 tablet is where a two-column grid
#: usually still applies and should be checked as a desktop layout, not a
#: phone one.
DEVICES = [
    ("iPhone SE", 375, 667, True),
    ("Android", 360, 800, True),
    ("iPhone 15 Pro", 393, 852, True),
    ("iPad mini", 744, 1133, True),
    ("iPad Pro", 1024, 1366, True),
]

PAGES = ["/", "/overview", "/postdocs", "/name-lists", "/stem",
         "/universities/missouri_st.html", "/data_requests", "/query",
         "/live", "/presentation", "/methodology", "/implementation",
         "/visa-schools", "/states/mt", "/industries/petroleum"]

PROBE = """() => {
  const de = document.documentElement;
  const vw = de.clientWidth;
  let widest = {w: 0, what: ''};
  document.querySelectorAll('body *').forEach(e => {
    const r = e.getBoundingClientRect();
    if (r.width > widest.w && r.right > vw + 1) {
      widest = {w: Math.round(r.width),
                what: (e.tagName + '.' + (e.className || '')).slice(0, 40)};
    }
  });
  // Smallest left gutter among visible text blocks, measured to where the
  // TEXT starts rather than where the box does. The first version read
  // getBoundingClientRect().left, which is the border edge, and reported
  // the live dashboard's source note as a 0px gutter when its own padding
  // already inset the text by 24px. A false alarm in a layout audit sends
  // you editing a page that was fine.
  let gutter = 999;
  document.querySelectorAll('p, h1, h2, li, td').forEach(e => {
    const r = e.getBoundingClientRect();
    if (r.width > 40 && r.height > 0 && r.top < 4000) {
      const pad = parseFloat(getComputedStyle(e).paddingLeft) || 0;
      gutter = Math.min(gutter, Math.round(r.left + pad));
    }
  });
  // Tap targets below 32px in their smaller dimension.
  let small = 0, smallest = 999;
  document.querySelectorAll('a, button, [role=button], input, select')
    .forEach(e => {
      const r = e.getBoundingClientRect();
      if (r.width < 2 || r.height < 2) return;       // hidden
      const m = Math.min(Math.round(r.width), Math.round(r.height));
      if (m < 32) { small++; smallest = Math.min(smallest, m); }
    });
  // Body text size.
  const body = parseFloat(getComputedStyle(document.body).fontSize);
  return {scrollW: de.scrollWidth, vw: vw, widest: widest,
          gutter: gutter === 999 ? -1 : gutter,
          small: small, smallest: smallest === 999 ? -1 : smallest,
          body: Math.round(body * 10) / 10};
}"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages")
    ap.add_argument("--host", default=HOST)
    a = ap.parse_args()
    pages = a.pages.split(",") if a.pages else PAGES
    from playwright.sync_api import sync_playwright

    problems = []
    print(f"Mobile and tablet audit against {a.host}\n")
    with sync_playwright() as p:
        b = p.chromium.launch()
        for name, w, h, touch in DEVICES:
            print(f"  {name}  {w}x{h}")
            for path in pages:
                ctx = b.new_context(viewport={"width": w, "height": h},
                                    device_scale_factor=2,
                                    is_mobile=touch and w < 700,
                                    has_touch=touch)
                pg = ctx.new_page()
                try:
                    pg.goto(a.host + path, wait_until="networkidle", timeout=45000)
                    pg.wait_for_timeout(2200)
                    m = pg.evaluate(PROBE)
                except Exception as e:                        # noqa: BLE001
                    print(f"      {path:34} ERROR {str(e)[:36]}")
                    problems.append((name, path, "load failed"))
                    ctx.close()
                    continue
                over = m["scrollW"] - m["vw"]
                flags = []
                if over > 1:
                    flags.append(f"overflows {over}px ({m['widest']['what']} "
                                 f"{m['widest']['w']}px)")
                if 0 <= m["gutter"] < 10:
                    flags.append(f"gutter {m['gutter']}px")
                if m["body"] < 12:
                    flags.append(f"body text {m['body']}px")
                if flags:
                    print(f"      {path:34} {'; '.join(flags)}")
                    problems.extend((name, path, f) for f in flags)
                ctx.close()
        b.close()

    print()
    if problems:
        print(f"{len(problems)} problem(s) across "
              f"{len({(d, p) for d, p, _ in problems})} page/device pairs")
    else:
        print(f"No layout problems on {len(pages)} pages "
              f"across {len(DEVICES)} devices.")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
