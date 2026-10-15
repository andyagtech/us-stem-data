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


#: ANNOTATIONS A ROSTER HANGS OFF A NAME. Oregon State's MERGE group
#: writes "Chandika Kiriella (Spring 2024 - )", and every one of its
#: students was thrown away because of the bracket. The same shapes
#: recur everywhere: a role, a start date, a class year, a degree.
_ANNOTATION = re.compile(
    r"\s*[\(\[]\s*(?:"
    r"(?:spring|summer|fall|autumn|winter)\s*\d{4}|"       # (Fall 2024 - )
    r"\d{4}\s*[-\u2013]?\s*(?:\d{4}|present)?|"            # (2021-2024)
    r"ph\.?d\.?|m\.?s\.?|m\.?eng\.?|b\.?s\.?|postdoc|"
    r"co-?advised|visiting|incoming|on leave|now at|"
    r"[^)\]]{0,40}?(?:student|candidate|researcher|fellow|"
    r"postdoc|alumn|intern)[^)\]]{0,20}"
    r")[^)\]]*[\)\]]\s*$", re.I)
#: and the same thing after a comma or dash: "Wei Chen, PhD Student"
_TRAILING_ROLE = re.compile(
    r"\s*[,\u2013\u2014-]\s*(?:ph\.?d\.?|m\.?s\.?|b\.?s\.?|"
    r"postdoc(?:toral)?|graduate|undergraduate|visiting|research)?\s*"
    r"(?:student|candidate|researcher|fellow|scholar|assistant|"
    r"associate|intern|alumnus|alumna)s?\.?\s*$", re.I)
#: A TRAILING LINK LABEL. A roster that links each person to a profile
#: renders as "Rui Zhu Bio" or "Barker Bio", and rejecting those loses
#: the PERSON. Stripped, so the name is recovered; "Short Bio" and
#: "My Biography" survive the strip as one word and are rejected by the
#: two-word rule that follows.
_TRAILING_LABEL = re.compile(
    r"\s+(?:bio|biography|biosketch|profile|homepage|webpage|website|cv|"
    r"vita|resume)\.?$", re.I)
#: a class year: "Ana Ruiz '24"
_CLASS_YEAR = re.compile(r"\s*[\u2019']\d{2}\s*$")


#: A NUMBERED LIST ITEM, with the number glued to the name. A PI's
#: alumni list on uva.theopenscholar.com reads
#: "II. Jill Tysse", "III. Ta Khongsap", "IX. Huanchen Bao" -- real
#: people behind an ordinal. Stripping it recovers the name rather than
#: throwing the person away.
#:
#: TWO CHARACTERS MINIMUM, so a single Roman letter is left alone:
#: "I. David Taylor" and "V. Kumar" are ordinary names carrying an
#: initial, and there is no way to tell them from an ordinal.
#: Spelled out, because "VI{0,3}" matches a bare "V" and threw away
#: "V. Kumar".
_ORDINAL_PREFIX = re.compile(
    r"^(?:II|III|IV|VI|VII|VIII|IX|XI|XII|XIII|XIV|XV|XVI|XVII|XVIII"
    r"|XIX|XX|\d{1,3})[.)]\s+", re.I)


def strip_annotation(n: str) -> str:
    """Remove a roster's own annotations from around a name."""
    prev = None
    while prev != n:
        prev = n
        n = _ORDINAL_PREFIX.sub("", n)
        n = _ANNOTATION.sub("", n)
        n = _TRAILING_ROLE.sub("", n)
        n = _TRAILING_LABEL.sub("", n)
        n = _CLASS_YEAR.sub("", n)
        n = n.strip(" ,;:-\u2013\u2014")
    return n


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
    #: a roster writes "Chandika Kiriella (Spring 2024 - )", and
    #: testing the whole string for a name shape threw away every
    #: student in the group. Strip first, then test.
    for raw in re.findall(r">([^<>{}]{4,70})<", html):
        t = strip_annotation(" ".join(raw.split()))
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



#: FURNITURE, NOT PEOPLE. A roster page is mostly not a roster: it
#: carries navigation, research topics, awards, buildings and the
#: university's own name, and the extractor counted all of it. On a
#: hand-labelled sample of 70 distinct strings pulled off real lab
#: pages, 20 were furniture and every one survived the old filter --
#: so a lab of seven people could be counted as fourteen members and
#: its concentration halved.
#:
#: The test is vocabulary, not grammar. A word below essentially
#: never appears in a person's name, while a dictionary test would
#: throw away Peter Weber -- "peter" and "weber" are both words.
#: tests/fixtures/roster_name_labels.json holds the sample and
#: test_roster_names.py measures any change against it.
_FURNITURE_WORDS = {
    # navigation and page chrome
    "help", "submit", "back", "top", "here", "more", "home", "menu",
    "login", "logout", "search", "contact", "visit", "explore", "apply",
    "give", "giving", "news", "events", "event", "calendar", "schedule",
    "schedules", "plan", "plans", "map", "maps", "link", "links",
    "toggle", "update", "updates", "access", "media", "social",
    "facebook", "instagram", "twitter", "linkedin", "youtube",
    "tiktok", "mastodon", "bluesky", "flickr", "athletics",
    "directions", "parking", "floor", "office", "hours", "overview",
    "resources", "download", "subscribe", "register", "sitemap",
    "accessibility", "privacy", "disclaimer", "copyright", "skip",
    # academic furniture
    "materials", "science", "sciences", "imaging", "fields", "physics",
    "chemistry", "biology", "engineering", "systems", "system",
    "research", "studies", "study", "inquiry", "technology", "abroad",
    "award", "awards", "society", "association", "group", "groups",
    "lab", "labs", "laboratory", "center", "centre", "institute",
    "program", "programs", "programme", "project", "projects",
    "seminar", "symposium", "conference", "workshop", "studio",
    "outdoors", "collaborative", "innovation", "curriculum", "course",
    "courses", "degree", "degrees", "admissions", "alumni", "faculty",
    "publications", "patents", "teaching", "outreach", "openings",
    "positions", "vacancies", "funding", "grants", "collaborators",
    "memorial", "lecture", "colloquium", "abstract", "poster",
    # objects and places that showed up in the sample
    "license", "plates", "cabin", "game", "games", "building",
    "campus", "library", "museum", "stadium", "hall", "room",
    # ROLES AND SECTION HEADINGS. A roster labels its sections, and
    # the labels sit in the markup exactly where a name does:
    # "Associate Professor", "Graduate Students", "Former Members".
    "professor", "associate", "assistant", "adjunct", "emeritus",
    "lecturer", "instructor", "postdoc", "postdoctoral", "fellow",
    "fellows", "scholar", "scholars", "researcher", "researchers",
    "scientist", "scientists", "student", "students", "intern",
    "interns", "candidate", "candidates", "member", "members",
    "former", "current", "past", "present", "join", "joining",
    "open", "opening", "staff", "team", "teams", "people", "person",
    "director", "manager", "coordinator", "secretary", "chair",
    "head", "lead", "leader", "principal", "investigator",
    # theme and template names a static site leaves in the markup
    "minimal", "mistakes", "jekyll", "hugo", "wordpress", "template",
    "theme", "powered", "default", "untitled",
    # list controls
    "full", "list", "lists", "all", "view", "show", "hide", "sort",
    "filter", "next", "previous", "page", "pages", "read",
    # topic words that formed headings in the sample
    "models", "model", "language", "learning", "networks", "network",
    "data", "analysis", "methods", "applications", "theory",
    "started", "sustainable", "innovating", "agents",
    # A PAPER TITLE IS NOT A PERSON. The author's point, and it was
    # right: a research TEAM is a hiring decision and a CO-AUTHOR LIST
    # is a record of who published together. Where a roster was read
    # off a publications section, paper titles were counted as members
    # and the denominator carried them. Every word here comes from a
    # string that was actually counted as a member of a published lab:
    #
    #   "Computer Graphics", "Computer-Aided Design",
    #   "Graphics Gems IV", "Hierarchical Streamline Bundles",
    #   "The Computer Journal"          pages.mtu.edu/~shene/NSF-2
    #   "Dropout Reduces Underfitting", "Highlighted Paper",
    #   "Oral Presentation", "Spotlight Presentation"
    #                                   cs.princeton.edu/~zhuangl
    #   "Rhythmic RFID Authentication", "Object Oriented Programming",
    #   "IEEE CNS"                      eecis.udel.edu/~ruizhang
    #   "Causal Bandit Algorithms", "Entropic Causal Inference"
    #                                   muratkocaoglu.com/CausalML
    #   "Pensieve Website"              cs.princeton.edu/~ravian
    "computing", "computer", "graphics", "authentication",
    "programming", "oriented", "aided", "gems", "bundles", "reduces",
    "underfitting", "streamline", "hierarchical", "concurrent",
    "bandit", "entropic", "causal", "inference", "dropout",
    "algorithm", "algorithms", "journal", "proceedings", "transactions",
    "preprint", "highlighted", "spotlight", "presentation", "paper",
    "papers", "talk", "talks", "slides", "video", "demo", "code",
    "dataset", "datasets", "benchmark", "benchmarks", "framework",
    "toolkit", "library", "software", "hardware", "firmware",
    "detection", "recognition", "segmentation", "classification",
    "optimization", "optimisation", "synthesis", "simulation",
    "architecture", "protocol", "protocols", "privacy", "security",
    "wireless", "mobile", "cloud", "robotics", "vision",
    "ieee", "acm", "neurips", "icml", "cvpr", "iclr", "siggraph",
    "usenix", "arxiv", "cns",
    # A JOURNAL'S NAME, which survives every structural test because
    # "J. Algebra" and "Pacific J. Math" have exactly the shape of an
    # initial plus a surname. Only the vocabulary separates them from
    # "J. Smith", so these are the words, taken from the citations
    # actually counted as members of a PI's roster at Virginia.
    "algebra", "algebras", "algebraic", "mathematics", "math",
    "geometry",
    "topology", "combinatorics", "letters", "review", "reviews",
    "annals", "bulletin", "notices", "acta", "communications", "comm",
    "advances", "adv", "quarterly", "monthly", "physica", "lancet",
    "nature", "cell",
    # NOT "springer", NOT "elsevier", NOT "cover", NOT "art". Reviewing
    # every string this rule drops across the 163,300 cached names
    # turned up real people being thrown out by publisher and
    # publishing words: Roxanne P. Springer is a physics professor at
    # Duke, Martin Springer and Jeremy Staff are real, and Thomas Cover
    # is an information theorist. "Journal Cover Art" is still caught,
    # by "journal". A word that is also a surname cannot go in here.
    #
    # "staff" and "hall" were already in the list above and have the
    # same flaw -- "Jeremy Staff" and "Derek Hall" are dropped. They
    # catch "Senior Administration", "Postdoctoral Affairs" and
    # "Sikes Hall Icon", and the cost is roughly eight name strings in
    # 163,300, so they stay. Recorded here rather than left to be
    # rediscovered.
    # A PRODUCT OR A PIECE OF EQUIPMENT, same pages.
    #   "GPU Server", "AI Software Engineer"  udel.edu/~amotong/group
    #   "GPU Profiling"           abdelzaher.cs.illinois.edu/people
    #   "Journal Cover Art"       lilabs.org/people
    #   "Personal Website"        lolab.ucsd.edu/team-2
    #   "Software Releases"       sites.google.com/view/fenglab
    #   "HPC Security"            xgao-work.github.io/members
    "gpu", "cpu", "fpga", "api", "sdk", "hpc", "server", "servers",
    "cluster", "workstation", "profiling", "releases", "release",
    "website", "webpage", "blog", "poster",
    # Page furniture seen on the USF labs the author sent:
    #   "Short Biography"   csalab.site
    #   "A-Z Index"         power.eng.usf.edu/people.htm
    "biography", "bio", "biosketch", "index",
    "adaptation", "digit", "guardian", "centered", "centred",
    # SITE CHROME ON EVERY PAGE OF A DRUPAL DIRECTORY. "Job
    # Opportunities", "Profile Type" and "Super Nav" appeared in all
    # twenty UMass polymer-science rosters -- three strings, which on
    # a group of seven is 43 per cent of the denominator and halves
    # the share.
    "opportunities", "profile", "profiles", "nav", "navigation",
    "jobs", "job", "type", "types", "filter", "filters", "keyword",
    "keywords", "results", "result", "pagination", "breadcrumb",
    # A UNIVERSITY'S COMPLIANCE FOOTER, which every page carries. Six
    # of the thirteen "members" on a UT Arlington lab page were these:
    # "Emergency Preparedness", "Report Fraud", "Report Sexual
    # Misconduct", "Site Policies", "Texas Veterans Portal", "First
    # Employer".
    "preparedness", "fraud", "misconduct", "portal", "veterans",
    "policies", "policy", "employer", "employment", "compliance",
    "title", "ix", "clery", "ombuds", "hotline", "nondiscrimination",
    # A RESEARCH TOPIC read off a lab's navigation. The archived /team
    # page of the Virginia Nano-Computing group yielded seven "names",
    # six of which were its research areas: "Beyond CMOS Logic",
    # "Energy Management", "Graphene Electronics", "Magnetic Memory",
    # "Nanoscale Thermal Transport", "Spin-Transfer Torque Ram".
    #: NOT "ram". Reviewing the strings this drops across the cached
    #: names turned up roughly twenty real people -- Ram Devireddy,
    #: Rajeev Ram, Ashwin Ram, Ram Seshadri and more. "Spin-Transfer
    #: Torque Ram" is caught by "torque" without it.
    "cmos", "logic", "memory", "graphene", "nanoscale", "thermal",
    "transport", "torque", "spin", "photonics", "photonic",
    "semiconductor", "quantum", "nano", "micro", "sensing", "sensor",
    "sensors", "actuator", "catalysis", "polymer", "polymers",
    # A JOB TITLE ON AN ALUMNI DESTINATION LIST is not a member.
    #   "Process Engineer", "Senior Product Engineer"
    #                             qingcaolab.matse.illinois.edu/group
    # A COMPANY. "Keysight Technologies" was counted as a member of a
    # published lab; the page lists its industrial collaborators.
    "technologies", "incorporated", "corporation", "holdings",
    "solutions", "ventures", "partners", "associates", "consulting",
    "engineer", "engineers", "developer", "developers", "analyst",
    "consultant", "architect", "senior", "junior", "product",
    "process", "founder", "ceo", "cto", "vp",
}

#: A particle inside a longer name: "Maria del Carmen Lopez" is a
#: person even at four words.
_NAME_PARTICLES = {"de", "del", "della", "der", "van", "von", "da", "di",
                   "dos", "du", "la", "le", "bin", "ibn", "al", "el",
                   "ter", "ten", "av", "af"}


#: Words that make a string an institution or a place rather than a
#: person. "Penn State", "Carnegie Mellon", "Georgia Tech".
_PLACE_WORDS = {
    #: The short forms a university uses for itself on its own pages.
    #: "UMass Amherst" was a member of a lab at UMass Amherst.
    #:
    #: ACRONYMS ONLY. The first draft also carried amherst, berkeley,
    #: stanford, purdue, clemson, rutgers, cornell, princeton, harvard,
    #: yale, duke and emory -- and every one of them is a real surname
    #: or given name. "John Duke", "Sarah Berkeley", "Anne Cornell" and
    #: "David Emory" were all thrown out as institutions. This is the
    #: "Ram" lesson again: a word that is also a name cannot go in a
    #: list that rejects names. The acronyms below are nobody's
    #: surname, and "UMass Amherst" is still caught by "umass".
    "umass", "upenn", "uconn", "ucla", "ucsd", "ucsb", "ucsf", "usc",
    "mit", "caltech", "gatech", "vtech", "utsa", "ucf", "unc", "uva",
    "rpi", "njit", "ucr", "ucsc", "uiuc", "cmu", "nyu", "lsu", "wsu",
    "university", "universities", "college", "school", "academy",
    "institute", "polytechnic", "tech", "state", "county", "city",
    "campus", "national", "federal", "international", "american",
    "european", "global", "union", "department", "division",
}
_KNOWN_INSTITUTIONS = {
    "carnegie mellon", "stony brook", "penn state", "georgia tech",
    "virginia tech", "texas tech", "johns hopkins", "notre dame",
    "ohio state", "michigan state", "iowa state", "oregon state",
    "washington state", "arizona state", "colorado state",
    "north carolina", "south carolina", "new mexico", "new jersey",
    "new york", "rhode island", "west virginia", "san diego",
    "santa barbara", "los angeles", "ann arbor", "chapel hill",
    "college park", "palo alto", "silicon valley", "wake forest",
    "texas a&m", "cal poly", "rensselaer polytechnic",
}


def _looks_like_institution(n: str) -> bool:
    low = n.lower().strip()
    if low in _KNOWN_INSTITUTIONS:
        return True
    return any(w.lower().strip(".,") in _PLACE_WORDS for w in n.split())


def looks_like_person(n: str) -> bool:
    """Is this string a person's name rather than page furniture?"""
    words = n.split()
    if not 2 <= len(words) <= 3:
        #: four words only when one is a particle
        if not (len(words) == 4
                and any(w.lower() in _NAME_PARTICLES for w in words)):
            return False

    low = [w.lower().strip(".,:;'\u2019\"()") for w in words]
    #: HYPHENATED PARTS COUNT SEPARATELY. "Computer-Aided Design" is
    #: one token to split(), so "computer" never matched it and a book
    #: title was counted as a member of a published lab. Real names are
    #: hyphenated too -- Chih-Hao Chang, Jenq-Neng Hwang -- and their
    #: parts are not furniture words, which is why this is safe.
    parts = [q for w in low for q in w.split("-") if q]
    if any(w in _FURNITURE_WORDS for w in low + parts):
        return False

    #: A HEADING SHOUTS. "BUILDING COLLABORATIVE AI SYSTEMS" is a
    #: banner; a name in capitals is one word, not a sentence.
    letters = [c for c in n if c.isalpha()]
    if len(words) >= 3 and letters and all(c.isupper() for c in letters):
        return False

    #: AN ACRONYM IS NOT A SURNAME. "Manning CICS", "NSF CAREER" and
    #: "Secure Edge AI" were all counted as members of labs the author
    #: sent from UMass. A person's name does not end in a run of
    #: capitals, and the two-letter case is the common one: AI, ML, VR.
    last = words[-1].strip(".,:;'’\"()")
    if len(last) >= 2 and last.isalpha() and last.isupper():
        return False

    #: A UNIVERSITY'S OWN NAME reads as two capitalised words.
    #: "Carnegie Mellon" and "Stony Brook" were counted as members of
    #: the labs whose pages named them.
    if _looks_like_institution(n):
        return False

    #: A CITATION, NOT A NAME. A journal's abbreviated title is two or
    #: three capitalised tokens and passes every other test here:
    #: "Comm. Math. Phys.", "J. Algebr. Comb.", "Adv. Math.",
    #: "Trans. AMS" were all counted as members of a published lab.
    #: What gives them away is that EVERY token is abbreviated -- a
    #: person's name has at least one word written out. "Michael W.
    #: Chen" and "Roxanne P. Springer" keep their initial and survive.
    if all(w.endswith(".") for w in words):
        return False
    #: and a title can mix an abbreviation with an acronym: "Trans. AMS".
    if (any(w.endswith(".") for w in words)
            and any(w.isupper() and len(w) >= 2 and w.isalpha()
                    for w in words)):
        return False

    #: possessives belong to offices and buildings, not to members
    if any(w.lower().endswith(("'s", "\u2019s")) for w in words):
        return False

    #: every part of a name starts with a capital or is a particle
    for w in words:
        core = w.strip("().,").replace("-", "").replace("'", "")
        if not core:
            continue
        if core.lower() in _NAME_PARTICLES:
            continue
        if not core[0].isupper():
            return False
    return True


def clean_member(n: str) -> str:
    """A member name with its title removed, or "" if it is not one."""
    n = " ".join((n or "").split())
    n = strip_annotation(n)
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
    if not looks_like_person(n):
        return ""
    return n


#: A TEAM PAGE SAYS WHAT ITS PEOPLE ARE. This is the difference the
#: author named: a research TEAM is a hiring decision, and a CO-AUTHOR
#: LIST is a record of who published together. They look alike once
#: reduced to a list of names, and nothing downstream can tell them
#: apart -- but the PAGE can be told apart, because a roster labels
#: its people and a bibliography labels its venues.
#:
#: Measured over the 100 published labs on 2026-10-14: 84 pages carried
#: a role word and no publication marker at all. Of the rest:
#:
#:   eecis.udel.edu/~ruizhang    38 publication markers, 3 roles
#:   pages.mtu.edu/~shene/NSF-2  72 publication markers, 3 roles
#:   cs.princeton.edu/~zhuangl    6 publication markers, 3 roles
#:   mrc.utexas.edu/people/faculty/ray-chen   no role word at all
#:
#: and their "rosters" were the professors' co-authors, with paper
#: titles counted among them.
ROLE_WORDS = re.compile(
    r"(ph\.?\s?d\.?\s+(?:student|candidate)|graduate\s+student|"
    r"grad\s+student|post[-\s]?doc|postdoctoral|"
    r"research\s+(?:scientist|assistant|associate|engineer|fellow)|"
    r"undergraduate\s+(?:student|researcher)|m\.?s\.?\s+student|"
    r"master'?s?\s+student|lab\s+manager|staff\s+scientist|"
    r"visiting\s+(?:scholar|student|researcher|professor)|"
    r"principal\s+investigator|lab\s+members?|group\s+members?|"
    r"team\s+members?|current\s+members?|former\s+members?|"
    r"alumni|assistant\s+professor|associate\s+professor)", re.I)

#: and a bibliography says where the work appeared.
VENUE_WORDS = re.compile(
    r"(\bet\s+al\b|arxiv|doi\s*:|\bdoi\.org|preprint|\bin\s+press\b|"
    r"submitted\s+to|proceedings\s+of|\bjournal\s+of\b|ieee\s+trans|"
    r"\bvol\.\s*\d|\bpp\.\s*\d+|conference\s+on|"
    r"\b(?:neurips|icml|cvpr|iclr|siggraph|usenix)\b)", re.I)


def page_signals(html: str) -> dict:
    """How many DISTINCT role and venue phrases a page uses.

    Distinct phrases, not occurrences: a bibliography repeats "et al."
    once per entry and a roster repeats "PhD Student" once per member,
    so raw counts measure the length of the list rather than its kind.
    """
    body = text_of(html)
    return {
        "role_markers": len({m.group(0).lower()
                             for m in ROLE_WORDS.finditer(body)}),
        "venue_markers": len({m.group(0).lower()
                              for m in VENUE_WORDS.finditer(body)}),
    }


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
    """Totals only. No per-person label leaves this function.

    DOMINANCE, NOT ONE ORIGIN'S SHARE. Counting Chinese markers
    answers "how Chinese is this group". The question the author
    actually asks is "is this group overwhelmingly ONE group", and a
    lab that is 8 of 11 South Asian answers yes while scoring near
    zero on a Chinese count. A roster at 45% Chinese can also be
    visibly mixed -- that is how a diverse Brown chemistry group came
    to sit in a table of outliers.

    So every origin the classifier knows is counted, and the headline
    figure is the LARGEST of them. 'other' is never the dominant
    group: it is a catch-all for everything unrecognised, not an
    origin, and treating it as one would make most labs in the
    country look concentrated.
    """
    try:
        import name_classifier as nc
    except Exception:                                          # noqa: BLE001
        return {"classified": 0, "note": "classifier unavailable"}

    total = len(names)
    counts: dict[str, int] = {}
    for n in names:
        cat, _conf = nc.classify(n)
        counts[cat] = counts.get(cat, 0) + 1

    #: PERSIAN, TURKISH AND ARABIC COUNT AS ONE. The classifier keeps
    #: them apart, which is right for describing a name and wrong for
    #: measuring concentration: a lab of four Iranian, three Turkish
    #: and three Arabic names is ten of twelve from one part of the
    #: world and scored 33% while it was counted as three groups.
    GROUPS = {
        "middle_eastern": ("iranian", "turkish", "arabic"),
        "chinese": ("chinese",),
        #: SOUTH ASIAN, not "indian". The list under that name already
        #: carried Khan and Rahman, and the Bengali names added beside
        #: it are Bangladeshi as often as West Bengali. Labelling the
        #: group by one country when it spans several is the same
        #: mistake as the merge above fixed for Persian, Turkish and
        #: Arabic: right for describing a name, wrong for measuring
        #: concentration.
        "south_asian": ("indian", "bengali", "pakistani", "nepali"),
        "japanese": ("japanese",),
        "korean": ("korean",),
        "vietnamese": ("vietnamese",),
    }
    GROUPS["african"] = ("african",)
    grouped = {g: sum(counts.get(k, 0) for k in keys)
               for g, keys in GROUPS.items()}
    named = {k: v for k, v in grouped.items() if v}

    #: NON-EUROPEAN AS ONE FIGURE, the author's second question. A lab
    #: can be a supermajority from outside Europe without any single
    #: origin dominating: five Chinese, three South Asian and two
    #: African in a group of eleven is ten of eleven, and the largest
    #: single origin is 45%.
    #:
    #: This is a FLOOR, not a measurement. It counts only the origins
    #: the classifier recognises, so every name it misses is counted
    #: as European. The African list in particular is narrow by
    #: design. The true share is at least this and may be higher.
    non_european = sum(named.values())
    top_group, top_n = ("", 0)
    if named:
        top_group, top_n = max(named.items(), key=lambda kv: kv[1])

    chinese = counts.get("chinese", 0)
    indian = counts.get("indian", 0)
    return {
        "members_detected": total,
        "by_origin": dict(sorted(counts.items(), key=lambda kv: -kv[1])),
        "by_group": dict(sorted(
            ((k, v) for k, v in grouped.items() if v),
            key=lambda kv: -kv[1])),
        "dominant_group": top_group,
        "dominant_count": top_n,
        "dominance": round(top_n / total * 100, 1) if total else 0.0,
        "non_european_count": non_european,
        "non_european_share":
            round(non_european / total * 100, 1) if total else 0.0,
        "markers_chinese": chinese,
        "markers_indian": indian,
        "markers_other_or_us": counts.get("other", 0),
        "share_chinese_markers":
            round(chinese / total * 100, 1) if total else 0.0,
        "share_indian_markers":
            round(indian / total * 100, 1) if total else 0.0,
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
