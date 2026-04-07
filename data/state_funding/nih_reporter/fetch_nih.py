#!/usr/bin/env python3
"""
Fetch NIH RePORTER grant totals for the 101 universities in the PhD Demographics
project (FY2020-2024).

Source: https://api.reporter.nih.gov/v2/projects/search
Reads entity mappings from /Users/andy/usds_china/pipeline/entity_map.json to
find all known NIH org_name variations for each university key. Paginates
through the API, aggregates counts/dollars by fiscal year, and tallies grants
by organization's `dept_type` as a proxy for "top departments" (the public
API does not expose named academic departments; `dept_type` is a coarse
NIH-assigned code such as BIOLOGY, ENGINEERING, MISCELLANEOUS).

Saves progress incrementally to nih_by_university.json so the script is
resumable.
"""
import json
import os
import sys
import time
import urllib.request
import urllib.error
from collections import defaultdict

API_URL = "https://api.reporter.nih.gov/v2/projects/search"
ENTITY_MAP = "/Users/andy/usds_china/pipeline/entity_map.json"
STEM_DIR = "/Users/andy/usds_china/site/data/stem"
OUT_PATH = "/Users/andy/usds_china/data/state_funding/nih_reporter/nih_by_university.json"
FISCAL_YEARS = [2020, 2021, 2022, 2023, 2024]
PAGE_SIZE = 500
RATE_LIMIT_SEC = 1.0
MAX_RETRIES = 4


def load_key_to_orgnames():
    em = json.load(open(ENTITY_MAP))
    key_to_names = defaultdict(list)
    for org, key in em.items():
        # Only keep ALL-CAPS org-name-ish entries (skip short aliases)
        if len(org) < 5:
            continue
        key_to_names[key].append(org)
    # Deduplicate while preserving order
    for k in key_to_names:
        seen = set()
        dedup = []
        for n in key_to_names[k]:
            if n not in seen:
                seen.add(n)
                dedup.append(n)
        key_to_names[k] = dedup
    return dict(key_to_names)


def get_university_keys():
    keys = []
    for fn in sorted(os.listdir(STEM_DIR)):
        if fn.endswith(".json") and fn != "_search.json":
            keys.append(fn[:-5])
    return keys


def post_json(body, retries=MAX_RETRIES):
    data = json.dumps(body).encode()
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                API_URL,
                data=data,
                headers={"Content-Type": "application/json", "User-Agent": "usds_china-research/1.0"},
            )
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                wait = (attempt + 1) * 5
                print(f"  HTTP {e.code}, retry in {wait}s")
                time.sleep(wait)
                continue
            raise
        except Exception as e:
            if attempt < retries - 1:
                wait = (attempt + 1) * 3
                print(f"  {type(e).__name__}: {e}, retry in {wait}s")
                time.sleep(wait)
                continue
            raise
    return None


def fetch_all_for_key(key, org_names):
    """Return (by_year dict, dept_counter dict)."""
    by_year = {str(y): {"grant_count": 0, "total_dollars": 0} for y in FISCAL_YEARS}
    dept_counter = defaultdict(int)
    seen_project_nums = set()

    for year in FISCAL_YEARS:
        offset = 0
        while True:
            body = {
                "criteria": {
                    "fiscal_years": [year],
                    "org_names": org_names,
                },
                "include_fields": [
                    "ProjectNum",
                    "FiscalYear",
                    "AwardAmount",
                    "Organization",
                ],
                "limit": PAGE_SIZE,
                "offset": offset,
            }
            try:
                resp = post_json(body)
            except Exception as e:
                print(f"  FAIL {key} FY{year} offset={offset}: {e}")
                break
            if not resp:
                break
            results = resp.get("results") or []
            meta = resp.get("meta") or {}
            total = meta.get("total", 0)

            for r in results:
                pn = r.get("project_num")
                if pn and pn in seen_project_nums:
                    continue
                if pn:
                    seen_project_nums.add(pn)
                amt = r.get("award_amount") or 0
                by_year[str(year)]["grant_count"] += 1
                by_year[str(year)]["total_dollars"] += int(amt)
                org = r.get("organization") or {}
                dept = org.get("dept_type") or "UNSPECIFIED"
                dept_counter[dept] += 1

            offset += len(results)
            if not results or offset >= total:
                break
            # NIH RePORTER caps offset at 14,999
            if offset >= 14500:
                print(f"  WARN {key} FY{year}: hit 14.5k offset cap (total={total})")
                break
            time.sleep(RATE_LIMIT_SEC)
        time.sleep(RATE_LIMIT_SEC)
    return by_year, dept_counter


def main():
    key_to_names = load_key_to_orgnames()
    keys = get_university_keys()

    # Load existing progress
    if os.path.exists(OUT_PATH):
        out = json.load(open(OUT_PATH))
    else:
        out = {}

    # Optional filter via CLI arg (for testing single university)
    if len(sys.argv) > 1:
        keys = [k for k in keys if k in sys.argv[1:]]

    for i, key in enumerate(keys, 1):
        if key in out and out[key].get("_complete"):
            print(f"[{i}/{len(keys)}] {key}: already complete, skipping")
            continue
        org_names = key_to_names.get(key, [])
        if not org_names:
            print(f"[{i}/{len(keys)}] {key}: NO ORG NAMES in entity_map, skipping")
            out[key] = {"name": None, "by_year": {}, "top_departments": [], "_complete": False, "_error": "no_org_names"}
            continue
        print(f"[{i}/{len(keys)}] {key}: querying {len(org_names)} org_name variant(s)")
        by_year, dept_counter = fetch_all_for_key(key, org_names)
        total_grants = sum(v["grant_count"] for v in by_year.values())
        total_dollars = sum(v["total_dollars"] for v in by_year.values())
        top_depts = sorted(dept_counter.items(), key=lambda x: -x[1])[:10]
        out[key] = {
            "name": org_names[0],
            "org_name_variants": org_names,
            "by_year": by_year,
            "top_departments": top_depts,
            "total_grants_2020_2024": total_grants,
            "total_dollars_2020_2024": total_dollars,
            "_complete": True,
        }
        print(f"  -> {total_grants:,} grants, ${total_dollars:,}")
        # Save after each university
        with open(OUT_PATH, "w") as f:
            json.dump(out, f, indent=2)

    print(f"\nDone. Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
