#!/usr/bin/env python3
"""The employment route that needs no visa, measured from the vendors' sitemaps.

WHAT AN EMPLOYER OF RECORD DOES

An American company that wants a particular foreign worker has, on this site's
other pages, three ways to get one: sponsor an H-1B, hire a graduate on OPT, or
wait on a green card. An employer of record is the fourth, and it is different
in kind. The worker never enters the United States. A company already
incorporated in the worker's country signs the employment contract, runs the
local payroll and carries the local liability; the American firm directs the
work and pays an invoice. No petition, no cap, no lottery, no consulate.

WHY THERE IS NO FEDERAL NUMBER FOR IT

Every figure elsewhere on this site exists because a form was filed. An LCA
exists because an employer promised a wage for work IN the United States. An
I-129 exists because someone asked to admit a person. A SEVIS record exists
because a school enrolled one. An employer-of-record hire generates none of
these, because nobody is admitted and no work happens here.

So this is not a dataset with a gap in it. It is a route that is unmeasured by
construction, and no amount of care with the federal files will ever count it.
That is the finding, and it bounds every other number on this site: the visa
routes are a floor on how many foreign workers American companies employ, never
a total.

WHAT THIS BUILDER MEASURES INSTEAD

The vendors publish sitemaps, and a sitemap is a list of claims its author
chose to make. Three things are counted from them, and each one is a URL a
reader can open:

  references   which vendors publish a page naming a competitor. The edge is
               read from the URL -- deel.com/deel-vs-competitors/rippling/ --
               and never from marketing prose, so no judgement of mine decides
               who references whom.
  h1b_pages    pages whose own address contains "h1b" or "h-1b". This is the
               industry making the substitution argument in its own words, and
               it does not need paraphrasing: one of them is called
               "do-h-1b-visas-even-matter-if-you-can-hire-employees-in-any-country".
  countries    distinct country pages under each vendor's own country-guide
               path. A measured count of pages they publish, not the number
               they advertise.

DECLARED, NOT GUESSED. A company becomes a node only if it is in COMPANIES
below. The slug "1095a-vs-1095b" is not a company and neither is
"employees-vs-contractors", and a parser that accepted any X-vs-Y would have
filled the graph with tax forms. Every comparison URL that does not resolve to
two declared companies is counted in `unmatched_comparisons` and the commonest
are printed, so the registry's coverage is visible instead of assumed.

A VENDOR WHOSE SITEMAP CANNOT BE READ IS RECORDED AS UNAVAILABLE, never as
zero. Two of the nine serve a sitemap index and one sits behind a bot wall; a
zero there would read as "publishes no comparisons", which is a different claim
from "we could not look".

Sources: each vendor's own robots.txt and sitemap.xml. robots.txt was read for
all nine hosts first; none disallows the sitemap or the paths counted here.
Only the URL LISTS are cached, never page bodies -- the addresses are the
evidence and the prose is not needed.

Usage:
    python3 scripts/build_eor_market.py
    python3 scripts/build_eor_market.py --fetch      # re-harvest the sitemaps
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from atomic_write import write_json

ROOT = Path(__file__).resolve().parents[1]
URLS = ROOT / "data" / "eor" / "urls"
OUT = ROOT / "site" / "data" / "eor_market.json"

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120 Safari/537.36")

#: The vendors harvested, with the path their own country guides sit under.
#: `country_path` has one capture group: the country slug. It is declared per
#: vendor because each one chose a different shape, and the pattern is written
#: into the output so a reader can check the count against the sitemap.
SEED: tuple[dict, ...] = (
    {"key": "deel", "name": "Deel", "host": "www.deel.com",
     "country_path": r"^/hiring/employees/([a-z-]+)/?$"},
    {"key": "rippling", "name": "Rippling", "host": "www.rippling.com",
     "country_path": r"^/country-hiring/([a-z-]+)/?$"},
    {"key": "remote", "name": "Remote", "host": "remote.com",
     "country_path": r"^/country-explorer/([a-z-]+)(?:/employer-of-record)?/?$"},
    {"key": "oyster", "name": "Oyster", "host": "www.oysterhr.com",
     "country_path": r"^/hire-employees/([a-z-]+)/?$"},
    {"key": "pebl", "name": "Pebl (formerly Velocity Global)",
     "host": "www.velocityglobal.com",
     "country_path": r"^/countries/([a-z-]+)/?$"},
    {"key": "gp", "name": "G-P (Globalization Partners)", "host": "www.g-p.com",
     "country_path": r"^/globalpedia/([a-z-]+)/?$"},
    {"key": "papaya", "name": "Papaya Global", "host": "www.papayaglobal.com",
     "country_path": r"^/countrypedia/country/([a-z-]+)/?$"},
    {"key": "multiplier", "name": "Multiplier", "host": "www.multiplier.com",
     "country_path": r"^/(?:employer-of-record|global-payroll)/([a-z-]+)/?$"},
    {"key": "safeguard", "name": "Safeguard Global",
     "host": "www.safeguardglobal.com",
     "country_path": r"^/country/([a-z-]+)/[a-z-]+/?$"},
)

#: alias in a URL slug -> (canonical name, what kind of company it is).
#:
#: `eor` sells employment in countries where the client has no entity: the
#: route this page is about. `us_payroll` sells US payroll, benefits or PEO
#: service, which is a domestic product and is here only because the EOR
#: vendors compare themselves to it. `other_software` is everything else a
#: vendor's own comparison pages reach for -- identity, spend, ERP -- and it is
#: kept because leaving it out would overstate how tight the EOR cluster is.
COMPANIES: dict[str, tuple[str, str]] = {
    "deel": ("Deel", "eor"),
    "rippling": ("Rippling", "eor"),
    "remote": ("Remote", "eor"),
    "oyster": ("Oyster", "eor"), "oysterhr": ("Oyster", "eor"),
    "pebl": ("Pebl (formerly Velocity Global)", "eor"),
    "velocity-global": ("Pebl (formerly Velocity Global)", "eor"),
    "g-p": ("G-P (Globalization Partners)", "eor"),
    "gp": ("G-P (Globalization Partners)", "eor"),
    "globalization-partners": ("G-P (Globalization Partners)", "eor"),
    "papaya": ("Papaya Global", "eor"),
    "papaya-global": ("Papaya Global", "eor"),
    "multiplier": ("Multiplier", "eor"),
    "safeguard-global": ("Safeguard Global", "eor"),
    "remofirst": ("RemoFirst", "eor"),
    "skuad": ("Skuad", "eor"),
    "ontop": ("Ontop", "eor"),
    "velocity": ("Pebl (formerly Velocity Global)", "eor"),
    "globalpeo": ("Globalization Partners", "eor"),
    "atlas": ("Atlas", "eor"),
    "borderless": ("Borderless AI", "eor"),
    "playroll": ("Playroll", "eor"),
    "adp": ("ADP", "us_payroll"),
    "gusto": ("Gusto", "us_payroll"),
    "trinet": ("TriNet", "us_payroll"),
    "justworks": ("Justworks", "us_payroll"),
    "paychex": ("Paychex", "us_payroll"),
    "paycom": ("Paycom", "us_payroll"),
    "paylocity": ("Paylocity", "us_payroll"),
    "dayforce": ("Dayforce", "us_payroll"),
    "ceridian": ("Dayforce", "us_payroll"),
    "bamboohr": ("BambooHR", "us_payroll"),
    "quickbooks": ("QuickBooks", "us_payroll"),
    "workday": ("Workday", "other_software"),
    "sap": ("SAP", "other_software"),
    "okta": ("Okta", "other_software"),
    "auth0": ("Auth0", "other_software"),
    "brex": ("Brex", "other_software"),
    "expensify": ("Expensify", "other_software"),
    "1password": ("1Password", "other_software"),
    "netsuite": ("NetSuite", "other_software"),
    "cloudpay": ("CloudPay", "eor"),
    "paycor": ("Paycor", "us_payroll"),
    "sap-success-factors": ("SAP SuccessFactors", "other_software"),
    "successfactors": ("SAP SuccessFactors", "other_software"),
    "globalization": ("G-P (Globalization Partners)", "eor"),
    "horizons": ("Horizons", "eor"),
    "omnipresent": ("Omnipresent", "eor"),
    "velocityglobal": ("Pebl (formerly Velocity Global)", "eor"),
}

#: The language prefixes to drop. Every vendor publishes the same comparison in
#: a dozen locales, and counting them all would multiply one published claim
#: into twelve.
LOCALE = re.compile(
    r"^/(?:[a-z]{2})(?:-[a-z]{2})?/(?=.)", re.I)
LOCALE_CODES = {
    "es", "fr", "pt", "de", "ja", "nl", "ko", "it", "zh", "sv", "da", "pl",
    "id", "th", "vi", "tr", "ru", "ar", "he", "hi", "ms", "fi", "nb", "cs",
    "el", "uk", "ro", "bg", "hu", "sk", "sl", "hr", "lt", "lv", "et", "en",
}

COMPARISON = re.compile(
    r"(?:^|/)(?:compare|.*-vs-competitors)/([a-z0-9-]+)/?$"
    r"|(?:^|/)([a-z0-9-]+)-(?:vs|versus)-([a-z0-9-]+)/?$"
    r"|(?:^|/)([a-z0-9-]+)-alternatives?/?$")
H1B = re.compile(r"h-?1-?b", re.I)


def canonical_path(url: str) -> str:
    """The path with any locale prefix removed, so one claim counts once."""
    path = re.sub(r"https?://[^/]+", "", url)
    m = LOCALE.match(path)
    if m:
        head = path[1:m.end() - 1].split("-")[0].lower()
        if head in LOCALE_CODES:
            return path[m.end() - 1:]
    return path


def fetch_sitemap(host: str, dest: Path) -> str:
    """Harvest one vendor's sitemap, following a sitemap index one level.

    Returns "" on success or a short reason on failure. The reason is kept and
    published: a vendor behind a bot wall must not come out of this looking
    like a vendor with nothing to say.
    """
    def get(url: str) -> str:
        try:
            return subprocess.run(["curl", "-sL", "-m", "60", "-A", UA, url],
                                  capture_output=True, text=True,
                                  check=True).stdout
        except subprocess.CalledProcessError as exc:
            return f"__ERR__{exc.returncode}"

    body = get(f"https://{host}/sitemap.xml")
    if body.startswith("__ERR__") or len(body) < 200:
        return f"sitemap unreadable ({len(body)} bytes)"
    locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", body)
    if "<sitemapindex" in body:
        collected: list[str] = []
        for child in locs[:40]:
            sub = get(child)
            if not sub.startswith("__ERR__"):
                collected += re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", sub)
        locs = collected
    if not locs:
        return "sitemap contained no URLs"
    dest.write_text("\n".join(sorted(set(locs))) + "\n", encoding="utf-8")
    return ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch", action="store_true",
                    help="re-harvest every vendor sitemap")
    args = ap.parse_args()
    URLS.mkdir(parents=True, exist_ok=True)

    providers, edges = [], []
    unmatched: Counter = Counter()
    h1b_pages: list[dict] = []

    for spec in SEED:
        dest = URLS / f"{spec['key']}.txt"
        problem = ""
        if args.fetch or not dest.exists():
            problem = fetch_sitemap(spec["host"], dest)
        if problem and not dest.exists():
            providers.append({**spec, "available": False, "reason": problem,
                              "urls": 0, "countries": 0, "references": 0,
                              "h1b_pages": 0})
            print(f"  {spec['name']:<34} UNAVAILABLE: {problem}")
            continue

        urls = [u for u in dest.read_text().splitlines() if u.strip()]
        # Keep the ENGLISH original where one exists. Deel publishes
        # "todo-sobre-la-visa-h-1b" alongside "h-1b-visa-explained": stripping
        # the /es/ prefix leaves two different paths, so the same claim counted
        # twice and inflated the H-1B page count. A path reachable only under a
        # locale prefix is a translation with no English original, and it is
        # counted separately rather than silently with the rest.
        paths: dict[str, str] = {}
        english: set[str] = set()
        for u in urls:
            path = canonical_path(u)
            was_localised = path != re.sub(r"https?://[^/]+", "", u)
            if not was_localised:
                english.add(path)
            if path not in paths or not was_localised:
                paths[path] = u
        country_re = re.compile(spec["country_path"])
        countries = {m.group(1) for p in paths if (m := country_re.match(p))}

        mine = {alias for alias, (name, _) in COMPANIES.items()
                if name == COMPANIES.get(spec["key"], ("", ""))[0]}
        mine.add(spec["key"])

        refs, seen_edges = [], set()
        for path, url in sorted(paths.items()):
            m = COMPARISON.search(path.rstrip("/"))
            if not m:
                continue
            tokens = [t for t in m.groups() if t]
            hits = {COMPANIES[t][0] for t in tokens if t in COMPANIES}
            self_name = COMPANIES.get(spec["key"], (spec["name"], ""))[0]
            others = sorted(hits - {self_name})
            if not others:
                unmatched[" vs ".join(tokens)] += 1
                continue
            for other in others:
                if other in seen_edges:
                    continue
                seen_edges.add(other)
                refs.append(other)
                edges.append({"from": self_name, "to": other, "url": url})

        pages = sorted(url for path, url in paths.items()
                       if H1B.search(path) and path in english)
        translated = sum(1 for path in paths
                         if H1B.search(path) and path not in english)
        for url in pages:
            h1b_pages.append({"provider": spec["name"], "url": url,
                              "slug": canonical_path(url).rstrip("/").split("/")[-1]})

        providers.append({
            "key": spec["key"], "name": spec["name"], "host": spec["host"],
            "available": True, "reason": "",
            "urls": len(urls), "unique_paths": len(paths),
            "country_path": spec["country_path"],
            "countries": len(countries),
            "references": len(refs), "references_to": sorted(refs),
            "h1b_pages": len(pages),
            "h1b_pages_translated_only": translated,
        })
        print(f"  {spec['name']:<34} {len(urls):>6} urls  "
              f"{len(countries):>3} countries  {len(refs):>2} refs  "
              f"{len(pages):>3} H-1B pages")

    inbound: Counter = Counter(e["to"] for e in edges)
    outbound: Counter = Counter(e["from"] for e in edges)
    named = sorted(set(inbound) | set(outbound))
    kinds = {name: kind for alias, (name, kind) in COMPANIES.items()
             for _ in (0,)}
    network = [{"company": n,
                "kind": kinds.get(n, "unknown"),
                "references_made": outbound.get(n, 0),
                "referenced_by": inbound.get(n, 0),
                "in_seed": any(p["name"] == n for p in providers)}
               for n in named]
    network.sort(key=lambda r: (-r["referenced_by"], -r["references_made"], r["company"]))

    live = [p for p in providers if p["available"]]
    out = {
        "generated": date.today().isoformat(),
        "method": {
            "what": "Reference edges, country pages and H-1B pages counted from "
                    "each vendor's own sitemap.xml.",
            "edge_rule": "An edge exists when a vendor publishes a URL whose own "
                         "path names another declared company.",
            "locales_collapsed": True,
            "companies_declared": len(set(v[0] for v in COMPANIES.values())),
            "no_federal_count": "An employer-of-record hire produces no LCA, no "
                                "I-129 and no SEVIS record, because nobody is "
                                "admitted to the United States.",
        },
        "totals": {
            "providers_sought": len(SEED),
            "providers_read": len(live),
            "providers_unavailable": len(SEED) - len(live),
            "urls_read": sum(p["urls"] for p in live),
            "companies_in_network": len(network),
            "eor_companies_in_network": sum(1 for r in network if r["kind"] == "eor"),
            "reference_edges": len(edges),
            "h1b_pages": len(h1b_pages),
            "providers_with_h1b_pages": sum(1 for p in live if p["h1b_pages"]),
            "countries_max": max((p["countries"] for p in live), default=0),
            "h1b_pages_translated_only": sum(p.get("h1b_pages_translated_only", 0)
                                             for p in live),
            "unmatched_comparisons": sum(unmatched.values()),
        },
        "providers": providers,
        "network": network,
        "edges": sorted(edges, key=lambda e: (e["from"], e["to"])),
        "h1b_pages": h1b_pages,
        "unmatched_comparisons": [{"slug": k, "count": v}
                                  for k, v in unmatched.most_common(40)],
    }
    write_json(OUT, out, indent=2)
    t = out["totals"]
    print(f"Wrote {OUT.relative_to(ROOT)}")
    print(f"  {t['providers_read']}/{t['providers_sought']} vendors read, "
          f"{t['urls_read']:,} URLs")
    print(f"  {t['companies_in_network']} companies in the reference network "
          f"({t['eor_companies_in_network']} of them employer-of-record), "
          f"{t['reference_edges']} edges")
    print(f"  {t['h1b_pages']} pages whose address names the H-1B, across "
          f"{t['providers_with_h1b_pages']} vendors")
    print(f"  {t['unmatched_comparisons']} comparison URLs matched no declared "
          f"company; commonest:")
    for row in out["unmatched_comparisons"][:10]:
        print(f"      {row['count']:>3}  {row['slug']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
