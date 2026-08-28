#!/usr/bin/env python3
"""Two proxies for cap-exempt status, and why neither is sufficient.

USCIS records cap status on the I-129 and does not publish it. Anyone
counting cap-exempt employers is therefore using a proxy, and there are two
available:

  industry code   NAICS 61, Educational Services, in the USCIS Employer Data
                  Hub. Self-reported by the filer.
  a directory     a third-party list of employers it treats as cap-exempt,
                  compiled from employer type.

Comparing them shows both are wrong in different directions, and the NAICS
failure is the more interesting one: the codes are self-reported and often
describe something other than the institution. Washington University in St
Louis files as Manufacturing. The University of Colorado Denver files as
Information. Neither appears in NAICS 61 at all.

The directory in turn misses thousands of employers that NAICS 61 catches --
mostly school districts and for-profit colleges, which are fee-exempt or not
exempt at all rather than cap-exempt.

The conclusion is not that one proxy is better. It is that cap status cannot
be derived from published data, which is why it is the first item on the
briefing's data-needs page.

Usage:
  python3 scripts/compare_cap_exempt_proxies.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import join_fellowship_employers as J  # noqa: E402

DIRECTORY = ROOT / "data" / "cap_exempt" / "directory.json"
OUT = ROOT / "data" / "cap_exempt" / "proxy_comparison.json"
YEARS = (2024, 2025)


def main() -> int:
    if not DIRECTORY.exists():
        print("  no directory.json; run the directory scraper first")
        return 1
    listed = {}
    for e in json.loads(DIRECTORY.read_text())["employers"]:
        k = J.norm(e["name"])
        if k:
            listed.setdefault(k, e)

    hub = defaultdict(lambda: {"appr": 0, "naics": None, "state": None, "name": None})
    for y in YEARS:
        p = ROOT / "data" / "h1b" / f"h1b_datahub_fy{y}.csv"
        if not p.exists():
            continue
        for row, L in J.hub_rows(p):
            nm = row[L["name"]].strip().strip('"')
            k = J.norm(nm)
            if not k:
                continue
            a = hub[k]
            a["appr"] += J.num(row[L["new"]]) + J.num(row[L["cont"]])
            a["naics"] = a["naics"] or (row[L["naics"]] or "").strip().strip('"')
            a["state"] = a["state"] or row[L["state"]]
            a["name"] = a["name"] or nm

    in_dir = {k for k in listed if k in hub}
    in_61 = {k for k, v in hub.items() if (v["naics"] or "").startswith("61")}
    only_dir = sorted(in_dir - in_61, key=lambda k: -hub[k]["appr"])
    only_61 = sorted(in_61 - in_dir, key=lambda k: -hub[k]["appr"])

    def rows(keys, n):
        return [{"employer": hub[k]["name"], "state": hub[k]["state"],
                 "naics": hub[k]["naics"], "approvals": hub[k]["appr"]}
                for k in keys[:n]]

    doc = {
        "_comment": ("Two proxies for cap-exempt status compared against the "
                     "USCIS Employer Data Hub. NEITHER IS AUTHORITATIVE: cap "
                     "status lives on the I-129 and is not published. NAICS "
                     "codes are self-reported and frequently describe "
                     "something other than the institution, so major "
                     "universities are absent from NAICS 61 entirely."),
        "years": list(YEARS),
        "directory": {"listed": len(listed), "found_in_hub": len(in_dir),
                      "approvals": sum(hub[k]["appr"] for k in in_dir)},
        "naics_61": {"employers": len(in_61),
                     "approvals": sum(hub[k]["appr"] for k in in_61)},
        "overlap": len(in_dir & in_61),
        "directory_only": {"count": len(only_dir), "largest": rows(only_dir, 20)},
        "naics_61_only": {"count": len(only_61), "largest": rows(only_61, 20)},
    }
    OUT.write_text(json.dumps(doc, indent=1) + "\n")

    print(f"  directory: {doc['directory']['listed']:,} listed, "
          f"{doc['directory']['found_in_hub']:,} in the hub, "
          f"{doc['directory']['approvals']:,} approvals")
    print(f"  NAICS 61:  {doc['naics_61']['employers']:,} employers, "
          f"{doc['naics_61']['approvals']:,} approvals")
    print(f"  overlap {doc['overlap']:,};  directory only {len(only_dir):,};  "
          f"NAICS 61 only {len(only_61):,}")
    print("  largest employers the directory catches and NAICS 61 misses:")
    for r in doc["directory_only"]["largest"][:8]:
        print(f"     {r['approvals']:>5,}  {r['employer'][:42]:44} {(r['naics'] or '')[:30]}")
    print(f"  wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
