#!/usr/bin/env python3
"""Fetch + cache the latin subsets of the house typefaces and inline them as
base64 data URIs, so OG cards render identically with no network at screenshot
time.

Cache lives outside the repo (~/.cache/phd-og-fonts) so nothing font-shaped is
committed or deployed. First run downloads ~10 woff2 files; later runs are
offline.
"""
import base64
import hashlib
import re
import urllib.request
from pathlib import Path

CACHE = Path.home() / ".cache" / "phd-og-fonts"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
CSS_URL = ("https://fonts.googleapis.com/css2?"
           "family=Newsreader:wght@400;500;600"
           "&family=Public+Sans:wght@300;400;500;600;700"
           "&family=IBM+Plex+Mono:wght@400;500&display=swap")


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def _cached(name: str, fetch) -> bytes:
    CACHE.mkdir(parents=True, exist_ok=True)
    p = CACHE / name
    if p.exists() and p.stat().st_size > 0:
        return p.read_bytes()
    data = fetch()
    p.write_bytes(data)
    return data


BLOCK = re.compile(r"@font-face\s*\{(.*?)\}", re.S)
FIELD = {k: re.compile(k + r":\s*([^;]+);") for k in
         ("font-family", "font-style", "font-weight", "src", "unicode-range")}


def font_css() -> str:
    """Return @font-face rules with base64-inlined latin woff2 payloads.

    Several weights of these families are served from one variable-font file.
    We dedupe by payload and emit a single face spanning the weight range,
    which cuts the inlined CSS from ~440KB to ~115KB.
    """
    css = _cached("google.css", lambda: _get(CSS_URL)).decode()
    faces = {}
    for body in BLOCK.findall(css):
        vals = {}
        for k, rx in FIELD.items():
            m = rx.search(body)
            vals[k] = m.group(1).strip() if m else ""
        # Keep only the plain "latin" subset (the one that starts at U+0000):
        # it covers everything on the cards and drops ~80% of the bytes.
        if not vals["unicode-range"].startswith("U+0000-00FF"):
            continue
        m = re.search(r"url\((https://[^)]+\.woff2)\)", vals["src"])
        if not m:
            continue
        url = m.group(1)
        fam = vals["font-family"].strip("'\"")
        weight = int(vals["font-weight"])
        blob = _cached(f"{fam.replace(' ', '')}-{weight}.woff2",
                       lambda u=url: _get(u))
        key = (fam, vals["font-style"], hashlib.sha1(blob).hexdigest())
        faces.setdefault(key, {"blob": blob, "weights": []})["weights"].append(weight)

    out = []
    for (fam, style, _), f in faces.items():
        lo, hi = min(f["weights"]), max(f["weights"])
        rng = str(lo) if lo == hi else f"{lo} {hi}"
        b64 = base64.b64encode(f["blob"]).decode()
        out.append(
            "@font-face{font-family:'%s';font-style:%s;font-weight:%s;"
            "src:url(data:font/woff2;base64,%s) format('woff2');}"
            % (fam, style, rng, b64)
        )
    if not out:
        raise RuntimeError("no latin font faces resolved")
    return "\n".join(out)


if __name__ == "__main__":
    css = font_css()
    print(f"{len(css):,} bytes of inlined @font-face CSS, cache at {CACHE}")
