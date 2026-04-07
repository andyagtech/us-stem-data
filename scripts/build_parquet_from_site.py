#!/usr/bin/env python3
"""
Build stem_records.parquet and nonstem_records.parquet from existing site/data/{stem,nonstem}/*.json
files. Includes all 9 fields (university, department, year, name, classification, confidence, title, url, degree).

Run: python3 scripts/build_parquet_from_site.py
"""
import json
import os
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).parent.parent
SITE_DIR = ROOT / "site" / "data"
OUT_DIR = SITE_DIR / "exports"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def build(track: str):
    src = SITE_DIR / track
    if not src.is_dir():
        print(f"  {track}: directory missing, skipping")
        return

    rows = []
    files = sorted(src.glob("*.json"))
    for jf in files:
        if jf.name.startswith("_"):
            continue
        with open(jf) as f:
            data = json.load(f)
        key = data.get("key", jf.stem)
        for r in data.get("records", []):
            rows.append({
                "university": key,
                "department": r[0] if len(r) > 0 else "",
                "year": int(r[1]) if len(r) > 1 and r[1] else 0,
                "name": r[2] if len(r) > 2 else "",
                "classification": r[3] if len(r) > 3 else "",
                "confidence": r[4] if len(r) > 4 else "",
                "title": r[5] if len(r) > 5 else "",
                "url": r[6] if len(r) > 6 else "",
                "degree": r[7] if len(r) > 7 else "",
            })

    if not rows:
        print(f"  {track}: no records")
        return

    df = pd.DataFrame(rows)
    out_path = OUT_DIR / f"{track}_records.parquet"
    con = duckdb.connect()
    con.register("rec_df", df)
    con.execute(f"COPY rec_df TO '{out_path}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    con.close()
    size_mb = out_path.stat().st_size / 1024 / 1024
    print(f"  {track}: {len(df):,} records → {out_path.name} ({size_mb:.1f} MB)")


if __name__ == "__main__":
    print("Building Parquet exports from site/data/{stem,nonstem}/*.json...")
    build("stem")
    build("nonstem")
    print("Done.")
