#!/usr/bin/env python3
"""Every institutional repository this site read, named and linked.

WHY

The university pages link each dissertation to the record in that school's
own repository, which is what makes a single name checkable. What no page
did was say which repositories those were, all together, so a reader could
see the whole source list and go to any of them directly.

WHERE THE URLS COME FROM

data/dept_links.json, which holds the per-department repository search URLs
the harvest actually used. The repository is the host those URLs share, so
this is the address the site really read rather than one looked up by hand
afterwards.

WHAT IT DOES NOT CLAIM

No record count. The per-institution record files published on this site are
a filtered view, not the harvest, and printing their length beside a
repository name would read as "this many records exist there", which is not
what it would be measuring. An institution whose repository host cannot be
derived is listed as such rather than dropped.

Usage:
    python3 scripts/build_repository_index.py
"""
from __future__ import annotations

import collections
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
DEPT_LINKS = ROOT / "data" / "dept_links.json"
UNI_INDEX = ROOT / "site" / "data" / "universities_index.json"
OUT = ROOT / "site" / "data" / "repository_index.json"

sys.path.insert(0, str(ROOT / "scripts"))
from atomic_write import write_text                          # noqa: E402

#: Hosts that resolve a record but are not the repository itself. A handle
#: service forwards to wherever the institution actually keeps the file, so
#: naming it as the repository would be wrong.
INDIRECT = {"hdl.handle.net", "doi.org", "dx.doi.org", "resolver.caltech.edu"}


def main() -> int:
    if not DEPT_LINKS.exists():
        print(f"ERROR: {DEPT_LINKS.relative_to(ROOT)} is missing.")
        return 1
    dept = json.loads(DEPT_LINKS.read_text())
    names = {u["key"]: u["name"]
             for u in json.loads(UNI_INDEX.read_text())["universities"]}

    rows = []
    for key in sorted(set(dept) | set(names)):
        hosts = collections.Counter()
        for d in (dept.get(key) or {}).values():
            u = d.get("repo_search") or ""
            if u:
                hosts[urlsplit(u).netloc] += 1
        host = hosts.most_common(1)[0][0] if hosts else ""
        rows.append({
            "key": key,
            "name": names.get(key, key),
            "repository": host,
            "url": f"https://{host}/" if host else "",
            #: A handle or DOI resolver is a redirector, not the archive.
            "indirect": host in INDIRECT,
            "departments_searched": sum(hosts.values()),
        })

    have = [r for r in rows if r["repository"]]
    out = {
        "source": "data/dept_links.json, the repository search URLs used by "
                  "the harvest",
        "institutions": len(rows),
        "with_repository": len(have),
        "without_repository": len(rows) - len(have),
        "indirect_resolvers": sum(1 for r in have if r["indirect"]),
        "note": "The repository is the host the harvest's own search URLs "
                "share. A handle or DOI host is a resolver that forwards to "
                "the institution's archive, and is marked as such.",
        "repositories": rows,
    }
    write_text(OUT, json.dumps(out, indent=1))
    print(f"wrote {OUT.relative_to(ROOT)}")
    print(f"  {len(rows)} institutions, {len(have)} with a repository, "
          f"{len(rows) - len(have)} without")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
