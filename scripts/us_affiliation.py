#!/usr/bin/env python3
"""Is this laboratory in the United States?

WHY THIS EXISTS. The table's top entry was the Cheng Lab at 91.4%
from one origin, credited to Illinois. It is at Westlake University
in Hangzhou. A Chinese laboratory staffed by Chinese students is not
a finding, and the page implied it was.

It reached the table because the crawl found Jianjun Cheng through an
Illinois faculty directory -- he was there before -- and followed his
research link to cheng-lab.com. The host is a .com and looks
American. Only the page says otherwise, and it says it loudly:
"Westlake" thirty-eight times against "Illinois" four.

Two tests, in order:

  a foreign top-level domain settles it outright;

  otherwise the page is read, and a foreign institution that
  outweighs the American one claimed for it means the lab is not here.

The second test is deliberately conservative. A US lab mentions
foreign places constantly -- collaborators, conferences, where an
alumnus went -- so a mention is not disqualifying. Being named more
often than the university we credited is.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

#: A country-code domain, or an academic domain under one.
FOREIGN_TLD = re.compile(
    r"\.(?:ac|edu|gov|org|co)?\.?"
    r"(?:cn|hk|tw|jp|kr|sg|in|pk|bd|lk|ir|il|sa|ae|qa|kw|tr|eg|za|"
    r"uk|ie|de|fr|nl|be|ch|at|it|es|pt|gr|se|no|dk|fi|is|pl|cz|sk|"
    r"hu|ro|bg|hr|si|rs|ua|ru|by|ee|lv|lt|au|nz|ca|mx|br|ar|cl|co|"
    r"pe|ve|ng|ke|gh|ma|tn|dz|vn|th|my|id|ph|np|kz|uz)$", re.I)

#: Foreign institutions and the cities that identify them. A name
#: here is checked against the page, not the URL.
FOREIGN_MARKERS = (
    # China
    "westlake university", "tsinghua", "peking university", "fudan",
    "shanghai jiao tong", "zhejiang university", "nanjing university",
    "harbin institute", "university of science and technology of china",
    "sun yat-sen", "wuhan university", "xi'an jiaotong", "beihang",
    "tongji", "southeast university", "shandong university",
    "chinese academy of sciences", "shenzhen", "hangzhou", "guangzhou",
    "beijing", "shanghai", "nanjing", "wuhan", "chengdu", "xiamen",
    "southern university of science and technology", "shanghaitech",
    # Hong Kong, Taiwan, Singapore, Korea, Japan
    "university of hong kong", "chinese university of hong kong",
    "hong kong university of science", "city university of hong kong",
    "national taiwan university", "tsinghua university, taiwan",
    "national university of singapore", "nanyang technological",
    "kaist", "seoul national university", "postech", "yonsei",
    "university of tokyo", "kyoto university", "osaka university",
    "tohoku university", "riken",
    # Europe, Middle East, elsewhere
    "eth zurich", "epfl", "tu delft", "tu munich",
    "technical university of munich", "max planck", "cnrs",
    "sorbonne", "universite", "universität", "universiteit",
    "politecnico", "universidad", "universidade", "karolinska",
    "chalmers", "kth royal", "leiden university", "utrecht",
    "ku leuven", "tel aviv university", "technion",
    "hebrew university", "weizmann", "king abdullah university",
    "kaust", "indian institute of technology", "iit delhi",
    "iit bombay", "tsinghua-berkeley",
    "university of toronto", "mcgill", "ubc", "waterloo, ontario",
    "university of melbourne", "monash", "australian national",
    "university of sydney", "tsinghua shenzhen",
)
_MARKER_RE = re.compile("|".join(re.escape(m) for m in FOREIGN_MARKERS),
                        re.I)

#: American institutions and the words that identify one. A page that
#: names these is describing a US laboratory, whoever its alumni are.
US_MARKERS = (
    "caltech", "california institute of technology", "stanford",
    "berkeley", "ucla", "ucsd", "ucsb", "mit", "massachusetts institute",
    "harvard", "princeton", "yale", "columbia", "cornell",
    "carnegie mellon", "georgia tech", "georgia institute",
    "university of michigan", "michigan state", "ohio state",
    "penn state", "pennsylvania state", "purdue", "illinois",
    "wisconsin", "minnesota", "maryland", "virginia tech",
    "north carolina", "duke", "johns hopkins", "rice university",
    "texas a&m", "texas a & m", "ut austin", "university of texas",
    "arizona state", "university of arizona", "colorado",
    "university of washington", "oregon state", "iowa state",
    "notre dame", "northwestern", "vanderbilt", "emory",
    "rutgers", "pittsburgh", "boston university", "northeastern",
    "new york university", "nyu", "lehigh", "stevens institute",
    "rensselaer", "worcester polytechnic", "dartmouth", "brown university",
    "clemson", "auburn", "vanderbilt", "louisiana state", "lsu",
    "stony brook", "buffalo", "syracuse", "delaware", "connecticut",
    "massachusetts amherst", "umass", "utah", "nebraska", "kansas",
    "oklahoma", "missouri", "kentucky", "tennessee", "alabama",
    "mississippi state", "new mexico", "nevada", "hawaii",
    "united states", "u.s.", "usa", "national science foundation",
    "nsf", "nih", "department of energy", "darpa", "onr", "afosr",
)
_US_RE = re.compile("|".join(re.escape(m) for m in US_MARKERS), re.I)


#: an email domain outside the United States
_MAIL = re.compile(r"[\w.+-]+@([\w.-]+\.[a-z]{2,})", re.I)


def _mail_domains(html: str) -> tuple[int, int]:
    """(foreign addresses, US .edu addresses) on the page."""
    foreign = us = 0
    for dom in _MAIL.findall(html or ""):
        d = dom.lower().rstrip(".")
        if FOREIGN_TLD.search(d):
            foreign += 1
        elif d.endswith((".edu", ".gov", ".mil")):
            us += 1
    return foreign, us


def _text(html: str) -> str:
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html or "",
               flags=re.S | re.I)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t))


#: A UNIVERSITY'S OWN SHORTHAND, which its labs put in their hosts.
#: ipl-uw.github.io is Washington's Information Processing Lab, and no
#: rule derived from "University of Washington-Seattle Campus" finds
#: "uw" inside "ipluw" -- the abbreviation has to be known.
ABBREVIATIONS = {
    "washington": ("uw",), "michigan": ("umich",),
    "illinois": ("uiuc", "illinois"), "california-berkeley": ("ucb",),
    "california-los angeles": ("ucla",),
    "california-san diego": ("ucsd",),
    "california-santa barbara": ("ucsb",),
    "california-irvine": ("uci",), "california-davis": ("ucd",),
    "california-riverside": ("ucr",),
    "massachusetts institute of technology": ("mit",),
    "carnegie mellon": ("cmu",), "georgia institute": ("gatech", "gt"),
    "texas at austin": ("utexas", "ut"), "texas a & m": ("tamu",),
    "pennsylvania state": ("psu",), "ohio state": ("osu",),
    "michigan state": ("msu",), "arizona state": ("asu",),
    "stony brook": ("sbu", "stonybrook"),
    "virginia polytechnic": ("vt",), "johns hopkins": ("jhu",),
    "new york university": ("nyu",),
    "southern california": ("usc",), "minnesota": ("umn",),
    "maryland": ("umd",), "wisconsin": ("wisc",),
    "north carolina state": ("ncsu",), "purdue": ("purdue",),
    "colorado boulder": ("cu", "colorado"),
    "massachusetts-amherst": ("umass",),
    "louisiana state": ("lsu",), "texas tech": ("ttu",),
    "new jersey institute": ("njit",),
    "rensselaer": ("rpi",), "worcester": ("wpi",),
    "michigan technological": ("mtu",),
    "missouri university of science": ("mst",),
    "illinois institute": ("iit",), "illinois chicago": ("uic",),
    "connecticut": ("uconn",), "notre dame": ("nd",),
    "mines": ("mines",), "buffalo": ("ub", "buffalo"),
    "houston": ("uh",), "delaware": ("udel",), "utah": ("utah",),
    "florida": ("uf",), "central florida": ("ucf",),
    "florida state": ("fsu",), "oregon state": ("osu", "oregonstate"),
    "iowa state": ("iastate",), "kansas": ("ku",),
    "nebraska-lincoln": ("unl",), "new mexico": ("unm",),
    "tennessee": ("utk",), "kentucky": ("uky",),
    "south carolina": ("sc",), "mississippi state": ("msstate",),
    "cincinnati": ("uc",), "pittsburgh": ("pitt",),
    "stevens": ("stevens",), "lehigh": ("lehigh",),
    "dartmouth": ("dartmouth",), "clemson": ("clemson",),
}


#: Tokens that are not distinctive enough to identify a university.
_WEAK = {"university", "college", "institute", "school", "state",
         "main", "campus", "the", "of", "and", "at", "technology",
         "polytechnic", "a", "m", "new", "north", "south", "east",
         "west", "central"}


def _tokens(institution: str) -> set:
    """Distinctive words and initials for a university's name."""
    words = re.findall(r"[a-z]+", (institution or "").lower())
    strong = {w for w in words if len(w) > 3 and w not in _WEAK}
    #: initials of the strong words: Washington -> uw via "u"+"w" is
    #: not reliable, but "uw" as a whole token in a host is
    out = set(strong)
    for w in list(strong):
        out.add(w[:4])
    return out


def _claims_home(host: str, html: str, institution: str) -> bool:
    """Does the lab's own host or title name the claimed university?"""
    toks = _tokens(institution)
    if not toks:
        return False
    hay = host.replace("-", "").replace(".", " ")
    m = re.search(r"<title[^>]*>(.*?)</title>", html or "",
                  re.I | re.S)
    title = re.sub(r"<[^>]+>", " ", m.group(1)).lower() if m else ""
    #: a .edu host under the university's own domain is conclusive
    if host.endswith(".edu"):
        return True
    for t in toks:
        if len(t) >= 4 and (t in hay or t in title):
            return True
    #: the university's own shorthand, anywhere in the host
    low = (institution or "").lower()
    raw_host = host.lower()
    for key, abbrs in ABBREVIATIONS.items():
        if key not in low:
            continue
        for ab in abbrs:
            if ab in raw_host or re.search(rf"\b{re.escape(ab)}\b", title):
                return True
    return False


def check(url: str, html: str, claimed_institution: str) -> tuple[bool, str]:
    """(is_us, reason). False means do not treat this as a US lab."""
    try:
        host = urlparse(url).netloc.lower()
    except ValueError:
        return False, "unparseable host"
    bare = host.split(":")[0]
    if FOREIGN_TLD.search(bare):
        return False, f"foreign domain {bare}"
    #: A .edu, .gov OR .mil HOST IS CONCLUSIVE and has to be tested
    #: before anything else. www-math.mit.edu was rejected because the
    #: institution was recorded as "MIT", too short for the name
    #: matcher, so the test that should have passed it never ran.
    if bare.endswith((".edu", ".gov", ".mil")):
        return True, ""

    if not html:
        return True, ""
    text = _text(html).lower()

    #: THE CONTACT EMAIL SETTLES IT FASTEST. The Cheng group's page
    #: carries chengjianjun@westlake.edu.cn, and its banner reads
    #: "WESTLAKE UNIVERSITY | SCHOOL OF ENGINEERING". No word-counting
    #: was needed; the address was on the page. A roster whose emails
    #: are overwhelmingly foreign is a foreign roster.
    foreign_mail, us_mail = _mail_domains(html)
    if foreign_mail and foreign_mail > us_mail:
        return False, (f"{foreign_mail} contact addresses on foreign "
                       f"domains against {us_mail} on .edu")
    #: AND A .edu ADDRESS IS POSITIVE EVIDENCE, not merely the absence
    #: of a foreign one. skotheimlab.com carries four .edu addresses
    #: and no foreign ones, and was rejected anyway because its
    #: alumni list names Munich and Hefei -- the marker test ran on a
    #: page that had already proved where it lives.
    if us_mail and us_mail >= foreign_mail:
        return True, ""

    #: THE LAB'S OWN ADDRESS SETTLES IT. ipl-uw.github.io is the
    #: Information Processing Lab at Washington, and its alumni page
    #: lists where people WENT -- Beijing, National Taiwan University,
    #: Hangzhou -- which the marker test read as a foreign lab. A US
    #: laboratory names foreign places constantly; what it cannot fake
    #: is carrying its own university in its host or its title.
    if _claims_home(bare, html, claimed_institution):
        return True, ""

    #: how often the page names the university we credited it to
    claimed = (claimed_institution or "").lower()
    own = 0
    for part in re.split(r"[-,]", claimed):
        part = part.strip()
        if len(part) > 5 and part not in ("university", "college",
                                          "main campus", "institute"):
            own = max(own, text.count(part))

    hits: dict = {}
    for m in _MARKER_RE.findall(text):
        key = m.lower()
        hits[key] = hits.get(key, 0) + 1
    if not hits:
        return True, ""

    #: EVERY MARKER COUNTS, not just the commonest. The Cheng Lab
    #: page names "Westlake University" three times and "champaign"
    #: three times, so comparing single markers called it a tie and
    #: let it through; taken together it names Westlake, Peking,
    #: Shenzhen, Sun Yat-sen and Beijing eight times over.
    total = sum(hits.values())
    named = sorted(hits, key=lambda k: -hits[k])[:3]

    #: A US LAB NAMES US PLACES. dabirilab.com is Caltech's and
    #: daklab.org is Columbia's; both list where alumni went --
    #: Technion, Max Planck, Tokyo -- and both were rejected for it.
    #: Weighing foreign mentions against American ones, rather than
    #: against the one name we happened to record, tells a lab that
    #: has moved abroad from a lab whose graduates have.
    us_hits = len(_US_RE.findall(text)) + own

    if total > own and total >= 3 and total > us_hits:
        return False, (f"names {', '.join(named)} {total}x against "
                       f"{own}x for the institution claimed")
    return True, ""
