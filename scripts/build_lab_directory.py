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
    sql = (f"-- Every thesis and dissertation this site holds for this\n"
           f"-- department. Names are as the university published them.\n"
           f"SELECT year, name, title, url\n"
           f"FROM stem_records\n"
           f"WHERE university = '{slug}'\n"
           f"  AND department = '{dept.replace(chr(39), chr(39) * 2)}'\n"
           f"ORDER BY year DESC, name")
    return ("/query?sql=" + quote(sql), dept, n)



def standouts_html(sec: list, urls: dict, urls_loose: dict,
                   dept_index: dict, n: int = 8) -> str:
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
    MIN_DOCTORATES = 20
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

        ev = []
        if th:
            ev.append(f'<a href="{E(th[0])}" target="_blank" rel="noopener">'
                      f'{fmt_n(th[2])} theses in {E(th[1])}</a>')
        if u.get("students_url"):
            ev.append(f'<a href="{E(u["students_url"])}" target="_blank" '
                      f'rel="noopener">Graduate roster</a>')
        if u.get("faculty_url"):
            ev.append(f'<a href="{E(u["faculty_url"])}" target="_blank" '
                      f'rel="noopener">Faculty</a>')
        if not u.get("students_url") and u.get("directory_url"):
            ev.append(f'<a href="{E(u["directory_url"])}" target="_blank" '
                      f'rel="noopener">Department directory</a>')
        if u.get("url"):
            ev.append(f'<a href="{E(u["url"])}" target="_blank" '
                      f'rel="noopener">Department page</a>')
        #: A case with nothing to click is not a case worth featuring.
        if not ev:
            continue

        share = r.get("nra_share") or 0
        d, nra = r.get("doctorates") or 0, r.get("nra") or 0
        missing = []
        if not (u.get("students_url") or u.get("directory_url")):
            missing.append("no public graduate roster")
        if not u.get("faculty_url"):
            missing.append("no faculty page found")
        note = (f'<p class="miss">{E("; ".join(missing))}.</p>'
                if missing else "")

        cards.append(f"""
  <article class="card">
    <div class="pct">{share:.1f}%</div>
    <h3>{E(inst)}</h3>
    <p class="fld">{SECTOR_LABEL.get(field, field)}</p>
    <p class="cnt">{fmt_n(nra)} of {fmt_n(d)} doctorates awarded to
      non-residents, 2015&ndash;2022</p>
    <div class="ev">{" &middot; ".join(ev)}</div>
    {note}
  </article>""")

    if not cards:
        return ""
    return f"""
<section id="standouts">
<h2>The sharpest cases</h2>
<p class="sub">The highest non-resident shares on this site, on programs
awarding at least {MIN_DOCTORATES} doctorates over the window, so the
share rests on more than a handful of degrees. Every card links to what
is behind it. Figures are IPEDS field codes, a census of degrees
conferred, not a count of people and not a statement about anyone's
origin.</p>
<div class="cards">{"".join(cards)}</div>
</section>"""


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
    #: the department is the longest surviving segment, not the first
    t = max(keep, key=len)
    #: strip a leading "Department of" and a trailing institution
    t = re.sub(r"^(the\s+)?(department|dept\.?|school|division)\s+of\s+", "",
               t, flags=re.I).strip()
    for tail in (head, head.replace("The ", ""), "University", "College of Engineering"):
        if tail and t.lower().endswith(tail.lower()) and len(t) > len(tail) + 3:
            t = t[: -len(tail)].strip(" -\u2013\u2014|,")
    t = t.strip(" -|,")
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
    lab_rows.sort(key=lambda r: -(r["share"] or 0))

    # ---- programs in the sectors that carry a federal access regime
    #: EVERY SECTOR. This was limited to the ones carrying an access
    #: regime, which left out AI, materials and bio -- the three with the
    #: most programs in them. Ordered by non-resident share, because that
    #: is what the table is for.
    sec = sorted(security.get("targets", []),
                 key=lambda r: -(r.get("nra_share") or 0))
    standouts = standouts_html(sec, urls, urls_loose, dept_index)

    # ---- programs by concentration, from the dissertation record
    prog = ranked.get("targets", [])

    def lab_row(r):
        snap = (f'<a class="sm" href="/labs/{E(Path(r["snapshot"]).name)}">'
                f'snapshot</a>' if r.get("snapshot") else "")
        od = ' <span class="od" title="fetched despite robots.txt">ovr</span>' \
             if r.get("overridden") else ""
        return (f'<tr><td><a href="{E(r["url"])}" target="_blank" '
                f'rel="noopener">{E(r["group"][:62])}</a>{od}</td>'
                f'<td class="mut">{E(r["institution"][:34])}</td>'
                f'<td class="num">{r["members"]}</td>'
                f'<td class="mut">{E(r["retrieved"])} {snap}</td></tr>')

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
<meta name="robots" content="noindex, nofollow">
<title>Lab and Program Directory</title>
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
  .card .ev {{ font-size: .82rem; line-height: 1.75; }}
  .card .miss {{ font-size: .75rem; color: var(--text-muted);
    margin: .4rem 0 0; font-style: italic; }}
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
<h1>Lab and program directory</h1>
<p class="lede">A navigation index: the programs and research groups this
analysis has reached, each one a direct link to the department and, where
one exists, to its public roster.</p>
<div class="warn"><strong>Every department link here was fetched and
checked.</strong> A URL is only listed if it returned 200 and the page
itself proved it is the right department &mdash; a university 404 handler
also answers 200. The non-resident shares are IPEDS field-code figures, a
census rather than an estimate.</div>

{standouts}
<section id="find">
<h2>Find an institution, program or lab</h2>
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
</section>

<section id="labs">
<h2>Examples of statistically anomalous non-diversity</h2>
<p class="sub">Rosters read and snapshotted, so the count can be checked
against the page as it stood. {len(lab_rows)} so far &mdash; the crawler
reads roughly a third of lab sites, because they share no common
structure.</p>
<div class="tw"><table>
<thead><tr><th>Group</th><th>Institution</th><th class="num">Members listed</th>
<th>Archived</th></tr></thead>
<tbody>{''.join(lab_row(r) for r in lab_rows)}</tbody></table></div>
</section>

<section id="regime">
<h2>STEM programs</h2>
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
      <option>25</option><option selected>50</option><option>100</option>
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
</section>

<section id="programs">
<h2>Programs by thesis volume</h2>
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
      <option>25</option><option selected>50</option><option>100</option>
      <option>250</option><option value="0">All</option>
    </select></label>
  <span class="count"></span>
</div>
<div class="tw"><table id="t-prog">
<thead><tr><th class="so">Program</th><th class="so">Institution</th>
<th class="so">Sector</th><th class="num so" data-t="n" data-dir="-1">Theses</th>
<th class="so">Department page</th><th>People</th></tr></thead>
<tbody>{''.join(prog_row(r) for r in prog)}</tbody></table></div>
</section>
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
  function apply() {{
    var t = txt.value.toLowerCase().trim(), sc = sel.value;
    var onlyRes = res.checked, cap = parseInt(lim.value, 10) || 0;
    var shown = 0, matched = 0;
    rows.forEach(function (tr) {{
      var ok = true;
      if (t) ok = (tr.dataset.inst || '').indexOf(t) >= 0 ||
                  tr.cells[0].textContent.toLowerCase().indexOf(t) >= 0;
      if (ok && sc) ok = tr.dataset.sector === sc;
      if (ok && onlyRes) ok = tr.dataset.resolved === '1';
      if (ok) {{
        matched++;
        if (!cap || shown < cap) {{ tr.style.display = ''; shown++; }}
        else tr.style.display = 'none';
      }} else tr.style.display = 'none';
    }});
    out.textContent = (cap && matched > shown)
      ? shown + ' of ' + matched + ' shown' : matched + ' rows';
  }}
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
        var n = parseFloat(v.replace(/[^0-9.\-]/g, ''));
        return isNaN(n) ? -Infinity : n;
      }}
      rows.sort(function (a, b) {{
        var ka = key(a), kb = key(b);
        return ka < kb ? -dir : ka > kb ? dir : 0;
      }});
      rows.forEach(function (tr) {{ tbody.appendChild(tr); }});
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
