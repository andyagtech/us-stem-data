#!/usr/bin/env python3
"""Build an IPEDS ground-truth dataset of non-resident-alien (NRA) share of
doctoral completions.

Source
------
IPEDS Completions "A" files under ``data/ipeds/`` (``c{year}_a.csv`` /
``C{year}_A.csv``, with ``_rv`` revised variants preferred when present).

Outputs (gzipped CSV, written under ``data/ipeds/nra_ground_truth/``)
--------------------------------------------------------------------
  doctoral_nra_by_cip.csv.gz    tidy grain: unitid x year x cipcode x awlevel
                                x majornum
  doctoral_nra_by_cip2.csv.gz   same, rolled up to the 2-digit CIP family
  doctoral_inst_totals.csv.gz   the IPEDS CIPCODE=99 institution aggregate rows
  _metadata.md                  provenance / exclusions / caveats

Parquet is written instead of gzipped CSV when duckdb or pyarrow is importable.
Neither is installed in this environment, so CSV.GZ is the working format.

Why the code looks the way it does -- verified quirks of the source files
------------------------------------------------------------------------
* The first header cell carries a UTF-8 BOM in the 2023+ files, and the LAST
  header cell carries a trailing space in the 2002-2007 files (``'CRACE24 '``).
  Every header cell is therefore stripped and upper-cased before use.
* ``CIPCODE`` is space padded in several years (``'99     '``) and appears
  as ``'99'``, ``'99.0000'`` and (pre-1995) ``'990000'``.  It is normalised to
  a dotted ``NN.NNNN`` form, with the institution aggregate as plain ``'99'``.
* ``CIPCODE`` 99 is an institution-level AGGREGATE.  It is split into its own
  output file so it can never be summed alongside real CIP rows.
* Two award-level schemes coexist.  Through 2007 doctoral awards are
  AWLEVEL 09 (doctor's) and 10 (first-professional).  From 2010 they are 17
  (research/scholarship), 18 (professional practice) and 19 (other).  In the
  2008 and 2009 files BOTH schemes appear, institution by institution, with
  ZERO institutions using both (verified).  AWLEVEL is kept as a column and
  never merged.
* Two race schemes coexist.  Through 2007 race is CRACE01-CRACE24; from 2011
  it is CNRALT/CASIAT/CWHITT/...  In 2008-2010 both appear and they are
  COMPLEMENTARY, so they are SUMMED, not overwritten.  Verified at row level:
  legacy race totals + modern race totals + CNRALT + CUNKNT == CTOTALT for
  100% of rows in 2008, 2009 and 2010, including the ~2,000 rows per year
  where both schemes are non-zero.
* NRA and grand total are the one thing the schemes agree on.  Legacy
  CRACE17 == CRACE01 + CRACE02 == non-resident-alien total and legacy
  CRACE24 == CRACE15 + CRACE16 == grand total (verified: 0 exceptions in
  200,336 rows of c2002).  In the 2008-2010 files those two live in CNRALT
  and CTOTALT and are populated for every row under either scheme, so
  ``nra_share`` is NOT affected by the race-scheme transition.

Usage
-----
    python3 scripts/build_ipeds_nra_ground_truth.py            # build
    python3 scripts/build_ipeds_nra_ground_truth.py --validate # build + checks
    python3 scripts/build_ipeds_nra_ground_truth.py --validate-only
"""

from __future__ import annotations

import argparse
import csv
import gzip
import logging
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
import sys as _sys, pathlib as _pl
_sys.path.insert(0, str(_pl.Path(__file__).resolve().parent.parent))
from pipeline.models import STEM_NARROW   # noqa: E402


REPO = Path(__file__).resolve().parent.parent
IPEDS = REPO / "data" / "ipeds"
OUTDIR = IPEDS / "nra_ground_truth"

log = logging.getLogger("ipeds_nra")

# Award levels retained.  09/10 are the pre-2010 scheme, 17/18/19 the modern
# one.  Legacy 11 (post-first-professional certificate) is excluded: it is not
# a doctorate.
DOCTORAL_AWLEVELS = {"9", "10", "17", "18", "19"}

AWLEVEL_LABELS = {
    "9": "Doctor's degree (pre-2010 scheme)",
    "10": "First-professional degree (pre-2010 scheme)",
    "17": "Doctor's degree - research/scholarship",
    "18": "Doctor's degree - professional practice",
    "19": "Doctor's degree - other",
}

# Canonical output measures -> (modern column, legacy CRACE column)
# ``None`` means the scheme has no such category.
MEASURES = [
    # name          modern      legacy
    ("total",       "CTOTALT",  "CRACE24"),
    ("total_men",   "CTOTALM",  "CRACE15"),
    ("total_women", "CTOTALW",  "CRACE16"),
    ("nra",         "CNRALT",   "CRACE17"),
    ("nra_men",     "CNRALM",   "CRACE01"),
    ("nra_women",   "CNRALW",   "CRACE02"),
    ("asian",       "CASIAT",   "CRACE20"),
    ("white",       "CWHITT",   "CRACE22"),
    ("black",       "CBKAAT",   "CRACE18"),
    ("hispanic",    "CHISPT",   "CRACE21"),
    ("aian",        "CAIANT",   "CRACE19"),
    ("nhpi",        "CNHPIT",   None),      # not separable before 2011
    ("two_or_more", "C2MORT",   None),      # not separable before 2011
    ("unknown",     "CUNKNT",   "CRACE23"),
]

# Measures where the two schemes are the SAME underlying quantity (the legacy
# column was simply renamed) and must therefore NOT be summed in 2008-2010,
# where both column names are present in the same file.
SHARED_MEASURES = {"total", "total_men", "total_women", "nra", "nra_men", "nra_women"}

# The 1996-2001 files stop at CRACE16: they carry only the men/women columns
# and none of the CRACE17-CRACE24 total columns.  When the legacy TOTAL column
# is absent from a file, derive it from its men/women pair.  Only applied when
# the total column is genuinely missing, so the 2008-2010 files (which do have
# CRACE18-CRACE22) never double count.
LEGACY_PAIRS = {
    "total":       ("CRACE15", "CRACE16"),
    "nra":         ("CRACE01", "CRACE02"),
    "black":       ("CRACE03", "CRACE04"),
    "aian":        ("CRACE05", "CRACE06"),
    "asian":       ("CRACE07", "CRACE08"),
    "hispanic":    ("CRACE09", "CRACE10"),
    "white":       ("CRACE11", "CRACE12"),
    "unknown":     ("CRACE13", "CRACE14"),
}

COUNT_COLS = [m[0] for m in MEASURES]

OUT_COLS = ["unitid", "year", "awlevel", "cipcode", "majornum"] + COUNT_COLS + ["nra_share"]
OUT_COLS_CIP2 = ["unitid", "year", "awlevel", "cip2", "majornum"] + COUNT_COLS + ["nra_share"]
OUT_COLS_INST = ["unitid", "year", "awlevel", "majornum"] + COUNT_COLS + ["nra_share"]


# --------------------------------------------------------------------------
# file discovery
# --------------------------------------------------------------------------

def discover_files() -> dict[int, Path]:
    """Map data year -> completions file, preferring the revised (_rv) release.

    Only the "A" (award-level x CIP x race) files are usable.  The 1984-1994
    ``c{year}_cip.csv`` files carry only CRACE15/CRACE16 (total men / total
    women) and have no citizenship breakdown at all, so they cannot contribute
    to an NRA dataset and are skipped.
    """
    base: dict[int, Path] = {}
    rev: dict[int, Path] = {}
    for p in sorted(IPEDS.glob("*.csv")):
        name = p.name.lower()
        m = re.fullmatch(r"c(\d{4})_a(_rv)?\.csv", name)
        if not m:
            continue
        digits, is_rv = m.group(1), bool(m.group(2))
        n = int(digits)
        if 1980 <= n <= 2100:
            year = n
        else:
            # academic-year named files: c9596_a.csv -> data year 1996,
            # i.e. the END of the academic year, matching the C{year}
            # convention used from 2000 on.
            end = int(digits[2:])
            year = 1900 + end if end > 50 else 2000 + end
        (rev if is_rv else base)[year] = p
    out = dict(base)
    out.update(rev)
    return dict(sorted(out.items()))


# --------------------------------------------------------------------------
# parsing helpers
# --------------------------------------------------------------------------

def read_rows(path: Path):
    """Yield dicts with stripped/upper-cased keys.  Handles BOM and the
    trailing-space header cell found in the 2002-2007 files."""
    with open(path, newline="", encoding="utf-8-sig", errors="replace") as fh:
        reader = csv.reader(fh)
        header = [h.strip().upper() for h in next(reader)]
        width = len(header)
        for row in reader:
            if len(row) < width:
                row = row + [""] * (width - len(row))
            yield dict(zip(header, row))
    return


def to_int(value: str | None) -> int:
    if not value:
        return 0
    value = value.strip()
    if not value:
        return 0
    try:
        n = int(float(value))
    except ValueError:
        return 0
    # IPEDS uses negative sentinels in a handful of legacy files.
    return n if n > 0 else 0


CIP_RE = re.compile(r"^(\d{2})\.?(\d{0,4})")


def normalise_cip(raw: str) -> tuple[str, str] | None:
    """Return (cipcode, cip2) or None if unparseable.

    ``'99     '``, ``'99'``, ``'99.0000'`` and ``'990000'`` all normalise to
    ``('99', '99')`` -- the institution aggregate.
    """
    raw = (raw or "").strip()
    if not raw:
        return None
    m = CIP_RE.match(raw)
    if not m:
        return None
    fam, rest = m.group(1), m.group(2)
    if fam == "99":
        return "99", "99"
    if "." in raw:
        detail = raw.split(".", 1)[1].strip()
    else:
        detail = raw[2:].strip()
    detail = (detail + "0000")[:4] if detail else "0000"
    return f"{fam}.{detail}", fam


def normalise_awlevel(raw: str) -> str:
    raw = (raw or "").strip().lstrip("0")
    return raw or "0"


# --------------------------------------------------------------------------
# extraction
# --------------------------------------------------------------------------

def extract_counts(row: dict, columns: set[str]) -> dict[str, int]:
    """Pull the canonical measures out of one raw row, merging the legacy and
    modern race schemes correctly.

    * shared measures (total / NRA and their sex splits): take the modern
      column if the file has it, else the legacy column.  Never summed --
      in 2008-2010 both names exist but they are the same quantity.
    * race-breakdown measures: SUM the modern and legacy columns.  They are
      complementary, both within a file and, for the ~2,000 rows per year in
      2008-2010 where both are non-zero, within a single row.
    """
    out: dict[str, int] = {}
    for name, modern, legacy in MEASURES:
        has_modern = modern in columns
        has_legacy = legacy is not None and legacy in columns
        pair = LEGACY_PAIRS.get(name)
        # Fall back to the legacy men/women pair only when the legacy total
        # column is absent from this file entirely (1996-2001).
        use_pair = (
            not has_legacy
            and pair is not None
            and pair[0] in columns
            and pair[1] in columns
        )
        if name in SHARED_MEASURES:
            if has_modern:
                out[name] = to_int(row.get(modern))
            elif has_legacy:
                out[name] = to_int(row.get(legacy))
            elif use_pair:
                out[name] = to_int(row.get(pair[0])) + to_int(row.get(pair[1]))
            else:
                out[name] = 0
        else:
            total = 0
            if has_modern:
                total += to_int(row.get(modern))
            if has_legacy:
                total += to_int(row.get(legacy))
            elif use_pair:
                total += to_int(row.get(pair[0])) + to_int(row.get(pair[1]))
            out[name] = total
    return out


def share(nra: int, total: int) -> str:
    return f"{nra / total:.6f}" if total > 0 else ""


def build(outdir: Path, years: list[int] | None = None) -> dict:
    outdir.mkdir(parents=True, exist_ok=True)
    files = discover_files()
    if years:
        files = {y: p for y, p in files.items() if y in years}

    stats = {
        "years": [],
        "rows_cip": 0,
        "rows_cip2": 0,
        "rows_inst": 0,
        "per_year": {},
        "recon": [],
        "dropped_awlevel_rows": 0,
    }

    cip_path = outdir / "doctoral_nra_by_cip.csv.gz"
    cip2_path = outdir / "doctoral_nra_by_cip2.csv.gz"
    inst_path = outdir / "doctoral_inst_totals.csv.gz"

    with gzip.open(cip_path, "wt", newline="", compresslevel=9) as fcip, \
         gzip.open(cip2_path, "wt", newline="", compresslevel=9) as fcip2, \
         gzip.open(inst_path, "wt", newline="", compresslevel=9) as finst:

        w_cip = csv.writer(fcip)
        w_cip2 = csv.writer(fcip2)
        w_inst = csv.writer(finst)
        w_cip.writerow(OUT_COLS)
        w_cip2.writerow(OUT_COLS_CIP2)
        w_inst.writerow(OUT_COLS_INST)

        for year, path in files.items():
            log.info("reading %s (year %d)", path.name, year)
            cip2_acc: dict[tuple, dict[str, int]] = defaultdict(lambda: defaultdict(int))
            # for reconciliation: summed real-CIP rows vs the CIPCODE 99 row
            sum_real: dict[tuple, dict[str, int]] = defaultdict(lambda: defaultdict(int))
            inst_rows: dict[tuple, dict[str, int]] = {}
            n_cip = 0
            n_zero = 0
            columns: set[str] = set()

            for row in read_rows(path):
                if not columns:
                    columns = set(row.keys())
                aw = normalise_awlevel(row.get("AWLEVEL", ""))
                if aw not in DOCTORAL_AWLEVELS:
                    continue
                cip = normalise_cip(row.get("CIPCODE", ""))
                if cip is None:
                    continue
                cipcode, cip2 = cip
                unitid = (row.get("UNITID") or "").strip()
                if not unitid:
                    continue
                majornum = (row.get("MAJORNUM") or "1").strip() or "1"
                counts = extract_counts(row, columns)

                key = (unitid, aw, majornum)
                if cipcode == "99":
                    tgt = inst_rows.setdefault(key, defaultdict(int))
                    for k, v in counts.items():
                        tgt[k] += v
                    continue

                # All-zero rows carry no information and are not uniformly
                # reported: the 1998 file emits explicit zero doctoral rows for
                # ~3,000 institutions that award no doctorates, while 1997 and
                # 1999 do not.  Dropping them keeps the output compact and the
                # institution counts comparable across years.  Reconciliation
                # below still accumulates them, so the CIP-99 check is unaffected.
                if counts["total"] > 0:
                    w_cip.writerow(
                        [unitid, year, aw, cipcode, majornum]
                        + [counts[c] for c in COUNT_COLS]
                        + [share(counts["nra"], counts["total"])]
                    )
                    n_cip += 1
                else:
                    n_zero += 1
                acc = cip2_acc[(unitid, aw, cip2, majornum)]
                sr = sum_real[key]
                for k, v in counts.items():
                    acc[k] += v
                    sr[k] += v

            for (unitid, aw, cip2, majornum), acc in sorted(cip2_acc.items()):
                if acc["total"] <= 0:
                    continue
                w_cip2.writerow(
                    [unitid, year, aw, cip2, majornum]
                    + [acc[c] for c in COUNT_COLS]
                    + [share(acc["nra"], acc["total"])]
                )
            for (unitid, aw, majornum), acc in sorted(inst_rows.items()):
                if acc["total"] <= 0:
                    continue
                w_inst.writerow(
                    [unitid, year, aw, majornum]
                    + [acc[c] for c in COUNT_COLS]
                    + [share(acc["nra"], acc["total"])]
                )

            # -- reconciliation against the CIPCODE 99 aggregate --------------
            keys = set(sum_real) | set(inst_rows)
            mismatch_total = mismatch_nra = 0
            worst = None
            missing99 = 0
            for key in keys:
                real = sum_real.get(key)
                agg = inst_rows.get(key)
                if agg is None:
                    missing99 += 1
                    continue
                rt = real["total"] if real else 0
                rn = real["nra"] if real else 0
                if rt != agg["total"]:
                    mismatch_total += 1
                    d = abs(rt - agg["total"])
                    if worst is None or d > worst[0]:
                        worst = (d, key, rt, agg["total"])
                if rn != agg["nra"]:
                    mismatch_nra += 1

            stats["years"].append(year)
            stats["rows_cip"] += n_cip
            stats["zero_rows_dropped"] = stats.get("zero_rows_dropped", 0) + n_zero
            stats["rows_cip2"] += sum(1 for a in cip2_acc.values() if a["total"] > 0)
            stats["rows_inst"] += sum(1 for a in inst_rows.values() if a["total"] > 0)
            stats["per_year"][year] = {
                "file": path.name,
                "cip_rows": n_cip,
                "cip2_rows": sum(1 for a in cip2_acc.values() if a["total"] > 0),
                "inst_rows": sum(1 for a in inst_rows.values() if a["total"] > 0),
                "zero_rows_dropped": n_zero,
            }
            stats["recon"].append({
                "year": year,
                "keys": len(keys),
                "no_99_row": missing99,
                "total_mismatch": mismatch_total,
                "nra_mismatch": mismatch_nra,
                "worst": worst,
            })

    write_metadata(outdir, files, stats)
    return stats


def write_metadata(outdir: Path, files: dict[int, Path], stats: dict) -> None:
    yrs = sorted(files)
    lines = [
        "# IPEDS doctoral non-resident-alien (NRA) ground truth",
        "",
        f"Built by `scripts/build_ipeds_nra_ground_truth.py`. Rebuild with:",
        "",
        "    python3 scripts/build_ipeds_nra_ground_truth.py --validate",
        "",
        "## Source",
        "",
        "IPEDS Completions survey, component A (awards by CIP x award level x",
        "race/ethnicity x sex), files `data/ipeds/c{year}_a.csv`. The revised",
        "(`_rv`) release is preferred where it exists.",
        "",
        f"Data years: {yrs[0]}-{yrs[-1]} ({len(yrs)} files).",
        "Year = the end of the academic year in which the award was conferred",
        "(the IPEDS collection year), so 1996 means 1995-96 and 2025 is the",
        "provisional 2024-25 release.",
        "",
        "## Files",
        "",
        "| file | grain | rows |",
        "| --- | --- | --- |",
        f"| `doctoral_nra_by_cip.csv.gz` | unitid x year x awlevel x cipcode x majornum | {stats['rows_cip']:,} |",
        f"| `doctoral_nra_by_cip2.csv.gz` | unitid x year x awlevel x 2-digit CIP family x majornum | {stats['rows_cip2']:,} |",
        f"| `doctoral_inst_totals.csv.gz` | unitid x year x awlevel x majornum (IPEDS CIPCODE=99 aggregate) | {stats['rows_inst']:,} |",
        "",
        "Measure columns (all integer counts): " + ", ".join(COUNT_COLS) + ".",
        "`nra_share` = nra / total, blank when total is 0.",
        "",
        "## Exclusions applied",
        "",
        "* **CIPCODE 99 is removed from the per-subject files** and written to",
        "  `doctoral_inst_totals.csv.gz` instead. It is the institution-level",
        "  aggregate; summing it alongside real CIP rows double-counts.",
        "* **Award levels**: only doctoral levels are kept -- 17, 18, 19 in the",
        "  modern scheme and 9, 10 in the pre-2010 scheme. AWLEVEL is a column",
        "  and the levels are never merged. Legacy 11 (post-first-professional",
        "  certificate) is excluded as not a doctorate.",
        "* **1984-1994** (`c{year}_cip.csv`) are excluded entirely: those files",
        "  carry only CRACE15/CRACE16 (total men / total women) and have no",
        "  citizenship breakdown, so no NRA measure exists for them.",
        "* Negative sentinel values are floored to 0.",
        "* `MAJORNUM` is preserved rather than filtered. 1 = first major,",
        "  2 = second major. Filter to `majornum == 1` for a degree count.",
        "  Measured: second-major doctoral awards are 0.00-0.14% of first-major",
        "  totals over 1996-2025, so the choice barely moves any share.",
        "* Rows whose `total` is 0 are dropped. They carry no information and",
        "  are not reported uniformly: the 1998 file emits explicit zero",
        "  doctoral rows for ~3,000 institutions that award no doctorates,",
        f"  which 1997 and 1999 do not. {stats.get('zero_rows_dropped', 0):,} such rows were dropped.",
        "",
        "## Race-scheme handling (the 2008-2010 transition)",
        "",
        "IPEDS replaced the legacy `CRACE01`-`CRACE24` columns with named",
        "columns (`CNRALT`, `CASIAT`, `CWHITT`, ...). Institutions converted",
        "individually, so the 2008, 2009 and 2010 files contain BOTH schemes.",
        "",
        "* Race-breakdown measures (asian, white, black, hispanic, aian, nhpi,",
        "  two_or_more, unknown) are **summed** across the two schemes. They",
        "  are complementary, not redundant. Verified: for every row of the",
        "  2008, 2009 and 2010 files, legacy race totals + modern race totals",
        "  + CNRALT + CUNKNT == CTOTALT exactly (0 exceptions), including the",
        "  ~2,000 rows a year where both schemes are non-zero on the same row.",
        "* Total and NRA measures are **not** summed. Legacy `CRACE24` was",
        "  renamed `CTOTALT` and legacy `CRACE17` was renamed `CNRALT`; in",
        "  2008-2010 only the new names appear and they are populated for",
        "  100% of rows under either scheme. Verified on c2002:",
        "  `CRACE17 == CRACE01 + CRACE02` and `CRACE24 == CRACE15 + CRACE16`",
        "  for all 200,336 rows.",
        "* Consequence: `nra_share` is unaffected by the race-scheme",
        "  transition. Only the domestic race breakdown was ever at risk.",
        "* `nhpi` and `two_or_more` do not exist before 2011 and are 0 for",
        "  legacy-scheme rows; do not read that as a real trend.",
        "",
        "## Award-level scheme transition",
        "",
        "The 2008 and 2009 files also contain both AWLEVEL schemes. Verified:",
        "no institution reports under both in the same year (0 overlap of",
        "{9,10,11} with {17,18,19} in 2008 and 2009), so the two are",
        "complementary at institution level. AWLEVEL 17 series counts are",
        "therefore severely undercounted in 2008-2009 and absent before 2008.",
        "For any series spanning 2010, filter on AWLEVEL 17 only from 2010",
        "onward and treat 2008-2009 AWLEVEL 17 as partial coverage.",
        "",
        "## Known source problems",
        "",
        "* The first header cell has a UTF-8 BOM in the 2023-2025 files; the",
        "  LAST header cell has a trailing space in 2002-2007 (`'CRACE24 '`).",
        "* `CIPCODE` is space padded in several years (`'99     '`).",
        "* Data year 2025 is provisional (no `_rv` release yet).",
        "* 1990 and 1995 have no completions file on disk.",
        "* The 1998 file (`c9798_a.csv`) lists 3,841 institutions with doctoral",
        "  rows against 787 that actually award a doctorate; the surplus are",
        "  all-zero placeholder rows unique to that year.",
        "* Nine (unitid, awlevel) keys across 1996-1998 have real CIP rows but",
        "  no CIPCODE 99 row. All nine carry zero completions, so the",
        "  reconciliation is exact for every key with any awards.",
        "* AWLEVEL 17 is NOT the NSF Survey of Earned Doctorates universe. It",
        "  is broader (82,438 in 2023 vs ~57,900 SED research doctorates),",
        "  because IPEDS classifies EdD/DBA/PsyD-type degrees under 17 at many",
        "  institutions. Do not cross-cite the two without reconciling first.",
    ]
    (outdir / "_metadata.md").write_text("\n".join(lines) + "\n")


# --------------------------------------------------------------------------
# validation
# --------------------------------------------------------------------------

SANITY_FAMILIES = STEM_NARROW   # single source: pipeline/models.py.
# Seven scripts each carried their own copy of this set. They all happened
# to agree, which is exactly why the drift would have been silent: change
# models.py and the copies keep the old definition without a word.
SANITY_CASES = [
    # unitid, label, first year, last year (inclusive), expected pct, tolerance
    ("126775", "Colorado School of Mines", 2015, 2023, 39.8, 0.1),
    ("196079", "Binghamton (SUNY)", 2015, 2022, 56.9, 0.1),
]


def _load_cip2(path: Path):
    with gzip.open(path, "rt", newline="") as fh:
        for row in csv.DictReader(fh):
            yield row


def validate(outdir: Path, stats: dict | None = None) -> list[str]:
    report: list[str] = []
    cip2_path = outdir / "doctoral_nra_by_cip2.csv.gz"

    want = {c[0] for c in SANITY_CASES}
    sanity = defaultdict(lambda: [0, 0])
    by_aw = defaultdict(lambda: defaultdict(lambda: [0, 0]))     # year -> aw -> [total, nra]
    insts = defaultdict(lambda: defaultdict(set))                # year -> aw -> unitids
    race_cov = defaultdict(lambda: defaultdict(int))             # year -> measure -> count
    second_major = defaultdict(lambda: [0, 0])                   # year -> [mn1, mn2]

    for row in _load_cip2(cip2_path):
        y, aw = int(row["year"]), row["awlevel"]
        t, n = int(row["total"]), int(row["nra"])
        second_major[y][0 if row["majornum"] == "1" else 1] += t
        if row["majornum"] != "1":
            continue
        by_aw[y][aw][0] += t
        by_aw[y][aw][1] += n
        insts[y][aw].add(row["unitid"])
        for c in ("nhpi", "two_or_more", "unknown", "asian", "white"):
            race_cov[y][c] += int(row[c])
        if row["unitid"] in want and aw == "17" and row["cip2"] in SANITY_FAMILIES:
            for uid, _lbl, y0, y1, _e, _tol in SANITY_CASES:
                if row["unitid"] == uid and y0 <= y <= y1:
                    sanity[uid][0] += t
                    sanity[uid][1] += n

    years = sorted(by_aw)

    # --- 1. sanity checks -------------------------------------------------
    report.append("## 1. Sanity checks (AWLEVEL 17, CIP families "
                  + ",".join(sorted(SANITY_FAMILIES)) + ", majornum 1)")
    report.append("")
    ok_all = True
    for uid, label, y0, y1, expected, tol in SANITY_CASES:
        total, nra = sanity[uid]
        pct = 100 * nra / total if total else 0.0
        ok = abs(pct - expected) <= tol
        ok_all &= ok
        report.append(
            f"* {label} ({uid}) {y0}-{y1}: {nra:,}/{total:,} = {pct:.2f}% "
            f"(expected ~{expected}%) -- {'PASS' if ok else 'FAIL'}"
        )
    report.append("")

    # --- 2. reconciliation against CIPCODE 99 -----------------------------
    if stats:
        report.append("## 2. Reconciliation vs the CIPCODE 99 institution aggregate")
        report.append("")
        report.append("Sum of all real-CIP doctoral rows per (unitid, awlevel, majornum)")
        report.append("compared with that institution's CIPCODE 99 row.")
        report.append("")
        report.append("| year | keys | no 99 row | total mismatch | nra mismatch |")
        report.append("| --- | --- | --- | --- | --- |")
        bad = 0
        for r in stats["recon"]:
            bad += r["total_mismatch"] + r["nra_mismatch"]
            report.append(
                f"| {r['year']} | {r['keys']:,} | {r['no_99_row']:,} | "
                f"{r['total_mismatch']:,} | {r['nra_mismatch']:,} |"
            )
        report.append("")
        report.append(f"Total mismatching keys across all years: {bad}.")
        report.append("")

    # --- 3. national series by award level --------------------------------
    report.append("## 3. National doctoral completions by award level (majornum 1)")
    report.append("")
    report.append("| year | aw9 | aw10 | aw17 | aw18 | aw19 | all doctoral | "
                  "aw17 NRA% | aw9 NRA% | inst w/ aw17 |")
    report.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for y in years:
        row = by_aw[y]
        tot = sum(v[0] for v in row.values())
        a17 = row.get("17", [0, 0])
        a9 = row.get("9", [0, 0])
        report.append(
            f"| {y} | {row.get('9', [0])[0]:,} | {row.get('10', [0])[0]:,} | "
            f"{a17[0]:,} | {row.get('18', [0])[0]:,} | {row.get('19', [0])[0]:,} | "
            f"{tot:,} | "
            f"{(100*a17[1]/a17[0]) if a17[0] else 0:.2f}% | "
            f"{(100*a9[1]/a9[0]) if a9[0] else 0:.2f}% | "
            f"{len(insts[y].get('17', ())):,} |"
        )
    report.append("")

    # --- 4. schema-driven discontinuities ---------------------------------
    report.append("## 4. Discontinuity scan")
    report.append("")

    def flag(series_name, get, threshold=0.15):
        out = []
        prev = None
        for y in years:
            v = get(y)
            if prev is not None and prev[1] > 0 and abs(v - prev[1]) / prev[1] > threshold:
                out.append(f"* {series_name}: {prev[0]} -> {y}: "
                           f"{prev[1]:,} -> {v:,} ({100*(v-prev[1])/prev[1]:+.1f}%)")
            prev = (y, v)
        return out

    all_doc = flag("all doctoral awards",
                   lambda y: sum(v[0] for v in by_aw[y].values()))
    aw17 = flag("AWLEVEL 17 total", lambda y: by_aw[y].get("17", [0, 0])[0])
    report.append("Jumps above 15% year over year:")
    report.append("")
    report += (all_doc or ["* all doctoral awards: none (series is continuous "
                           "across the 2008-2010 award-level transition)"])
    report += (aw17 or ["* AWLEVEL 17 total: none"])
    report.append("")
    report.append("Award-level scheme coverage (institutions reporting each scheme):")
    report.append("")
    report.append("| year | inst using {9,10} | inst using {17,18,19} | overlap |")
    report.append("| --- | --- | --- | --- |")
    for y in years:
        legacy = insts[y].get("9", set()) | insts[y].get("10", set())
        modern = (insts[y].get("17", set()) | insts[y].get("18", set())
                  | insts[y].get("19", set()))
        if not legacy and y > 2010:
            continue
        report.append(f"| {y} | {len(legacy):,} | {len(modern):,} | "
                      f"{len(legacy & modern):,} |")
    report.append("")
    report.append("Race-category columns that are structurally absent, not zero "
                  "(all doctoral levels, majornum 1):")
    report.append("")
    report.append("| year | nhpi | two_or_more | unknown | asian | white |")
    report.append("| --- | --- | --- | --- | --- | --- |")
    for y in years:
        d = race_cov[y]
        report.append(f"| {y} | {d['nhpi']:,} | {d['two_or_more']:,} | "
                      f"{d['unknown']:,} | {d['asian']:,} | {d['white']:,} |")
    report.append("")

    # --- 5. second majors --------------------------------------------------
    report.append("## 5. Second majors (MAJORNUM 2) as a share of doctoral awards")
    report.append("")
    shares = []
    for y in years:
        a, b = second_major[y]
        if a:
            shares.append(100 * b / a)
    if shares:
        report.append(f"Range {min(shares):.2f}% - {max(shares):.2f}% of first-major "
                      f"totals across {years[0]}-{years[-1]}. Filter to "
                      "`majornum == 1` unless second majors are wanted.")
    report.append("")
    report.append(f"**Sanity checks: {'ALL PASS' if ok_all else 'FAILURE'}**")
    return report


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--outdir", default=str(OUTDIR))
    ap.add_argument("--years", type=int, nargs="*", help="restrict to these data years")
    ap.add_argument("--validate", action="store_true", help="run validation after building")
    ap.add_argument("--validate-only", action="store_true", help="validate existing output")
    ap.add_argument("--report", help="write the validation report to this path")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)
    outdir = Path(args.outdir)

    stats = None
    if not args.validate_only:
        stats = build(outdir, args.years)
        log.info("wrote %s rows (cip), %s (cip2), %s (inst totals)",
                 f"{stats['rows_cip']:,}", f"{stats['rows_cip2']:,}",
                 f"{stats['rows_inst']:,}")
        for p in sorted(outdir.iterdir()):
            log.info("  %-32s %8.1f KB", p.name, p.stat().st_size / 1024)

    if args.validate or args.validate_only:
        report = validate(outdir, stats)
        text = "\n".join(report)
        print(text)
        if args.report:
            Path(args.report).write_text(text + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
