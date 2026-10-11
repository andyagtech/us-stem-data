#!/usr/bin/env python3
"""A clickable index of the programs and labs worth looking at.

The analysis so far lives in three JSON files and a pile of snapshots,
which is useless to anyone trying to work through it. This is the page
that makes it navigable: every program and lab in one place, sorted by
concentration, each one a link out to where it describes itself.

WHAT EACH ROW IS. A program row is a university department, its
non-resident or name-marker share, and a link to find it. A lab row is a
research group whose public roster has been read and archived, with the
count and a link to both the live page and the snapshot.

WHAT NO ROW IS. Nobody is named and nobody is labeled. A share is a
count over a group, and the name-marker shares are floors because the
classifier skips names it cannot place. The page says so where it matters
rather than once at the bottom.

PRIVATE. The directory is a working list, not a publication, so it is
declared in private_pages.py and stays out of the sitemap, the contents
page and the assistant's map.

Usage:
  python3 scripts/build_lab_directory.py
"""
from __future__ import annotations

import html
from urllib.parse import quote
import json
from lab_overrides import apply as apply_lab_overrides
import re
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from atomic_write import write_text                            # noqa: E402

LABS = ROOT / "data" / "labs"
OUT = ROOT / "site" / "lab-directory.html"
E = html.escape

#: A share needs a denominator worth quoting. Module level so
#: the methodology section can state the same number the cards
#: were filtered by, rather than a copy that can drift.
MIN_DOCTORATES = 20

SECTOR_LABEL = {
    "nuclear": "Nuclear", "aerospace": "Aerospace", "petroleum": "Petroleum",
    "mining": "Mining &amp; metals", "battery": "Battery &amp; materials",
    "ai": "AI &amp; computing", "bio": "Bioengineering",
    "semiconductor": "Semiconductors", "robotics": "Robotics",
    #: The wider STEM search list. These are fields, not critical
    #: industries, and carry no restriction claim.
    "math": "Mathematics", "cs": "Computer science",
    "ee": "Electrical &amp; computer eng", "me": "Mechanical eng",
    "chemeng": "Chemical eng", "civil": "Civil eng",
    "industrial": "Industrial &amp; systems eng", "physics": "Physics",
    "chemistry": "Chemistry", "biomed": "Biomedical eng",
    "optics": "Optics &amp; photonics",
    "oceanatmos": "Earth &amp; atmospheric",
}


def fmt_n(n) -> str:
    """Thousands separators, because a bare 12594 reads as a year."""
    try:
        return f"{int(n):,}"
    except (TypeError, ValueError):
        return str(n if n is not None else "")


def _unesc(t: str) -> str:
    """A page title already carries HTML entities; escaping it again
    turned Texas A&M into Texas A&amp;M on screen."""
    return html.unescape(t or "")


def jload(name, default=None):
    f = LABS / name
    if not f.exists():
        return default if default is not None else {}
    return json.loads(f.read_text())




#: Department page titles are whatever the university put in <title>, which
#: runs to "Home | Nuclear, Plasma & Radiological Engineering | Grainger
#: Engineering | Illinois". Normalising them makes the column scannable.
_TITLE_NOISE = re.compile(
    r"^(home|welcome|index)\s*[|\u2013\u2014-]\s*|"
    r"\s*[|\u2013\u2014-]\s*(home|welcome)\s*$", re.I)



#: THE TWO SOURCES NAME INSTITUTIONS DIFFERENTLY. The dissertation record
#: uses the short form the harvest was configured with -- "UCLA", "Boston
#: U", "CO School of Mines" -- while IPEDS uses the registered name,
#: "University of California-Los Angeles". Keying the join on the raw
#: string matched almost nothing, so every program row showed "not
#: resolved" even where its department page had been found and verified.

#: Acronyms and house styles the fuzzy key cannot reach. "UCLA" shares no
#: word with "University of California-Los Angeles", so these are mapped
#: explicitly rather than by a cleverer matcher that would also map things
#: it should not.
ALIAS = {
    "ucla": "university of california los angeles",
    "caltech": "california institute of technology",
    "mit": "massachusetts institute of technology",
    "njit": "new jersey institute of technology",
    "rpi": "rensselaer polytechnic institute",
    "rit": "rochester institute of technology",
    "lsu": "louisiana state university",
    "nc state": "north carolina state university",
    "penn state": "pennsylvania state university",
    "missouri s&t": "missouri university of science and technology",
    "cmu": "carnegie mellon university",
    "gatech": "georgia institute of technology",
    "uiuc": "university of illinois urbana champaign",
    "ucsd": "university of california san diego",
    "ucsb": "university of california santa barbara",
    "uc riverside": "university of california riverside",
    "uc berkeley": "university of california berkeley",
    "ucberkeley": "university of california berkeley",
    "ucdavis": "university of california davis",
    "uc davis": "university of california davis",
    "ut austin": "university of texas austin",
    "ut dallas": "university of texas dallas",
    "ut arlington": "university of texas arlington",
    "texas a&m": "texas a m university",
    "ole miss": "university of mississippi",
    "vt": "virginia polytechnic institute",
    "wash u st louis": "washington university in st louis",
    "washu": "washington university in st louis",
    "co school of mines": "colorado school of mines",
    "michigan tech": "michigan technological university",
    "stony brook": "stony brook university",
    "u buffalo": "university at buffalo",
    "asu": "arizona state university",
    "osu": "ohio state university",
    "psu": "pennsylvania state university",
    "unl": "university of nebraska lincoln",
    "u nebraska-lincoln": "university of nebraska lincoln",
}

_ABBR = {
    "u": "university", "univ": "university", "co": "colorado",
    "cal": "california", "st": "state", "inst": "institute",
    "tech": "technology", "poly": "polytechnic", "mech": "mechanical",
}


def inst_key(name: str) -> str:
    """A loose key two spellings of one university both land on."""
    raw = (name or "").strip().lower()
    raw = ALIAS.get(raw, raw)
    n = re.sub(r"[^a-z0-9 ]", " ", raw)
    n = re.sub(r"\b(the|of|at|in|and|main|campus|system|college)\b", " ", n)
    words = [_ABBR.get(w, w) for w in n.split()]
    #: Drop the generic tail so "cornell university" meets "cornell".
    words = [w for w in words if w not in ("university", "institute",
                                           "technology", "state")] or words
    return " ".join(sorted(set(words)))



#: Words that identify a dissertation department as belonging to a field.
#: Used only to build a link INTO the query tool, so a loose match is
#: fine: the reader sees the SQL and can widen it.
FIELD_DEPT_WORDS = {
    "industrial": ("industrial", "systems eng", "operations research"),
    "ee": ("electrical", "computer eng"),
    "cs": ("computer science", "computing"),
    "me": ("mechanical",),
    "civil": ("civil", "environmental eng"),
    "chemeng": ("chemical eng",),
    "math": ("mathematic", "statistic", "applied math"),
    "physics": ("physics", "astronom"),
    "chemistry": ("chemistry", "biochem"),
    "biomed": ("biomedical", "bioengineering"),
    "nuclear": ("nuclear",),
    "aerospace": ("aerospace", "aeronaut"),
    "petroleum": ("petroleum",),
    "mining": ("mining", "metallurg"),
    "battery": ("material",),
    "ai": ("computer science", "electrical", "computing"),
    "optics": ("optic", "photonic"),
    "oceanatmos": ("atmospher", "ocean", "geoscience", "earth"),
}



#: The degree -> field map is no longer a word list. It is generated by
#: scripts/classify_degrees.py, which asks a model to read the
#: registrar's own degree names and group them. The hand-written
#: version got "Industrial-Organizational Psychology" wrong, filing a
#: psychology degree under industrial engineering because the word
#: "industrial" was in it, and would have gone on getting that class of
#: thing wrong forever. "Explosives Engineering" is mining. "Ceramic"
#: and "Metallurgical" are materials. A list of substrings holds only
#: the cases somebody already thought of.
#:
#: The COUNTS stay exact: they are read from the universities' own
#: repositories. Only the grouping is the model's, and the page says so.


def degree_split(splits: dict, classes: dict, uni_slug: str,
                 dept: str, field: str):
    """(in_this_field, total, other_degrees) from the registrar's own
    degree names, or None if this department has not been split.

    A combined department's thesis count is not any one field's count.
    Missouri S&T's "Geosciences & Geo/Petroleum Eng" holds 413, of
    which 172 are Petroleum Engineering and 241 are earth science. The
    repository records the degree conferred on every record page, so
    the split is the registrar's and not a guess at the title.
    """
    p = (splits or {}).get(f"{uni_slug}|{dept}")
    if not p:
        return None
    cls = (classes or {}).get("classification") or {}
    mine = other = 0
    others: list = []
    for deg, n in (p.get("degrees") or {}).items():
        if (cls.get(deg) or {}).get("field") == field:
            mine += n
        else:
            other += n
            others.append((deg, n))
    others.sort(key=lambda kv: -kv[1])
    return mine, p.get("with_degree", mine + other), others


def thesis_link(dept_index: dict, institution: str, field: str) -> tuple | None:
    """A deep link to every thesis this site holds for one department.

    Returns (url, department, records) or None. Matches the IPEDS name to
    the dissertation record's own university slug through inst_key(),
    then picks the department whose name carries one of the field's
    words, largest first.

    Reads the COMPLETE index, not the ranked search targets: the ranking
    stops at 400 rows and the highest-share programme on the site is
    below that cut, so a lookup against it failed exactly where it
    mattered and gave no sign of having failed.
    """
    want = inst_key(institution)
    words = FIELD_DEPT_WORDS.get(field) or ()
    names = dept_index.get("names") or {}
    best = None
    for slug, depts in (dept_index.get("index") or {}).items():
        if inst_key(names.get(slug, slug)) != want and inst_key(slug) != want:
            continue
        for dept, n in depts.items():
            dl = dept.lower()
            if dl == "general" or not any(w in dl for w in words):
                continue
            if best is None or n > best[2]:
                best = (slug, dept, n)
    if not best:
        return None
    slug, dept, n = best
    #: A COMBINED DEPARTMENT IS NOT THIS FIELD'S COUNT. Missouri S&T
    #: awards through "Geosciences & Geo/Petroleum Eng", so the same
    #: 413 theses were offered on the petroleum card and again on the
    #: earth-and-atmospheric card, each reading as if it were that
    #: field's own output. 69 department names across the corpus span
    #: more than one field this way: "Mechanical & Aerospace Eng",
    #: "Mining & Nuclear Eng", "Electrical Engineering and Computer
    #: Science". The link is still the right one -- it is where those
    #: theses actually sit -- but the card has to say what it covers.
    dl = dept.lower()
    spans = sorted(f for f, ws in FIELD_DEPT_WORDS.items()
                   if any(w in dl for w in ws))
    sql = (f"-- Every thesis and dissertation this site holds for this\n"
           f"-- department. Names are as the university published them.\n"
           f"SELECT year, name, title, url\n"
           f"FROM stem_records\n"
           f"WHERE university = '{slug}'\n"
           f"  AND department = '{dept.replace(chr(39), chr(39) * 2)}'\n"
           f"ORDER BY year DESC, name")
    return ("/query?sql=" + quote(sql), dept, n, spans, slug)





#: A LAB PAGE TITLE IS ITS NAVIGATION, NOT ITS NAME. The crawler reads
#: whatever the <title> says, which is usually the section heading with
#: the group bolted on: "People - DukeNLP", "Members - Computer
#: Systems Lab", "Group - Jianfeng LU's homepage". Two forms are
#: useful to a reader -- the group's own name, or the principal
#: investigator's -- so this reduces a title to one of them.
_SECTION_WORD = re.compile(
    r"^\s*(people|members?|our team|the team|group members?|lab members?|"
    r"students|researchers|home|homepage|about|team|personnel|current)\s*"
    r"[|\u2013\u2014:-]+\s*", re.I)
_TRAILING_SECTION = re.compile(
    r"\s*[|\u2013\u2014:-]+\s*(people|members?|home ?page|home|about|team|"
    r"students|personnel)\s*$", re.I)
_PERSON = re.compile(
    r"^[A-Z][a-zA-Z.'\u2019-]+(?: [A-Z][a-zA-Z.'\u2019-]+){1,2}$")
_HAS_GROUP_WORD = re.compile(r"\b(lab|laboratory|group|centre|center|"
                             r"institute|project|team)\b", re.I)


#: WHEN THE TITLE NAMES NOTHING, THE URL OFTEN DOES. A page called
#: "Research Group" or "Featured research projects" is useless in a
#: table, but it sits at /faculty/qiang-xu/ or on lavi-lab.github.io,
#: and those name the thing the row is about.
_URL_USELESS = {"people", "members", "member", "home", "index", "about",
                "team", "group", "lab", "research", "faculty", "staff",
                "students", "default", "main", "www", "pages", "sites",
                "edu", "com", "org", "net", "github", "io", "html",
                "research-group", "featured-research-projects"}


def name_from_url(url: str) -> str:
    """A lab or a person's name recovered from the address."""
    if not url:
        return ""
    m = re.match(r"https?://([^/]+)(/.*)?$", url)
    if not m:
        return ""
    host, path = m.group(1), m.group(2) or ""
    #: a dedicated host says the name outright: lavi-lab.github.io
    first = host.split(".")[0].lower()
    if first.endswith("-lab") or first.endswith("lab"):
        stem = re.sub(r"-?lab$", "", first)
        if stem and stem not in _URL_USELESS:
            label = stem.upper() if len(stem) <= 5 else stem.title()
            return f"{label} Lab"
    #: /faculty/qiang-xu/ -> a person
    for seg in reversed([x for x in path.split("/") if x]):
        seg = re.sub(r"\.(html?|php|aspx?)$", "", seg, flags=re.I)
        if seg.lower() in _URL_USELESS or not seg:
            continue
        if re.fullmatch(r"[a-z]+-[a-z]+(-[a-z]+)?", seg, re.I):
            person = " ".join(w.capitalize() for w in seg.split("-"))
            if _PERSON.match(person):
                return f"{person}\u2019s Research Group"
        break
    return ""


def tidy_group(title: str, institution: str) -> str:
    """The group's own name, or "<PI>'s Research Group".

    Split on every separator and pick the segment that NAMES
    something, rather than the first. "People | Rubinstein Lab" split
    on the bar gives "People" first, and taking it threw the lab away
    and kept the navigation.
    """
    t = _unesc(title or "").strip()
    if not t:
        return ""
    head = (institution or "").split("-")[0].split(",")[0].strip()
    head_words = {w.lower() for w in head.split() if len(w) > 3}

    parts = [x.strip() for x in
             re.split(r"\s*[|\u00b7]\s*|\s+[\u2013\u2014-]\s+", t)
             if x.strip()]

    def useless(x: str) -> bool:
        xl = x.lower().strip(" .")
        if _SECTION_WORD.match(xl + " - ") or xl in (
                "people", "members", "member", "home", "homepage", "about",
                "team", "students", "our team", "the team", "personnel",
                "group", "research group", "lab", "current"):
            return True
        #: a segment that is only the university
        return bool(head_words) and set(xl.split()) <= head_words

    named = [x for x in parts if not useless(x)]
    t = max(named, key=len) if named else (parts[0] if parts else t)

    prev = None
    while prev != t:
        prev = t
        t = _SECTION_WORD.sub("", t)
        t = _TRAILING_SECTION.sub("", t)
        t = t.strip(" |,-\u2013\u2014")

    #: "... at Michigan Technological University" -- the institution
    #: has its own column, and repeating it here cost the name the
    #: room it needed and truncated mid-word.
    if head:
        t = re.sub(r"\s+(?:at|of|,)\s+" + re.escape(head) + r"\b.*$",
                   "", t, flags=re.I).strip(" |,-\u2013\u2014")

    #: A FREE-HOST SLUG CARRIES A DISAMBIGUATOR. wixsite's
    #: "susmint-laboratory-1" becomes "Susmint Laboratory 1", and the
    #: trailing 1 is the host's, not the laboratory's.
    t = re.sub(r"\s+\d{1,2}$", "", t) if re.search(
        r"\b(lab|laboratory|group|centre|center)\s+\d{1,2}$", t, re.I) else t

    #: "Jianfeng LU's homepage" is a person, not a page
    m = re.match(r"^(.*?)[\u2019']s\s+(?:home ?page|page|site|group|lab|"
                 r"research group)$", t, re.I)
    if m:
        t = m.group(1).strip()

    if _PERSON.match(t) and not _HAS_GROUP_WORD.search(t):
        #: lab pages write the surname in capitals often enough to matter
        t = " ".join(w.capitalize() if w.isupper() and len(w) > 1 else w
                     for w in t.split())
        return f"{t}\u2019s Research Group"
    return t


def group_label(row: dict) -> str:
    """The name shown in the table: title first, then the address."""
    t = tidy_group(row.get("title"), row.get("institution"))
    tl = t.lower().strip()
    vague = tl in (
        "", "research group", "research", "featured research projects",
        "research projects", "projects", "group", "lab", "laboratory")
    #: a symposium or workshop page names an EVENT. The group that
    #: ran it is usually in the host: lavi-lab.github.io.
    vague = vague or bool(re.search(
        r"\b(symposium|workshop|conference|seminar|talks?|news|"
        r"featured)\b", tl))
    if vague:
        t = name_from_url(row.get("url") or "") or t
    return t or _unesc(row.get("title") or row.get("url") or "")


def lab_outliers_html(outliers: dict) -> str:
    """Individual research groups, ranked by composition.

    A DIFFERENT UNIT FROM EVERYTHING ELSE ON THIS PAGE. The tables
    above count degrees a department conferred. This counts the people
    a named principal investigator currently lists on their own
    laboratory page. One is a federal census; the other is what a group
    publishes about itself.

    Ordered by share and size, not by a p-value. Against the US
    population share of 1.6% every research group in American STEM
    comes out "significant", including ones carrying FEWER marked names
    than the department around them, so a test against the census
    separates nothing. The department figure rides alongside, because a
    group at 73.9% in a department at 30.5% is the interesting case and
    a group at 33% in a department at 33% is not.
    """
    rows = apply_lab_overrides(
        [dict(r) for r in ((outliers or {}).get("outliers") or [])])
    if not rows:
        return ""
    lab_field_opts = "".join(
        f'<option value="{E(f)}">{SECTOR_LABEL.get(f, f)}</option>'
        for f in sorted({r.get("field") for r in rows if r.get("field")}))
    body = []
    for r in rows:
        kid = bool(r.get("child_of"))
        also = r.get("also_see")
        extra = ("" if not also else
                 f' <a class="also" href="{E(also["url"])}" '
                 f'target="_blank" rel="noopener">{E(also["label"])}</a>')
        body.append(
            f'<tr class="{"kid" if kid else ""}" '
            f'data-field="{E(r.get("field") or "")}" '
            f'data-inst="{E((r.get("institution") or "").lower())}">'
            f'<td><a href="{E(r["url"])}" target="_blank" rel="noopener">'
            f'{E(group_label(r)[:54])}</a>{extra}</td>'
            f'<td class="mut">{E(r.get("institution") or "")}</td>'
            f'<td><span class="chip s-{E(r.get("field") or "")}">'
            f'{SECTOR_LABEL.get(r.get("field"), r.get("field") or "")}</span></td>'
            f'<td class="num">{r["members"]}</td></tr>')

    n_inst = len({r["institution"] for r in rows})
    tested = (outliers or {}).get("tested", 0)
    return f"""
<details class="sec" id="labs-found" open>
<summary><h2>Research Labs with Major Statistical Differences to the US Population</h2><a class="sec-anchor" href="#labs-found" title="Link to this section" aria-label="Link to this section">#</a></summary>
<p class="sub">{len(rows)} labs at {n_inst} institutions, found by
reading {tested} public member lists. This counts the people a named
principal investigator lists on their own laboratory page, which is a
different thing from the degree counts above: those are a federal
census, this is what a group publishes about itself.</p>
<div class="ctl" data-for="t-labs">
  <input class="ff" type="search" placeholder="Filter&hellip;"
         aria-label="Filter rows">
  <select class="fs" aria-label="Filter by field">
    <option value="">All fields</option>{lab_field_opts}</select>
  <label class="chk"><input type="checkbox" class="fr"> Hide unresolved</label>
  <span class="spacer"></span>
  <label class="chk">Rows
    <select class="fn" aria-label="Rows to show">
      <option selected>25</option><option>50</option><option>100</option>
      <option value="0">All</option>
    </select></label>
  <span class="count"></span>
</div>
<div class="tw"><table id="t-labs">
<thead><tr><th class="so">Research lab</th><th class="so">Institution</th>
<th class="so">Field</th><th class="num so" data-t="n" data-dir="-1">Members
</th></tr></thead>
<tbody>{"".join(body)}</tbody></table></div>
</details>"""


def standouts_html(sec: list, urls: dict, urls_loose: dict,
                   dept_index: dict, splits: dict, degree_classes: dict,
                   n: int = 8) -> str:
    """The sharpest cases, with every piece of evidence behind each.

    A reader should not have to sort a table to find the extremes. These
    are the highest non-resident shares on a programme large enough for
    the share to mean something, and each card carries the three things
    that let someone check it: the theses this site holds, the
    department's own graduate roster, and its faculty page.

    A card only shows a link it actually has. There is no placeholder
    for a roster a department does not publish -- that absence is itself
    a finding, and the card says so rather than leaving a dead control.
    """
    rows = [r for r in sec if (r.get("doctorates") or 0) >= MIN_DOCTORATES
            and (r.get("nra_share") or 0) >= 85]
    rows.sort(key=lambda r: (-(r.get("nra_share") or 0),
                             -(r.get("doctorates") or 0)))

    cards = []
    for r in rows:
        if len(cards) >= n:
            break
        inst, field = r["institution"], r["sector"]
        u = (urls.get((inst, field))
             or urls_loose.get((inst_key(inst), field)) or {})
        th = thesis_link(dept_index, inst, field)

        #: ONE ORDER, EVERY CARD: what the people wrote, then who the
        #: people are, then the department. A reader comparing two
        #: cards should find the same thing in the same place.
        ev = []
        if th:
            ev.append(f'<a href="{E(th[0])}" target="_blank" '
                      f'rel="noopener">Dissertations and theses</a>')

        if u.get("students_url"):
            ev.append(f'<a href="{E(u["students_url"])}" target="_blank" '
                      f'rel="noopener">Graduate roster</a>')
        elif u.get("directory_url"):
            ev.append(f'<a href="{E(u["directory_url"])}" target="_blank" '
                      f'rel="noopener">Department directory</a>')
        if u.get("faculty_url"):
            ev.append(f'<a href="{E(u["faculty_url"])}" target="_blank" '
                      f'rel="noopener">Faculty</a>')
        if u.get("url"):
            ev.append(f'<a href="{E(u["url"])}" target="_blank" '
                      f'rel="noopener">Department page</a>')
        if not ev:
            continue

        share = r.get("nra_share") or 0
        d, nra = r.get("doctorates") or 0, r.get("nra") or 0
        missing = []
        if u.get("student_roster_checked_absent"):
            missing.append("no public graduate roster")
        elif not (u.get("students_url") or u.get("directory_url")):
            missing.append("no public graduate roster")
        if not u.get("faculty_url"):
            missing.append("no faculty page found")
        note = (f'<p class="miss">{"; ".join(missing)}.</p>'
                if missing else "")

        cards.append(f"""
  <article class="card">
    <div class="pct">{share:.1f}%</div>
    <h3>{E(inst)}</h3>
    <p class="fld">{E(r.get("ipeds_field") or "")
                     or SECTOR_LABEL.get(field, field)}</p>
    <p class="cnt">{fmt_n(nra)} of {fmt_n(d)} doctorates awarded to
      non-residents, 2015&ndash;2022</p>
    <ul class="ev">{"".join(f"<li>{x}</li>" for x in ev)}</ul>
    {note}
  </article>""")

    if not cards:
        return ""
    return f"""
<details class="sec" id="standouts" open>
<summary><h2>Highest Non-Resident Shares by Program</h2><a class="sec-anchor" href="#standouts" title="Link to this section" aria-label="Link to this section">#</a></summary>
<div class="cards">{"".join(cards)}</div>
</details>"""


def tidy_title(t: str, institution: str, sector: str) -> str:
    """A short, honest label for a department page link.

    University <title> tags are a hierarchy, not a name: "Home | Nuclear,
    Plasma & Radiological Engineering | Grainger Engineering | Illinois",
    "Aerospace | Aerospace Engineering | Illinois", "Home - Department of
    Aerospace Engineering and Engineering Mechanics". Taking the first
    segment gave a column full of the word "Home".

    So: split on every separator a university uses, drop the boilerplate
    segments, drop the ones naming the institution or the college, and
    keep the longest of what remains -- which is reliably the department.
    """
    t = _unesc(t or "").strip()
    #: Some department pages have no <title> and the resolver stored the
    #: URL instead. "Https://nuc.berkeley.edu" is not a department name.
    if not t or re.match(r"^https?://", t, re.I):
        return f"{SECTOR_PLAIN.get(sector, sector)} department"

    parts = [x.strip() for x in re.split(r"\s*[|\u00b7\u2013\u2014]\s*|\s+-\s+", t)
             if x.strip()]
    head = institution.split("-")[0].split(",")[0].strip()
    head_words = {w.lower() for w in head.split() if len(w) > 3}

    def junk(x: str) -> bool:
        xl = x.lower().strip(" .")
        if xl in ("home", "welcome", "index", "main", "homepage", "overview"):
            return True
        if re.fullmatch(r"(college|school|department|dept\.?)( of)?( engineering)?",
                        xl):
            return True
        #: a segment that is only the university or its college
        if xl == head.lower() or (head_words and
                                  set(xl.split()) <= head_words):
            return True
        return False

    keep = [x for x in parts if not junk(x)]
    if not keep:
        keep = parts

    #: PREFER THE SEGMENT THAT NAMES A DEPARTMENT, not the longest one.
    #: Taking the longest kept "Transfer Information . Credit By
    #: Examination Info" and "Students Accelerate Engineering, Tech
    #: Skills at Toyota Hackathon" -- a page of notices and a news
    #: story, each longer than the department beside it in the title.
    DEPT = re.compile(
        r"\b(department|school|college|division|institute|programme|"
        r"program|engineering|sciences?|mathematics|physics|chemistry|"
        r"biology|computing|statistics)\b", re.I)
    #: and a title that is only a notice is not a department at all
    NOTICE = re.compile(
        r"\b(transfer information|credit by examination|hackathon|"
        r"accelerate|wins?|award|news|story|celebrat|announce|"
        r"admissions?|apply|visit|open house|commencement)\b", re.I)

    named = [x for x in keep if DEPT.search(x) and not NOTICE.search(x)]
    if named:
        t = max(named, key=len)
    else:
        clean = [x for x in keep if not NOTICE.search(x)]
        t = max(clean or keep, key=len)
    #: strip a leading "Department of" and a trailing institution
    t = re.sub(r"^(the\s+)?(department|dept\.?|school|division)\s+of\s+", "",
               t, flags=re.I).strip()
    for tail in (head, head.replace("The ", ""), "University", "College of Engineering"):
        if tail and t.lower().endswith(tail.lower()) and len(t) > len(tail) + 3:
            t = t[: -len(tail)].strip(" -\u2013\u2014|,")
    t = t.strip(" -|,")

    #: A ROLE IS NOT A DEPARTMENT NAME. "Computer Science Graduate
    #: Students" is the Computer Science department; the rest is the
    #: page's own section heading, which every roster page carries and
    #: which tells a reader nothing they cannot see from the column.
    t = re.sub(r"\s*[-\u2013:]?\s*\b(graduate|phd|doctoral|current|"
               r"prospective)?\s*(students?|people|members?|directory|"
               r"roster|faculty(?: and staff)?)\s*$", "", t,
               flags=re.I).strip(" -|,")

    #: What is left over sometimes names nothing at all: "Students",
    #: "SCS Directory", "Graduate". The field is more use than a word
    #: lifted off a navigation bar.
    if t.lower() in ("", "students", "student", "graduate", "people",
                     "directory", "scs directory", "members", "roster",
                     "graduate study", "graduate admissions", "overview"):
        t = ""

    if len(t) < 4:
        t = f"{SECTOR_PLAIN.get(sector, sector)} department"
    return t[0].upper() + t[1:] if t else t


SECTOR_PLAIN = {
    "nuclear": "Nuclear engineering", "aerospace": "Aerospace engineering",
    "petroleum": "Petroleum engineering", "mining": "Mining engineering",
    "battery": "Materials science", "ai": "Computer science",
    "bio": "Bioengineering", "semiconductor": "Semiconductors",
    "robotics": "Robotics",
    "math": "Mathematics", "cs": "Computer science",
    "ee": "Electrical and computer engineering",
    "me": "Mechanical engineering", "chemeng": "Chemical engineering",
    "civil": "Civil engineering",
    "industrial": "Industrial and systems engineering",
    "physics": "Physics", "chemistry": "Chemistry",
    "biomed": "Biomedical engineering", "optics": "Optics and photonics",
    "oceanatmos": "Earth and atmospheric science",
}


def roster_cell(u: dict) -> str:
    """At most two links: students and faculty, or one combined directory."""
    if not u:
        return '<span class="mut">&mdash;</span>'
    bits = []
    if u.get("students_url"):
        bits.append(f'<a class="stu" href="{E(u["students_url"])}" '
                    f'target="_blank" rel="noopener">students</a>')
    if u.get("faculty_url"):
        bits.append(f'<a href="{E(u["faculty_url"])}" target="_blank" '
                    f'rel="noopener">faculty</a>')
    if not bits and u.get("directory_url"):
        bits.append(f'<a href="{E(u["directory_url"])}" target="_blank" '
                    f'rel="noopener">directory</a>')
    return " &middot; ".join(bits) or '<span class="mut">&mdash;</span>'


def build_index(rosters, security, ranked, urls, urls_loose) -> list[dict]:
    """One record per institution, with its programs and labs inside it.

    INSTITUTION FIRST, because that is how a reader thinks about this. A
    lab belongs to a university and often to more than one department --
    the Information Processing Lab sits across electrical engineering and
    computer science -- so nesting labs under the department would have to
    pick one and would be wrong as often as not. They hang off the
    institution instead.
    """
    by_inst: dict[str, dict] = {}

    def slot(name):
        return by_inst.setdefault(name, {
            "name": name, "programs": [], "labs": [], "sectors": set(),
            "max_nra": None})

    for t in security.get("targets", []):
        e = slot(t["institution"])
        u = (urls.get((t["institution"], t["sector"]))
             or urls_loose.get((inst_key(t["institution"]), t["sector"])) or {})
        e["programs"].append({
            "name": t["sector_name"], "sector": t["sector"],
            "kind": "field", "doctorates": t["doctorates"],
            "nra": t.get("nra_share"), "url": u.get("url"),
            "roster": u.get("people_url"), "roster_kind": u.get("people_kind")})
        e["sectors"].add(t["sector"])
        if t.get("nra_share") is not None:
            e["max_nra"] = max(e["max_nra"] or 0, t["nra_share"])

    for t in ranked.get("targets", []):
        e = slot(t["university"])
        u = (urls.get((t["university"], t["critical_sector"]))
             or urls_loose.get((inst_key(t["university"]), t["critical_sector"])) or {})
        e["programs"].append({
            "name": t["department"], "sector": t["critical_sector"],
            "kind": "department", "theses": t["records"],
            "url": u.get("url"), "roster": u.get("people_url"),
            "roster_kind": u.get("people_kind")})
        if t["critical_sector"]:
            e["sectors"].add(t["critical_sector"])

    for inst in rosters.get("institutions", {}).values():
        for pg in inst.get("pages", []):
            if pg.get("status") != "ok":
                continue
            c = pg.get("composition") or {}
            if (c.get("members_detected") or 0) < 8:
                continue
            #: the harvester's label carries the programme in brackets;
            #: the institution is whatever precedes the em dash.
            nm = inst["name"].split("\u2014")[0].strip()
            e = slot(nm)
            e["labs"].append({
                "name": (pg.get("title") or pg["url"])[:70],
                "url": pg["url"], "members": c.get("members_detected"),
                "snapshot": Path(pg["snapshot"]).name if pg.get("snapshot") else None,
                "retrieved": (pg.get("retrieved") or "")[:8]})

    out = []
    for e in by_inst.values():
        e["sectors"] = sorted(x for x in e["sectors"] if x)
        #: de-duplicate programs that both sources produced
        seen, progs = set(), []
        for pr in sorted(e["programs"],
                         key=lambda r: -(r.get("nra") or r.get("theses") or 0)):
            k = (pr["name"].lower(), pr["kind"])
            if k in seen:
                continue
            seen.add(k)
            progs.append(pr)
        e["programs"] = progs
        out.append(e)
    out.sort(key=lambda e: (-(e["max_nra"] or 0), -len(e["labs"]), e["name"]))
    return out


def main() -> int:
    rosters = jload("rosters.json")
    urls, urls_loose = {}, {}
    for r in jload("program_urls.json").get("rows", []):
        if r.get("status") == "ok":
            urls[(r["institution"], r["sector"])] = r
            urls_loose[(inst_key(r["institution"]), r["sector"])] = r

    def find_url(inst, sector):
        if not sector:
            return None
        return (urls.get((inst, sector))
                or urls_loose.get((inst_key(inst), sector)))
    security = jload("security_targets.json")
    #: Fold the wider STEM search list into the same table. Both carry
    #: "a subject at an institution with a non-resident share", which is
    #: all this table shows. The six critical industries keep their
    #: restriction field; these fields have none, and the table does not
    #: claim one for them.
    dept_index = jload("department_index.json")
    stem = jload("stem_targets.json")
    for t in (stem.get("targets") or []):
        security.setdefault("targets", []).append({
            "sector": t["field"], "sector_name": t["field_name"],
            "institution": t["institution"], "unitid": t.get("unitid"),
            "doctorates": t["doctorates"], "nra": t.get("nra"),
            "nra_share": t.get("nra_share"), "cips": t.get("cips"),
            "restriction": None, "restriction_note": "",
            #: IPEDS's own name for the code that produced most of
            #: these awards. The card is headed with this rather than
            #: my name for a group of codes -- "Earth & atmospheric" is
            #: not a programme any university offers, so a reader who
            #: went looking for it could not find it.
            "ipeds_field": t.get("ipeds_field") or "",
            "top_cip": t.get("top_cip"),
        })
    ranked = jload("search_targets.json")

    index = build_index(rosters, security, ranked, urls, urls_loose)

    # ---- labs whose roster has been read and archived
    lab_rows = []
    for inst in rosters.get("institutions", {}).values():
        for p in inst.get("pages", []):
            if p.get("status") != "ok":
                continue
            c = p.get("composition") or {}
            n = c.get("members_detected") or 0
            if n < 8:
                continue
            lab_rows.append({
                "group": p.get("title") or p["url"],
                "institution": inst["name"],
                "url": p["url"], "members": n,
                "share": c.get("share_chinese_markers"),
                "snapshot": p.get("snapshot"),
                "retrieved": p.get("retrieved", "")[:8],
                "overridden": p.get("robots_overridden"),
            })
    #: And the region-balanced harvest, which reads the student rosters
    #: the URL resolver found rather than a hand-written seed list. That
    #: list held seven institutions, which is why this table showed
    #: three rows and looked like the work had stopped.
    for r in (jload("resolved_rosters.json").get("rows") or []):
        if r.get("status") != "ok":
            continue
        c = r.get("composition") or {}
        n = c.get("members_detected") or 0
        if n < 8:
            continue
        lab_rows.append({
            "group": group_label(r),
            "institution": r["institution"], "url": r["url"], "members": n,
            "share": c.get("share_chinese_markers"),
            "sector": r.get("sector", ""), "state": r.get("state", ""),
            "region": r.get("region", ""),
            "snapshot": r.get("snapshot"), "retrieved": "",
            "overridden": r.get("robots_overridden"),
            "frameable": bool(r.get("frameable")),
            "frame_refused": r.get("frame_refused", ""),
            "archive_url": r.get("archive_url", ""),
            "archive_date": r.get("archive_date", ""),
        })

    #: One page, one row. "Purdue" and "Purdue University-Main Campus"
    #: are the same place under two spellings and produced the same
    #: roster twice.
    _byurl: dict = {}
    for r in lab_rows:
        prev = _byurl.get(r["url"])
        if prev is None or len(r["institution"]) > len(prev["institution"]):
            _byurl[r["url"]] = r
    lab_rows = list(_byurl.values())

    #: VIEWABLE ROWS FIRST, then region, then share.
    #:
    #: A row whose page refuses framing and has no snapshot cannot be
    #: opened in the viewer at all, so it drops to the bottom rather
    #: than sitting between two rows that can -- a reader working down
    #: the table should not hit a link that behaves differently without
    #: warning. Region-balancing still applies within each group, so
    #: the viewable rows keep the geographic spread.
    def _viewable(r):
        return bool(r.get("frameable") or r.get("archive_url"))

    _seen: dict = {}
    _ordered = []
    for r in sorted(lab_rows, key=lambda r: (not _viewable(r),
                                             -(r["share"] or 0))):
        key = ("" if _viewable(r) else "z-") + (r.get("region") or "?")
        _seen.setdefault(key, []).append(r)
    #: Exhaust the viewable regions completely before starting the
    #: unviewable ones. Round-robining over every key at once put the
    #: new-tab-only rows back in the middle, which is the thing this
    #: ordering exists to prevent.
    for group in (False, True):
        keys = [k for k in _seen if k.startswith("z-") == group]
        while any(_seen[k] for k in keys):
            for k in keys:
                if _seen[k]:
                    _ordered.append(_seen[k].pop(0))
    lab_rows = _ordered

    # ---- programs in the sectors that carry a federal access regime
    #: EVERY SECTOR. This was limited to the ones carrying an access
    #: regime, which left out AI, materials and bio -- the three with the
    #: most programs in them. Ordered by non-resident share, because that
    #: is what the table is for.
    sec = sorted(security.get("targets", []),
                 key=lambda r: -(r.get("nra_share") or 0))
    degree_classes = jload("degree_classification.json")
    lab_outliers = lab_outliers_html(jload("lab_outliers.json"))
    frameable_n = sum(1 for r in lab_rows if r.get("frameable"))
    archive_n = sum(1 for r in lab_rows
                    if not r.get("frameable") and r.get("archive_url"))
    standouts = standouts_html(sec, urls, urls_loose, dept_index,
                               jload("degree_splits.json"), degree_classes)

    # ---- programs by concentration, from the dissertation record
    prog = ranked.get("targets", [])

    def lab_row(r):
        state_suffix = (f' &middot; {E(r["state"])}'
                        if r.get("state") else '')
        if not (r.get("frameable") or r.get("archive_url")):
            state_suffix += ' <span class="mut nr">new tab only</span>' 
        od = ' <span class="od" title="fetched despite robots.txt">ovr</span>' \
             if r.get("overridden") else ""
        #: The group name is a page <title> like every other, so it
        #: goes through the same normaliser. Taken raw and cut at 62
        #: characters it produced "People &ndash; Nuclear Engineering
        #: and Radiation Science | Mis": an unescaped entity, a
        #: "People" prefix that is the section not the name, and a
        #: university sliced in half.
        name = tidy_title(r["group"], r["institution"],
                          r.get("sector", ""))
        return (f'<tr data-inst="{E(r["institution"].lower())}" '
                f'data-resolved="1">'
                f'<td><a href="{E(r["url"])}" target="_blank" '
                #: data-frame says whether this page can be
                #: shown inside ours. Measured at build time by
                #: probe_framing.py, because a browser gives no
                #: usable signal when a frame is refused.
                f'rel="noopener" data-frame="{1 if r.get("frameable") else 0}" '
                f'data-archive="{E(r.get("archive_url") or "")}" '
                f'data-archived="{E(r.get("archive_date") or "")}"'
                f'>{E(name[:62])}</a>{od}</td>'
                f'<td class="mut">{E(r["institution"][:34])}'
                f'{state_suffix}</td>'
                f'<td class="num">{r["members"]}</td></tr>')

    def sec_row(r):
        u = find_url(r["institution"], r["sector"])
        dept = (f'<a href="{E(u["url"])}" target="_blank" rel="noopener">'
                f'{E(tidy_title(u.get("title"), r["institution"], r["sector"]))}</a>'
                if u else '<span class="mut nr">not resolved</span>')
        return (f'<tr data-sector="{E(r["sector"])}" '
                f'data-inst="{E(r["institution"].lower())}" '
                f'data-resolved="{"1" if u else "0"}">'
                f'<td>{E(r["institution"][:40])}</td>'
                f'<td><span class="chip s-{r["sector"]}">'
                f'{SECTOR_LABEL.get(r["sector"], r["sector"])}</span></td>'
                f'<td class="num">{r["doctorates"]}</td>'
                f'<td class="num hi">{r["nra_share"]}%</td>'
                f'<td>{dept}</td><td>{roster_cell(u)}</td></tr>')

    def prog_row(r):
        chip = (f'<span class="chip s-{r["critical_sector"]}">'
                f'{SECTOR_LABEL.get(r["critical_sector"], r["critical_sector"])}</span>'
                if r["critical_sector"] else '<span class="chip s-none">&mdash;</span>')
        u = find_url(r["university"], r["critical_sector"])
        dept = (f'<a href="{E(u["url"])}" target="_blank" rel="noopener">'
                f'{E(tidy_title(u.get("title"), r["university"], r["critical_sector"]))}</a>'
                if u else '<span class="mut nr">not resolved</span>')
        return (f'<tr data-sector="{E(r["critical_sector"] or "none")}" '
                f'data-inst="{E(r["university"].lower())}" '
                f'data-resolved="{"1" if u else "0"}">'
                f'<td>{E(r["department"][:42])}</td>'
                f'<td class="mut">{E(r["university"][:28])}</td>'
                f'<td>{chip}</td>'
                f'<td class="num">{r["records"]}</td>'
                f'<td>{dept}</td><td>{roster_cell(u)}</td></tr>')

    sec_opts = "".join(
        f'<option value="{E(x)}">{SECTOR_LABEL.get(x, "Other")}</option>'
        for x in sorted({t["sector"] for t in security.get("targets", [])}
                        | {t["critical_sector"] for t in ranked.get("targets", [])
                           if t["critical_sector"]}))
    sectors_present = sorted({r["critical_sector"] or "none" for r in prog})
    filters = "".join(
        f'<button type="button" class="f" data-f="{E(s)}">'
        f'{SECTOR_LABEL.get(s, "Other") if s != "none" else "Other"}</button>'
        for s in sectors_present)

    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>American Citizen Underrepresentation by Field</title>
<link rel="stylesheet" href="/style.css">
<style>
  .wrap {{ max-width: 1240px; margin: 0 auto; padding: 1.75rem 1.25rem 4rem; }}
  h1 {{ font-size: 1.9rem; margin: 0 0 .5rem; }}
  .lede {{ color: var(--text-muted); max-width: 74ch; line-height: 1.65;
    margin: 0 0 .5rem; font-size: .95rem; }}
  .warn {{ border-left: 3px solid var(--hl); background: var(--surface);
    padding: .7rem .9rem; border-radius: 0 8px 8px 0; margin: 1rem 0 0;
    font-size: .85rem; line-height: 1.6; max-width: 80ch; }}
  section {{ margin-top: 2.4rem; }}
  h2 {{ font-size: 1.15rem; margin: 0 0 .3rem; }}
  .sub {{ color: var(--text-muted); font-size: .86rem; margin: 0 0 .8rem;
    max-width: 78ch; line-height: 1.6; }}
  .tw {{ overflow-x: auto; }}
  table {{ width: 100%; border-collapse: collapse; font-size: .84rem; }}
  th {{ text-align: left; font-size: .68rem; text-transform: uppercase;
    letter-spacing: .05em; color: var(--text-muted); font-weight: 700;
    padding: .4rem .5rem; border-bottom: 1px solid var(--border);
    white-space: nowrap; position: sticky; top: 0; background: var(--bg); }}
  td {{ padding: .36rem .5rem; border-bottom: 1px solid var(--border);
    vertical-align: top; }}
  td.num, th.num {{ text-align: right; font-variant-numeric: tabular-nums;
    white-space: nowrap; }}
  td.hi {{ color: var(--hl); font-weight: 700; }}
  td.mut {{ color: var(--text-muted); }}
  a {{ color: var(--hl); }}
  .sm {{ font-size: .74rem; }}
  a.stu {{ font-weight: 700; }}
  .od {{ font-size: .62rem; background: var(--border); border-radius: 3px;
    padding: 0 .25rem; color: var(--text-muted); }}
  .chip {{ font-size: .66rem; text-transform: uppercase; letter-spacing: .04em;
    padding: .1rem .4rem; border-radius: 999px; white-space: nowrap;
    border: 1px solid var(--border); color: var(--text-muted); }}
  .chip.s-nuclear, .chip.s-aerospace {{ border-color: var(--hl);
    color: var(--hl); font-weight: 700; }}
  .search {{ position: relative; max-width: 620px; }}
  #q {{ width: 100%; font: inherit; font-size: 1rem; padding: .6rem .8rem;
    border: 1px solid var(--border); border-radius: 9px;
    background: var(--surface); color: var(--text); }}
  #q:focus {{ outline: 2px solid var(--hl); outline-offset: -1px; }}
  .ac {{ position: absolute; z-index: 20; left: 0; right: 0; top: calc(100% + 4px);
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 9px; overflow: hidden; box-shadow: 0 8px 24px rgba(0,0,0,.18); }}
  .ac button {{ display: block; width: 100%; text-align: left; font: inherit;
    font-size: .86rem; padding: .45rem .8rem; background: none; border: 0;
    cursor: pointer; color: var(--text); }}
  .ac button:hover {{ background: var(--bg); color: var(--hl); }}
  .results {{ display: grid; gap: .9rem; margin: 1rem 0 0;
    grid-template-columns: repeat(auto-fill, minmax(330px, 1fr)); }}
  .card {{ border: 1px solid var(--border); border-radius: 10px;
    padding: .85rem 1rem; background: var(--surface); }}
  .card h3 {{ font-size: .98rem; margin: 0 0 .5rem; }}
  .card .k {{ font-size: .66rem; text-transform: uppercase; letter-spacing: .06em;
    color: var(--text-muted); margin: .6rem 0 .25rem; font-weight: 700; }}
  .card ul {{ list-style: none; padding: 0; margin: 0; }}
  .card li {{ font-size: .82rem; line-height: 1.5; padding: .12rem 0;
    border-bottom: 1px solid var(--border); }}
  .card li:last-child {{ border-bottom: 0; }}
  .card ul.lab li {{ font-weight: 600; }}
  .hint {{ font-size: .82rem; color: var(--text-muted); margin: .7rem 0 0; }}
  .lnk {{ font: inherit; font-size: .82rem; background: none; border: 0;
    padding: 0; color: var(--hl); cursor: pointer; text-decoration: underline; }}
  th.so {{ cursor: pointer; user-select: none; position: relative;
    padding-right: 1.1rem; }}
  th.so:hover {{ color: var(--text); }}
  th.so::after {{ content: "\\2195"; position: absolute; right: .25rem;
    opacity: .3; font-weight: 400; }}
  th.so[aria-sort="ascending"]::after {{ content: "\\2191"; opacity: 1;
    color: var(--hl); }}
  th.so[aria-sort="descending"]::after {{ content: "\\2193"; opacity: 1;
    color: var(--hl); }}
  th.so:focus-visible {{ outline: 2px solid var(--hl); outline-offset: -2px; }}
  .note.model {{ font-size: .8rem; color: var(--text-muted);
    line-height: 1.65; max-width: 74ch; margin: 0 0 .9rem;
    border-left: 2px solid var(--border); padding-left: .8rem; }}
  /* FIXED COLUMN WIDTHS. With auto layout the browser re-measures
     every column against the rows currently in it, so sorting a table
     made the columns jump -- the content changed, so the widths did.
     Fixed layout decides once from the header row and never moves. */
  table#t-stem, table#t-prog, table#t-labs, table#t-rosters {{
    table-layout: fixed; width: 100%; }}
  /* Fixed layout splits the width equally unless told otherwise, which
     gave a sector chip the same room as a department name. These are
     the proportions the content actually needs. */
  #t-prog th:nth-child(1) {{ width: 17%; }}
  #t-prog th:nth-child(2) {{ width: 13%; }}
  #t-prog th:nth-child(3) {{ width: 13%; }}
  #t-prog th:nth-child(4) {{ width: 7%; }}
  #t-prog th:nth-child(5) {{ width: 34%; }}
  #t-prog th:nth-child(6) {{ width: 16%; }}
  #t-stem th:nth-child(1) {{ width: 22%; }}
  #t-stem th:nth-child(2) {{ width: 13%; }}
  #t-stem th:nth-child(3) {{ width: 9%; }}
  #t-stem th:nth-child(4) {{ width: 10%; }}
  #t-stem th:nth-child(5) {{ width: 30%; }}
  #t-stem th:nth-child(6) {{ width: 16%; }}
  /* A group inside a larger one is indented under it. Listing both as
     peers counts the same laboratory twice. */
  #t-labs tr.kid td:first-child {{ padding-left: 1.9rem; position: relative; }}
  #t-labs tr.kid td:first-child::before {{ content: "\\21b3";
    position: absolute; left: .7rem; color: var(--text-muted);
    font-size: .8rem; }}
  .also {{ font-size: .72rem; color: var(--text-muted);
    text-decoration: none; border-bottom: 1px dotted currentColor;
    margin-left: .4rem; white-space: nowrap; }}
  .also:hover {{ color: var(--hl); }}
  #t-labs th:nth-child(1) {{ width: 38%; }}
  #t-labs th:nth-child(2) {{ width: 28%; }}
  #t-labs th:nth-child(3) {{ width: 22%; }}
  #t-labs th:nth-child(4) {{ width: 12%; }}
  #t-rosters th:nth-child(1) {{ width: 48%; }}
  #t-rosters th:nth-child(2) {{ width: 34%; }}
  #t-rosters th:nth-child(3) {{ width: 18%; }}
  table#t-stem td, table#t-prog td, table#t-labs td, table#t-rosters td,
  table#t-stem th, table#t-prog th, table#t-labs th, table#t-rosters th {{
    overflow: hidden; text-overflow: ellipsis; }}
  table#t-stem td a, table#t-prog td a, table#t-labs td a,
  table#t-rosters td a {{ display: inline-block; max-width: 100%;
    overflow: hidden; text-overflow: ellipsis; vertical-align: bottom;
    white-space: nowrap; }}
  /* the sort glyph gets its own fixed slot so swapping it moves nothing */
  th.so::after {{ display: inline-block; width: .75em; text-align: center; }}

  /* Collapsible sections. Open at rest -- a page of shut drawers reads
     as an empty page -- and the control is there to fold away what a
     reader is finished with. */
  .sec-anchor {{ color: var(--text-muted); text-decoration: none;
    font-size: .9rem; opacity: 0; transition: opacity .12s;
    padding: 0 .2rem; }}
  details.sec > summary:hover .sec-anchor,
  .sec-anchor:focus-visible {{ opacity: 1; }}
  .sec-anchor:hover {{ color: var(--hl); }}
  .sec-anchor.copied::after {{ content: " copied"; font-size: .7rem;
    color: var(--hl); }}
  details.sec {{ border-top: 1px solid var(--border); margin: 1.8rem 0 0; }}
  details.sec > summary {{ cursor: pointer; list-style: none;
    padding: .9rem 0 .4rem; display: flex; align-items: baseline;
    gap: .55rem; }}
  details.sec > summary::-webkit-details-marker {{ display: none; }}
  details.sec > summary::before {{ content: "\\25bc"; font-size: .58rem;
    color: var(--text-muted); transition: transform .15s; }}
  details.sec:not([open]) > summary::before {{ transform: rotate(-90deg); }}
  details.sec > summary h2 {{ margin: 0; }}
  details.sec > summary:hover h2 {{ color: var(--hl); }}
  .tw {{ max-height: 70vh; overflow: auto; }}
  .cards {{ display: grid; gap: .8rem;
    grid-template-columns: repeat(auto-fit, minmax(290px, 1fr)); }}
  .card {{ border: 1px solid var(--border); border-left: 3px solid var(--hl);
    border-radius: 0 10px 10px 0; padding: .85rem 1rem;
    background: var(--surface); }}
  .card .pct {{ font-size: 1.7rem; font-weight: 800; color: var(--hl);
    line-height: 1.05; font-variant-numeric: tabular-nums; }}
  .card h3 {{ font-size: .98rem; margin: .25rem 0 .1rem; line-height: 1.3; }}
  .card .fld {{ font-size: .78rem; color: var(--text-muted);
    text-transform: uppercase; letter-spacing: .05em; margin: 0 0 .4rem; }}
  .card .cnt {{ font-size: .83rem; line-height: 1.5; margin: 0 0 .55rem; }}
  ul.ev {{ list-style: none; padding: 0; margin: 0 0 .5rem;
    font-size: .85rem; line-height: 1.85; }}
  ul.ev li::before {{ content: "\\203a"; color: var(--hl);
    margin-right: .45rem; font-weight: 700; }}
  .card .ev-old {{ font-size: .82rem; line-height: 1.75; }}
  .card .miss {{ font-size: .75rem; color: var(--text-muted);
    margin: .4rem 0 0; font-style: italic; }}
  .viewer-ctl {{ margin: 0 0 .7rem; }}
  #viewer {{ border: 1px solid var(--border); border-radius: 10px;
    overflow: hidden; margin: 0 0 1rem; background: var(--surface); }}
  .viewer-bar {{ display: flex; gap: .5rem; align-items: center;
    padding: .45rem .6rem; border-bottom: 1px solid var(--border); }}
  .viewer-title {{ flex: 1; font-size: .82rem; font-weight: 600;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  #viewer-frame {{ width: 100%; height: 62vh; min-height: 380px;
    border: 0; display: block; background: #fff; }}
  @media (max-width: 700px) {{ #viewer-frame {{ height: 70vh; }} }}
  .pager {{ display: flex; flex-wrap: wrap; gap: .25rem; align-items: center;
    margin: .6rem 0 0; }}
  .pg {{ font: inherit; font-size: .78rem; min-width: 1.9rem; padding: .2rem .45rem;
    border: 1px solid var(--border); border-radius: 6px; cursor: pointer;
    background: var(--surface); color: var(--text); }}
  .pg:hover:not(:disabled) {{ border-color: var(--hl); color: var(--hl); }}
  .pg.on {{ background: var(--hl); color: #fff; border-color: var(--hl);
    font-weight: 700; }}
  .pg:disabled {{ opacity: .35; cursor: default; }}
  .pg-gap {{ color: var(--text-muted); padding: 0 .15rem; font-size: .78rem; }}
  .ctl {{ display: flex; flex-wrap: wrap; gap: .5rem; align-items: center;
    margin: 0 0 .7rem; }}
  .ctl .ff {{ font: inherit; font-size: .82rem; padding: .3rem .6rem;
    border: 1px solid var(--border); border-radius: 7px; min-width: 15rem;
    background: var(--surface); color: var(--text); }}
  .ctl select {{ font: inherit; font-size: .82rem; padding: .3rem .4rem;
    border: 1px solid var(--border); border-radius: 7px;
    background: var(--surface); color: var(--text); }}
  .chk {{ font-size: .8rem; color: var(--text-muted); display: inline-flex;
    gap: .3rem; align-items: center; }}
  .ctl .spacer {{ flex: 1; }}
  .ctl .count {{ font-size: .76rem; color: var(--text-muted);
    font-variant-numeric: tabular-nums; }}
  td .nr {{ font-style: italic; }}
  .filters {{ display: flex; flex-wrap: wrap; gap: .35rem; margin: 0 0 .7rem; }}
  .f {{ font: inherit; font-size: .76rem; padding: .25rem .6rem;
    border: 1px solid var(--border); background: var(--surface);
    border-radius: 999px; cursor: pointer; color: var(--text-muted); }}
  .f.on {{ border-color: var(--hl); color: var(--hl); font-weight: 600; }}
</style>
  <script id="phd-theme-boot">(function(){{try{{var t=localStorage.getItem("phd-theme");if(t==="light"||t==="dark")document.documentElement.dataset.theme=t;}}catch(e){{}}}})();</script>
  <script defer src="/theme.js"></script>
</head>
<body data-page="lab-directory">
<main class="wrap">
<h1>American citizen underrepresentation by field</h1>



{standouts}

{lab_outliers}


<details class="sec" id="labs" open>
<summary><h2>Examples of Statistically Anomalous Student Rosters</h2><a class="sec-anchor" href="#labs" title="Link to this section" aria-label="Link to this section">#</a></summary>
<div class="ctl viewer-ctl">
  <label class="chk"><input type="checkbox" id="inpage" checked>
    Display in page</label>
  <span class="spacer"></span>
  <span class="count" id="frame-note">{frameable_n + archive_n} of
    {len(lab_rows)} can be shown here &mdash; {frameable_n} live and
    {archive_n} from the Internet Archive, because most university
    sites refuse to be framed. The rest open in a new tab.</span>
</div>
<div id="viewer" hidden>
  <div class="viewer-bar">
    <span class="viewer-title" id="viewer-title"></span>
    <a id="viewer-out" href="#" target="_blank" rel="noopener"
       class="dl-btn">Open in a new tab</a>
    <button type="button" id="viewer-close" class="dl-btn">Close</button>
  </div>
  <iframe id="viewer-frame" title="Roster page"
          referrerpolicy="no-referrer" loading="lazy"></iframe>
</div>
<div class="ctl" data-for="t-rosters">
  <input class="ff" type="search" placeholder="Filter&hellip;"
         aria-label="Filter rows">
  <select class="fs" hidden aria-label="unused"><option value=""></option></select>
  <input type="checkbox" class="fr" hidden aria-hidden="true">
  <span class="spacer"></span>
  <label class="chk">Rows
    <select class="fn" aria-label="Rows to show">
      <option selected>25</option><option>50</option><option>100</option>
      <option value="0">All</option>
    </select></label>
  <span class="count"></span>
</div>
<div class="tw"><table id="t-rosters">
<thead><tr><th class="so">Department</th><th class="so">Institution</th>
<th class="num so" data-t="n" data-dir="-1">Members listed</th></tr></thead>
<tbody>{''.join(lab_row(r) for r in lab_rows)}</tbody></table></div>
</details>

<details class="sec" id="regime" open>
<summary><h2>STEM programs</h2><a class="sec-anchor" href="#regime" title="Link to this section" aria-label="Link to this section">#</a></summary>
<p class="sub">From IPEDS field codes, so this does not depend on what a
university called its department. Share is non-resident doctorates.
<strong>students</strong> links to a graduate roster where the department
publishes one; <strong>people</strong> is a faculty-and-staff page.</p>
<div class="ctl" data-for="t-stem">
  <input class="ff" type="search" placeholder="Filter institution or program&hellip;"
         aria-label="Filter rows">
  <select class="fs" aria-label="Filter by sector"><option value="">All sectors</option>{sec_opts}</select>
  <label class="chk"><input type="checkbox" class="fr"> Hide unresolved</label>
  <span class="spacer"></span>
  <label class="chk">Rows
    <select class="fn" aria-label="Rows to show">
      <option selected>25</option><option>50</option><option>100</option>
      <option>250</option><option value="0">All</option>
    </select></label>
  <span class="count"></span>
</div>
<div class="tw"><table id="t-stem">
<thead><tr><th class="so">Institution</th><th class="so">Sector</th>
<th class="num so" data-t="n">Doctorates</th>
<th class="num so" data-t="n" data-dir="-1">Non-resident</th>
<th class="so">Department page</th><th>People</th></tr></thead>
<tbody>{''.join(sec_row(r) for r in sec)}</tbody></table></div>
</details>

<details class="sec" id="programs" open>
<summary><h2>Programs by thesis volume</h2><a class="sec-anchor" href="#programs" title="Link to this section" aria-label="Link to this section">#</a></summary>
<p class="sub">{len(prog)} departments from the dissertation record, with
the size of their thesis output. Where the department site has been
resolved and verified, the last column links straight to it and to its
roster.</p>
<div class="ctl" data-for="t-prog">
  <input class="ff" type="search" placeholder="Filter institution or program&hellip;"
         aria-label="Filter rows">
  <select class="fs" aria-label="Filter by sector"><option value="">All sectors</option>{sec_opts}</select>
  <label class="chk"><input type="checkbox" class="fr"> Hide unresolved</label>
  <span class="spacer"></span>
  <label class="chk">Rows
    <select class="fn" aria-label="Rows to show">
      <option selected>25</option><option>50</option><option>100</option>
      <option>250</option><option value="0">All</option>
    </select></label>
  <span class="count"></span>
</div>
<div class="tw"><table id="t-prog">
<thead><tr><th class="so">Program</th><th class="so">Institution</th>
<th class="so">Sector</th><th class="num so" data-t="n" data-dir="-1">Theses</th>
<th class="so">Department page</th><th>People</th></tr></thead>
<tbody>{''.join(prog_row(r) for r in prog)}</tbody></table></div>
</details>


<details class="sec" id="find" open>
<summary><h2>Find an institution, program or lab</h2><a class="sec-anchor" href="#find" title="Link to this section" aria-label="Link to this section">#</a></summary>
<p class="sub">Type any part of a university, a department or a research
group. {len(index)} institutions, {sum(len(e["programs"]) for e in index)}
programs, {sum(len(e["labs"]) for e in index)} labs with an archived
roster.</p>
<div class="search">
  <input id="q" type="search" autocomplete="off" spellcheck="false"
         placeholder="Missouri, aerospace, nuclear, Stony Brook&hellip;"
         aria-label="Search institutions, programs and labs">
  <div id="ac" class="ac" role="listbox" hidden></div>
</div>
<div id="results" class="results"></div>
<p class="hint" id="hint">Start typing, or
<button type="button" class="lnk" data-q="nuclear">nuclear</button>,
<button type="button" class="lnk" data-q="aerospace">aerospace</button>,
<button type="button" class="lnk" data-q="Missouri">Missouri S&amp;T</button>,
<button type="button" class="lnk" data-q="Stony Brook">Stony Brook</button>.</p>
</details>

<details class="sec" id="methodology" open>
<summary><h2>Methodology</h2><a class="sec-anchor" href="#methodology" title="Link to this section" aria-label="Link to this section">#</a></summary>
<p class="sub">The shares are IPEDS field codes: a census of degrees
conferred, not a count of people and not a statement about anyone's
origin. A card appears where a program awarded at least
{MIN_DOCTORATES} doctorates over the window, so the share rests on more
than a handful of degrees.</p>
<p class="sub">Every department link was fetched and checked. A URL is
listed only if it returned 200 and the page itself proved it is the
right department &mdash; a university 404 handler also answers 200.</p>
<p class="sub">The research-group table counts people a principal
investigator lists on a public laboratory page. Those pages are
archived. A name-marker share is an inference from names, never a
statement of anyone's citizenship, and it is given with its
denominator because a share of twelve is twelve. It says how unusual a
composition is and not why: a group recruits from who applies, from
collaborators, from a shared language, from a technique taught in few
places.</p>
<p class="sub">Where a department bundles several subjects, the split
comes from the <strong>degree conferred</strong>, taken one record at a
time from the university's own repository. Those counts are exact.
Grouping the degree names into the fields named here is
<strong>approximate and generated by Super Intelligence</strong>
({E(degree_classes.get("model", "a model"))},
{E(degree_classes.get("generated", ""))}).</p>
</details>
</main>
<script id="idx" type="application/json">__INDEX__</script>
<script>
(function () {{
  var IDX = JSON.parse(document.getElementById('idx').textContent);
  var q = document.getElementById('q'), ac = document.getElementById('ac');
  var res = document.getElementById('results'), hint = document.getElementById('hint');

  // A blended match: the institution name, any of its programs, any of
  // its labs, or a sector. One index, one pass -- 131 institutions is
  // small enough that there is no reason to build a trie for it.
  function hits(term) {{
    var t = term.toLowerCase().trim();
    if (!t) return [];
    var out = [];
    IDX.forEach(function (e) {{
      var inInst = e.name.toLowerCase().indexOf(t) >= 0;
      var progs = e.programs.filter(function (p) {{
        return inInst || p.name.toLowerCase().indexOf(t) >= 0
            || (p.sector || '').indexOf(t) >= 0; }});
      var labs = e.labs.filter(function (l) {{
        return inInst || l.name.toLowerCase().indexOf(t) >= 0; }});
      if (inInst || progs.length || labs.length) {{
        out.push({{e: e, programs: progs, labs: labs, inInst: inInst}});
      }}
    }});
    // Institution-name matches first, then by how much they carry.
    out.sort(function (a, b) {{
      if (a.inInst !== b.inInst) return a.inInst ? -1 : 1;
      return (b.labs.length + b.programs.length) - (a.labs.length + a.programs.length);
    }});
    return out;
  }}

  function esc(x) {{ return String(x).replace(/[&<>"]/g, function (c) {{
    return {{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[c]; }}); }}

  function rosterLink(p) {{
    if (!p.roster) return '';
    var k = p.roster_kind === 'students' ? 'students' : 'people';
    return ' <a class="' + (k === 'students' ? 'stu' : '') + '" href="' +
           esc(p.roster) + '" target="_blank" rel="noopener">' + k + ' &rarr;</a>';
  }}

  function render(list) {{
    if (!list.length) {{ res.innerHTML = '<p class="sub">Nothing matches.</p>'; return; }}
    res.innerHTML = list.slice(0, 12).map(function (h) {{
      var e = h.e;
      var progs = h.programs.slice(0, 14).map(function (p) {{
        var val = p.nra != null ? p.nra + '% non-resident'
                 : (p.theses ? p.theses + ' theses' : '');
        var link = p.url ? '<a href="' + esc(p.url) + '" target="_blank" rel="noopener">'
                   + esc(p.name) + '</a>' : esc(p.name);
        return '<li>' + link + ' <span class="mut">' + esc(val) + '</span>'
             + rosterLink(p) + '</li>';
      }}).join('');
      var labs = h.labs.map(function (l) {{
        return '<li><a href="' + esc(l.url) + '" target="_blank" rel="noopener">'
             + esc(l.name) + '</a> <span class="mut">' + l.members
             + ' listed</span>' + (l.snapshot ? ' <a class="sm" href="/labs/'
             + esc(l.snapshot) + '">snapshot</a>' : '') + '</li>';
      }}).join('');
      return '<article class="card"><h3>' + esc(e.name) + '</h3>'
           + (labs ? '<p class="k">Labs</p><ul class="lab">' + labs + '</ul>' : '')
           + (progs ? '<p class="k">Programs</p><ul>' + progs + '</ul>' : '')
           + '</article>';
    }}).join('');
  }}

  function suggest(term) {{
    var t = term.toLowerCase().trim();
    if (!t) {{ ac.hidden = true; return; }}
    var names = [];
    IDX.forEach(function (e) {{
      if (e.name.toLowerCase().indexOf(t) >= 0) names.push(e.name);
      e.labs.forEach(function (l) {{
        if (l.name.toLowerCase().indexOf(t) >= 0) names.push(l.name); }});
      e.programs.forEach(function (p) {{
        if (p.name.toLowerCase().indexOf(t) >= 0 && names.indexOf(p.name) < 0)
          names.push(p.name); }});
    }});
    names = names.slice(0, 8);
    if (!names.length) {{ ac.hidden = true; return; }}
    ac.innerHTML = names.map(function (n) {{
      return '<button type="button" role="option">' + esc(n) + '</button>'; }}).join('');
    ac.hidden = false;
  }}

  var timer;
  q.addEventListener('input', function () {{
    clearTimeout(timer);
    timer = setTimeout(function () {{
      hint.style.display = q.value ? 'none' : '';
      suggest(q.value);
      render(hits(q.value));
    }}, 90);
  }});
  ac.addEventListener('click', function (e) {{
    var b = e.target.closest('button'); if (!b) return;
    q.value = b.textContent; ac.hidden = true;
    hint.style.display = 'none'; render(hits(q.value));
  }});
  q.addEventListener('keydown', function (e) {{
    if (e.key === 'Escape') {{ ac.hidden = true; }}
  }});
  document.addEventListener('click', function (e) {{
    if (!e.target.closest('.search')) ac.hidden = true;
  }});
  document.querySelectorAll('.lnk').forEach(function (b) {{
    b.addEventListener('click', function () {{
      q.value = b.dataset.q; hint.style.display = 'none';
      render(hits(q.value)); q.focus();
    }});
  }});
}})();
</script>
<script>
/* One controller for every table with a .ctl bar above it. Filters AND
   together: free text over institution and first cell, sector, and
   whether the row resolved to a real department page. The row cap is
   applied AFTER filtering, so "50" means fifty matches rather than fifty
   rows of which some are hidden. */
document.querySelectorAll('.ctl').forEach(function (bar) {{
  var table = document.getElementById(bar.dataset.for);
  if (!table) return;
  var rows = [].slice.call(table.tBodies[0].rows);
  var txt = bar.querySelector('.ff'), sel = bar.querySelector('.fs');
  var res = bar.querySelector('.fr'), lim = bar.querySelector('.fn');
  var out = bar.querySelector('.count');
  /* PAGES, NOT A CAP. The row count used to truncate: "25 of 32
     shown" and no way to reach the other seven. It is now a page
     size, with a bar under the table to move between pages. */
  var page = 1;
  var pager = document.createElement('div');
  pager.className = 'pager';
  var wrap = table.closest('.tw');
  if (wrap && wrap.parentNode) wrap.parentNode.insertBefore(
      pager, wrap.nextSibling);

  function apply() {{
    var t = txt.value.toLowerCase().trim(), sc = sel.value;
    var onlyRes = res.checked, size = parseInt(lim.value, 10) || 0;
    var hits = [];
    rows.forEach(function (tr) {{
      var ok = true;
      if (t) ok = (tr.dataset.inst || '').indexOf(t) >= 0 ||
                  tr.cells[0].textContent.toLowerCase().indexOf(t) >= 0;
      if (ok && sc) ok = tr.dataset.sector === sc;
      if (ok && onlyRes) ok = tr.dataset.resolved === '1';
      if (ok) hits.push(tr); else tr.style.display = 'none';
    }});
    var pages = size ? Math.max(1, Math.ceil(hits.length / size)) : 1;
    if (page > pages) page = pages;
    var from = size ? (page - 1) * size : 0;
    var to = size ? from + size : hits.length;
    hits.forEach(function (tr, i) {{
      tr.style.display = (i >= from && i < to) ? '' : 'none';
    }});

    out.textContent = hits.length
      ? (size && hits.length > size
         ? (from + 1) + '\u2013' + Math.min(to, hits.length) +
           ' of ' + hits.length
         : hits.length + ' rows')
      : 'no rows';

    pager.innerHTML = '';
    if (pages > 1) {{
      var mk = function (label, target, on) {{
        var b = document.createElement('button');
        b.type = 'button';
        b.className = 'pg' + (on ? ' on' : '');
        b.textContent = label;
        if (target === null) {{ b.disabled = true; }}
        else b.addEventListener('click', function () {{
          page = target; apply();
          wrap.scrollTop = 0;
        }});
        pager.appendChild(b);
      }};
      mk('\u2039', page > 1 ? page - 1 : null, false);
      //: first, last, and a window around the current page -- a
      //: hundred numbered buttons is not navigation
      var nums = [];
      for (var i = 1; i <= pages; i++) {{
        if (i === 1 || i === pages || Math.abs(i - page) <= 2) nums.push(i);
      }}
      var prev = 0;
      nums.forEach(function (i) {{
        if (i - prev > 1) {{
          var e = document.createElement('span');
          e.className = 'pg-gap'; e.textContent = '\u2026';
          pager.appendChild(e);
        }}
        mk(String(i), i, i === page);
        prev = i;
      }});
      mk('\u203a', page < pages ? page + 1 : null, false);
    }}
  }}
  //: a filter or a new page size starts again at page one
  [txt, sel, res, lim].forEach(function (el) {{
    el.addEventListener('change', function () {{ page = 1; }});
  }});
  [txt, sel, res, lim].forEach(function (el) {{
    el.addEventListener(el.classList.contains('ff') ? 'input' : 'change', apply);
  }});

  /* Sorting. The row cap is applied after the sort, so "top 50 by
     doctorates" means the fifty largest, not the first fifty of the
     original order re-ranked among themselves. A numeric column strips
     everything but digits and the decimal point, so "94.4%" and "1,216"
     both compare as numbers. */
  var tbody = table.tBodies[0];
  [].forEach.call(table.tHead.rows[0].cells, function (th, i) {{
    if (!th.classList.contains('so')) return;
    th.tabIndex = 0;
    th.setAttribute('role', 'button');
    function go() {{
      var numeric = th.dataset.t === 'n';
      var first = parseInt(th.dataset.dir || '1', 10);
      var dir = th.dataset.on === '1' ? -parseInt(th.dataset.cur, 10) : first;
      [].forEach.call(table.tHead.rows[0].cells, function (o) {{
        delete o.dataset.on; o.removeAttribute('aria-sort');
      }});
      th.dataset.on = '1'; th.dataset.cur = dir;
      th.setAttribute('aria-sort', dir === 1 ? 'ascending' : 'descending');
      function key(tr) {{
        var v = tr.cells[i].textContent.trim();
        if (!numeric) return v.toLowerCase();
        var n = parseFloat(v.replace(/[^0-9.-]/g, ''));
        return isNaN(n) ? -Infinity : n;
      }}
      /* A NESTED ROW MOVES WITH ITS PARENT. Sorting the flat list
         would strand an indented child under whatever row happened to
         land above it, which reads as a claim about that row. */
      var tops = rows.filter(function (r) {{
        return !r.classList.contains('kid'); }});
      /* keyed on the element, not its row index -- an index shifts
         as soon as the first row is re-appended */
      var kids = new Map();
      var owner = null;
      rows.forEach(function (r) {{
        if (r.classList.contains('kid')) {{
          if (owner) {{
            if (!kids.has(owner)) kids.set(owner, []);
            kids.get(owner).push(r);
          }}
        }} else {{ owner = r; }}
      }});
      tops.sort(function (a, b) {{
        var ka = key(a), kb = key(b);
        return ka < kb ? -dir : ka > kb ? dir : 0;
      }});
      tops.forEach(function (tr) {{
        tbody.appendChild(tr);
        (kids.get(tr) || []).forEach(function (k) {{ tbody.appendChild(k); }});
      }});
      rows = [].slice.call(tbody.rows);
      apply();
    }}
    th.addEventListener('click', go);
    th.addEventListener('keydown', function (e) {{
      if (e.key === 'Enter' || e.key === ' ') {{ e.preventDefault(); go(); }}
    }});
  }});

  apply();
}});
</script>
<script>
/* "Display in page" shows a roster inside this page instead of
   navigating away, so a reader can move between departments without
   losing their place in the table.

   MOST OF THESE PAGES REFUSE TO BE FRAMED. Nine of thirty-three allow
   it; the rest send X-Frame-Options or a frame-ancestors policy, and a
   browser gives almost no usable signal when that happens -- the load
   event fires either way in some browsers and not at all in others, so
   waiting to find out shows a blank rectangle and then guesses. Each
   link therefore carries data-frame, measured at build time by
   probe_framing.py, and a link that cannot be framed opens in a new tab
   whatever the checkbox says. The checkbox is a preference, not a
   promise the other site has made. */
(function () {{
  var box = document.getElementById('inpage');
  var viewer = document.getElementById('viewer');
  var frame = document.getElementById('viewer-frame');
  var title = document.getElementById('viewer-title');
  var out = document.getElementById('viewer-out');
  var close = document.getElementById('viewer-close');
  var labs = document.getElementById('labs');
  if (!box || !viewer || !labs) return;

  function show(url, name, original) {{
    frame.src = url;
    title.textContent = name;
    // "Open in a new tab" always goes to the LIVE page, never the
    // archive: a reader following up wants the real thing.
    out.href = original || url;
    viewer.hidden = false;
    viewer.scrollIntoView({{ block: 'nearest', behavior: 'smooth' }});
  }}
  close.addEventListener('click', function () {{
    viewer.hidden = true;
    frame.src = 'about:blank';     // stop it loading in the background
  }});

  labs.addEventListener('click', function (e) {{
    var a = e.target.closest('a[data-frame]');
    if (!a || !box.checked) return;          // unchecked: the href wins
    var live = a.dataset.frame === '1';
    var arch = a.dataset.archive || '';
    // The live page first where it allows framing. Where it does not,
    // the Internet Archive's copy, which sends no X-Frame-Options -- and
    // which is the better thing to point at anyway, being the page as it
    // stood on a stated date rather than whatever it says today.
    var src = live ? a.href : arch;
    if (!src) return;                        // neither: the href wins
    e.preventDefault();
    var label = a.textContent.trim();
    if (!live) {{
      var d = a.dataset.archived || '';
      label += d
        ? '  \u00b7  archived ' + d.slice(0, 4) + '-' + d.slice(4, 6) +
          '-' + d.slice(6, 8)
        : '  \u00b7  archived copy';
    }}
    show(src, label, a.href);
  }});

  //: With the box off, every link is an ordinary new-tab link, which is
  //: what target="_blank" already does. Nothing to undo.
}})();
</script>
<script>
/* The section links copy their URL and do not toggle the section they
   sit in -- a click inside a <summary> opens or closes it by default,
   which is the opposite of what a link to a section should do. */
document.addEventListener('click', function (e) {{
  var a = e.target.closest && e.target.closest('a.sec-anchor');
  if (!a) return;
  e.preventDefault();
  e.stopPropagation();
  var id = a.getAttribute('href').slice(1);
  var el = document.getElementById(id);
  if (el && !el.open) el.open = true;
  history.replaceState(null, '', '#' + id);
  var url = location.href;
  var done = function () {{
    a.classList.add('copied');
    setTimeout(function () {{ a.classList.remove('copied'); }}, 1400);
  }};
  if (navigator.clipboard && navigator.clipboard.writeText) {{
    navigator.clipboard.writeText(url).then(done, done);
  }} else {{ done(); }}
  if (el) el.scrollIntoView({{ block: 'start', behavior: 'smooth' }});
}});
</script>
<script src="/analytics-beacon.js" defer></script>
<script src="/sidebar.js"></script>
</body>
</html>
"""
    #: AFTER formatting. The index is JSON and JSON is all braces; putting
    #: it through the f-string would need every one doubled and one missed
    #: brace would be a silent syntax error in the page.
    page = page.replace("__INDEX__", json.dumps(index, separators=(",", ":")))
    write_text(OUT, page)
    print(f"Wrote {OUT.relative_to(ROOT)}")
    print(f"  {len(lab_rows)} archived rosters, {len(sec)} STEM "
          f"programs, {len(prog)} ranked programs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
