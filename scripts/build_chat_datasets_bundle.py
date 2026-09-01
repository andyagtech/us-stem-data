#!/usr/bin/env python3
"""Put the published datasets where the assistant can actually query them.

The assistant already carries a knowledge file per finding, so it can
DISCUSS the wage levels or the green-card queue. It cannot look anything up:
its bundle holds a dozen files from an earlier stage of the project and none
of the datasets built since. Asked for the Level I wage in a particular
occupation, or the queue in a particular year, it has prose and no numbers.

This copies the published datasets into the bundle, minus the ones that are
too large or serve the site rather than a question.

SIZE IS THE CONSTRAINT. The bundle ships with the Lambda, so every file is
weighed against what it answers. Anything over the cap is skipped and named
rather than silently dropped.

Usage:
  python3 scripts/build_chat_datasets_bundle.py
  python3 scripts/build_chat_datasets_bundle.py --max-kb 400
"""
from __future__ import annotations

import argparse
import gzip
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from atomic_write import write_json                          # noqa: E402
SITE = ROOT / "site" / "data"
OUT = ROOT / "cloud" / "chat" / "chat_data" / "datasets"

# Served to the website or already in the bundle in another form; nothing a
# question would reach for.
SKIP = {"live_bundle", "site_map", "universities_index", "taxonomy",
        "us_states", "distribution", "parquet_exports", "og_cards",
        "level_rankings", "legal_directory"}
MAX_KB_DEFAULT = 600


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-kb", type=int, default=MAX_KB_DEFAULT)
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.json*"):
        old.unlink()

    copied, skipped, oversize = [], [], []
    for p in sorted(SITE.glob("*.json")):
        key = p.stem
        if key in SKIP:
            skipped.append(key)
            continue
        kb = p.stat().st_size / 1024
        if kb > args.max_kb:
            # Large files are gzipped rather than dropped -- most of these
            # are long series that compress by an order of magnitude.
            gz = OUT / f"{key}.json.gz"
            with p.open("rb") as fh, gzip.open(gz, "wb", compresslevel=9) as out:
                shutil.copyfileobj(fh, out)
            gkb = gz.stat().st_size / 1024
            if gkb > args.max_kb:
                gz.unlink()
                oversize.append((key, round(kb), round(gkb)))
                continue
            copied.append((key, round(gkb), True))
            continue
        shutil.copy2(p, OUT / p.name)
        copied.append((key, round(kb), False))

    index = {
        "_comment": (
            "Published datasets shipped with the assistant so it can look "
            "figures up rather than only describe them. Each file is the same "
            "JSON served at /data/<key>.json on the site, and each carries "
            "its own _comment with the limits on how it may be read -- those "
            "limits travel with the data and are not optional. Files marked "
            "gzipped must be decompressed before parsing."),
        "generated_from": "site/data",
        "files": [{"key": k, "kb": kb, "gzipped": gz} for k, kb, gz in copied],
        "skipped_as_site_only": sorted(skipped),
        "omitted_too_large": [{"key": k, "kb": kb, "gzipped_kb": g}
                              for k, kb, g in oversize],
    }
    write_json(OUT / "index.json", index)

    total = sum(kb for _k, kb, _g in copied)
    print(f"  {len(copied)} datasets, {total / 1024:.1f} MB in "
          f"{OUT.relative_to(ROOT)}")
    print(f"  skipped as site-only: {len(skipped)}")
    for k, kb, g in oversize:
        print(f"  OMITTED {k}: {kb} KB ({g} KB gzipped) over the "
              f"{args.max_kb} KB cap")
    big = sorted(copied, key=lambda x: -x[1])[:5]
    print("  largest:", ", ".join(f"{k} {kb}KB{'gz' if g else ''}"
                                  for k, kb, g in big))
    return 0


if __name__ == "__main__":
    sys.exit(main())
