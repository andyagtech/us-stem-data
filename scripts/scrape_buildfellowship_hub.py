#!/usr/bin/env python3
"""Archive the Build Fellowship project listings.

Each project page names the fellow, the role they hold, and the COMPANY they
hold it at. That last field is the one no government dataset carries: USCIS
counts petitions from affiliated nonprofits without naming an employer, and
the Employer Data Hub names the nonprofit rather than the firm the fellow
actually works for. The organisation publishes the link itself.

The pages are server-rendered, so plain HTTP is enough; no browser is needed
for 243 pages. Fetches are cached to disk and rate-limited, and a re-run only
retrieves what is missing.

robots.txt was checked: it disallows /admin and /survey. /projects is
permitted.

WHAT THIS IS. A record of what the organisation publishes about its own
programme, captured at a point in time. It carries no visa status: a listing
says a named person leads a project at a named company, not what authorisation
they hold. Do not read a fellow's presence here as evidence of a petition.

Usage:
  python3 scripts/scrape_buildfellowship_hub.py --links      # refresh the index
  python3 scripts/scrape_buildfellowship_hub.py              # fetch and parse
  python3 scripts/scrape_buildfellowship_hub.py --parse-only # reparse the cache
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "buildfellowship" / "projects"
LINKS = ROOT / "data" / "buildfellowship" / "project_links.json"
OUT = ROOT / "data" / "buildfellowship" / "projects.json"
BASE = "https://hub.buildfellowship.com"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120 Safari/537.36")
DELAY = 0.7          # polite; 243 pages is a few minutes


def fetch(url: str, dest: Path) -> bool:
    r = subprocess.run(["curl", "-sL", "--max-time", "45", "-A", UA, "-o", str(dest), url],
                       capture_output=True, text=True)
    return r.returncode == 0 and dest.exists() and dest.stat().st_size > 2000


def refresh_links() -> int:
    """Enumerate every project from the listing, which is infinite-scrolled."""
    from playwright.sync_api import sync_playwright
    seen: set[str] = set()
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_context(viewport={"width": 1400, "height": 1000}).new_page()
        pg.goto(f"{BASE}/projects", wait_until="domcontentloaded", timeout=60000)
        pg.wait_for_timeout(5000)
        stable = 0
        for _ in range(60):
            before = len(seen)
            seen.update(h for h in pg.eval_on_selector_all(
                "a[href*='/projects/']", "els => els.map(e => e.getAttribute('href'))")
                if h and h.count("/") >= 2)
            pg.mouse.wheel(0, 4000)
            pg.wait_for_timeout(800)
            stable = stable + 1 if len(seen) == before else 0
            if stable >= 4:
                break
        body = pg.inner_text("body")
        b.close()
    m = re.search(r"([\d,]+)\s+projects", body, re.I)
    stated = int(m.group(1).replace(",", "")) if m else None
    LINKS.parent.mkdir(parents=True, exist_ok=True)
    LINKS.write_text(json.dumps(
        {"stated_total": stated, "captured": len(seen), "links": sorted(seen)}, indent=1) + "\n")
    print(f"  page states {stated} projects; captured {len(seen)}")
    if stated and len(seen) != stated:
        print("  WARNING: capture does not match the stated total")
    return 0


def flight_blob(html: str) -> str:
    """Decode the Next.js flight payload.

    The pages LOOK server-rendered -- curl returns the company name, which is
    why plain HTTP was chosen -- but the text sits inside self.__next_f script
    pushes, not in markup. Stripping <script> first, which is the normal thing
    to do, left exactly one visible line: the site title. Every one of 243
    pages parsed to nothing.
    """
    chunks = re.findall(r'self\.__next_f\.push\(\[1,"((?:[^"\\]|\\.)*)"\]\)', html)
    out = []
    for c in chunks:
        try:
            out.append(json.loads('"' + c + '"'))
        except json.JSONDecodeError:
            continue
    return "".join(out)


def resolve_refs(blob: str) -> dict[str, str]:
    """Map flight string ids to their text.

    Long strings are not inlined: the payload defines them separately as
    "<id>:T<hex length>,<text>" and the object carries "$<id>" in their place.
    Read without resolving, every long bio came back as the literal "$1a".
    The length prefix is authoritative -- the text contains commas and
    newlines, so it cannot be delimited by scanning.
    """
    out: dict[str, str] = {}
    # Definitions are not always at a line start: some are run together with
    # the preceding chunk ("...fer!1b:T44c,"). Anchoring on "\n" left six
    # bios unresolved. A lookbehind for a non-alphanumeric character keeps the
    # id from matching the tail of a longer token.
    for m in re.finditer(r"(?<![0-9a-zA-Z])([0-9a-f]{1,4}):T([0-9a-f]+),", blob):
        try:
            n = int(m.group(2), 16)
        except ValueError:
            continue
        start = m.end()
        out[m.group(1)] = blob[start:start + n]
    return out


def deref(value, refs: dict[str, str]):
    """Replace "$id" placeholders anywhere in a parsed structure."""
    if isinstance(value, str):
        if value.startswith("$") and value[1:] in refs:
            return refs[value[1:]]
        return value
    if isinstance(value, list):
        return [deref(v, refs) for v in value]
    if isinstance(value, dict):
        return {k: deref(v, refs) for k, v in value.items()}
    return value


def balanced(blob: str, start: int) -> str | None:
    """The JSON object beginning at `start`, respecting strings and escapes."""
    depth, in_str, esc = 0, False, False
    for i in range(start, min(len(blob), start + 200_000)):
        ch = blob[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return blob[start:i + 1]
    return None


def parse(slug: str, html: str) -> dict:
    """Pull the project object out of the flight payload."""
    blob = flight_blob(html)
    refs = resolve_refs(blob)
    project = None
    for m in re.finditer(r'\{"id"|\{"title"|\{"slug"', blob):
        raw = balanced(blob, m.start())
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and obj.get("title") and "fellows" in obj:
            project = deref(obj, refs)
            break
    if project is None:
        return {"slug": slug}

    fellows = []
    for f in project.get("fellows") or []:
        if isinstance(f, dict):
            fellows.append({k: f.get(k) for k in
                            ("name", "role", "organization", "bio", "linkedinUrl")})
    return {
        "slug": slug,
        "url": f"{BASE}/projects/{slug}",
        "title": project.get("title"),
        "summary": project.get("summary"),
        "status": project.get("status"),
        "project_area": project.get("project_area"),
        "categories": project.get("categories"),
        "level": project.get("level"),
        "duration": project.get("duration"),
        "schedule": project.get("schedule"),
        "cycle_id": project.get("cycle_id"),
        "application_timeline": project.get("applicationTimeline"),
        # description is a string on most projects and a rich-text dict on
        # others; keep whichever, truncated only when it is text.
        "description": (lambda d: d[:1500] if isinstance(d, str) else d)(
            project.get("description")),
        "goals": project.get("goals"),
        "prerequisites": project.get("prerequisites"),
        "fellows": fellows,
        # `organization` is almost always the nonprofit itself. The firm the
        # fellow actually works for is named in their bio prose, so it is
        # extracted separately and kept apart from the published field.
        "organization": fellows[0]["organization"] if fellows else None,
        "employers_from_bio": employers_from(fellows),
    }


# "X is a <role> at <Employer>, where ..." then "X is a <job> at <Employer>."
# The first clause names the nonprofit, the second the fellow's real employer.
BIO_AT = re.compile(
    r"\bis (?:a|an|the)\s+[^.]{3,70}?\s+at\s+"
    r"([A-Z][\w&.,'\u2019\-/ ]{2,48}?)(?:[,.]|\s+where\b|\s+in\b|$)")
NONPROFIT = re.compile(r"open\s*avenue|build\s+fellow", re.I)


def normalise_employer(name: str) -> str:
    """Fold the spelling variants the bios are written in.

    They are free prose, so the same firm appears as "DREAM Venture Labs" and
    "Dream Venture Labs", and as "Citadel" and "Citadel Securities". Casing is
    folded to a canonical form; genuinely different names are left alone,
    because merging "Citadel" into "Citadel Securities" would be a guess.
    """
    name = re.sub(r"\s+", " ", name).strip(" ,.;:")
    name = re.sub(r"\b(Inc|LLC|Ltd|Corp|Co)\b\.?$", "", name).strip(" ,.")
    return name


def group_employers(records: list[dict]) -> dict[str, int]:
    """Count employers, folding case.

    The bios are prose: "DREAM Venture Labs" and "Dream Venture Labs" are the
    same firm and were being counted as two. Grouping is case-insensitive and
    the commonest spelling is kept for display. Distinct names are NOT merged
    -- rolling "Citadel" into "Citadel Securities" would be a guess about
    which entity a fellow works for.
    """
    variants: dict[str, dict[str, int]] = {}
    for r in records:
        for e in r.get("employers_from_bio") or []:
            v = variants.setdefault(e.casefold(), {})
            v[e] = v.get(e, 0) + 1
    out = {}
    for spellings in variants.values():
        canonical = max(spellings, key=lambda k: (spellings[k], k))
        out[canonical] = sum(spellings.values())
    return out


def employers_from(fellows: list[dict]) -> list[str]:
    out = []
    for f in fellows:
        bio = (f.get("bio") or "").replace("\n", " ")
        for hit in BIO_AT.findall(bio):
            if NONPROFIT.search(hit):
                continue
            e = normalise_employer(hit)
            if len(e) > 2 and e not in out:
                out.append(e)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--links", action="store_true", help="refresh the project index")
    ap.add_argument("--parse-only", action="store_true", help="reparse the cache")
    args = ap.parse_args()

    if args.links:
        return refresh_links()
    if not LINKS.exists():
        print("  no project index; run with --links first")
        return 1

    idx = json.loads(LINKS.read_text())
    slugs = [h.rsplit("/", 1)[-1] for h in idx["links"]]
    CACHE.mkdir(parents=True, exist_ok=True)

    fetched = failed = 0
    if not args.parse_only:
        for i, slug in enumerate(slugs, 1):
            dest = CACHE / f"{slug}.html"
            if dest.exists() and dest.stat().st_size > 2000:
                continue
            if fetch(f"{BASE}/projects/{slug}", dest):
                fetched += 1
            else:
                failed += 1
                dest.unlink(missing_ok=True)
            time.sleep(DELAY)
            if i % 40 == 0:
                print(f"    {i}/{len(slugs)}...")
        print(f"  fetched {fetched}, failed {failed}, "
              f"cached {len(list(CACHE.glob('*.html')))}")

    records, unparsed = [], []
    for slug in slugs:
        p = CACHE / f"{slug}.html"
        if not p.exists():
            unparsed.append(slug)
            continue
        rec = parse(slug, p.read_text(errors="replace"))
        if not rec.get("title"):
            unparsed.append(slug)
            continue
        records.append(rec)

    firms = group_employers(records)
    no_employer = sum(1 for r in records if not r.get("employers_from_bio"))

    OUT.write_text(json.dumps({
        "_comment": ("Build Fellowship project listings, as the organisation "
                     "publishes them. `company` is the firm the fellow works "
                     "for -- the link no government dataset carries. These "
                     "pages record NO visa status: a listing says a named "
                     "person leads a project at a named company, not what "
                     "authorisation they hold. `organization` is the field the "
                     "site publishes and is almost always the nonprofit; "
                     "`employers_from_bio` is extracted from prose and is a "
                     "best effort, not a published field."),
        "source": f"{BASE}/projects",
        "captured": time.strftime("%Y-%m-%d"),
        "stated_total": idx.get("stated_total"),
        "projects_parsed": len(records),
        "unparsed": unparsed,
        "employers": [{"name": k, "projects": v} for k, v in
                      sorted(firms.items(), key=lambda kv: (-kv[1], kv[0]))],
        "projects_naming_no_employer": no_employer,
        "projects": records,
    }, indent=1) + "\n")

    print(f"  parsed {len(records)} of {idx.get('stated_total')} projects; "
          f"{len(unparsed)} unparsed")
    print(f"  distinct employers named in bios: {len(firms)}; "
          f"{no_employer} projects name none")
    for name, n in sorted(firms.items(), key=lambda kv: -kv[1])[:10]:
        print(f"     {n:>3}  {name[:52]}")
    print(f"  wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
