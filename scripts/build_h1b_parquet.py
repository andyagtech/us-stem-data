#!/usr/bin/env python3
"""Parquet exports for the H-1B work, queryable in the browser.

WHY PARQUET AND WHY SEPARATE FILES

The JSON datasets behind each page carry what that page draws. They cannot
answer a question nobody anticipated -- "is this employer in here?" -- without
somebody running a scan over 4 GB. Parquet over HTTP fixes that: a reader
issues SQL in their own browser and the engine fetches only the column chunks
it needs.

THIS DOES NOT TOUCH THE STEM EXPORTS. stem_records.parquet and
nonstem_records.parquet are built by build_parquet_from_site.py, read by
/query through DuckDB-Wasm, and are not written, moved or re-read here. These
files are new, separately named, and served to different pages. Nothing about
the dissertation corpus or the assistant that answers on it changes.

WHAT IS EXPORTED, AND WHY EACH ONE

  perm_public        one row per PERM filing by a public employer: employer,
                     job, worksite, CITIZENSHIP, birth country, the visa held.
                     The end-to-end table; small enough to query whole.
  h1b_employers      every employer in the LCA corpus with their filings,
                     industry, wages and states. This is what makes an
                     employer lookup a second rather than a four-minute scan.
  h1b_industry       every six-digit NAICS with its totals.
  h1b_occupation     every SOC code with its totals.

Output: site/data/exports/h1b_*.parquet

Usage:
    python3 scripts/build_h1b_parquet.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "site" / "data"
OUT = DATA / "exports"

#: Never written by this script. Named so that a future edit cannot quietly
#: add them to the loop.
PROTECTED = {"stem_records.parquet", "nonstem_records.parquet"}


def write(df, name: str) -> None:
    """Written through DuckDB, which is already a dependency here.

    pandas' own to_parquet wants pyarrow or fastparquet, and neither is in
    the lockfile. build_parquet_from_site.py already writes the dissertation
    exports with DuckDB, so this uses the same engine rather than adding a
    package for one script.
    """
    import duckdb
    if name in PROTECTED:
        raise SystemExit(f"FAIL: {name} belongs to the dissertation corpus and "
                         f"is built elsewhere. Refusing to write it.")
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    con = duckdb.connect()
    con.register("t", df)
    con.execute(f"COPY t TO '{path}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    con.close()
    print(f"  {name:<28}{len(df):>9,} rows  {path.stat().st_size / 1e6:>7.1f} MB")


def main() -> int:
    import pandas as pd

    before = {p.name: p.stat().st_mtime for p in OUT.glob("*.parquet")
              if p.name in PROTECTED}

    # ---- the end-to-end public-employer table ---------------------------
    src = DATA / "public_employer_perm.json"
    if src.exists():
        d = json.loads(src.read_text())
        write(pd.DataFrame(d["records"]), "h1b_perm_public.parquet")
    else:
        print("  public_employer_perm.json not built yet; skipping")

    # ---- every employer in the LCA corpus -------------------------------
    src = DATA / "h1b_by_industry.json"
    if src.exists():
        d = json.loads(src.read_text())
        rows = []
        for code, e in d["by_code"].items():
            for name, n in e["top_employers"]:
                rows.append({"employer": name, "naics": code,
                             "naics_filings": e["filings"],
                             "employer_filings": n,
                             "median_wage": e["median_wage"],
                             "low_level_pct": e["low_level_pct"]})
        write(pd.DataFrame(rows), "h1b_employers.parquet")

        ind = [{"naics": c, "filings": e["filings"], "positions": e["positions"],
                "employers": e["employers"], "median_wage": e["median_wage"],
                "low_level_pct": e["low_level_pct"],
                "top_title": (e["top_titles"][0][0] if e["top_titles"] else None),
                "top_employer": (e["top_employers"][0][0] if e["top_employers"] else None),
                "top_state": (e["top_states"][0][0] if e["top_states"] else None)}
               for c, e in d["by_code"].items()]
        write(pd.DataFrame(ind), "h1b_industry.parquet")

    # ---- every occupation ------------------------------------------------
    src = DATA / "h1b_by_occupation.json"
    if src.exists():
        d = json.loads(src.read_text())
        occ = [{"soc": c, "soc_title": e["soc_title"], "filings": e["filings"],
                "employers": e["employers"], "median_wage": e["median_wage"],
                "top_title": (e["top_titles"][0][0] if e["top_titles"] else None),
                "top_employer": (e["top_employers"][0][0] if e["top_employers"] else None)}
               for c, e in d["by_soc"].items()]
        write(pd.DataFrame(occ), "h1b_occupation.parquet")
    else:
        print("  h1b_by_occupation.json not built yet; skipping")

    after = {p.name: p.stat().st_mtime for p in OUT.glob("*.parquet")
             if p.name in PROTECTED}
    if before != after:
        raise SystemExit("FAIL: a protected dissertation export changed. "
                         "That must never happen.")
    print(f"  dissertation exports untouched: {', '.join(sorted(before)) or 'none present'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
