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
    script: str                       # builder under scripts/, no extension
    produces: tuple[str, ...]
    summary: str
    source: str                       # issuing agency, or "derived"
    consumes: tuple[str, ...] = ()
    cadence: str = "on source update"
    notes: str = ""
    args: str = ""                    # how to invoke, if not bare
    archived_at: str = ""             # where the source lives when not on disk

    def offloaded(self) -> tuple[str, ...]:
        """Consumed paths that are archived rather than kept locally.

        Some sources are large, rebuildable and needed only when their step is
        re-run -- the 4 GB of DOL disclosure files behind `lca`, for one. They
        are pushed to S3 and deleted locally, which is fine right up until a
        check that asserts every catalogued path exists starts failing.
        Recording WHERE the data went keeps that check honest: a path may be
        absent only if the catalogue says where to get it back.
        """
        if not self.archived_at:
            return ()
        return tuple(p for p in self.consumes if not (ROOT / p).exists())

    def script_path(self) -> Path | None:
        """Where this entry's builder lives. Most are Python; a few are shell."""
        for ext in (".py", ".sh"):
            cand = ROOT / "scripts" / f"{self.script}{ext}"
            if cand.exists():
                return cand
        return None

    def script_rel(self) -> str:
        """Display path, falling back to .py for an entry pointing at nothing."""
        sp = self.script_path()
        return str(sp.relative_to(ROOT)) if sp else f"scripts/{self.script}.py"

    def out_paths(self) -> list[Path]:
        return [ROOT / p for p in self.produces]

    def in_paths(self) -> list[Path]:
        return [ROOT / p for p in self.consumes]

    def missing_outputs(self) -> list[str]:
        return [p for p in self.produces if not (ROOT / p).exists()]

    def missing_inputs(self) -> list[str]:
        return [p for p in self.consumes if not (ROOT / p).exists()]

    def is_priority(self) -> bool:
        """Refreshing this matters more than the mtime alone suggests."""
        return "HIGHEST-PRIORITY" in (self.notes or "")

    def stale(self) -> bool:
        """True when any declared input is newer than the oldest output.

        A declared input may be a directory -- cloud/chat/knowledge is one --
        in which case the newest file inside it counts. Without that, editing
        a knowledge file would leave the curated answers looking current while
        the assistant had already moved on.
        """
        outs = [p for p in self.out_paths() if p.exists()]
        if not outs:
            return False
        newest_in = 0.0
        for p in self.in_paths():
            if p.is_dir():
                for child in p.rglob("*"):
                    if child.is_file():
                        newest_in = max(newest_in, child.stat().st_mtime)
            elif p.exists():
                newest_in = max(newest_in, p.stat().st_mtime)
        if not newest_in:
            return False
        return newest_in > min(p.stat().st_mtime for p in outs)


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
        key="opt",
        script="parse_opt_reports",
        source="DHS Student and Exchange Visitor Program (SEVP) published reports",
        consumes=("data/sevp/", "data/h1b/"),
        produces=("data/h1b/opt_by_university.json",
                  "data/h1b/opt_national.json",
                  "data/h1b/opt_employers.json"),
        summary=("Optional Practical Training: the national OPT / STEM OPT / CPT "
                 "series 2007-2024, the Top 100 school tables 2017-2024 in both "
                 "flavours, and the 2024 Top 200 employers."),
        cadence="annual, when SEVP publishes",
        notes=("Two DIFFERENT kinds of number live here and must not be mixed. "
               "opt_national.json is a complete national count. The per-school "
               "and per-employer tables are TOP-N RANKINGS: a school missing "
               "from a year placed outside the top 100 that year, it did not "
               "have zero OPT students. Summing schools therefore gives a floor, "
               "not a total, and a school entering or leaving the list between "
               "years may only reflect the cutoff moving. Use the national table "
               "for anything published as a total. `opt` is pre- plus "
               "post-completion OPT; `stem_opt` is the 24-month STEM extension. "
               "In the employer table a student on both programmes is counted "
               "once in total but in both columns, so the columns do not sum."),
    ),
    Dataset(
        key="lca",
        script="aws_lca_rebuild",
        source="US DOL Office of Foreign Labor Certification, LCA disclosure files",
        consumes=("data/h1b/lca/",),
        archived_at="s3://phd-demographics-raw-data/data/h1b/lca/",
        produces=("data/h1b/lca_by_university.json",),
        summary=("H-1B Labor Condition Applications aggregated per university: "
                 "volume, job titles, SOC codes and wage quartiles. Feeds every "
                 "university page."),
        cadence="quarterly, when DOL publishes a new disclosure file",
        notes=("Rows are deduplicated on CASE_NUMBER (LCA_CASE_NUMBER in FY2013). "
               "DOL's quarterly files overlap inconsistently -- some are a single "
               "quarter, some are cumulative to an arbitrary date -- so ADD every "
               "file DOL publishes and NEVER delete one that looks superseded. "
               "Dedup makes a redundant file free; a deleted one may be "
               "unrecoverable. The intermediate csv_cache/ is ~6 GB and derived: "
               "never back it up, delete it whenever space is needed. When it "
               "will not fit locally, scripts/aws_lca_rebuild.sh runs the "
               "pipeline's own aggregation on EC2. The source .xlsx are NOT "
               "kept locally either: they are archived to the prefix in "
               "archived_at and listed in data/h1b/lca_archive_manifest.json. "
               "Restore them before re-running. See data/h1b/LCA_ARCHIVE.md."),
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
        key="level_rankings",
        script="build_level_rankings",
        source="derived",
        consumes=("data/ipeds/",),
        produces=("site/data/level_rankings.json",),
        summary=("Non-resident share rankings at BOTH master's and doctoral "
                 "level: by institution, by 4-digit CIP, fastest risers, "
                 "largest cohorts, and the within-institution contrast."),
        cadence="after a new Completions year lands",
        notes=("Every ranking is a ratio, so every one carries a cohort floor "
               "and publishes how many units cleared it -- a programme with 4 "
               "degrees all to non-residents reads 100% and means nothing. "
               "Floors differ by level because master's cohorts are far larger. "
               "The within-institution contrast is the strongest cut here: it "
               "holds the institution fixed, so it cannot be answered with "
               "'that university is internationally oriented'. The OPT/H-1B "
               "reading of that contrast is a READING and is labelled as one on "
               "the page; IPEDS records awards, not admissions or intent."),
    ),
    Dataset(
        key="tuition",
        script="build_tuition_revenue",
        source="derived",
        consumes=("data/ipeds_tuition/", "data/ipeds_finance/", "data/ipeds/"),
        produces=("site/data/tuition.json",),
        summary=("What the core-STEM master's expansion is worth in tuition: "
                 "published out-of-state graduate rates against non-resident "
                 "master's degrees conferred, with the audited sector total "
                 "alongside, in constant 2024 dollars."),
        cadence="annually, when IPEDS IC and finance files are released",
        notes=("The billings figure is an ESTIMATE and must always be published "
               "as one: a published sticker rate multiplied by a degree count, "
               "not receipts and not net of waivers. It is defensible at "
               "master's level only because NSF GSS 2024 puts master's "
               "assistantship rates at 7.0% RA / 6.9% TA, so ~86% hold neither "
               "and therefore carry no tuition waiver; the same method would be "
               "wrong for undergraduates. Never add it to, or subtract it from, "
               "the F1B01/F2D01 finance series -- that series is net and covers "
               "every level, so the two are different quantities. Inputs come "
               "from BOTH NCES mirrors: complete-data-files lacks IC2014_AY, "
               "datacenter/data lacks the newest year."),
    ),
    Dataset(
        key="university_distribution",
        script="build_university_distribution",
        source="derived",
        consumes=("data/ipeds/nra_index.csv.gz",),
        produces=("site/data/university_distribution.json",),
        summary=("Per-university department distributions: every 4-digit CIP "
                 "programme with 15+ doctorates, 2015-2022, with its share."),
        cadence="after nra_index changes",
        notes=("4-digit grain deliberately. At 2-digit, 'Engineering' at Purdue "
               "collapses sixteen programmes running 30-82% into one bar, which "
               "is the averaging this chart exists to undo. A single headline "
               "share per university misleads: MIT runs 15.8% to 73.2% and the "
               "average describes none of its departments."),
    ),
    Dataset(
        key="distribution",
        script="build_distribution",
        source="derived",
        consumes=("data/ipeds/nra_index.csv.gz",),
        produces=("site/data/distribution.json",),
        summary=("National department histogram by non-resident share, "
                 "2010/2015/2020/2025, at 4-digit CIP."),
        cadence="after nra_index changes",
    ),
    Dataset(
        key="support_by_citizenship",
        script="build_support_by_citizenship",
        source="NSF Survey of Earned Doctorates, Table 4-1",
        produces=("site/data/support_by_citizenship.json",),
        summary=("Primary source of support by citizenship. The allocation "
                 "evidence: 76.0% of international S&E doctorate recipients are "
                 "on assistantships against 53.1% of citizens."),
        cadence="annually, when SED publishes",
        notes=("SED gives citizenship but not whether an assistantship is "
               "federal or institutional; GSS gives the federal split but not "
               "citizenship. The two CANNOT be multiplied - doing so assumes "
               "the federal share is identical for both groups, which nothing "
               "measures."),
    ),
    Dataset(
        key="curated_answers",
        script="curated_answers",
        args="--export cloud/chat/curated_answers.yaml",
        source="derived (the live assistant)",
        consumes=(
            # The answers are only as current as the knowledge the assistant had
            # when they were exported. Any of these moving makes them stale.
            "cloud/chat/knowledge",
            "site/data/concentration_cases.json",
            "site/data/taxpayer_cost.json",
            "site/data/support_by_citizenship.json",
            "site/data/distribution.json",
            "site/data/programme_shares.json",
        ),
        produces=("cloud/chat/curated_answers.yaml",),
        summary=("The assistant's answers to the 31 most-asked questions, "
                 "exported for hand-editing and then seeded into the cache."),
        cadence="after ANY change to the knowledge base or the published data",
        notes=("HIGHEST-PRIORITY REFRESH. These answers are what most visitors "
               "actually read -- they are served from cache, so a stale one is "
               "repeated verbatim to everyone who asks. They go stale silently: "
               "the assistant improves, the data updates, and the cached answer "
               "keeps saying what it said in the old world. `datasets` reports "
               "this as STALE whenever a knowledge file or a published dataset "
               "is newer than the export. Re-export, re-edit the voice, --check, "
               "--seed."),
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
            flag = "STALE (priority)" if d.is_priority() else "STALE"
            note = ("what most visitors actually read; a stale answer is "
                    "repeated verbatim" if d.is_priority()
                    else "input newer than output")
            problems += 1
        elif not d.produces:
            flag, note = "ok", "writes only where told (--json)"
        else:
            flag, note = "ok", ""
        print(f"  {d.key:<{width}}{flag:<15}{note}")
        if verbose:
            print(f"  {'':<{width}}  script:  {d.script_rel()} {d.args}".rstrip())
            print(f"  {'':<{width}}  source:  {d.source}")
            print(f"  {'':<{width}}  {d.summary}")
            if d.notes:
                print(f"  {'':<{width}}  NOTE: {d.notes}")
            print()

    priority_stale = [d for d in CATALOG if d.is_priority() and d.stale()]
    if priority_stale:
        print("  ATTENTION")
        for d in priority_stale:
            print(f"    {d.key} is stale and is high priority: {d.summary}")
            runner = "" if d.script_rel().endswith(".sh") else "python3 "
            print(f"    rebuild: {runner}{d.script_rel()} {d.args}".rstrip())
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
