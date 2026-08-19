#!/usr/bin/env python3
"""
Append-only refresh for the ETD sources that are NOT in scrape_oai_etds.REPOS
and whose original bespoke scraper did not survive in scripts/archive/.

Covers four repositories:

  northwestern  Northwestern ARCH (Samvera/Hyrax + Blacklight `catalog.json`)
  uf            UF Digital Collections (api.patron.uflib.ufl.edu `exactsearch`)
  uva           UVA Libra ETD (sitemap + `api/works/{id}` JSON)
  pdx           PDXScholar (bepress OAI-PMH, selective `from=` harvest)

Every source writes into the university's existing raw CSV, preserving its
historical column order. Runs are:

  * append-only  — the CSV is opened in "a" mode and is never rewritten;
  * deduped      — a CheckpointDB (scripts/scrape_checkpoint.py) is seeded once
                   from the ids already in the CSV, so a re-run can only ever
                   add records that are genuinely new;
  * resumable    — the checkpoint is committed as rows are written, so an
                   interrupted run picks up where it stopped.

Usage:
    python scripts/refresh_frozen_etds.py --source pdx --from 2026-01-01
    python scripts/refresh_frozen_etds.py --source uf --years 2016-2026
    python scripts/refresh_frozen_etds.py --source northwestern
    python scripts/refresh_frozen_etds.py --source uva --delay 0.4
"""

import argparse
import csv
import json
import logging
import re
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from scrape_checkpoint import CheckpointDB  # noqa: E402

log = logging.getLogger(__name__)
csv.field_size_limit(10_000_000)

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
TIMEOUT = 45

NS = {
    "oai": "http://www.openarchives.org/OAI/2.0/",
    "dc": "http://purl.org/dc/elements/1.1/",
    "oai_dc": "http://www.openarchives.org/OAI/2.0/oai_dc/",
    "sm": "http://www.sitemaps.org/schemas/sitemap/0.9",
}

SOURCES = {
    "northwestern": {
        "csv": "data/western_us_dissertations/northwestern_etds.csv",
        "db": "data/western_us_dissertations/northwestern_refresh.db",
        "id_field": "id",
        "fields": ["id", "url", "title", "creator", "date", "degree_type",
                   "subject", "description", "keywords", "type"],
    },
    "uf": {
        "csv": "data/western_us_dissertations/uf_etds.csv",
        "db": "data/western_us_dissertations/uf_refresh.db",
        "id_field": "bib_id",
        "fields": ["bib_id", "url", "title", "creator", "date", "degree",
                   "degree_level", "department", "description"],
    },
    "uva": {
        "csv": "data/western_us_dissertations/uva_etds.csv",
        "db": "data/western_us_dissertations/uva_refresh.db",
        "id_field": "id",
        "fields": ["id", "url", "title", "author", "date", "degree",
                   "department", "keywords", "description", "doi"],
    },
    "pdx": {
        "csv": "data/or_wa_dissertations/pdxscholar_dissertations.csv",
        "db": "data/or_wa_dissertations/pdx_refresh.db",
        "id_field": "identifier",
        "fields": ["source", "identifier", "title", "creator", "contributor",
                   "date", "subject", "description", "type"],
    },
}


def fetch(url, retries=3, delay=1.0, accept=None):
    """GET a URL with retries. Returns bytes, or None if it never succeeded."""
    headers = {"User-Agent": UA}
    if accept:
        headers["Accept"] = accept
    for attempt in range(retries):
        try:
            with urlopen(Request(url, headers=headers), timeout=TIMEOUT) as resp:
                return resp.read()
        except (HTTPError, URLError, TimeoutError, OSError) as e:
            log.warning("  attempt %d failed (%s): %s", attempt + 1, url[:110], e)
            if attempt < retries - 1:
                time.sleep(delay * (attempt + 2))
    return None


def fetch_json(url, **kw):
    raw = fetch(url, **kw)
    if raw is None:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        log.warning("  bad JSON from %s: %s", url[:110], e)
        return None


def flat(value, sep="; "):
    """Flatten a list/scalar into a string."""
    if value is None:
        return ""
    if isinstance(value, list):
        return sep.join(str(v).strip() for v in value if v)
    return str(value).strip()


def seed_checkpoint(db, csv_path, id_field):
    """Seed the dedup DB from the ids already in the CSV (once)."""
    if db.get_state("seeded_from_csv"):
        return
    if not csv_path.exists():
        log.error("Expected existing CSV %s — refusing to create it here", csv_path)
        sys.exit(1)
    log.info("Seeding dedup checkpoint from %s ...", csv_path)
    batch = []
    with open(csv_path, encoding="utf-8", errors="replace") as f:
        for row in csv.DictReader(f):
            ident = (row.get(id_field) or "").strip()
            if ident:
                batch.append(ident)
            if len(batch) >= 5000:
                db.mark_done_batch(batch)
                batch = []
    if batch:
        db.mark_done_batch(batch)
    db.set_state("seeded_from_csv", "1")
    log.info("  seeded %d existing ids", db.count_done())


class Appender:
    """Append-only CSV writer with checkpoint-backed dedup."""

    def __init__(self, csv_path, fields, db, id_field):
        self.path = csv_path
        self.fields = fields
        self.db = db
        self.id_field = id_field
        self.written = 0
        self.skipped = 0
        with open(csv_path, encoding="utf-8", errors="replace") as f:
            header = next(csv.reader(f), None)
        if header != fields:
            log.error("Header mismatch for %s\n  on disk: %s\n  expected: %s",
                      csv_path, header, fields)
            sys.exit(1)
        self.fh = open(csv_path, "a", newline="", encoding="utf-8")
        self.writer = csv.DictWriter(self.fh, fieldnames=fields)

    def add(self, row):
        ident = (row.get(self.id_field) or "").strip()
        if not ident or self.db.is_done(ident):
            self.skipped += 1
            return False
        self.writer.writerow({k: row.get(k, "") for k in self.fields})
        self.fh.flush()
        self.db.mark_done(ident)
        self.written += 1
        return True

    def close(self):
        self.fh.close()


# ──────────────────────────────────────────────────────────────
# Northwestern — ARCH Blacklight catalog.json
# ──────────────────────────────────────────────────────────────
NU_BASE = "https://arch.library.northwestern.edu"
# Historical CSV holds both; resource_type -> the degree_type value already used.
NU_RESOURCE_TYPES = {"Dissertation": "phd", "Masters Thesis": "ms"}


def refresh_northwestern(app, args):
    for resource_type, degree_type in NU_RESOURCE_TYPES.items():
        page = 1
        total_pages = None
        while True:
            q = [("f[resource_type_sim][]", resource_type),
                 ("per_page", "100"), ("page", str(page)),
                 ("sort", "date_uploaded_dtsi desc")]
            data = fetch_json(f"{NU_BASE}/catalog.json?{urlencode(q)}", delay=args.delay)
            if data is None:
                log.error("  %s page %d failed — stopping this resource type",
                          resource_type, page)
                break
            resp = data.get("response", {})
            docs = resp.get("docs", [])
            pages = resp.get("pages", {})
            if total_pages is None:
                total_pages = pages.get("total_pages", 0)
                log.info("%s: %s records over %s pages",
                         resource_type, pages.get("total_count"), total_pages)
            for doc in docs:
                # date_created_tesim is the DEGREE date; date_uploaded_dtsi is
                # when ARCH ingested the item and routinely lags the degree by a
                # year (220 of the 400 most recent deposits were created in 2025
                # and deposited in 2026). Every other university in this corpus
                # is dated by degree/publication date and the site charts records
                # per graduation year, so the deposit date must not be used here.
                # Fall back to the deposit date only when no degree date exists.
                created = flat(doc.get("date_created_tesim"), sep=" ")
                if not re.search(r"\d{4}", created):
                    created = doc.get("date_uploaded_dtsi", "")
                app.add({
                    "id": doc.get("id", ""),
                    "url": f"{NU_BASE}/concern/generic_works/{doc.get('id','')}",
                    "title": flat(doc.get("title_tesim")),
                    "creator": flat(doc.get("creator_tesim")),
                    "date": created,
                    "degree_type": degree_type,
                    "subject": flat(doc.get("subject_tesim")),
                    "description": flat(doc.get("description_tesim"))[:500],
                    "keywords": flat(doc.get("keyword_tesim")),
                    "type": flat(doc.get("resource_type_tesim")),
                })
            log.info("  %s page %d/%s — new so far %d (dupes %d)",
                     resource_type, page, total_pages, app.written, app.skipped)
            if not pages.get("next_page"):
                break
            page = pages["next_page"]
            time.sleep(args.delay)


# ──────────────────────────────────────────────────────────────
# University of Florida — patron API `exactsearch`
# ──────────────────────────────────────────────────────────────
UF_API = "https://api.patron.uflib.ufl.edu/exactsearch"
UF_PAGE = 25  # server-fixed page size


def refresh_uf(app, args):
    start_year, end_year = args.years
    for year in range(start_year, end_year + 1):
        start = 0
        total = None
        while True:
            q = [("aggregationcodes", "ufetd"),
                 ("publication_date", str(year)), ("start", str(start))]
            data = fetch_json(f"{UF_API}?{urlencode(q)}", delay=args.delay)
            if data is None:
                log.error("  %d start=%d failed — skipping rest of year", year, start)
                break
            hits = data.get("hits", [])
            if total is None:
                total = data.get("hit_count", 0)
                log.info("%d: %d records advertised", year, total)
            if not hits:
                break
            for h in hits:
                bibid = h.get("bibid", "")
                vid = h.get("vid", "00001")
                # The `ufetd` aggregation also carries IR items that are not
                # degree ETDs — "Project in Lieu of Thesis", field reports,
                # student projects (bib_ids AA*/IR*). They have no
                # etd_degree_level and no discipline, and the historical
                # snapshot contains none of them (it is entirely UFE*). Skip
                # them so the population stays comparable across years.
                if not h.get("etd_degree_level"):
                    continue
                app.add({
                    "bib_id": bibid,
                    "url": f"https://ufdc.ufl.edu/{bibid}/{vid}",
                    "title": h.get("title", ""),
                    "creator": flat(h.get("creator")),
                    # conv_date is the normalised YYYY-MM-DD; the pipeline only
                    # needs the year out of this column.
                    "date": h.get("conv_date") or h.get("publication_date", ""),
                    # No per-degree string ("Ph.D."/"M.S.") is exposed by this
                    # API; degree_level ("Doctorate"/"Masters") drives
                    # infer_degree_type on its own.
                    "degree": "",
                    "degree_level": flat(h.get("etd_degree_level")),
                    # Historical rows store the raw Python list repr here and
                    # load_records() ast-parses it — keep that shape.
                    "department": str(h.get("etd_degree_discipline") or ""),
                    "description": flat(h.get("abstract") or h.get("general_note"))[:500],
                })
            log.info("  %d start=%d — new so far %d (dupes %d)",
                     year, start, app.written, app.skipped)
            start += UF_PAGE
            if start >= min(total, 10000):
                break
            time.sleep(args.delay)


# ──────────────────────────────────────────────────────────────
# UVA Libra ETD — sitemap + api/works/{id}
# ──────────────────────────────────────────────────────────────
UVA_BASE = "https://libraetd.lib.virginia.edu"


def refresh_uva(app, args):
    log.info("Fetching Libra ETD sitemap ...")
    raw = fetch(f"{UVA_BASE}/sitemap.xml", delay=args.delay)
    if raw is None:
        log.error("Cannot fetch sitemap — aborting")
        return
    text = raw.decode("utf-8", "replace")
    # NB: ids must allow hyphens. UVA introduced a second id format in late 2025
    # ("oid-d2fi1umu6jjc717r144g") alongside the original ("000000264"); a
    # [A-Za-z0-9]+ pattern silently skips every one of them, which is most of
    # the recent cohort.
    ids = re.findall(r"/public_view/([A-Za-z0-9-]+)</loc>", text)
    total_locs = text.count("<loc>")
    log.info("  %d items in sitemap (%d <loc> entries)", len(ids), total_locs)
    if len(ids) != total_locs:
        # Loud, not silent: a parse that drops entries looks exactly like a
        # complete run in the logs otherwise.
        log.error("  SITEMAP PARSE GAP: %d <loc> entries but only %d ids matched "
                  "— %d entries unparsed", total_locs, len(ids), total_locs - len(ids))

    todo = [i for i in ids if not app.db.is_done(i)]
    log.info("  %d not yet in the CSV", len(todo))
    if args.limit:
        todo = todo[:args.limit]

    for n, item_id in enumerate(todo, 1):
        d = fetch_json(f"{UVA_BASE}/api/works/{item_id}", delay=args.delay)
        time.sleep(args.delay)
        if d is None:
            continue
        author = d.get("author") or {}
        name = ", ".join(x for x in [(author.get("lastName") or "").strip(),
                                     (author.get("firstName") or "").strip()] if x)
        app.add({
            "id": item_id,
            "url": f"{UVA_BASE}/public_view/{item_id}",
            "title": d.get("title", ""),
            "author": name,
            "date": d.get("publishedAt", ""),
            "degree": d.get("degree", ""),
            "department": d.get("program") or author.get("department", ""),
            "keywords": flat(d.get("keywords")),
            "description": (d.get("abstract") or "")[:500],
            "doi": d.get("persistentLink", ""),
        })
        if n % 100 == 0:
            log.info("  %d/%d fetched — new %d (dupes %d)",
                     n, len(todo), app.written, app.skipped)


# ──────────────────────────────────────────────────────────────
# PDXScholar — bepress OAI-PMH selective harvest
# ──────────────────────────────────────────────────────────────
PDX_OAI = "https://pdxscholar.library.pdx.edu/do/oai/"
PDX_SET = "publication:open_access_etds"
PDX_SOURCE = "Portland State - Open Access ETDs"  # the value historical rows use


def refresh_pdx(app, args):
    url = (f"{PDX_OAI}?verb=ListRecords&metadataPrefix=oai_dc&set={PDX_SET}")
    if args.from_date:
        url += f"&from={args.from_date}"
    page = 0
    while url:
        page += 1
        raw = fetch(url, delay=args.delay)
        if raw is None:
            log.error("  page %d failed — stopping", page)
            break
        text = raw.decode("utf-8", "replace")
        if "noRecordsMatch" in text:
            log.info("  no records match")
            break
        try:
            root = ET.fromstring(text)
        except ET.ParseError as e:
            log.error("  XML parse error on page %d: %s", page, e)
            break

        for record in root.findall(".//oai:record", NS):
            header = record.find("oai:header", NS)
            if header is not None and header.get("status") == "deleted":
                continue
            meta = record.find("oai:metadata/oai_dc:dc", NS)
            if meta is None:
                continue
            ident_elem = header.find("oai:identifier", NS) if header is not None else None
            ident = ident_elem.text.strip() if ident_elem is not None and ident_elem.text else ""

            def one(tag):
                e = meta.find(f"dc:{tag}", NS)
                return e.text.strip() if e is not None and e.text else ""

            def many(tag):
                return "; ".join(e.text.strip() for e in meta.findall(f"dc:{tag}", NS) if e.text)

            app.add({
                "source": PDX_SOURCE,
                "identifier": ident,
                "title": one("title"),
                "creator": many("creator"),
                "contributor": many("contributor"),
                "date": one("date"),
                "subject": many("subject"),
                "description": one("description")[:500],
                "type": one("type"),
            })

        token_elem = root.find(".//oai:resumptionToken", NS)
        token = token_elem.text.strip() if token_elem is not None and token_elem.text else None
        log.info("  page %d — new so far %d (dupes %d)", page, app.written, app.skipped)
        url = f"{PDX_OAI}?verb=ListRecords&resumptionToken={token}" if token else None
        time.sleep(args.delay)


HANDLERS = {
    "northwestern": refresh_northwestern,
    "uf": refresh_uf,
    "uva": refresh_uva,
    "pdx": refresh_pdx,
}


def parse_years(text):
    m = re.fullmatch(r"(\d{4})-(\d{4})", text or "")
    if not m:
        raise argparse.ArgumentTypeError("expected YYYY-YYYY, e.g. 2016-2026")
    return int(m.group(1)), int(m.group(2))


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--source", required=True, choices=sorted(SOURCES))
    p.add_argument("--delay", type=float, default=1.0, help="Seconds between requests")
    p.add_argument("--from", dest="from_date", default=None,
                   help="OAI selective harvest cutoff YYYY-MM-DD (pdx only)")
    p.add_argument("--years", type=parse_years, default=(2016, 2026),
                   help="Year range to sweep (uf only, default 2016-2026)")
    p.add_argument("--limit", type=int, default=0, help="Max new items to fetch (uva)")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(message)s", datefmt="%H:%M:%S")

    cfg = SOURCES[args.source]
    csv_path = REPO_ROOT / cfg["csv"]
    db = CheckpointDB(REPO_ROOT / cfg["db"])
    seed_checkpoint(db, csv_path, cfg["id_field"])

    before = db.count_done()
    app = Appender(csv_path, cfg["fields"], db, cfg["id_field"])
    try:
        HANDLERS[args.source](app, args)
    finally:
        app.close()
        log.info("=" * 60)
        log.info("%s: appended %d new records (%d duplicates skipped) -> %s",
                 args.source, app.written, app.skipped, csv_path)
        log.info("known ids: %d -> %d", before, db.count_done())
        db.close()


if __name__ == "__main__":
    main()
