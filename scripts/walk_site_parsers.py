#!/usr/bin/env python3
"""Walk every department named in the per-institution modules.

Each module lists its departments explicitly. For each one this
takes the faculty directory, visits every profile under it, follows
the professor's own research link, and reads the roster there.

Where a department's markup defeats the shared reader, its entry
names a reader of its own and only that department changes.
"""
from __future__ import annotations

import argparse
import importlib
import json
import pkgutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lab_store                                              # noqa: E402
import site_parsers                                           # noqa: E402
from walk_department import faculty_of, roster_under          # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
#: WHICH DEPARTMENTS ARE ALREADY DONE. A walk of 505 departments runs
#: for hours, and a dropped connection used to mean starting at the
#: beginning. Each department is recorded the moment it finishes, so a
#: restart picks up where the last one stopped.
DONE = ROOT / "data" / "labs" / ".walk_done.json"


def done_set() -> set:
    if not DONE.exists():
        return set()
    try:
        return set(json.loads(DONE.read_text()))
    except Exception:                                         # noqa: BLE001
        return set()


def mark_done(url: str, seen: set) -> None:
    seen.add(url)
    tmp = DONE.with_suffix(".tmp")
    tmp.write_text(json.dumps(sorted(seen)))
    tmp.replace(DONE)


def modules() -> list:
    out = []
    for m in pkgutil.iter_modules(site_parsers.__path__):
        mod = importlib.import_module(f"site_parsers.{m.name}")
        if hasattr(mod, "targets"):
            out.append(mod)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--institution", help="substring of one university")
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--max-faculty", type=int, default=40)
    ap.add_argument("--restart", action="store_true",
                    help="ignore the resume file and walk everything")
    a = ap.parse_args()

    seen = set() if a.restart else done_set()

    jobs = []
    for mod in modules():
        for t in mod.targets():
            if a.institution and a.institution.lower() not in \
                    t["institution"].lower():
                continue
            jobs.append(t)
    skipped = [t for t in jobs if t["url"] in seen]
    jobs = [t for t in jobs if t["url"] not in seen]
    print(f"Walking {len(jobs)} department directories"
          + (f" ({len(skipped)} already done)" if skipped else ""))

    found = []
    for t in jobs:
        try:
            profs = faculty_of(t["url"])[: a.max_faculty]
        except Exception as exc:                              # noqa: BLE001
            #: a department that fails is NOT marked done, so a
            #: restart tries it again once the network is back
            print(f"  !! {t['url'][:54]}: {str(exc)[:40]}", flush=True)
            continue
        if not profs:
            mark_done(t["url"], seen)
            continue
        hits = 0
        with ThreadPoolExecutor(max_workers=a.workers) as ex:
            for r in ex.map(lambda u: roster_under(
                    u, t["institution"], t["department_field"]), profs):
                if r:
                    r["department"] = t.get("department")
                    found.append(r)
                    hits += 1
                time.sleep(0.01)
        mark_done(t["url"], seen)
        if hits:
            print(f"  {hits:>3} rosters  {t['department']:<28} "
                  f"{t['institution'][:30]}", flush=True)
        #: store as we go, so a long walk is not lost to an interruption
        if len(found) >= 40:
            print("   ", lab_store.merge(found, source="site-parsers"))
            found = []

    if found:
        print("\n ", lab_store.merge(found, source="site-parsers"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
