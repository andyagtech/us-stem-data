#!/usr/bin/env python3
"""The government's own register of China-related prosecutions, parsed.

WHY THIS IS BUILT FROM AN ARCHIVED PAGE

The Justice Department ran the China Initiative from November 2018 and
published, on a National Security Division page, a dated list of example
prosecutions. The Initiative was ended on 23 February 2022. The page was not
updated after 19 November 2021 and now sits under /archives/.

That page is the only official enumeration of these cases that has ever
existed. Nothing replaced it. So the register here is the government's own
list, parsed from its own words, and the fact that it stops in 2021 is itself
the finding: after that date a reader can find cases one press release at a
time and can never know how many there were. No rate, no trend, no denominator.

WHAT IS DERIVED AND WHAT IS QUOTED

Every case's date, headline and summary are DOJ's, unedited. This script adds
exactly two things, and both record their own evidence so a reader can check
them:

  category        which kind of case, from a keyword test over DOJ's own
                  headline and summary
  research_role   whether DOJ's own words place the defendant in a research
                  job or a degree programme

Each carries the matched phrase in `evidence`, so no classification here is a
private judgement. A case DOJ described without any such phrase is
`unclassified`, not guessed.

WHAT THIS IS NOT

It is not a list of convictions. The list mixes charges, pleas and verdicts,
and the snapshot froze in 2021 while the courts kept going -- three of the
academic cases on it later collapsed. Outcomes stated here are only the ones
DOJ stated on the page, as of its own last-updated date; `outcome_stated` is
false where the page's summary announced a charge and nothing more.

A charge is an allegation. Nothing in this dataset says any person named in it
is guilty of anything.

Sources:
  data/security/pages/doj_nsd_china_initiative.html   the archived DOJ page
  data/security/cases_since.json                      cases after the list
                                                      stopped, each with a
                                                      primary .gov source

Usage:
    python3 scripts/build_security_cases.py
    python3 scripts/build_security_cases.py --fetch     # re-download sources
"""
from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from atomic_write import write_json

ROOT = Path(__file__).resolve().parents[1]
PAGES = ROOT / "data" / "security" / "pages"
SINCE = ROOT / "data" / "security" / "cases_since.json"
OUT = ROOT / "site" / "data" / "security_cases.json"

ARCHIVE_URL = ("https://www.justice.gov/archives/nsd/information-about-"
               "department-justice-s-china-initiative-and-compilation-china-related")
ARCHIVE_FILE = PAGES / "doj_nsd_china_initiative.html"

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120 Safari/537.36")

MONTHS = ("January February March April May June July August September "
          "October November December").split()
DATE_RE = re.compile(
    r"^(%s)\s+(\d{1,2}),\s+(20\d\d)$" % "|".join(MONTHS))

#: WHO THE DEFENDANT WAS, read from DOJ's own headline and nothing else.
#:
#: The first version of this test ran over the headline AND the summary, and it
#: was wrong in a way worth recording. "University" in a summary can be the
#: VICTIM (the APT41 hacking indictment names the universities that were
#: attacked) or the RECIPIENT (a man who exported goods TO Northwestern
#: Polytechnical University). Both came out as academic cases. The institution
#: appearing in a case says nothing about who the defendant was.
#:
#: So the role is matched on a ROLE WORD -- professor, researcher, student,
#: laboratory employee -- in the headline, where DOJ states the defendant's own
#: job. "University" on its own is not evidence of anything and is not here.
#: The first pattern that matches wins and the matched text is stored, so every
#: classification on the page can be checked against DOJ's words by a reader.
ROLES: tuple[tuple[str, str], ...] = (
    ("faculty", r"\bprofessors?\b|\bfaculty\b"),
    # NASA and the national labs are employers in these headlines. NIH is NOT
    # and was removed from this pattern: "Researcher Indicted for Scheme to
    # Defraud National Institutes of Health" is a university employee and a
    # federal FUNDER, and matching the funder put him in the wrong chair.
    ("federal_lab", r"National Laborator(?:y|ies)|\bNASA\b"),
    ("hospital_researcher", r"hospital researcher|medical researcher"),
    ("university_researcher",
     r"university researcher|\bresearcher\b(?![^,]*\binstitute settlement)|"
     r"research (?:scientist|associate|fellow)|\bpostdoc\w*|"
     r"\bprincipal investigator\b|\bscholars?\b"),
    ("student", r"\bgraduate students?\b|\bdoctoral (?:students?|candidates?)\b|"
                r"\bPh\.?D\.? (?:students?|candidates?)\b|\bvisiting (?:scholar|student)\b"),
    ("degree_holder", r"\bPh\.?D\.?\b|\bdoctorate\b"),
    ("corporate_technical",
     r"\bengineers?\b|\bchemists?\b|\bscientists?\b|\btechnicians?\b"),
)

#: The roles that put a person inside the pipeline this site measures: a
#: university post, a graduate programme, a federal laboratory or a hospital
#: research job. A chemist or engineer at a company is a research worker too,
#: but their training is not established by DOJ's headline, so they are counted
#: separately and never folded into this group.
PIPELINE_ROLES = frozenset(
    {"faculty", "university_researcher", "student", "federal_lab",
     "hospital_researcher"})

#: Items on the list that are not a criminal case against a person. The list
#: mixes them in with the prosecutions: two are recommendations to the FCC, one
#: is a civil settlement with an institute, one is a court-authorised technical
#: operation against web shells. Counting them as prosecutions would inflate
#: every share on the page, so they are separated and counted in the open.
NOT_A_PROSECUTION = (
    r"Recommends? that the FCC|Recommend the FCC|"
    r"Reaches \$[\d.]+ Million Settlement|Court-Authorized Effort")

#: What the case was about. Tested after the role, because the role is the more
#: specific fact: "Former GE Engineer ... Charged with Economic Espionage" is
#: both, and this site cares which chair the person sat in.
CATEGORIES: tuple[tuple[str, str], ...] = (
    ("state_actor",
     r"intelligence officer|ministry of state security|\bMSS\b|"
     r"People'?s Liberation Army|\bPLA\b|Chinese Military Personnel|"
     r"act(?:ing|ed)? (?:in the (?:U\.?S\.?|United States) )?as (?:an|illegal)"
     r"[^.]{0,30}agents?|agents? of the (?:Chinese|PRC)|Espionage Act|"
     r"\bCIA Officer\b|State Department Employee|"
     r"on behalf of the (?:Chinese|PRC) government"),
    ("cyber",
     r"\bhack(?:er|ing|s)?\b|computer intrusion|malicious cyber|web shells|"
     r"\bAPT\d"),
    ("export_control",
     r"illegal(?:ly)? export|export[- ]control|\bsmuggl|unlicensed export|"
     r"Entity List|conspiring to (?:illegally )?export|conspiracy to export|"
     r"violate the Export|U\.?S\.? export (?:laws|restrictions)"),
    ("trade_secrets",
     r"trade secrets?|economic espionage"),
    ("fraud_or_sanctions",
     r"bank fraud|sanctions|Foreign Corrupt Practices|misleading|"
     r"multi-level marketing|obstruction of justice"),
    ("grant_or_visa_fraud",
     r"grant fraud|grant applications?|false statements?|visa fraud|"
     r"failing to disclose|conflict of interest|wire fraud"),
)


def fetch(url: str, dest: Path) -> None:
    """Download one page through justice.gov's bot interstitial.

    A plain GET returns a 2.5 KB challenge page with a `bm-verify` token in a
    meta refresh, not the document. The retry below -- keep the cookie jar,
    replay the token -- is what turns that into the real 130 KB page. Without
    it this script would cheerfully cache the challenge and parse nothing, so
    the size is asserted rather than trusted.
    """
    jar = dest.with_suffix(".cookies")
    first = subprocess.run(
        ["curl", "-sL", "-c", str(jar), "-A", UA, url],
        capture_output=True, text=True, check=True).stdout
    token = re.search(r"bm-verify=([^'\"&]+)", first)
    if token:
        sep = "&" if "?" in url else "?"
        body = subprocess.run(
            ["curl", "-sL", "-b", str(jar), "-c", str(jar), "-A", UA,
             "-H", f"Referer: {url}", f"{url}{sep}bm-verify={token.group(1)}"],
            capture_output=True, text=True, check=True).stdout
    else:
        body = first
    jar.unlink(missing_ok=True)
    if len(body) < 20_000 or "bm-verify" in body[:3000]:
        raise SystemExit(
            f"FAIL: {url} returned {len(body)} bytes, which is the bot "
            f"interstitial and not the document. Nothing written.")
    dest.write_text(body, encoding="utf-8")
    print(f"  fetched {len(body):,} bytes -> {dest.relative_to(ROOT)}")


def text_of(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def classify(haystack: str, table) -> tuple[str, str]:
    for name, pattern in table:
        m = re.search(pattern, haystack, re.I)
        if m:
            return name, m.group(0)
    return "unclassified", ""


def parse_archive(path: Path) -> tuple[list[dict], str]:
    """Pull the dated case list out of the archived NSD page.

    The entries are flat siblings -- a date paragraph, a linked headline, then
    one or more summary paragraphs -- so they are read as a run rather than as
    nested blocks. One entry of the 58 does not use the <b><u> wrapper the
    other 57 do, which is why the date is matched on its TEXT and not on its
    markup.
    """
    raw = path.read_text(encoding="utf-8", errors="replace")
    art = re.search(r"<article.*?</article>", raw, re.S)
    if not art:
        raise SystemExit(f"FAIL: no <article> in {path}. Page layout changed.")
    body = re.sub(r"<(script|style).*?</\1>", " ", art.group(0), flags=re.S)

    stamp = re.search(r"Last Updated\s+(\w+ \d{1,2}, 20\d\d)", text_of(body))
    last_updated = stamp.group(1) if stamp else ""

    start = body.find("China-Related Cases Examples")
    if start < 0:
        raise SystemExit("FAIL: the case-list heading is gone from the page.")
    blocks = re.findall(r"<p[^>]*>(.*?)</p>", body[start:], re.S)

    cases: list[dict] = []
    pending: dict | None = None
    for block in blocks:
        plain = text_of(block)
        if not plain:
            continue
        d = DATE_RE.match(plain)
        if d:
            if pending:
                cases.append(pending)
            month = MONTHS.index(d.group(1)) + 1
            pending = {"date": f"{d.group(3)}-{month:02d}-{int(d.group(2)):02d}",
                       "title": "", "url": "", "summary": ""}
            continue
        if pending is None:
            continue
        if not pending["title"]:
            pending["title"] = plain
            href = re.search(r'href="([^"]+)"', block)
            pending["url"] = href.group(1) if href else ""
            continue
        pending["summary"] = (pending["summary"] + " " + plain).strip()
    if pending:
        cases.append(pending)

    for c in cases:
        hay = f"{c['title']} {c['summary']}"
        # The role comes from the headline alone. See the note on ROLES: a
        # summary names victims and recipients as readily as defendants.
        c["research_role"], c["research_evidence"] = classify(c["title"], ROLES)
        c["in_pipeline"] = c["research_role"] in PIPELINE_ROLES
        prosecution = re.search(NOT_A_PROSECUTION, c["title"], re.I)
        if prosecution:
            c["category"], c["category_evidence"] = "not_a_prosecution", prosecution.group(0)
        elif c["in_pipeline"]:
            c["category"], c["category_evidence"] = "research_pipeline", c["research_evidence"]
        else:
            c["category"], c["category_evidence"] = classify(hay, CATEGORIES)
        # DOJ announced some of these as charges and some as results. The
        # distinction is the difference between an allegation and a finding,
        # so it is read off the words rather than assumed either way.
        c["outcome_stated"] = bool(re.search(
            r"\bconvict|\bpleaded guilty|\bguilty plea|\bsentenc|\bacquitt|"
            r"\bdismiss|deferred prosecution|\bextradit", hay, re.I))
        c["source"] = "DOJ NSD China Initiative compilation (archived)"
    return cases, last_updated


def normalise(text: str) -> str:
    """Flatten the typography so a quoted phrase can be matched.

    DOJ pages use curly apostrophes and non-breaking spaces. A phrase typed
    with a straight apostrophe is the same phrase and must not fail the check
    over a character the reader cannot see.
    """
    for bad, good in (("\u2018", "'"), ("\u2019", "'"), ("\u201c", '"'),
                      ("\u201d", '"'), ("\u2013", "-"), ("\u2014", "-"),
                      ("\u00a0", " ")):
        text = text.replace(bad, good)
    return re.sub(r"\s+", " ", text).strip().lower()


def load_since() -> list[dict]:
    """Cases charged after the official list stopped being updated.

    These are not from any list, because there is no list. Each one is a
    single press release someone had to already know to look for, which is the
    point the page makes with them.

    EVERY QUOTED PHRASE IS CHECKED against the cached page, and a miss fails
    the build. The weaker version of this check tested only that the
    defendant's surname appeared somewhere on the page, which a DOJ press
    release about a different case in the same district would also satisfy.
    Checking the phrases means the words this site puts in DOJ's mouth are
    DOJ's words, verified against the document, every time the build runs.
    """
    if not SINCE.exists():
        return []
    rows = json.loads(SINCE.read_text())
    for r in rows:
        for url_key, file_key, quote_key in (
                ("url", "cached_as", "quotes"),
                ("outcome_url", "outcome_cached_as", "outcome_quotes")):
            if file_key not in r:
                continue
            cached = PAGES / r[file_key]
            if not cached.exists():
                raise SystemExit(
                    f"FAIL: {r[file_key]} is declared by {SINCE.name} and is "
                    f"not on disk. Run with --fetch.")
            page = normalise(text_of(cached.read_text(encoding="utf-8",
                                                      errors="replace")))
            surname = r["name"].split()[-1]
            if surname.lower() not in page:
                raise SystemExit(
                    f"FAIL: '{surname}' does not appear in {r[file_key]}. "
                    f"The declared source does not name the defendant.")
            for quote in r.get(quote_key, ()):
                if normalise(quote) not in page:
                    raise SystemExit(
                        f"FAIL: {r['name']}: this phrase is not in "
                        f"{r[file_key]}:\n    {quote}")
        r["source"] = "DOJ press release; no official list covers this period"
        r["verified_quotes"] = len(r.get("quotes", ())) + len(r.get("outcome_quotes", ()))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch", action="store_true",
                    help="re-download the archived DOJ page and the press releases")
    args = ap.parse_args()

    PAGES.mkdir(parents=True, exist_ok=True)
    if args.fetch:
        fetch(ARCHIVE_URL, ARCHIVE_FILE)
        for r in json.loads(SINCE.read_text()) if SINCE.exists() else []:
            fetch(r["url"], PAGES / r["cached_as"])
    if not ARCHIVE_FILE.exists():
        raise SystemExit(f"FAIL: {ARCHIVE_FILE} missing. Run with --fetch.")

    cases, last_updated = parse_archive(ARCHIVE_FILE)
    since = load_since()

    by_year: dict[str, int] = {}
    by_category: dict[str, int] = {}
    by_role: dict[str, int] = {}
    for c in cases:
        by_year[c["date"][:4]] = by_year.get(c["date"][:4], 0) + 1
        by_category[c["category"]] = by_category.get(c["category"], 0) + 1
        by_role[c["research_role"]] = by_role.get(c["research_role"], 0) + 1

    prosecutions = [c for c in cases if c["category"] != "not_a_prosecution"]
    listed_only = [c for c in cases if c["category"] == "not_a_prosecution"]
    pipeline = [c for c in prosecutions if c["in_pipeline"]]
    any_research = [c for c in prosecutions if c["research_role"] != "unclassified"]

    def pct(num, den):
        return round(100 * num / den, 1) if den else 0.0

    out = {
        "generated": date.today().isoformat(),
        "list": {
            "name": "DOJ National Security Division, China Initiative case compilation",
            "url": ARCHIVE_URL,
            "last_updated": last_updated,
            "initiative_ended": "2022-02-23",
            "entries": len(cases),
            "first_case": min(c["date"] for c in cases) if cases else "",
            "last_case": max(c["date"] for c in cases) if cases else "",
        },
        "totals": {
            "entries": len(cases),
            "prosecutions": len(prosecutions),
            "not_a_prosecution": len(listed_only),
            "in_pipeline": len(pipeline),
            "in_pipeline_pct": pct(len(pipeline), len(prosecutions)),
            "any_research_role": len(any_research),
            "any_research_role_pct": pct(len(any_research), len(prosecutions)),
            "outcome_stated": sum(1 for c in prosecutions if c["outcome_stated"]),
            "charge_only": sum(1 for c in prosecutions if not c["outcome_stated"]),
            "charge_only_pct": pct(sum(1 for c in prosecutions
                                       if not c["outcome_stated"]), len(prosecutions)),
            "years_covered": len(by_year),
            "cases_since_list_stopped": len(since),
        },
        "by_year": dict(sorted(by_year.items())),
        "by_category": dict(sorted(by_category.items(), key=lambda kv: -kv[1])),
        "by_research_role": dict(sorted(by_role.items(), key=lambda kv: -kv[1])),
        "cases": sorted(cases, key=lambda c: c["date"], reverse=True),
        "since": sorted(since, key=lambda r: r["date"], reverse=True),
    }
    write_json(OUT, out, indent=2)
    print(f"Wrote {OUT.relative_to(ROOT)}")
    t = out["totals"]
    print(f"  {len(cases)} entries on the archived list, "
          f"{out['list']['first_case']} to {out['list']['last_case']}")
    print(f"  last updated by DOJ: {last_updated}")
    print(f"  {t['prosecutions']} are prosecutions; {t['not_a_prosecution']} are not")
    for k, v in out["by_category"].items():
        print(f"    {k:<22} {v:>3}")
    print(f"  in the research pipeline: {t['in_pipeline']} "
          f"({t['in_pipeline_pct']}% of prosecutions); any research role: "
          f"{t['any_research_role']} ({t['any_research_role_pct']}%)")
    print(f"  announced as a charge only: {t['charge_only']} ({t['charge_only_pct']}%)")
    for k, v in out["by_research_role"].items():
        print(f"    {k:<34} {v:>3}")
    print(f"  cases added since the list stopped: {len(since)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
