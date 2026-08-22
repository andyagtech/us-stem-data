#!/usr/bin/env python3
"""Re-harvest the DSpace repositories to recover true award dates. Resumable.

WHY ONLY DSPACE. Probing every platform showed the accession-vs-award defect is
confined to repositories that emit MULTIPLE dc:date values per record. DSpace
does; nothing else here does.

    mines (dspace)   ['2023-09-18T19:39:08Z', '2023-09-18T19:39:08Z', '2009']
    unm   (bepress)  ['2009-05-01T07:00:00Z']

Taking the first value on the DSpace record dates a 2009 thesis to 2023. On the
bepress record there is only one date and nothing to get wrong. So bepress (53),
invenio (3), figshare (1) and eprints (1) are left alone -- re-fetching them
would spend hours and change nothing.

SAFETY. Each repo is harvested independently. scrape_oai_etds writes to a
.csv.partial sibling and only replaces the live CSV once the date-fill guard
approves it, so a bad harvest costs a look at a partial file rather than a
restore from S3. All 110 CSVs were verified byte-identical to
s3://phd-demographics-raw-data/ before this run.

RESUMABILITY, two layers:
  * This runner keeps a manifest of repos already finished. Re-running skips
    them, so an interrupted run continues where it stopped.
  * Within one repo, scrape_oai_etds --resume continues from the OAI
    resumption token rather than restarting the walk.

Usage:
    python3 scripts/reharvest_dspace.py                 # start or continue
    python3 scripts/reharvest_dspace.py --status         # what is done
    python3 scripts/reharvest_dspace.py --repo mit       # one repo
    python3 scripts/reharvest_dspace.py --reset          # forget the manifest
"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "data" / "western_us_dissertations"
MANIFEST = CORPUS / "_reharvest_manifest.json"
PY = str(ROOT / ".venv" / "bin" / "python")
HARVESTER = str(ROOT / "scripts" / "scrape_oai_etds.py")


def targets() -> list[str]:
    sys.path.insert(0, str(ROOT / "scripts"))
    import scrape_oai_etds as S
    return sorted(k for k, v in S.REPOS.items()
                  if v.get("platform") in ("dspace", "dspace5"))


def load() -> dict:
    if MANIFEST.exists():
        try:
            return json.loads(MANIFEST.read_text())
        except json.JSONDecodeError:
            pass
    return {"started": None, "repos": {}}


def save(m: dict) -> None:
    tmp = MANIFEST.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(m, indent=1))
    tmp.replace(MANIFEST)


def date_fill(key: str) -> tuple[int, float]:
    p = CORPUS / f"{key}_etds.csv"
    if not p.exists():
        return (0, 0.0)
    try:
        with open(p, newline="", encoding="utf-8", errors="replace") as fh:
            rows = list(csv.DictReader(fh))
    except OSError:
        return (0, 0.0)
    if not rows:
        return (0, 0.0)
    filled = sum(1 for r in rows if (r.get("date") or "").strip())
    return (len(rows), 100.0 * filled / len(rows))


def run_one(key: str, delay: float) -> dict:
    before_n, before_pct = date_fill(key)
    t0 = time.time()
    proc = subprocess.run(
        [PY, HARVESTER, "--repo", key, "--delay", str(delay)],
        capture_output=True, text=True, timeout=7200)
    after_n, after_pct = date_fill(key)
    tail = (proc.stdout or "").strip().splitlines()[-1:] or [""]
    refused = "REFUSING to overwrite" in (proc.stdout + proc.stderr)
    return {
        "ok": proc.returncode == 0 and not refused,
        "refused": refused,
        "returncode": proc.returncode,
        "seconds": round(time.time() - t0, 1),
        "rows_before": before_n, "rows_after": after_n,
        "date_pct_before": round(before_pct, 1),
        "date_pct_after": round(after_pct, 1),
        "last_line": tail[0][:160],
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--reset", action="store_true")
    ap.add_argument("--delay", type=float, default=1.0)
    args = ap.parse_args()

    if args.reset:
        MANIFEST.unlink(missing_ok=True)
        print("  manifest cleared")
        return 0

    todo = [args.repo] if args.repo else targets()
    m = load()

    if args.status:
        done = [k for k in todo if k in m["repos"]]
        print(f"  {len(done)}/{len(todo)} repos finished")
        for k in todo:
            r = m["repos"].get(k)
            if not r:
                print(f"    {k:<18} pending")
            else:
                flag = "ok" if r["ok"] else ("REFUSED" if r.get("refused") else "FAILED")
                print(f"    {k:<18} {flag:<8} {r['rows_before']:>7,} -> {r['rows_after']:>7,} rows, "
                      f"date {r['date_pct_before']:>5.1f}% -> {r['date_pct_after']:>5.1f}%")
        return 0

    if not m["started"]:
        m["started"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        save(m)

    pending = [k for k in todo if k not in m["repos"]]
    print(f"  {len(todo)} target(s), {len(todo)-len(pending)} already done, "
          f"{len(pending)} to go", flush=True)

    for i, key in enumerate(pending, 1):
        print(f"  [{i}/{len(pending)}] {key} ...", flush=True)
        try:
            res = run_one(key, args.delay)
        except subprocess.TimeoutExpired:
            res = {"ok": False, "refused": False, "returncode": -1,
                   "seconds": 7200, "rows_before": 0, "rows_after": 0,
                   "date_pct_before": 0, "date_pct_after": 0,
                   "last_line": "TIMEOUT after 2h",
                   "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        m["repos"][key] = res
        save(m)                       # after EVERY repo, so a kill loses one
        flag = "ok" if res["ok"] else ("REFUSED" if res["refused"] else "FAILED")
        print(f"        {flag}  {res['rows_before']:,} -> {res['rows_after']:,} rows, "
              f"date {res['date_pct_before']}% -> {res['date_pct_after']}%, "
              f"{res['seconds']}s", flush=True)

    ok = sum(1 for r in m["repos"].values() if r["ok"])
    ref = sum(1 for r in m["repos"].values() if r.get("refused"))
    bad = len(m["repos"]) - ok - ref
    print(f"\n  finished: {ok} ok, {ref} refused by the guard, {bad} failed")
    print(f"  manifest: {MANIFEST}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
