"""The data catalog: what each derived artifact is, what builds it, what it needs.

WHY THIS EXISTS

`PIPELINE.md` documents the seven formal steps thoroughly, and those steps run
the dissertation corpus from harvest to deploy. But they are only half the
system. The other half -- acquiring federal data and turning it into the derived
artifacts the site and the assistant read -- lives in `scripts/`, where roughly
thirty files are called by nothing. Knowing which to run, in what order, after a
source updates was tribal knowledge. This module writes it down in a form that
can be checked against disk rather than trusted.

WHAT IT IS NOT

It is not a build system and it does not replace the pipeline. It answers three
questions and stops:

    what produces this file?          -> `produces`
    what does that need first?        -> `consumes`
    is it out of date?                -> compare mtimes

DECLARING TRUTHFULLY

Every path here is checked. `python3 -m pipeline datasets` reports any entry
whose declared inputs or outputs are missing, and lists scripts in `scripts/`
that no entry claims -- so the catalog's own coverage is visible instead of
assumed. An entry that lies shows up as a broken entry, not as silence.

Paths are repo-relative. A dataset with no `consumes` is a leaf: its input is a
file downloaded from an agency, and re-running it re-reads whatever is on disk.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Dataset:
    key: str
    script: str                       # module under scripts/, no .py
    produces: tuple[str, ...]
    summary: str
    source: str                       # issuing agency, or "derived"
    consumes: tuple[str, ...] = ()
    cadence: str = "on source update"
    notes: str = ""
    args: str = ""                    # how to invoke, if not bare

    def out_paths(self) -> list[Path]:
        return [ROOT / p for p in self.produces]

    def in_paths(self) -> list[Path]:
        return [ROOT / p for p in self.consumes]

    def missing_outputs(self) -> list[str]:
        return [p for p in self.produces if not (ROOT / p).exists()]

    def missing_inputs(self) -> list[str]:
        return [p for p in self.consumes if not (ROOT / p).exists()]

    def stale(self) -> bool:
        """True when any declared input is newer than the oldest output."""
        outs = [p for p in self.out_paths() if p.exists()]
        ins = [p for p in self.in_paths() if p.exists()]
        if not outs or not ins:
            return False
        return max(p.stat().st_mtime for p in ins) > min(
            p.stat().st_mtime for p in outs)


# ---------------------------------------------------------------------------
# The catalog. Ordered by dependency: an entry may only consume what an earlier
# entry produces.
# ---------------------------------------------------------------------------

CATALOG: tuple[Dataset, ...] = (
    Dataset(
        key="nra_index",
        script="build_nra_index",
        source="NCES IPEDS Completions (C{year}_A.csv)",
        produces=("data/ipeds/nra_index.csv.gz",
                  "data/ipeds/nra_index_meta.json",
                  "data/ipeds/cip_titles.csv"),
        summary=("Non-resident and total research doctorates by year, institution "
                 "and CIP code. The ground truth every headline share derives from."),
        cadence="annually, when IPEDS releases a new completions year",
        notes=("Research doctorates only -- award level 17 from 2010, legacy 9 "
               "before. Master's (level 7) is NOT in this index; scripts that "
               "need it read the raw completions files directly."),
    ),
    Dataset(
        key="nra_shares",
        script="compute_nra_shares",
        source="derived",
        consumes=("data/ipeds/nra_index.csv.gz",),
        produces=("pipeline/universities.json",),
        summary="Each university's headline NRA share, written into the registry.",
        args="--write",
        cadence="after nra_index changes",
        notes=("Pinned basis: CIP families 11,14,15,26,27,30,40,42; years "
               "2015-2022; award level 17. Changing any one changes every "
               "published share. Also rewrites the duplicate `nra` values in "
               "scripts/generate_name_lists.py, which holds its own copy."),
    ),
    Dataset(
        key="f1_series",
        script="build_f1_series",
        source="US Department of State, NIV detail tables",
        consumes=("data/h1b/state_dept/FYs97-24_NIVDetailTable.xlsx",),
        produces=(),                  # prints; --json writes where asked
        summary="F-1 student visa issuance by fiscal year, with China and India.",
        args="--json PATH",
        cadence="annually, when State publishes the new fiscal year",
        notes=("Two silent traps: sheets mix country rows with regional and grand "
               "totals (a naive sum triple-counts), and the column name changes "
               "from 'F-1' to 'F1' at FY2022. FY2015 = 644,233 is pinned as a "
               "verification anchor and the script warns if a change moves it."),
    ),
    Dataset(
        key="federal_support",
        script="build_federal_support_json",
        source="NSF NCSES federal S&E support tables",
        consumes=("data/federal_support/nsf25339-tab017.xlsx",),
        produces=("data/federal_support/federal_support_by_university.json",),
        summary="Federal science and engineering obligations per institution.",
    ),
    Dataset(
        key="workforce",
        script="build_workforce_data",
        source="NSF Survey of Doctorate Recipients",
        produces=("data/nsf_workforce/workforce_dashboard.json",),
        summary="Foreign-born share of the US doctoral workforce, for /workforce.html.",
        notes=("The SDR public-use file has NO state: geography is suppressed for "
               "confidentiality, so nothing here can answer a state-level question."),
    ),
    Dataset(
        key="live_bundle",
        script="build_live_bundle",
        source="derived",
        consumes=("data/ipeds/nra_index.csv.gz",
                  "data/h1b/state_dept/FYs97-24_NIVDetailTable.xlsx"),
        produces=("site/data/live_bundle.json",),
        summary=("Everything the live voice dashboard renders, in one ~9 KB file "
                 "so no chart update touches the network."),
        cadence="after nra_index or f1_series changes",
        notes=("Reads the raw IPEDS completions files directly for master's "
               "(award level 7), which nra_index does not carry."),
    ),
    Dataset(
        key="site_map",
        script="build_site_map",
        source="derived",
        produces=("site/data/chat/site_map.json",),
        summary=("Every page, title, description and anchor, walked from the "
                 "actual HTML so the assistant's page list cannot drift."),
        cadence="after any page is added, renamed or re-sectioned",
    ),
    Dataset(
        key="chat_facts",
        script="build_chat_facts",
        source="derived",
        consumes=("data/ipeds/nra_index.csv.gz",),
        produces=("cloud/chat/chat_data/universities_compact.json",
                  "cloud/chat/chat_data/national_series.json",
                  "cloud/chat/chat_data/nra_index.csv.gz"),
        summary="The data the chat Lambda ships with, in-zip. Nothing fetched at runtime.",
        cadence="before any chat deploy",
    ),
    Dataset(
        key="parquet_exports",
        script="build_parquet_from_site",
        source="derived",
        produces=("site/data/exports/stem_records.parquet",
                  "site/data/exports/nonstem_records.parquet"),
        summary="The whole record corpus as Parquet, for people who would rather compute.",
        cadence="after generate/build_pages",
        notes=("Requires duckdb. build_pages swallows the ImportError and still "
               "reports OK, which is how these silently served an April snapshot "
               "for four months. Check the row counts, not the exit code."),
    ),
    Dataset(
        key="concentration_cases",
        script="build_concentration_cases",
        source="derived",
        consumes=("data/ipeds/nra_index.csv.gz",),
        produces=("site/data/concentration_cases.json",),
        summary=("The 49 institution-and-field cells that are sustainedly "
                 "majority non-resident. Drives the landing-page hero."),
        cadence="after nra_index changes",
        notes=("Thresholds are deliberately conservative -- 80+ doctorates in "
               "the window, 70%+ in at least 6 of 8 years. Loosening them "
               "produces a longer list that is easier to attack. The payload "
               "carries the national context (domestic doctorates +32% against "
               "a total +33%) alongside the cases, so the page cannot show one "
               "without the other."),
    ),
    Dataset(
        key="taxpayer_cost",
        script="build_taxpayer_cost",
        source="derived (NSF NCSES Federal Support Survey + IPEDS)",
        consumes=("data/ipeds/nra_index.csv.gz",
                  "data/federal_support/federal_support_by_university.json"),
        produces=("site/data/taxpayer_cost.json",),
        summary=("Federal obligations per STEM research doctorate, against "
                 "non-resident share. Quantifies the public-investment claim."),
        cadence="after nra_index or federal_support changes",
        notes=("Research DOCTORATES only. Doctoral students are largely funded "
               "on federal grants; master's students mostly pay tuition, so "
               "combining the levels overstates the federal subsidy attached to "
               "master's degrees. The per-doctorate figure is an INTENSITY "
               "RATIO, not a cost of production -- federal obligations buy "
               "research, not degrees, and a campus with a national lab ranks "
               "high for unrelated reasons."),
    ),
    Dataset(
        key="long_series",
        script="build_long_series",
        source="derived",
        consumes=("data/ipeds/nra_index.csv.gz",),
        produces=("site/data/long_series.json",),
        summary=("Core-STEM doctorates 1995-2025: totals, non-resident and "
                 "domestic counts, share, and the by-field breakdown."),
        cadence="after nra_index changes",
        notes=("Sums BOTH award-level bases across 2008-09. Institutions "
               "migrated from level 9 to 17 one at a time and each reports "
               "exactly one -- verified zero report both -- so taking a single "
               "basis there drops ~20% of those years and puts a false trough "
               "in the middle of the series. Use models.bases_for(year), never "
               "award_level_basis(), for anything crossing the transition."),
    ),
    Dataset(
        key="og_cards",
        script="build_og_cards",
        source="derived",
        produces=("site/og",),
        summary="237 OpenGraph share cards, one per page and per university.",
        cadence="after any published share changes",
        notes=("Cards must use the NARROW 8-family STEM basis, matching the page "
               "headline. Rendering them on the broad 16-family set makes a card "
               "contradict the page it represents."),
    ),
)

BY_KEY = {d.key: d for d in CATALOG}


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def uncatalogued() -> list[str]:
    """Scripts in scripts/ that no catalog entry claims."""
    claimed = {d.script for d in CATALOG}
    out = []
    scripts_dir = ROOT / "scripts"
    if not scripts_dir.is_dir():
        return out
    for name in sorted(os.listdir(scripts_dir)):
        if not name.endswith(".py") or name.startswith("_"):
            continue
        stem = name[:-3]
        if stem not in claimed:
            out.append(stem)
    return out


def report(verbose: bool = False) -> int:
    """Print catalog status. Returns the number of problems found."""
    problems = 0
    print(f"Data catalog — {len(CATALOG)} datasets\n")
    width = max(len(d.key) for d in CATALOG) + 2

    for d in CATALOG:
        missing_out = d.missing_outputs()
        missing_in = d.missing_inputs()
        if missing_in:
            flag, note = "INPUT MISSING", ", ".join(missing_in)
            problems += 1
        elif missing_out and d.produces:
            flag, note = "NOT BUILT", ", ".join(missing_out)
            problems += 1
        elif d.stale():
            flag, note = "STALE", "input newer than output"
            problems += 1
        elif not d.produces:
            flag, note = "ok", "writes only where told (--json)"
        else:
            flag, note = "ok", ""
        print(f"  {d.key:<{width}}{flag:<15}{note}")
        if verbose:
            print(f"  {'':<{width}}  script:  scripts/{d.script}.py {d.args}".rstrip())
            print(f"  {'':<{width}}  source:  {d.source}")
            print(f"  {'':<{width}}  {d.summary}")
            if d.notes:
                print(f"  {'':<{width}}  NOTE: {d.notes}")
            print()

    extra = uncatalogued()
    print(f"\n{len(extra)} scripts not in the catalog "
          f"({len(CATALOG)} of {len(CATALOG) + len(extra)} catalogued):")
    for name in extra:
        print(f"  scripts/{name}.py")
    print("\nThese are one-off analyses, downloaders and helpers. A script "
          "belongs in the\ncatalog when something published depends on its "
          "output.")
    return problems


def order_for(keys: list[str] | None = None) -> list[Dataset]:
    """Catalog order, filtered. The catalog is declared in dependency order,
    so this is the order to re-run in."""
    if not keys:
        return list(CATALOG)
    want = set(keys)
    # pull in anything a requested dataset consumes
    for d in CATALOG:
        if d.key in want:
            for other in CATALOG:
                if set(other.produces) & set(d.consumes):
                    want.add(other.key)
    return [d for d in CATALOG if d.key in want]
