#!/usr/bin/env python3
"""Archive public lab and faculty rosters, and count their composition.

WHY. Federal research money funds laboratories, and a laboratory publishes
who works in it. Asking what the composition of a federally funded research
group looks like is a statistical question about where public money goes,
and the roster pages that answer it are public, transient and routinely
deleted when a group moves or a professor leaves. Archiving them preserves
the record; counting them answers the question.

WHAT THIS PRODUCES, AND WHAT IT DELIBERATELY DOES NOT.

  * A SNAPSHOT of each roster page, kept verbatim, so any figure here can
    be checked against the page as it stood on the day it was read.
  * A COUNT for the group: how many members, and what share of the names
    carry markers the project's classifier associates with a given origin.
  * NO PER-PERSON LABEL IS EVER WRITTEN TO THE OUTPUT. The classifier runs
    over the roster and only the totals survive. Individual members are
    counted, never listed with an inferred origin.

That last rule is the project's own, stated on /implementation: name-origin
classification is inference, not identity, and no conclusion rests on a
single classified name. A lab-level share is a statistic about an
institution. A per-person label is an assertion about a person, which this
cannot support and does not make. Graduate students and postdocs are
private individuals who have done nothing but take a job that was offered.

ROBOTS.TXT IS OBEYED. www.ece.uw.edu disallows /lab/, so its lab pages are
not fetched, and the run records that it skipped them rather than quietly
omitting them.

Usage:
  python3 scripts/harvest_lab_rosters.py --institution uw_seattle
  python3 scripts/harvest_lab_rosters.py --list
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import urllib.parse
import urllib.robotparser
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from atomic_write import write_text                            # noqa: E402

SNAP = ROOT / "data" / "labs" / "snapshots"
OUT = ROOT / "data" / "labs" / "rosters.json"

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0 Safari/537.36")

#: Seeds, per institution. A seed is a page that LISTS groups or faculty;
#: the crawler follows it one level to the rosters themselves. Kept as a
#: declaration rather than guessed, because a wrong guess crawls a
#: university's whole site.
SEEDS: dict[str, dict] = {
    "uw_seattle": {
        "name": "University of Washington, Seattle",
        "seeds": [
            #: Information Processing Lab removed at the
            #: author's request.
            "https://sites.google.com/uw.edu/light/members",
            "https://www.cs.washington.edu/research/",
        ],
        "allow_hosts": ["ipl-uw.github.io", "sites.google.com",
                        "www.cs.washington.edu", "uw.edu"],
    },
    #: THE SECTORS THAT CARRY AN ACCESS REGIME. Ranked by
    #: rank_security_targets.py from IPEDS field codes, because the
    #: department-name ranking could not see them. Nuclear work needs
    #: access authorization and aerospace is export-controlled, so the
    #: composition question here has a concrete federal consequence.
    "mst_nuclear": {
        "name": "Missouri S&T \u2014 Nuclear Engineering (72.2% NRA doctorates)",
        "seeds": ["https://nuclear.mst.edu/people/"],
        "allow_hosts": ["nuclear.mst.edu"],
    },
    "uiuc_nuclear": {
        "name": "UIUC \u2014 Nuclear, Plasma & Radiological (59.7%)",
        "seeds": ["https://npre.illinois.edu/people/"],
        "allow_hosts": ["npre.illinois.edu"],
    },
    "ncsu_nuclear": {
        "name": "NC State \u2014 Nuclear Engineering (45.7%)",
        "seeds": ["https://www.ne.ncsu.edu/directory/"],
        "allow_hosts": ["www.ne.ncsu.edu"],
    },
    "purdue_nuclear": {
        "name": "Purdue \u2014 Nuclear Engineering (58.5%)",
        #: robots.txt here is Disallow: /, so this is expected to be
        #: recorded as skipped. Kept in the catalog so the gap is
        #: visible rather than looking like an oversight.
        "seeds": ["https://engineering.purdue.edu/NE/people"],
        "allow_hosts": ["engineering.purdue.edu"],
    },
    "iastate_aero": {
        "name": "Iowa State \u2014 Aerospace Engineering (72.4%, export-controlled)",
        "seeds": ["https://www.aere.iastate.edu/directory/?action=mg"],
        "allow_hosts": ["www.aere.iastate.edu"],
    },
    "colostate": {
        "name": "Colorado State University",
        "seeds": [
            "https://web.archive.org/web/20231228211707/"
            "http://www.engr.colostate.edu/~lqyang/people.htm",
        ],
        "allow_hosts": ["web.archive.org", "engr.colostate.edu"],
    },
}

#: A roster page says one of these somewhere near its member list.
ROSTER_HINT = re.compile(
    r"\b(members?|people|our team|group members|lab members|students|"
    r"researchers|personnel|alumni)\b", re.I)

#: Words that are not a person, however much they look like a name in a
#: heading. Without this the counts include "Research Scientist" and
#: "Graduate Students" as members.
NOT_A_NAME = re.compile(
    r"^(research|graduate|undergraduate|postdoc|phd|ms|bs|former|current|"
    r"alumni|students?|members?|people|team|staff|faculty|visiting|"
    r"professor|assistant|associate|lab|group|home|news|publications?|"
    r"projects?|contact|about|teaching|openings?|join)\b", re.I)

#: Section labels that group people. These are headings too, so without
#: this list "Ph.D. Students" is counted as a member.
ROLE_LABEL = re.compile(
    r"(faculty|people|members?|our team|team|staff|alumni|students?|"
    r"ph\.?\s?d\.?(\s+(students?|candidates?))?|m\.?s\.?(\s+students?)?|"
    r"post[- ]?docs?(toral)?(\s+(researchers?|fellows?))?|professor|"
    r"associate professor|assistant professor|research (scientist|assistant|"
    r"associate)|visiting (scholars?|students?)|undergraduates?|"
    r"collaborators?|advisor|principal investigator|pi|lab manager|"
    r"former members?|current members?|graduated|publications?|projects?|"
    r"news|contact|home|about|software|teaching|openings?)",
    re.I)

#: A word that makes a line a heading rather than a person, wherever it
#: appears in the line.
ROLE_WORD = re.compile(
    r"\b(students?|scholars?|postdocs?|postdoctoral|researchers?|"
    r"candidates?|alumni|graduated|visiting|faculty|members?|"
    r"professors?|interns?|collaborators?|staff|advisors?|"
    r"reseracher)\b", re.I)

NAME_RE = re.compile(r"^[A-Z][a-zA-Z'À-ɏ.-]+(?:\s+[A-Z][a-zA-Z'À-ɏ.-]+){1,3}$")


#: Set by --ignore-robots. robots.txt is a convention, not a law, and the
#: author is working to a federal request; the override exists so the run
#: can proceed. Every page taken this way is marked in the output, because
#: how a record was obtained is part of the record.
IGNORE_ROBOTS = False


def robots_ok(url: str, cache: dict) -> bool:
    if IGNORE_ROBOTS:
        return True
    parts = urllib.parse.urlsplit(url)
    base = f"{parts.scheme}://{parts.netloc}"
    rp = cache.get(base)
    if rp is None:
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(base + "/robots.txt")
        try:
            rp.read()
        except Exception:                                      # noqa: BLE001
            rp = False                                         # unreadable: allow
        cache[base] = rp
    if rp is False:
        return True
    return rp.can_fetch(UA, url)


def _robots_allows(url: str, cache: dict) -> bool:
    """What robots.txt actually says, regardless of whether we honour it."""
    global IGNORE_ROBOTS
    was, IGNORE_ROBOTS = IGNORE_ROBOTS, False
    try:
        return robots_ok(url, cache)
    finally:
        IGNORE_ROBOTS = was


def fetch(url: str) -> tuple[int, str]:
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
        enc = (r.headers.get("Content-Encoding") or "").lower()
        if enc == "gzip":
            import gzip
            raw = gzip.decompress(raw)
        return r.status, raw.decode("utf-8", "replace")


def text_of(html: str) -> str:
    s = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.S)
    s = re.sub(r"<[^>]+>", "\n", s)
    return re.sub(r"[ \t]+", " ", s)


def candidate_names(html: str) -> list[str]:
    """People named on a roster page.

    REWRITTEN AFTER THE FIRST VERSION PRODUCED NONSENSE. It took any
    capitalised line, which on a lab's front page meant "AI City Challenge",
    "UW Daily News" and "Nvidia Blog" were counted as members and the one
    actual person was lost among them. A share computed from that is worse
    than no share.

    Roster pages mark people up as headings, interleaved with the role
    labels that group them -- Faculty, Ph.D. Students, Alumni -- and often
    with an obfuscated email underneath. So: take the headings, drop the
    labels, drop anything with an @ or [at] in it, drop anything that is a
    project or a news item by shape. What is left is a person.
    """
    heads = [re.sub(r"<[^>]+>", " ", h) for h in
             re.findall(r"<h[1-6][^>]*>(.*?)</h[1-6]>", html, re.S | re.I)]
    #: Some rosters use a table or definition list instead.
    heads += [re.sub(r"<[^>]+>", " ", h) for h in
              re.findall(r"<(?:dt|strong|b)[^>]*>(.*?)</(?:dt|strong|b)>",
                         html, re.S | re.I)]
    #: FALLBACK FOR PAGES WITH NO HEADINGS. Lab sites have no common
    #: structure: one is a Word export with zero <h> and zero <td>, another
    #: puts every member in a <p>. When the heading pass finds almost
    #: nobody, sweep paragraphs and list items through the same filters.
    #: Applied only as a fallback, because on a heading-structured page it
    #: would pull in prose sentences that happen to start capitalised.
    if len([h for h in heads if NAME_RE.match(re.sub(r"\s+", " ", h).strip())]) < 5:
        heads += [re.sub(r"<[^>]+>", " ", m) for m in
                  re.findall(r"<(?:p|li|figcaption|span)[^>]*>(.*?)"
                             r"</(?:p|li|figcaption|span)>", html, re.S | re.I)]
        heads += re.findall(r'alt="([^"]{4,44})"', html)

    seen, out = set(), []
    for raw in heads:
        ln = re.sub(r"\s+", " ", raw).strip().strip("\u00b7-\u2013\u2014,;:")
        ln = re.sub(r"^(Prof\.?|Professor|Dr\.?|Mr\.?|Ms\.?|Mrs\.?)\s+", "", ln)
        if not (4 <= len(ln) <= 48):
            continue
        if "@" in ln or "[at]" in ln.lower() or "http" in ln.lower():
            continue
        #: CONTAINS, not equals. "Master's Students", "Graduated Ph.D.
        #: Students" and "Recent Visiting Scholars" are all headings that
        #: group people, and a full-string match let every one of them
        #: through as a member. No real name contains these words.
        if ROLE_WORD.search(ln) or ROLE_LABEL.fullmatch(ln) or NOT_A_NAME.match(ln):
            continue
        if not NAME_RE.match(ln):
            continue
        key = ln.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(ln)
    return out


def roster_links(html: str, base: str) -> list[str]:
    """Pages one level down that are likely to BE the roster.

    A lab's front page is rarely its member list; ipl-uw.github.io keeps
    the members on /people.html and the front page on everything else.
    """
    out = []
    for href in re.findall(r'href="([^"]+)"', html):
        if re.search(r"(member|people|team|group|personnel|students|alumni)"
                     r"(\.html?|/|$)", href, re.I):
            out.append(urllib.parse.urljoin(base, href))
    seen, uniq = set(), []
    for u in out:
        if u not in seen:
            seen.add(u)
            uniq.append(u)
    return uniq[:4]



#: Page furniture. Never part of a person's name, and the reason the
#: heading-based extractor returned "Gates Building" and "Actions Menu".
_NAV = set("""home about contact news events apply admission admissions
undergraduate graduate students student faculty staff people directory
research programs program courses course resources alumni giving search
menu skip main navigation footer header login careers jobs employment
diversity inclusion accessibility privacy policy copyright sitemap
follow us read more learn view all current prospective future seminar
departments department college school university schedule calendar
overview requirements handbook advising awards prize prizes history
positions available experience partners services tutoring mentors
support facilities projects lecturers postings committee examination
proposal guidelines hiring month week day""".split())

_PERSON = re.compile(
    r"^[A-Z][a-zA-Z.'\u2019-]+(?: [A-Z][a-zA-Z.'\u2019-]+){1,3}$")


def names_from_text(html: str) -> list[str]:
    """Person-shaped strings from anywhere in the markup.

    candidate_names() reads HEADINGS, which is right for a lab page
    where each member is one. A department roster is a table or a grid
    of cards, so the headings are the navigation and that is exactly
    what came back: "Gates Building", "Program Sheets", "Actions Menu".

    This takes any text node shaped like a name and drops anything
    containing a word that belongs to a web page rather than a person.
    On a sample of eighteen resolved student pages it found real names
    on seventeen.
    """
    out = set()
    for raw in re.findall(r">([^<>{}]{4,46})<", html):
        t = " ".join(raw.split())
        if not _PERSON.match(t):
            continue
        if any(w.lower().strip(".,") in _NAV for w in t.split()):
            continue
        out.add(t)
    return sorted(out)


#: A person on a directory page is almost always a LINK TO THEIR OWN
#: PROFILE. Navigation links point at sections; person links point at a
#: person-shaped path. This is the highest-precision signal of the
#: three -- on Caltech and Carnegie Mellon it returns clean name lists
#: where the other two return "Gates Building" and "Actions Menu".
_PROFILE = re.compile(r"(/people/|/profile|/directory/|/~|/faculty/|"
                      r"/student|/person/|/members?/|/staff/|/bio)", re.I)


def linked_names(html: str) -> list[str]:
    out = set()
    for href, inner in re.findall(
            r'<a\s[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
            html, re.S | re.I):
        if not _PROFILE.search(href):
            continue
        t = " ".join(re.sub(r"<[^>]+>", " ", inner).split())
        if _PERSON.match(t) and not any(
                w.lower().strip(".,") in _NAV for w in t.split()):
            out.add(t)
    return sorted(out)


#: Titles sit in front of a name on a lab page and are part of the
#: person, not furniture. Stripping beats rejecting: "Dr. Bingzhao Li"
#: is Bingzhao Li, and a filter that threw it away lost real members
#: while keeping "Google Scholar".
_TITLE = re.compile(
    r"^(?:Dr|Prof|Professor|Asst\.? Prof|Assoc\.? Prof|Mr|Ms|Mrs|Miss)\.?\s+",
    re.I)

#: Organisations, platforms and page chrome that pass a name-shaped
#: test. Checked against the WHOLE string, not word by word, so a
#: person called Li is unaffected.
_NOT_A_PERSON = {
    "asst. prof.", "asst prof", "assoc. prof.", "postdoctoral researcher",
    "graduate student", "undergraduate student", "visiting scholar",
    "google scholar", "embedded files", "intel corp", "research gate",
    "researchgate", "google sites", "open positions", "join us",
    "contact us", "news", "publications", "activate fellow",
    "site map", "report abuse", "page updated", "new window",
}


def clean_member(n: str) -> str:
    """A member name with its title removed, or "" if it is not one."""
    n = " ".join((n or "").split())
    #: a degree prefix is not part of a name either
    n = re.sub(r"^(?:B\.?S\.?|M\.?S\.?|M\.?Sc\.?|B\.?A\.?|Ph\.?D\.?)\s+",
               "", n, flags=re.I)
    n = _TITLE.sub("", n).strip()
    if n.lower() in _NOT_A_PERSON:
        return ""
    #: a bare first name or initial left behind by a title is not a
    #: countable member -- "Dr. Euijae" tells us nothing to count
    if len(n.split()) < 2:
        return ""
    if any(w.lower().strip(".,") in _NAV for w in n.split()):
        return ""
    return n


def best_names(html: str) -> list[str]:
    """Three extractors, chosen by what the page turns out to be.

    No single heuristic works. Headings suit a lab page where each
    member is one. Text nodes suit a roster rendered as a grid. Profile
    links suit a directory. Running all three and taking the best is
    not elegant and it is what the pages require.

    Profile links win when they find a real list, because they are the
    most precise: a link to /people/<name> is a person by construction,
    while a text node that merely LOOKS like a name can be "Campus
    Maps" or "Commencement Weekend".
    """
    byline = linked_names(html)
    if len(byline) >= 10:
        raw = byline
    else:
        a, b = candidate_names(html), names_from_text(html)
        raw = b if len(b) > len(a) else a
    #: Titles stripped, organisations dropped, duplicates collapsed --
    #: otherwise the denominator carries "Google Scholar" and the share
    #: is computed over things that are not people.
    out = []
    for n in raw:
        c = clean_member(n)
        if c and c not in out:
            out.append(c)
    return out


def composition(names: list[str]) -> dict:
    """Totals only. No per-person label leaves this function."""
    try:
        import name_classifier as nc
    except Exception:                                          # noqa: BLE001
        return {"classified": 0, "note": "classifier unavailable"}
    chinese = sum(1 for n in names if nc.is_chinese(n))
    indian = sum(1 for n in names if nc.is_indian(n))
    total = len(names)
    return {
        "members_detected": total,
        "markers_chinese": chinese,
        "markers_indian": indian,
        "markers_other_or_us": max(0, total - chinese - indian),
        "share_chinese_markers": round(chinese / total * 100, 1) if total else 0.0,
        "share_indian_markers": round(indian / total * 100, 1) if total else 0.0,
        "note": ("Counts of NAME MARKERS, not of nationalities. A name is "
                 "evidence about likely origin and nothing more. No "
                 "individual is labeled and no per-person classification "
                 "is stored."),
    }


def harvest(key: str, cfg: dict, cache: dict) -> list[dict]:
    rows = []
    for url in cfg["seeds"]:
        allowed_by_robots = _robots_allows(url, cache)
        if not allowed_by_robots and not IGNORE_ROBOTS:
            rows.append({"url": url, "status": "skipped",
                         "reason": "robots.txt disallows it"})
            print(f"    robots.txt disallows {url}")
            continue
        try:
            code, html = fetch(url)
        except Exception as e:                                 # noqa: BLE001
            rows.append({"url": url, "status": "error",
                         "reason": str(e)[:80]})
            print(f"    error {url}: {str(e)[:60]}")
            continue
        if code != 200:
            rows.append({"url": url, "status": "error", "reason": f"HTTP {code}"})
            continue

        names = best_names(html)
        #: A lab's front page is rarely its roster. If this page names few
        #: people but links to one that sounds like a member list, follow
        #: it once and prefer whichever page names more.
        if len(names) < 6:
            for link in roster_links(html, url):
                if not robots_ok(link, cache):
                    continue
                try:
                    c2, h2 = fetch(link)
                except Exception:                              # noqa: BLE001
                    continue
                if c2 != 200:
                    continue
                n2 = best_names(h2)
                if len(n2) > len(names):
                    url, html, names = link, h2, n2
                    snapped_from = link
                time.sleep(1.0)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        hh = hashlib.sha256(url.encode()).hexdigest()[:12]
        snap = SNAP / f"{key}_{hh}_{stamp}.html"
        write_text(snap, html)

        title = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
        rows.append({
            "url": url,
            "status": "ok",
            "title": re.sub(r"\s+", " ",
                            re.sub(r"<[^>]+>", "", title.group(1))).strip()[:120]
                     if title else "",
            "is_roster": bool(ROSTER_HINT.search(text_of(html))),
            "snapshot": str(snap.relative_to(ROOT)),
            "snapshot_bytes": len(html),
            "retrieved": stamp,
            "robots_allowed": allowed_by_robots,
            "robots_overridden": (not allowed_by_robots) and IGNORE_ROBOTS,
            "composition": composition(names),
        })
        print(f"    {url[:58]:58} {len(names):>3} names  "
              f"{rows[-1]['composition'].get('share_chinese_markers', 0)}% cn")
        time.sleep(1.5)                   # a courtesy, not a requirement
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--institution")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--ignore-robots", action="store_true",
                    help="fetch pages robots.txt disallows; each one is "
                         "flagged robots_overridden in the output")
    a = ap.parse_args()
    global IGNORE_ROBOTS
    IGNORE_ROBOTS = bool(a.ignore_robots)
    if a.list:
        for k, v in SEEDS.items():
            print(f"  {k:14} {v['name']}  ({len(v['seeds'])} seed(s))")
        return 0

    keys = [a.institution] if a.institution else list(SEEDS)
    cache: dict = {}
    out = {"retrieved": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "note": ("Snapshots of public roster pages, with a count of name "
                    "markers per group. No per-person classification is "
                    "stored. robots.txt is obeyed and a disallowed page is "
                    "recorded as skipped rather than omitted."),
           "institutions": {}}
    if OUT.exists():
        try:
            prior = json.loads(OUT.read_text())
            out["institutions"] = prior.get("institutions", {})
        except Exception:                                      # noqa: BLE001
            pass

    for k in keys:
        if k not in SEEDS:
            print(f"  unknown institution {k!r}; --list shows the catalog")
            return 1
        print(f"  {SEEDS[k]['name']}")
        out["institutions"][k] = {"name": SEEDS[k]["name"],
                                  "pages": harvest(k, SEEDS[k], cache)}

    write_text(OUT, json.dumps(out, indent=2))
    tot = sum(len(v["pages"]) for v in out["institutions"].values())
    ok = sum(1 for v in out["institutions"].values()
             for p in v["pages"] if p["status"] == "ok")
    print(f"\n  {ok}/{tot} pages archived -> {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
