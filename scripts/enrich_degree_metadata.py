#!/usr/bin/env python3
"""Fetch degree name/level for non-bepress repos that oai_dc drops.

`scripts/enrich_etdms_degrees.py` handles bepress repos via the `oai_etdms`
metadata format. Non-bepress repositories expose the same information under
different metadata formats (or, for Figshare, only through the REST API):

    uiuc      IDEALS `native` prefix   -> thesis.degree.name / .level
    uhouston  DSpace `dim` prefix      -> thesis.degree.name
    uoregon   DSpace `dim` prefix      -> thesis.degree.name / .level
    msu       `mods` prefix            -> mods:note type="thesis"
    unt       `untl` prefix            -> untl:degree qualifier="name"/"level"
    cmu       Figshare REST API        -> custom_fields "Degree Type"
    gmu       TIND `marcxml` prefix    -> MARC 502 (degree) + 380 (resource type)

Writes mapping files to data/degree_enrichment/{repo_key}.json of the form
{identifier: {"level": "Dissertation"|"Thesis"|"", "name": "..."}} — the same
shape `enrich_etdms_degrees.py` writes, so
`generate_name_lists.infer_degree_type` can consult both directories.

Harvests are checkpointed to data/degree_enrichment/{repo_key}_checkpoint.json
and resume automatically.

Usage:
    python scripts/enrich_degree_metadata.py --repo uiuc
    python scripts/enrich_degree_metadata.py --list
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import logging
import re
import sys
import time
import urllib.parse
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "degree_enrichment"

# Reuse the harvester's user agents and its 403 fallback, so there is one
# behaviour: repositories disagree in both directions — IDEALS 403s the project
# token, several DSpace sites 403 browser strings.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from scrape_oai_etds import BROWSER_UA, PROJECT_UA  # noqa: E402

REQUEST_TIMEOUT = 90

log = logging.getLogger("enrich_degree")

# ──────────────────────────────────────────────────────────────
# Repository configurations
# ──────────────────────────────────────────────────────────────
REPOS = {
    "uiuc": {
        "source": "oai",
        "oai_base": "https://www.ideals.illinois.edu/oai-pmh",
        "metadata_prefix": "native",
        "sets": ["com_2142_5130"],
        "parser": "ideals_native",
    },
    "uhouston": {
        "source": "oai",
        "oai_base": "https://uh-ir.tdl.org/server/oai/request",
        "metadata_prefix": "dim",
        "sets": ["com_10657_1"],
        "parser": "dspace_dim",
    },
    "uoregon": {
        "source": "oai",
        "oai_base": "https://scholarsbank.uoregon.edu/server/oai/request",
        "metadata_prefix": "dim",
        "sets": ["com_1794_7556"],
        "parser": "dspace_dim",
    },
    "msu": {
        "source": "oai",
        "oai_base": "https://d.lib.msu.edu/oai",
        "metadata_prefix": "mods",
        "sets": ["etd"],
        "parser": "mods_note",
    },
    "unt": {
        "source": "oai",
        "oai_base": "https://digital.library.unt.edu/oai/",
        "metadata_prefix": "untl",
        "sets": ["collection:UNTETD"],
        "parser": "untl",
    },
    "gmu": {
        "source": "oai",
        "oai_base": "https://digitalcollections.gmu.edu/oai2d",
        "metadata_prefix": "marcxml",
        "sets": ["gmu_lib:ir_collections"],
        "parser": "marc502",
        # TIND record ids bear no relation to the MARS identifiers already in
        # the harvested CSV, but the MARS handle survives in MARC 024/035 and
        # reconstructs the harvest key.
        "identifier_re": r"(1920/\d+)",
        "identifier_template": "oai:MARS:{}",
    },
    "cmu": {
        "source": "figshare",
        "csv": "data/western_us_dissertations/cmu_etds.csv",
        "api_base": "https://api.figshare.com/v2/articles",
        # Only thesis records carry a Degree Type custom field.
        "type_filter": "thesis",
    },
}


# ──────────────────────────────────────────────────────────────
# Degree name -> level normalisation
# ──────────────────────────────────────────────────────────────
_DOCTORAL_RE = re.compile(
    r"doctor|doctoral|dissertation"
    r"|\bph\.?\s?d\b|\bed\.?\s?d\b|\bd\.?\s?ed\b|\bd\.?\s?n\.?\s?p\b"
    r"|\bd\.?\s?m\.?\s?a\b|\bdma\b|\bsc\.?\s?d\b|\bd\.?\s?sc\b"
    r"|\bpsy\.?\s?d\b|\bdr\.?\s?p\.?\s?h\b|\bd\.?\s?p\.?\s?h\b"
    r"|\bs\.?\s?j\.?\s?d\b|\bj\.?\s?s\.?\s?d\b|\bd\.?\s?b\.?\s?a\b"
    r"|\bd\.?\s?eng\b|\bd\.?\s?p\.?\s?t\b|\bau\.?\s?d\b|\bd\.?\s?v\.?\s?m\b",
    re.IGNORECASE,
)
_MASTERS_RE = re.compile(
    r"master"
    r"|\bm\.?\s?s\b|\bm\.?\s?a\b|\bm\.?\s?f\.?\s?a\b|\bm\.?\s?eng\b"
    r"|\bm\.?\s?b\.?\s?a\b|\bm\.?\s?ed\b|\bm\.?\s?mus\b|\bm\.?\s?p\.?\s?h\b"
    r"|\bm\.?\s?p\.?\s?a\b|\bm\.?\s?arch\b|\bm\.?\s?l\.?\s?a\b"
    r"|\bm\.?\s?acc\b|\bm\.?\s?sw\b|\bm\.?\s?c\.?\s?p\b|\bll\.?\s?m\b"
    r"|\bm\.?\s?s\.?\s?e\b|\bm\.?\s?u\.?\s?p\b|\bm\.?\s?t\b|\bm\.?\s?sc\b"
    r"|\bm\.?\s?u\.?\s?r\.?\s?p\b",
    re.IGNORECASE,
)
_BACHELORS_RE = re.compile(r"bachelor|\bb\.?\s?s\b|\bb\.?\s?a\b|\bb\.?\s?f\.?\s?a\b", re.IGNORECASE)


def degree_level(name: str, raw_level: str = "") -> str:
    """Normalise a degree name/level pair to "Dissertation", "Thesis" or "".

    The output uses the ETDMS vocabulary so the mapping is interchangeable
    with the one written by enrich_etdms_degrees.py.
    """
    text = (name or "").strip()
    lvl = (raw_level or "").strip().lower()
    if text:
        if _DOCTORAL_RE.search(text):
            return "Dissertation"
        if _MASTERS_RE.search(text):
            return "Thesis"
        if _BACHELORS_RE.search(text):
            return "Bachelor"
    if lvl:
        if "dissertation" in lvl or "doctor" in lvl:
            return "Dissertation"
        if "master" in lvl or lvl == "thesis":
            return "Thesis"
        if "bachelor" in lvl:
            return "Bachelor"
    return ""


# ──────────────────────────────────────────────────────────────
# OAI-PMH page parsers — each returns {identifier: {level, name}}
# ──────────────────────────────────────────────────────────────
_RECORD_RE = re.compile(r"<record\b[^>]*>(.*?)</record>", re.DOTALL)
_HEADER_ID_RE = re.compile(r"<header[^>]*>.*?<identifier>([^<]+)</identifier>", re.DOTALL)
_RT_RE = re.compile(r"<resumptionToken[^>]*>([^<]*)</resumptionToken>")

# DSpace `dim`: <dim:field mdschema="thesis" element="degree" qualifier="name">...
_DIM_RE = re.compile(
    r'<dim:field[^>]*mdschema="thesis"[^>]*element="degree"[^>]*qualifier="(name|level)"[^>]*>([^<]*)<'
)
# IDEALS `native`: <field schema="thesis" element="degree" qualifier="name">...
_NATIVE_RE = re.compile(
    r'<field schema="thesis" element="degree" qualifier="(name|level)">([^<]*)<'
)
# MODS: <mods:note type="thesis">Thesis (Ph. D.)--Michigan State University. ...
_MODS_NOTE_RE = re.compile(r'<mods:note type="thesis">([^<]*)<')
_MODS_PAREN_RE = re.compile(r"\(([^)]{1,40})\)")
# UNT: <untl:degree qualifier="name">Doctor of Philosophy</untl:degree>
_UNTL_RE = re.compile(r'<untl:degree qualifier="(name|level)">([^<]*)<')
# TIND MARCXML: MARC 502 carries the degree, MARC 380 the resource type
_MARC_502_RE = re.compile(r'<marc:datafield tag="502".*?</marc:datafield>', re.DOTALL)
_MARC_380_RE = re.compile(r'<marc:datafield tag="380".*?</marc:datafield>', re.DOTALL)
_MARC_SUB_RE = re.compile(r'<marc:subfield code="([a-z])">([^<]*)<')


def _extract(rec_body: str, parser: str) -> tuple[str, str]:
    """Return (raw_degree_name, raw_degree_level) for one record body."""
    if parser == "dspace_dim":
        found = dict((q, v.strip()) for q, v in _DIM_RE.findall(rec_body))
        return found.get("name", ""), found.get("level", "")
    if parser == "ideals_native":
        found = dict((q, v.strip()) for q, v in _NATIVE_RE.findall(rec_body))
        return found.get("name", ""), found.get("level", "")
    if parser == "untl":
        found = dict((q, v.strip()) for q, v in _UNTL_RE.findall(rec_body))
        return found.get("name", ""), found.get("level", "")
    if parser == "marc502":
        note = _MARC_502_RE.search(rec_body)
        if not note:
            # No dissertation note — not an ETD. MARC 380 alone is unreliable
            # here (presentations are filed as "Thesis"), so claim nothing.
            return "", ""
        subs = dict(_MARC_SUB_RE.findall(note.group(0)))
        # $a is the free-text thesis note, $b the degree level
        name = " ".join(x for x in (subs.get("a", ""), subs.get("b", "")) if x).strip()
        rtype = _MARC_380_RE.search(rec_body)
        raw_level = ""
        if rtype:
            raw_level = dict(_MARC_SUB_RE.findall(rtype.group(0))).get("a", "")
        return name, raw_level
    if parser == "mods_note":
        note = _MODS_NOTE_RE.search(rec_body)
        if not note:
            return "", ""
        text = note.group(1)
        paren = _MODS_PAREN_RE.search(text)
        # "Thesis (Ph. D.)--Michigan State University. Chemistry, 2019"
        return (paren.group(1).strip() if paren else ""), text.split("(")[0].strip()
    raise ValueError(f"unknown parser {parser}")


def parse_page(raw: bytes, cfg: dict) -> tuple[dict[str, dict], str]:
    """Return (mapping_for_page, next_resumption_token).

    `identifier_re` / `identifier_template` let a repo whose OAI identifiers do
    not match the harvested CSV rebuild the harvest key from the record body.
    """
    parser = cfg["parser"]
    ident_re = re.compile(cfg["identifier_re"]) if cfg.get("identifier_re") else None
    text = raw.decode("utf-8", errors="replace")
    mapping: dict[str, dict] = {}
    for rec_body in _RECORD_RE.findall(text):
        if ident_re:
            id_match = ident_re.search(rec_body)
            ident = cfg["identifier_template"].format(id_match.group(1)) if id_match else ""
        else:
            id_match = _HEADER_ID_RE.search(rec_body)
            ident = id_match.group(1).strip() if id_match else ""
        if not ident:
            continue
        name, raw_level = _extract(rec_body, parser)
        if not name and not raw_level:
            continue
        level = degree_level(name, raw_level)
        if name or level:
            mapping[ident] = {"level": level, "name": name}
    rt_match = _RT_RE.search(text)
    token = (rt_match.group(1) or "").strip() if rt_match else ""
    return mapping, token


# ──────────────────────────────────────────────────────────────
# Fetch helpers
# ──────────────────────────────────────────────────────────────
def _fetch(url: str, user_agent: str, accept: str | None = None) -> bytes:
    headers = {"User-Agent": user_agent}
    if accept:
        headers["Accept"] = accept
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
        return resp.read()


def _fetch_retry(url: str, accept: str | None = None, tries: int = 4) -> bytes | None:
    """Fetch with retries, mirroring scrape_oai_etds.fetch_oai_page.

    The project token is tried first; a 403 is retried once with a browser
    string, since neither string works everywhere.
    """
    user_agent = PROJECT_UA
    for attempt in range(tries):
        try:
            return _fetch(url, user_agent, accept)
        except urllib.error.HTTPError as e:
            if e.code == 403 and user_agent is PROJECT_UA:
                log.info("  403 with project user agent, retrying as a browser")
                user_agent = BROWSER_UA
                continue
            wait = 5 * (attempt + 1)
            log.warning("  fetch failed (%s), retry in %ds: %s", attempt + 1, wait, e)
            time.sleep(wait)
        except Exception as e:
            wait = 5 * (attempt + 1)
            log.warning("  fetch failed (%s), retry in %ds: %s", attempt + 1, wait, e)
            time.sleep(wait)
    return None


# ──────────────────────────────────────────────────────────────
# Checkpointing
# ──────────────────────────────────────────────────────────────
def _paths(key: str) -> tuple[Path, Path]:
    return OUT_DIR / f"{key}.json", OUT_DIR / f"{key}_checkpoint.json"


def _load_state(key: str) -> tuple[dict, dict]:
    out, ckpt = _paths(key)
    mapping = {}
    state = {}
    if out.exists():
        try:
            mapping = json.loads(out.read_text())
        except Exception:
            mapping = {}
    if ckpt.exists():
        try:
            state = json.loads(ckpt.read_text())
        except Exception:
            state = {}
    return mapping, state


def _save_state(key: str, mapping: dict, state: dict) -> None:
    out, ckpt = _paths(key)
    out.write_text(json.dumps(mapping, indent=2, sort_keys=True))
    ckpt.write_text(json.dumps(state, indent=2))


# ──────────────────────────────────────────────────────────────
# Harvesters
# ──────────────────────────────────────────────────────────────
def harvest_oai(key: str, cfg: dict, delay: float) -> dict[str, dict]:
    mapping, state = _load_state(key)
    if state.get("done"):
        log.info("%s already complete (%d records)", key, len(mapping))
        return mapping

    sets = cfg.get("sets") or [None]
    start_set = state.get("set_index", 0)
    token = state.get("token") or ""
    page = state.get("page", 0)

    for set_index in range(start_set, len(sets)):
        oai_set = sets[set_index]
        log.info("  set=%s (resuming at page %d)", oai_set or "(all)", page)
        while True:
            page += 1
            if token:
                url = f"{cfg['oai_base']}?verb=ListRecords&resumptionToken={urllib.parse.quote(token)}"
            else:
                params = f"verb=ListRecords&metadataPrefix={cfg['metadata_prefix']}"
                if oai_set:
                    params += f"&set={urllib.parse.quote(oai_set)}"
                url = f"{cfg['oai_base']}?{params}"
            raw = _fetch_retry(url)
            if raw is None:
                log.error("  giving up on page %d — checkpoint saved, rerun to resume", page)
                _save_state(key, mapping, {"set_index": set_index, "token": token, "page": page - 1})
                return mapping
            page_map, token = parse_page(raw, cfg)
            mapping.update(page_map)
            log.info("    page %d: +%d (total %d)", page, len(page_map), len(mapping))
            _save_state(key, mapping, {"set_index": set_index, "token": token, "page": page})
            if not token:
                break
            time.sleep(delay)
        token = ""
        page = 0

    _save_state(key, mapping, {"done": True})
    return mapping


def harvest_figshare(key: str, cfg: dict, delay: float) -> dict[str, dict]:
    """Figshare exposes degree only via the article detail endpoint.

    The OAI feed (oai_dc, qdc, uketd_dc, cerif) carries no degree field, so
    each thesis article has to be fetched individually. The checkpoint records
    every id already looked at — including the ones with no degree field — so a
    resumed run never re-fetches an article.
    """
    mapping, state = _load_state(key)
    csv_path = ROOT / cfg["csv"]
    type_filter = cfg.get("type_filter")

    ids: list[str] = []
    with open(csv_path, encoding="utf-8", errors="replace") as f:
        for row in csv.DictReader(f):
            if type_filter and type_filter not in (row.get("type", "") or "").lower():
                continue
            ident = row.get("identifier", "")
            m = re.search(r"article/(\d+)", ident)
            if m:
                ids.append(ident)
    checked = set(state.get("checked") or []) | set(mapping)
    log.info("  %d %s records in CSV, %d already checked", len(ids), type_filter or "", len(checked))

    todo = [i for i in ids if i not in checked]
    consecutive_failures = 0
    for n, ident in enumerate(todo, 1):
        article_id = re.search(r"article/(\d+)", ident).group(1)
        raw = _fetch_retry(f"{cfg['api_base']}/{article_id}", accept="application/json")
        if raw is None:
            # Figshare rate-limits with a transient 403. Leave the id unchecked so
            # a rerun picks it up, back off, and carry on with the next article.
            consecutive_failures += 1
            log.warning("  skipping %s after repeated failures (%d in a row)", ident, consecutive_failures)
            if consecutive_failures >= 20:
                log.error("  20 consecutive failures — stopping, rerun to resume")
                break
            time.sleep(30)
            continue
        consecutive_failures = 0
        try:
            data = json.loads(raw.decode("utf-8", errors="replace"))
        except Exception as e:
            log.warning("  bad JSON for %s: %s", ident, e)
            data = {}
        name = ""
        for field in data.get("custom_fields") or []:
            if field.get("name") == "Degree Type":
                value = field.get("value")
                if isinstance(value, list):
                    value = value[0] if value else ""
                name = (value or "").strip()
                break
        checked.add(ident)
        if name:
            mapping[ident] = {"level": degree_level(name), "name": name}
        if n % 50 == 0:
            _save_state(key, mapping, {"checked": sorted(checked)})
            log.info("    %d/%d fetched (%d with degree)", n, len(todo), len(mapping))
        time.sleep(delay)

    _save_state(key, mapping, {"checked": sorted(checked), "done": len(checked) >= len(ids)})
    return mapping


# ──────────────────────────────────────────────────────────────
def summarise(key: str, mapping: dict) -> None:
    levels = collections.Counter(v.get("level") or "(none)" for v in mapping.values())
    log.info("%s: %d records — %s", key, len(mapping), dict(levels))
    unmatched = collections.Counter(
        v.get("name", "") for v in mapping.values() if not v.get("level")
    )
    if unmatched:
        log.info("  unmatched degree names: %s", unmatched.most_common(15))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", help="Single repo key (default: all)")
    parser.add_argument("--list", action="store_true", help="List configured repos and exit")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between requests (s)")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.list:
        for k, cfg in sorted(REPOS.items()):
            print(f"  {k:<12} {cfg['source']:<9} {cfg.get('metadata_prefix', cfg.get('api_base', ''))}")
        return 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    targets = [args.repo] if args.repo else sorted(REPOS.keys())
    for key in targets:
        if key not in REPOS:
            log.error("%s not configured", key)
            continue
        cfg = REPOS[key]
        log.info("=== %s (%s) ===", key, cfg["source"])
        t0 = time.time()
        if cfg["source"] == "figshare":
            mapping = harvest_figshare(key, cfg, args.delay)
        else:
            mapping = harvest_oai(key, cfg, args.delay)
        log.info("%s: done in %.1fs", key, time.time() - t0)
        summarise(key, mapping)

    return 0


if __name__ == "__main__":
    sys.exit(main())
