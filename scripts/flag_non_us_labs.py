#!/usr/bin/env python3
"""Mark every stored roster that is not at a US university.

The table's top entry was a Chinese laboratory credited to Illinois.
A Chinese lab staffed by Chinese students is not a finding, and the
crawl had no way to tell: it reached the professor through an
Illinois directory, because he used to be there, and followed his
research link abroad.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lab_name_cache as cache                                # noqa: E402
from follow_lab_links import get                              # noqa: E402
from us_affiliation import check                              # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
LABS = ROOT / "data" / "labs" / "discovered_labs.json"


def judge(g: dict) -> dict:
    url = g["url"]
    #: a foreign domain needs no fetch
    ok, why = check(url, "", g.get("institution", ""))
    if not ok:
        return {**g, "us_affiliated": False, "not_us_because": why}
    html = get(url)
    ok, why = check(url, html, g.get("institution", ""))
    return {**g, "us_affiliated": bool(ok),
            **({"not_us_because": why} if not ok else {})}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=12)
    a = ap.parse_args()
    doc = json.loads(LABS.read_text())
    todo = [g for g in doc["groups"] if g.get("status") == "roster"]
    print(f"Checking {len(todo)} rosters for a US affiliation")

    out = []
    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        for i, g in enumerate(ex.map(judge, todo), 1):
            out.append(g)
            if not g.get("us_affiliated"):
                print(f"  NOT US  {g['url'][:52]}")
                print(f"          {g.get('not_us_because', '')[:68]}")
            if i % 300 == 0:
                print(f"  ... {i}/{len(todo)}", flush=True)
            time.sleep(0.005)

    by = {g["url"]: g for g in out}
    doc["groups"] = [by.get(g["url"], g) for g in doc["groups"]]
    n = sum(1 for g in doc["groups"] if g.get("us_affiliated") is False)
    doc["non_us_rosters"] = n
    LABS.write_text(json.dumps(doc, indent=2) + "\n")
    print(f"\n  {n} rosters are not at a US university")
    return 0


if __name__ == "__main__":
    sys.exit(main())
