#!/usr/bin/env python3
"""Fetch thesis.degree.level for bepress repos via oai_etdms.

The default `oai_dc` feed we harvest drops the degree field. The
`oai_etdms` metadata format (NDLTD standard) exposes a clean
`thesis.degree.level` value — "Dissertation" for PhD, "Thesis" for
Master's — plus the full `thesis.degree.name` (e.g. "Doctor of
Philosophy in Geoscience").

Writes mapping files to data/etdms_degrees/{repo_key}.json of the form
{identifier: {"level": "Dissertation"|"Thesis", "name": "..."}}.

`generate_name_lists.infer_degree_type` can then consult this mapping
to label records that were otherwise unlabeled.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
import urllib.parse
from pathlib import Path
from xml.etree import ElementTree as ET

import urllib.request

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "etdms_degrees"

NS = {
    "oai": "http://www.openarchives.org/OAI/2.0/",
    "etd": "http://www.ndltd.org/standards/metadata/etdms/1.0/",
}

log = logging.getLogger("enrich_etdms")


# Bepress repos: returns {key: {oai_base, sets}} for platform=bepress
def _load_bepress_repos() -> dict[str, dict]:
    sys.path.insert(0, str(ROOT / "scripts"))
    from scrape_oai_etds import REPOS

    return {
        k: {"oai_base": v["oai_base"], "sets": v.get("sets", [])}
        for k, v in REPOS.items()
        if v.get("platform") == "bepress"
    }


def _fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "etdms-enricher/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


# Bepress uses dot-separated element names like <thesis.degree.name>,
# <thesis.degree.level>, NOT namespaced <degree><level>. We parse them
# as literal local tags via regex since ET mangles them.
import re as _re

_NAME_RE = _re.compile(r"<thesis\.degree\.name>([^<]+)</thesis\.degree\.name>")
_LEVEL_RE = _re.compile(r"<thesis\.degree\.level>([^<]+)</thesis\.degree\.level>")
_RECORD_RE = _re.compile(r"<record\b[^>]*>(.*?)</record>", _re.DOTALL)
_ID_RE = _re.compile(r"<identifier>([^<]+)</identifier>")
_RT_RE = _re.compile(r"<resumptionToken[^>]*>([^<]*)</resumptionToken>")


def _parse_page(raw: bytes) -> tuple[dict[str, dict], str]:
    """Return (mapping_for_page, next_resumption_token)."""
    text = raw.decode("utf-8", errors="replace")
    mapping: dict[str, dict] = {}
    for rec_body in _RECORD_RE.findall(text):
        # The <identifier> under header is the first one; record-level identifiers are inside metadata
        id_match = _ID_RE.search(rec_body)
        if not id_match:
            continue
        ident = id_match.group(1).strip()
        name_match = _NAME_RE.search(rec_body)
        level_match = _LEVEL_RE.search(rec_body)
        name = name_match.group(1).strip() if name_match else ""
        level = level_match.group(1).strip() if level_match else ""
        if name or level:
            mapping[ident] = {"level": level, "name": name}
    rt_match = _RT_RE.search(text)
    token = (rt_match.group(1) or "").strip() if rt_match else ""
    return mapping, token


def harvest_one(repo_key: str, oai_base: str, sets: list[str], delay: float = 1.0) -> dict[str, dict]:
    """Return {identifier: {level, name}} for all theses sets in a bepress repo."""
    mapping: dict[str, dict] = {}
    sets_to_harvest = sets if sets else [None]

    for oai_set in sets_to_harvest:
        log.info("  set=%s", oai_set or "(all)")
        token: str | None = None
        page = 0
        while True:
            page += 1
            if token:
                url = f"{oai_base}?verb=ListRecords&resumptionToken={urllib.parse.quote(token)}"
            else:
                params = f"verb=ListRecords&metadataPrefix=oai_etdms"
                if oai_set:
                    params += f"&set={urllib.parse.quote(oai_set)}"
                url = f"{oai_base}?{params}"
            try:
                raw = _fetch(url)
            except Exception as e:
                log.error("  fetch failed: %s", e)
                break
            page_map, token = _parse_page(raw)
            mapping.update(page_map)
            log.info("    page %d: +%d (total %d)", page, len(page_map), len(mapping))
            if not token:
                break
            time.sleep(delay)

    return mapping


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", help="Single repo key (default: all bepress)")
    parser.add_argument("--list", action="store_true", help="List bepress repos and exit")
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(message)s",
        datefmt="%H:%M:%S",
    )

    repos = _load_bepress_repos()
    if args.list:
        for k, u in sorted(repos.items()):
            print(f"  {k:<18} {u}")
        return 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    targets = [args.repo] if args.repo else sorted(repos.keys())
    for key in targets:
        if key not in repos:
            log.error("%s not a bepress repo", key)
            continue
        log.info("=== %s ===", key)
        t0 = time.time()
        cfg = repos[key]
        mapping = harvest_one(key, cfg["oai_base"], cfg["sets"], delay=args.delay)
        out = OUT_DIR / f"{key}.json"
        out.write_text(json.dumps(mapping, indent=2, sort_keys=True))
        log.info("%s: %d records in %.1fs -> %s", key, len(mapping), time.time() - t0, out)

    return 0


if __name__ == "__main__":
    sys.exit(main())
