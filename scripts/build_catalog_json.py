#!/usr/bin/env python3
"""Regenerate /catalog.json from the live data.

IT WAS HAND-WRITTEN AND IT ROTTED. The published catalogue is the machine
-readable description of everything this site offers, it is linked from the
site as "Data Catalog (JSON)" and used as the API surface, and it was last
touched on 2026-03-31. By October it claimed 107 universities and 334,788
STEM records against a real 106 and 509,072 -- a third of the corpus missing
from the document that tells a machine what the corpus is.

It also described only the per-university record files. It said nothing about
the parquet exports behind the query console, and nothing about the ninety
catalogued datasets, so a reader of the catalogue could not discover most of
what is published.

Everything here is counted at build time from the files themselves or read
from pipeline/datasets.py. Nothing is typed, so it cannot drift again.

Usage:
  python3 scripts/build_catalog_json.py
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from atomic_write import write_text                            # noqa: E402
from pipeline.datasets import CATALOG                          # noqa: E402

SITE = ROOT / "site"
OUT = SITE / "catalog.json"

#: The record schema is a property of the file format, not of the data, so it
#: is the one part that is legitimately written here. It is asserted against
#: a real row below, so it cannot silently stop describing the files.
RECORD_FIELDS = [
    ("department", "string", "Department or field of study, normalised via the taxonomy"),
    ("year", "integer", "Year of award"),
    ("name", "string", "Author, as the awarding repository recorded it, with catalogue artefacts removed"),
    ("origin_class", "string", "Name-classification bucket"),
    ("confidence", "string", "Classifier confidence"),
    ("title", "string", "Title of the thesis or dissertation, truncated to 90 characters"),
    ("url", "string", "Link to the record in the awarding university's repository"),
    ("degree_type", "string", "PhD, MS or unlabelled"),
]


def university_group(track: str) -> dict:
    src = SITE / "data" / track
    files, total = [], 0
    for f in sorted(src.glob("*.json")):
        if f.name.startswith("_"):
            continue
        blob = json.loads(f.read_text())
        recs = blob.get("records") or []
        total += len(recs)
        files.append({
            "key": blob.get("key") or f.stem,
            "name": blob.get("name") or f.stem,
            "nra_pct": blob.get("nra"),
            "records": len(recs),
            "url": f"/data/{track}/{f.name}",
            "size_bytes": f.stat().st_size,
        })
    return {"description": f"{'STEM' if track == 'stem' else 'Non-STEM'} thesis "
                           f"and dissertation records by university",
            "format": "JSON", "count": len(files),
            "total_records": total, "files": files}


def exports_group() -> dict:
    d = SITE / "data" / "exports"
    files = []
    for f in sorted(d.glob("*.parquet")):
        files.append({"name": f.stem, "url": f"/data/exports/{f.name}",
                      "format": "Parquet", "size_bytes": f.stat().st_size})
    return {"description": "Columnar exports. These are the tables the SQL "
                           "console at /query loads, and they can be queried "
                           "directly with DuckDB from this URL.",
            "format": "Parquet", "count": len(files), "files": files}


def derived_group() -> dict:
    """Every catalogued dataset that publishes a JSON under site/data."""
    out = []
    for d in CATALOG:
        for produced in d.produces:
            if not produced.startswith("site/data/") or not produced.endswith(".json"):
                continue
            f = ROOT / produced
            if not f.exists():
                continue
            out.append({
                "key": d.key,
                "url": "/" + produced[len("site/"):],
                "summary": d.summary,
                "source": d.source,
                "source_url": getattr(d, "source_url", None),
                "cadence": getattr(d, "cadence", None),
                "size_bytes": f.stat().st_size,
            })
    out.sort(key=lambda r: r["key"])
    return {"description": "Built datasets. Each is produced by one script in "
                           "scripts/ from the federal source named in "
                           "source_url, and every figure on the site is read "
                           "from one of these at render time.",
            "format": "JSON", "count": len(out), "files": out}


def main() -> int:
    stem = university_group("stem")
    nonstem = university_group("nonstem")

    #: Prove the documented schema still matches a real row before publishing
    #: it. A catalogue that describes the wrong shape is worse than none.
    probe = json.loads((SITE / "data" / "stem" / "mit.json").read_text())
    row = (probe.get("records") or [[]])[0]
    if len(row) != len(RECORD_FIELDS):
        raise SystemExit(
            f"record shape changed: file has {len(row)} fields, the catalogue "
            f"documents {len(RECORD_FIELDS)}. Update RECORD_FIELDS.")

    sources = sorted({d.source_url for d in CATALOG
                      if getattr(d, "source_url", None)})

    cat = {
        "version": "2.0.0",
        "last_updated": datetime.now(timezone.utc)
                                .replace(microsecond=0).isoformat()
                                .replace("+00:00", "Z"),
        "description": ("Machine-readable catalogue of every dataset "
                        "published by phd-demographics.andy-barr.com. "
                        "Generated from the data at build time."),
        "source": "https://phd-demographics.andy-barr.com/",
        "license": "Public domain federal data. Attribution appreciated.",
        "contact": "https://phd-demographics.andy-barr.com/about",
        "totals": {
            "stem_records": stem["total_records"],
            "nonstem_records": nonstem["total_records"],
            "universities": stem["count"],
            "built_datasets": len(CATALOG),
        },
        "datasets": {
            "stem_universities": stem,
            "nonstem_universities": nonstem,
            "exports": exports_group(),
            "built_datasets": derived_group(),
        },
        "record_schema": {
            "description": ("Each university JSON holds a records array. "
                            "Each record is a positional array: "
                            + ", ".join(f[0] for f in RECORD_FIELDS)),
            "fields": [{"index": i, "name": n, "type": t, "description": d}
                       for i, (n, t, d) in enumerate(RECORD_FIELDS)],
        },
        "government_sources": sources,
    }
    write_text(OUT, json.dumps(cat, indent=2))
    print(f"Wrote {OUT.relative_to(ROOT)}")
    print(f"  {stem['count']} universities, "
          f"{stem['total_records']:,} STEM + {nonstem['total_records']:,} "
          f"non-STEM records")
    print(f"  {cat['datasets']['exports']['count']} parquet exports, "
          f"{cat['datasets']['built_datasets']['count']} built datasets, "
          f"{len(sources)} federal sources")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
