#!/usr/bin/env python3
"""
Merge validated dept_links research batches into dept_links_additional.json.

Reads every batch_*.json file under data/dept_links_research/ and applies
their entries to data/dept_links_additional.json. Each batch entry FULLY
replaces the existing entry for that university (the validated batches
are the source of truth — they may intentionally drop a misclassified
URL).

Idempotent: re-running with the same batches produces the same output.
Resumable: drop any new batch_*.json into the directory and re-run.
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESEARCH_DIR = ROOT / "data" / "dept_links_research"
TARGET = ROOT / "data" / "dept_links_additional.json"


def main() -> int:
    if not RESEARCH_DIR.is_dir():
        print(f"ERROR: {RESEARCH_DIR} does not exist")
        return 1

    batches = sorted(RESEARCH_DIR.glob("batch_*.json"))
    if not batches:
        print(f"ERROR: no batch_*.json files in {RESEARCH_DIR}")
        return 1

    target = json.loads(TARGET.read_text()) if TARGET.exists() else {}
    print(f"Loaded existing additional file: {len(target)} universities")

    touched_unis = []
    total_entries = 0
    for bp in batches:
        try:
            batch = json.loads(bp.read_text())
        except json.JSONDecodeError as e:
            print(f"  SKIP {bp.name}: invalid JSON ({e})")
            continue

        for uni, depts in batch.items():
            cleaned = {}
            for dept, urls in depts.items():
                kept = {k: v for k, v in urls.items() if v}
                if kept:
                    cleaned[dept] = kept
            target[uni] = cleaned
            touched_unis.append(uni)
            total_entries += len(cleaned)

        print(f"  + {bp.name}: {len(batch)} universities")

    TARGET.write_text(json.dumps(target, indent=2, ensure_ascii=False))
    print()
    print(f"Wrote {TARGET}")
    print(f"  {len(target)} universities total ({len(set(touched_unis))} touched by batches)")
    print(f"  {sum(len(v) for v in target.values())} entries")
    n_students = sum(1 for u in target.values() for x in u.values() if x.get("students"))
    n_faculty = sum(1 for u in target.values() for x in u.values() if x.get("faculty"))
    n_home = sum(1 for u in target.values() for x in u.values() if x.get("home"))
    print(f"  home: {n_home}  students: {n_students}  faculty: {n_faculty}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
