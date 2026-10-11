#!/usr/bin/env python3
"""Find a department by READING the engineering school's own index.

WHY GUESSING STOPPED WORKING. The pattern resolver tries a list of url
shapes -- mse.{domain}, matse.{domain}, engineering.{domain}/materials
and twenty more. That caught most fields and has now plateaued:
materials science and bioengineering are 58 of the remaining failures
because those two hide under more department names than anyone can
enumerate. Carnegie Mellon calls it Materials Science and Engineering,
Columbia folds it into Applied Physics and Applied Mathematics, Duke
runs it inside Mechanical Engineering and Materials Science.

So this stops guessing the address and reads the directory instead.
Fetch the engineering school's index, find the links, and pick the one
whose text names the field. The university tells us where its own
department is.

It is a SECOND PASS. It only looks at rows the pattern resolver could
not resolve, and it writes through the same merge, so a URL found here
sits beside one found there and the verifier checks both the same way.

Usage:
  python3 scripts/discover_department_urls.py --sector battery
  python3 scripts/discover_department_urls.py            # every sector
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from atomic_write import write_text                            # noqa: E402
import resolve_program_urls as rp                              # noqa: E402

OUT = ROOT / "data" / "labs" / "program_urls.json"

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0 Safari/537.36"}

#: Where a school lists its departments. Tried in order.
INDEX_PATHS = [
    "/departments", "/academics/departments", "/academics",
    "/about/departments", "/our-departments", "/schools-and-departments",
    "/academic-departments", "/departments-and-programs", "/programs",
]
INDEX_HOSTS = ["https://engineering.{d}", "https://www.{d}/engineering",
               "https://engr.{d}", "https://www.engineering.{d}",
               "https://{d}/engineering", "https://coe.{d}"]

#: Words that identify the department in a link's own text.
FIELD_WORDS = {
    "battery": ("materials science", "materials engineering",
                "materials science and engineering", "materials"),
    "bio": ("biomedical engineering", "bioengineering",
            "biological engineering", "biomedical"),
    "nuclear": ("nuclear engineering", "nuclear science", "nuclear"),
    "aerospace": ("aerospace engineering", "aeronautic", "aerospace"),
    "ai": ("computer science", "computer engineering", "computing"),
    "petroleum": ("petroleum engineering", "petroleum"),
    "mining": ("mining engineering", "mining", "metallurgical"),
    "me": ("mechanical engineering",),
    "ee": ("electrical", "electrical and computer"),
    "civil": ("civil engineering", "civil and environmental"),
    "chemeng": ("chemical engineering", "chemical and biomolecular"),
    "industrial": ("industrial engineering", "industrial and systems"),
}

#: A link whose text contains one of these is a programme or a course
#: listing, not the department's own site.
NOT_A_DEPARTMENT = re.compile(
    r"(undergraduate|graduate program|minor|certificate|course|admission|"
    r"apply|degree requirement|curriculum|handbook|advising|"
    #: A dated title is an event, not a department. Duke's index
    #: surfaced "2026 Duke-ORNL Workshop on Advanced Materials" and it
    #: scored higher than the department would have.
    r"\b(19|20)\d\d\b|workshop|seminar|symposium|lecture|webinar|"
    r"conference|news|story|award|prize|celebrat)", re.I)

#: And the url itself gives it away even when the text does not.
NOT_A_DEPARTMENT_URL = re.compile(
    r"(calendar|/events?/|/news/|/stories/|/blog/|/20\d\d/|"
    r"/award|/seminar|\?fq=|/search)", re.I)


def get(url: str, timeout: int = 15):
    try:
        r = requests.get(url, headers=UA, timeout=timeout, allow_redirects=True)
        return r.status_code, r.text, r.url
    except requests.RequestException:
        return 0, "", url


def links(html: str, base: str) -> list[tuple[str, str]]:
    """(text, absolute url) for every anchor, text squashed to one line."""
    out = []
    for m in re.finditer(r'<a\s[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
                         html, re.S | re.I):
        href, text = m.group(1), re.sub(r"<[^>]+>", " ", m.group(2))
        text = " ".join(text.split())
        if not text or len(text) > 90:
            continue
        out.append((text, urljoin(base, href)))
    return out


def find_index(domain: str) -> tuple[str, str] | None:
    """The engineering school's department index, as (url, html)."""
    for host in INDEX_HOSTS:
        base = host.format(d=domain)
        code, html, final = get(base, 12)
        if code != 200 or len(html) < 2000:
            continue
        #: the landing page may itself list the departments
        if len(links(html, final)) > 20:
            for path in INDEX_PATHS:
                c2, h2, f2 = get(final.rstrip("/") + path, 12)
                if c2 == 200 and len(h2) > 2000:
                    return f2, h2
            return final, html
    return None


def discover(institution: str, sector: str) -> dict | None:
    domain = rp.DOMAINS.get(institution)
    if not domain:
        return None
    words = FIELD_WORDS.get(sector)
    if not words:
        return None
    found = find_index(domain)
    if not found:
        return None
    index_url, html = found

    best = None
    for text, url in links(html, index_url):
        low = text.lower()
        if NOT_A_DEPARTMENT.search(low) or NOT_A_DEPARTMENT_URL.search(url):
            continue
        for rank, w in enumerate(words):
            if w in low:
                #: an earlier word in the list is a better match, and a
                #: longer link text is usually the full department name
                score = (-rank, len(text))
                if best is None or score > best[0]:
                    best = (score, text, url)
                break
    if not best:
        return None

    _, text, url = best
    #: Confirm the page is what the link said it was, the same way the
    #: pattern resolver does. A link can be stale.
    code, page, final = get(url, 15)
    if code != 200 or len(page) < 1500:
        return None
    body = re.sub(r"<[^>]+>", " ", page[:60000]).lower()
    if not any(t in body for t in (rp.PROOF.get(sector) or ())):
        return None
    title = re.search(r"<title[^>]*>(.*?)</title>", page, re.S | re.I)
    return {
        "institution": institution, "sector": sector, "status": "ok",
        "url": final,
        "title": " ".join(title.group(1).split())[:120] if title else "",
        "found_via": f"department index at {index_url}",
        "link_text": text,
    }


def rosters_for(row: dict) -> dict:
    """Find the student and faculty pages under an already-resolved url.

    The index pass finds the DEPARTMENT. Its rosters sit under paths the
    pattern resolver already knows, so this reuses that list rather than
    keeping a second copy that can drift out of step with it.
    """
    base = (row.get("url") or "").rstrip("/")
    if not base:
        return {}

    def probe(paths, require_students):
        for pp in paths:
            code, html, final = get(base + pp, 12)
            if code != 200 or len(html) < 2500:
                continue
            if rp.NOT_A_ROSTER.search(final):
                continue
            body = re.sub(r"<[^>]+>", " ", html)
            if require_students:
                if not rp.STUDENT_PROOF.search(body):
                    continue
                #: imported here, not at module scope: resolve_program_urls
                #: imports it inside its own function, so it is not an
                #: attribute of that module.
                import harvest_lab_rosters as hl
                if len(hl.candidate_names(html)) < 6:
                    continue
            return final
        return None

    out = {}
    stu = probe(rp.STUDENT_PATHS, True)
    fac = probe(rp.FACULTY_PATHS, False)
    if stu:
        out["students_url"] = stu
    if fac:
        out["faculty_url"] = fac
    if not (stu and fac):
        d = probe(rp.GENERIC_PATHS, False)
        if d:
            out["directory_url"] = d
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rosters-only", action="store_true",
                    help="skip discovery; find rosters under urls already "
                         "resolved but carrying none")
    ap.add_argument("--sector")
    ap.add_argument("--limit", type=int, default=80)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    doc = json.loads(OUT.read_text())
    rows = doc["rows"]

    if a.rosters_only:
        need = [r for r in rows if r.get("status") == "ok" and r.get("url")
                and not (r.get("students_url") or r.get("faculty_url")
                         or r.get("directory_url"))][: a.limit]
        print(f"Probing rosters under {len(need)} resolved departments")
        with ThreadPoolExecutor(max_workers=6) as ex:
            found = list(ex.map(rosters_for, need))
        n = 0
        for row, extra in zip(need, found):
            if extra:
                row.update(extra)
                n += 1
                print(f"  {row['institution'][:34]:36} "
                      f"{' '.join(sorted(extra))}")
        print(f"\n  {n} of {len(need)} gained a roster")
        if not a.dry_run and n:
            doc["rows"] = rows
            write_text(OUT, json.dumps(doc, indent=1))
            print(f"  wrote {OUT.relative_to(ROOT)}")
        return 0

    todo = [r for r in rows if r.get("status") != "ok"
            and (not a.sector or r.get("sector") == a.sector)
            and r.get("sector") in FIELD_WORDS][: a.limit]
    print(f"Reading department indexes for {len(todo)} unresolved rows")

    with ThreadPoolExecutor(max_workers=6) as ex:
        results = list(ex.map(
            lambda r: discover(r["institution"], r["sector"]), todo))

    hits = [x for x in results if x]
    for h in hits:
        print(f"  FOUND {h['sector']:10} {h['institution'][:34]:36} "
              f"{h['link_text'][:34]:36} {h['url'][:46]}")
    print(f"\n  {len(hits)} of {len(todo)} resolved by reading the index")

    if a.dry_run or not hits:
        return 0

    by_key = {(r["institution"], r["sector"]): r for r in rows}
    for h in hits:
        row = by_key.get((h["institution"], h["sector"]))
        if row is not None:
            row.update(h)
    doc["rows"] = rows
    write_text(OUT, json.dumps(doc, indent=1))
    print(f"  wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
