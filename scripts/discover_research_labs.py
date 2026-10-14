#!/usr/bin/env python3
"""Find research-group member pages from the departments already resolved.

THE SEARCH IS THE PROBLEM, NOT THE TEST. Two labs given by name can be
tested on their own. A LIST assembled by scanning cannot: test a
hundred groups against their department's rate and about five clear
p < 0.05 by chance, so a page of "unusual" groups found that way is
partly a page of noise. This script therefore records HOW MANY groups
it examined, which is the number the correction needs, and
rank_research_labs.py applies Benjamini-Hochberg to the whole set
rather than letting each group be judged alone.

HOW IT LOOKS. A department's people page links to faculty; a faculty
page links to a group; a group page has a members list. Rather than
walk all three hops for 398 departments, this looks for the shape
directly -- a link whose text or address says lab, group, or members --
and keeps the ones that turn out to carry a roster.

Usage:
  python3 scripts/discover_research_labs.py --limit 120
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import crawl_resume                                            # noqa: E402
import harvest_lab_rosters as hl                               # noqa: E402
import lab_store                                               # noqa: E402

URLS = ROOT / "data" / "labs" / "program_urls.json"
OUT = ROOT / "data" / "labs" / "discovered_labs.json"
#: WHICH DEPARTMENTS THIS HAS ALREADY WALKED. There was no record, and
#: the only trace of a crawled department was `found_from` on the rows
#: it produced -- so a department that yielded nothing looked exactly
#: like one never visited. With 563 resolved departments and no resume
#: file, the choice was to re-walk everything or to guess, and walking
#: a department is forty fetches against a university's own servers.
#: walk_site_parsers.py has kept a file like this since its first long
#: run; this is the same idea in the other crawler.
#: Seconds one department may spend on its candidate pages. Chosen so a
#: run of 400 departments across five workers finishes in an evening
#: rather than overnight, and so one unresponsive host cannot hold the
#: ordered results behind it.
DEPT_BUDGET = 180

#: The code get() returns when the certificate chain cannot be built.
#: Negative, so it can never collide with an HTTP status.
TLS_FAILED = -495
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 Chrome/124.0 Safari/537.36"}

#: A link that leads to a research group.
LAB_LINK = re.compile(
    r"\b(lab|laboratory|group|research group|team|our team|members|"
    r"people|the group|research team)\b", re.I)
#: and its address usually says so too
LAB_URL = re.compile(
    r"(lab|group|team|research|people|members|~)", re.I)
#: pages that are definitely not a group roster
NOT_LAB = re.compile(
    r"(/news|/event|/calendar|/apply|/admission|/course|/syllab|"
    r"/seminar|/giving|/alumni|/contact|/about$|/jobs|\.pdf$)", re.I)
#: "Lab" also means a room with equipment in it. These titles are
#: facility booking and safety pages, and the first wide crawl
#: returned several: "Lab Equipment Items (Fee For Service)".
NOT_A_RESEARCH_GROUP = re.compile(
    r"(equipment|checkout|fee for service|safety|booking|reserve|"
    r"inventory|machine shop|cleanroom access|instrument|core facility|"
    r"policy|handbook|training and access|rates?\b)", re.I)
#: a members page says so
MEMBERS = re.compile(
    r"\b(members|our team|the team|group members|lab members|people|"
    r"students|researchers|current members)\b", re.I)


#: domain -> institution, reversed from the resolver's hand-kept table.
#: THE CRAWLER WAS RECORDING THE WRONG UNIVERSITY. It credited each
#: group to the department it was reached FROM, so a Duke maths group
#: linked from a Caltech page was filed under Caltech. The host of the
#: page it actually landed on is the authority.
def _domain_map() -> dict:
    import resolve_program_urls as rp
    out = {}
    for inst, dom in rp.DOMAINS.items():
        d = dom.lower().lstrip("www.")
        #: keep the longest institution name per domain, so
        #: "Purdue University-Main Campus" beats "Purdue"
        if d not in out or len(inst) > len(out[d]):
            out[d] = inst
    return out


_DOMAINS: dict = {}


def institution_of(url: str, fallback: str) -> tuple:
    """(institution, how it was decided) from the page's own host."""
    global _DOMAINS
    if not _DOMAINS:
        _DOMAINS = _domain_map()
    host = urlparse(url).netloc.lower().lstrip("www.")
    #: walk up the subdomains: nlplab.cs.duke.edu -> duke.edu
    parts = host.split(".")
    for i in range(len(parts) - 1):
        cand = ".".join(parts[i:])
        if cand in _DOMAINS:
            return _DOMAINS[cand], "host"
    #: a lab on sites.google.com or github.io keeps the department's
    #: institution, because the address says nothing about where it is
    if "sites.google" in host or "github.io" in host:
        return fallback, "host is a hosting service; kept the department's"
    return fallback, "host not recognised; kept the department's"


#: (connect, read). A HOST THAT NEVER ANSWERS COST 25 MINUTES. One
#: department sat at the head of the queue while three sockets stayed in
#: SYN_SENT against an IPv6 address nothing was listening on; a single
#: scalar timeout spends its whole budget on the handshake. Four seconds
#: is generous for a connect and the read keeps the rest.
CONNECT_TIMEOUT = 4


def get(url: str, timeout: int = 15, tries: int = 2):
    """Fetch, with one retry, because a transient failure is not a verdict.

    A connection reset or a DNS blip used to return (0, "", url), which
    is written down as status http_0 and reads later exactly like a page
    that is really gone. Retrying once separates the two cheaply.
    """
    last = (0, "", url)
    for attempt in range(max(1, tries)):
        try:
            r = requests.get(url, headers=UA,
                             timeout=(CONNECT_TIMEOUT, timeout),
                             allow_redirects=True)
            if r.status_code == 429 and attempt + 1 < max(1, tries):
                #: WAIT WHEN TOLD TO WAIT. 12 rows came back http_429 --
                #: a university asking us to slow down, written down as
                #: if the page had failed. Capped, because a server may
                #: name an hour.
                try:
                    wait = min(30, max(1, int(r.headers.get("Retry-After", 5))))
                except (TypeError, ValueError):
                    wait = 5
                time.sleep(wait)
                continue
            return r.status_code, r.text, r.url
        except requests.Timeout:
            #: A timeout IS the answer: this host is too slow to crawl.
            #: Retrying doubles the cost for the same result.
            return 0, "", url
        except requests.exceptions.SSLError:
            #: AN INCOMPLETE CERTIFICATE CHAIN, NOT A DEAD PAGE. A
            #: server that omits its intermediate CA cannot be verified
            #: from certifi, while curl succeeds because the operating
            #: system completes the chain. math.virginia.edu is one;
            #: sites.utdallas.edu, pma.caltech.edu, cse.wustl.edu,
            #: qeg.mit.edu, seal.eng.wayne.edu and apl.washington.edu
            #: are six more already in the data, recorded as http_0 and
            #: so indistinguishable from a page that is really gone.
            #:
            #: This is reported, not worked around. Disabling
            #: verification would accept any certificate at all, and
            #: the fix belongs with the university.
            return TLS_FAILED, "", url
        except requests.RequestException:
            last = (0, "", url)
            if attempt + 1 < max(1, tries):
                time.sleep(1.0)
    return last


def links(html: str, base: str):
    for m in re.finditer(
            r'<a\s[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
            html, re.S | re.I):
        href = urljoin(base, m.group(1))
        text = " ".join(re.sub(r"<[^>]+>", " ", m.group(2)).split())
        if text and len(text) < 90:
            yield text, href


def roster_of(url: str) -> dict | None:
    """If this page lists a group's members, the counts."""
    code, html, final = get(url, 18)
    if code != 200 or len(html) < 1200 or NOT_LAB.search(final):
        return None
    #: A RESEARCH GROUP, NOT A DEPARTMENT ROSTER. The first pass
    #: returned "Current Graduate Students | Aeronautics" nine times:
    #: a departmental list, which the other pipeline already covers.
    #: A group names itself a lab or a group, on the page or in the
    #: address.
    title_m = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
    if title_m and NOT_A_RESEARCH_GROUP.search(title_m.group(1)):
        return None
    head = (html[:4000] + " " + final).lower()
    if not re.search(r"\b(lab|laborator|research group|our group|"
                     r"the group|research team)\b", head):
        return None
    names = hl.best_names(html)
    #: A GROUP, not a department. Four is a group; ninety is a
    #: directory and belongs to the department pipeline, not this one.
    if not 4 <= len(names) <= 60:
        return None
    comp = hl.composition(names)
    title = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
    return {
        "url": final,
        "title": " ".join(title.group(1).split())[:110] if title else "",
        "members": comp.get("members_detected") or 0,
        "composition": comp,
    }


def from_department(row: dict) -> tuple:
    """(rows, finished) for one department page.

    `finished` is False when the department page would not answer or the
    time budget ran out. A department is only ever marked done when it
    finished, so an unfinished one is tried again instead of being
    silently written off.
    """
    base = row.get("faculty_url") or row.get("url")
    if not base:
        return [], True
    code, html, final = get(base, 18)
    if code != 200:
        #: The department page itself did not answer. Nothing was
        #: learned, so nothing is marked: the next run tries again.
        return [], False
    host = urlparse(final).netloc

    #: THREE HOPS, BECAUSE THAT IS WHERE LABS LIVE. A department page
    #: lists faculty; a faculty profile links to that person's group;
    #: the group has a members page. Stopping at hop one found a single
    #: lab under sixteen departments, because departments rarely link
    #: to groups directly.
    profiles = []
    for text, href in links(html, final):
        if re.search(r"(/people/|/faculty/|/profile|/directory/|/~)", href) \
                and not NOT_LAB.search(href):
            profiles.append(href)
    seen: set = set()
    for prof in profiles[:14]:
        c2, h2, f2 = get(prof, 12)
        if c2 != 200:
            continue
        for text, href in links(h2, f2):
            if LAB_LINK.search(text) or re.search(r"(lab|group)", href, re.I):
                if not NOT_LAB.search(href):
                    seen.add(href)
        time.sleep(0.25)

    out = []
    for text, href in links(html, final):
        if not (LAB_LINK.search(text) or LAB_URL.search(href)):
            continue
        if NOT_LAB.search(href) or href in seen:
            continue
        #: stay on the university; a lab on sites.google.com is common
        #: and allowed, anything else is someone else's site
        h = urlparse(href).netloc
        if not (h == host or h.endswith(".edu") or "sites.google" in h
                or "github.io" in h):
            continue
        seen.add(href)
        if len(seen) > 40:
            break

    #: KEEP EVERY CANDIDATE, not only the ones that parse. A lab page
    #: whose roster this crawler cannot read is still a lab page, and
    #: the address is the expensive part to find -- re-deriving it
    #: later means crawling three hops again. Rows carry a status so a
    #: later pass can pick up where this one stopped.
    #: A WALL-CLOCK BUDGET PER DEPARTMENT. Forty candidates at a
    #: fifteen-second read is ten minutes for one department, and the
    #: run yields in order, so the slowest one hides every result
    #: behind it. Whatever is left when the budget runs out stays a
    #: candidate for the next pass: the department is not marked done
    #: unless it finished.
    deadline = time.monotonic() + DEPT_BUDGET
    out_of_time = False
    for href in list(seen):
        if time.monotonic() > deadline:
            out_of_time = True
            break
        code, html, final = get(href, 15)
        if code != 200:
            out.append({"url": href,
                        "status": ("tls_chain_incomplete"
                                   if code == TLS_FAILED
                                   else f"http_{code}"),
                        "institution": institution_of(
                            href, row["institution"])[0],
                        "department_field": row["sector"],
                        "found_from": base})
            continue
        title = re.search(r"<title[^>]*>(.*?)</title>", html, re.S | re.I)
        target = final
        for text, link in links(html, final):
            if MEMBERS.search(text) and not NOT_LAB.search(link):
                target = link
                break
        r = roster_of(target)
        if r:
            inst, how = institution_of(r["url"], row["institution"])
            r.update({"status": "roster", "institution": inst,
                      "institution_from": how,
                      "reached_via_department": row["institution"],
                      "department_field": row["sector"], "found_from": base})
            out.append(r)
        else:
            inst, how = institution_of(final, row["institution"])
            out.append({
                "url": final,
                "institution_from": how,
                "reached_via_department": row["institution"],
                "members_page_tried": target if target != final else "",
                "title": " ".join(title.group(1).split())[:110]
                         if title else "",
                "status": "no_roster_parsed",
                "institution": inst,
                "department_field": row["sector"], "found_from": base})
        time.sleep(0.4)
    if out_of_time:
        print(f"  .. out of time at {base[:58]}; "
              f"{len(out)} kept, the rest stay candidates", flush=True)
    return out, not out_of_time


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=80)
    ap.add_argument("--workers", type=int, default=5)
    ap.add_argument("--fields", help="comma-separated field keys to crawl")
    ap.add_argument("--exclude", help="field keys to skip")
    ap.add_argument("--restart", action="store_true",
                    help="ignore the resume file and walk everything")
    a = ap.parse_args()

    resume = crawl_resume.Resume("discover", why=(
        "Department pages discover_research_labs.py has finished walking. "
        "A department that yields no candidate is still walked, so "
        "without this file it looks unvisited for ever. A department that "
        "ran out of time or would not answer is NOT recorded, so the "
        "next run tries it again."))
    if a.restart:
        resume.reset()
    else:
        #: Seeded once, from the only evidence runs before this file
        #: left behind: a row names the department page it came from.
        seeded = resume.seed(
            g["found_from"] for g in
            (json.loads(OUT.read_text()).get("groups", [])
             if OUT.exists() else [])
            if g.get("found_from", "").startswith("http"))
        if seeded:
            print(f"  resume file seeded with {seeded} departments "
                  f"a row can prove were walked")

    rows = [r for r in json.loads(URLS.read_text())["rows"]
            if r.get("status") == "ok" and (r.get("faculty_url") or r.get("url"))]
    #: spread across institutions and fields rather than taking the
    #: first N, which would be one field in alphabetical order
    if a.fields:
        want = {x.strip() for x in a.fields.split(",")}
        rows = [r for r in rows if r["sector"] in want]
    if a.exclude:
        skip = {x.strip() for x in a.exclude.split(",")}
        rows = [r for r in rows if r["sector"] not in skip]

    by: dict = {}
    for r in rows:
        by.setdefault((r["institution"], r["sector"]), r)
    before = len(by)
    by = {k: r for k, r in by.items()
          if (r.get("faculty_url") or r.get("url")) not in resume.done}
    if before != len(by):
        print(f"  skipping {before - len(by)} departments already walked")
    #: ROUND-ROBIN ACROSS FIELDS. Taking the first N of a dict gave 77
    #: computing groups, 8 aerospace and 4 materials, because the
    #: computing departments come first and there are more of them.
    #: The author asked for all of STEM, so each field contributes in
    #: turn until the limit is reached.
    pools: dict = {}
    for r in by.values():
        pools.setdefault(r["sector"], []).append(r)
    picks, order = [], [k for k in pools if pools[k]]
    while order and len(picks) < a.limit:
        for k in list(order):
            if not pools[k]:
                order.remove(k)
                continue
            picks.append(pools[k].pop(0))
            if len(picks) >= a.limit:
                break
    print(f"Looking for research groups under {len(picks)} departments")

    #: STORE IN BATCHES, MARK AFTER STORING. This used to hold every
    #: row in memory and write once at the end, so a run that died at
    #: the ninetieth minute lost all ninety. walk_site_parsers.py has
    #: stored as it goes since its first long run; this is the same
    #: discipline, through lab_store so the write holds the lock.
    #:
    #: The ORDER is the invariant: rows are merged first and the
    #: department is marked second. A resume file that ran ahead of the
    #: data would be worse than none, because the rows would be gone
    #: and nothing would ever look there again.
    BATCH = 20
    pending_rows: list = []
    pending_depts: list = []
    seen_urls: set = set()
    kept = rosters = walked = unfinished = 0

    def flush() -> None:
        nonlocal pending_rows, pending_depts
        if pending_rows:
            r = lab_store.merge(pending_rows, source="discover")
            print(f"   stored: +{r['added']} new, {r['improved']} improved, "
                  f"{r['rosters']} rosters of {r['total']} candidates",
                  flush=True)
        #: marked only now, and only the departments that finished
        resume.mark_many(pending_depts)
        pending_rows, pending_depts = [], []

    try:
        with ThreadPoolExecutor(max_workers=a.workers) as ex:
            for row, (got, finished) in zip(
                    picks, ex.map(from_department, picks)):
                walked += 1
                base = row.get("faculty_url") or row.get("url")
                if finished:
                    pending_depts.append(base)
                else:
                    unfinished += 1
                for g in got:
                    #: one page, one row -- several departments link to
                    #: the same group and the first pass listed it once
                    #: each
                    if g["url"] in seen_urls:
                        continue
                    seen_urls.add(g["url"])
                    pending_rows.append(g)
                    kept += 1
                    if g.get("status") == "roster":
                        rosters += 1
                        print(f"  {g['members']:>3} members  "
                              f"{g['composition'].get('share_chinese_markers', 0):>5}%  "
                              f"{g['institution'][:24]:26} "
                              f"{g.get('title','')[:40]}", flush=True)
                if len(pending_depts) >= BATCH:
                    flush()
                    print(f"  .. {walked}/{len(picks)} departments, "
                          f"{rosters} rosters", flush=True)
    except KeyboardInterrupt:
        print("\n  interrupted; storing what is in hand", flush=True)
    finally:
        flush()
        #: The prose and the examined count, written once, under the
        #: same lock as the rows.
        summary = lab_store.merge([], source="discover", meta={
            "why": ("Research groups found by crawling departments already "
                    "resolved. The COUNT EXAMINED is the number that "
                    "matters for the correction: a list assembled by "
                    "scanning needs Benjamini-Hochberg over the whole "
                    "set, not a p-value per group."),
            "note_on_candidates": (
                "Rows with status 'roster' carry counts. The rest are lab "
                "pages whose member list this crawler could not read, "
                "kept because the ADDRESS is the expensive part: finding "
                "it took three hops from a department page."),
        }, meta_max={"departments_examined": len(resume.done)})
        print(f"\n  {summary['total']} lab URLs kept, "
              f"{summary['rosters']} with a readable roster")
        print(f"  walked {walked} departments this run, "
              f"{unfinished} unfinished and left for the next")
        print(f"  {len(resume.done)} departments finished in all")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
