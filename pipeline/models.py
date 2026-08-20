"""Model contracts: consistent intermediate and final shapes across varying sources.

THE PROBLEM THIS SOLVES

Federal sources change shape, and they do it silently. IPEDS recoded doctorate
award levels in 2010 and renamed its residency columns in 2008. USCIS switched
the H-1B data hub from UTF-8 CSV to UTF-16 tab-separated at FY2024. The State
Department renamed its F-1 column from "F-1" to "F1" at FY2022. Every one of
those produces a plausible wrong answer rather than an error.

Until now each reader carried its own `if year >= 2010` branches, so the same
distinction was re-derived in several places and could drift between them. It
did: two STEM definitions coexisted in this codebase and disagreed by up to 17
points, and 37 of 103 published NRA shares were wrong by more than 5 points.

Here, variance is DECLARED and consistency is CHECKED:

  SOURCE VARIANTS   how a raw file is shaped, per source, per year range.
                    Resolution is a lookup, not a conditional.

  MODEL CONTRACTS   the shape every model must have regardless of which source
                    vintage fed it -- columns, types, grain, and invariants that
                    must hold. Intermediate models normalise; final models are
                    what the site and the assistant read.

  VALIDATION        a produced artifact is checked against its contract, so a
                    source changing shape fails loudly at the boundary instead
                    of silently propagating.

VARIANCE IS SUPPORTED AT THREE GRAINS

  per year          award-level coding, column names, encodings (below)
  per data source   platform and metadata prefix per repository, already
                    declared in scrape_oai_etds.REPOS
  per university    file, year window, department source, type and degree
                    filters, campus filter -- already declared in
                    pipeline/universities.json under `processing`

The first was the missing one. The other two are referenced here so the whole
variance surface is documented in one place.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Source variants -- how a raw file is shaped, by year
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SourceVariant:
    """One vintage of one source. `applies` is an inclusive year range."""
    source: str
    applies: tuple[int, int]
    encoding: str = "utf-8-sig"
    delimiter: str = ","
    columns: dict[str, str] = field(default_factory=dict)   # canonical -> raw
    notes: str = ""

    def covers(self, year: int) -> bool:
        return self.applies[0] <= year <= self.applies[1]


SOURCE_VARIANTS: tuple[SourceVariant, ...] = (
    # --- IPEDS Completions ------------------------------------------------
    SourceVariant(
        source="ipeds_completions", applies=(1984, 2007),
        columns={"unitid": "UNITID", "cipcode": "CIPCODE", "awlevel": "AWLEVEL",
                 "nra_men": "CRACE01", "nra_women": "CRACE02",
                 "total_men": "CRACE15", "total_women": "CRACE16"},
        notes=("Residency arrives as four sex-split race columns; NRA is "
               "CRACE01+02 and the grand total CRACE15+16. CIPCODE is quoted "
               "in the pre-2008 files."),
    ),
    SourceVariant(
        source="ipeds_completions", applies=(2008, 2009),
        columns={"unitid": "UNITID", "cipcode": "CIPCODE", "awlevel": "AWLEVEL",
                 "nra": "CNRALT", "total": "CTOTALT"},
        notes=("TRANSITION YEARS. CNRALT/CTOTALT appear, and AWLEVEL 9 is being "
               "split into 17/18/19 -- but institution by institution, so both "
               "codings are live at once. Summing 9 and 17 in these years "
               "double-counts. Choose one basis per institution per year."),
    ),
    SourceVariant(
        source="ipeds_completions", applies=(2010, 2023),
        columns={"unitid": "UNITID", "cipcode": "CIPCODE", "awlevel": "AWLEVEL",
                 "nra": "CNRALT", "total": "CTOTALT"},
        notes="Award level 17 is the research doctorate; 18 is professional practice.",
    ),
    SourceVariant(
        source="ipeds_completions", applies=(2024, 2100),
        encoding="utf-8-sig",
        columns={"unitid": "UNITID", "cipcode": "CIPCODE", "awlevel": "AWLEVEL",
                 "nra": "CNRALT", "total": "CTOTALT"},
        notes="UTF-8 BOM on UNITID from C2023_A onward; utf-8-sig is required.",
    ),

    # --- USCIS H-1B Employer Data Hub -------------------------------------
    SourceVariant(
        source="uscis_h1b_hub", applies=(2010, 2023),
        encoding="utf-8-sig", delimiter=",",
        columns={"fiscal_year": "Fiscal Year", "employer": "Employer",
                 "initial_approvals": "Initial Approvals"},
        notes="Plain UTF-8 CSV.",
    ),
    SourceVariant(
        source="uscis_h1b_hub", applies=(2024, 2100),
        encoding="utf-16", delimiter="\t",
        columns={"fiscal_year": "Fiscal Year ",
                 "employer": "Employer (Petitioner) Name",
                 "initial_approvals": "New Employment Approval"},
        notes=("UTF-16 little-endian, TAB separated crosstab export, and the "
               "column names changed too. Read as UTF-8 CSV this yields "
               "garbage, not an error. Detect via the byte-order mark."),
    ),

    # --- State Department NIV detail tables --------------------------------
    SourceVariant(
        source="state_niv", applies=(1997, 2021),
        columns={"f1": "F-1"},
        notes=("Hyphenated visa-class headers. Sheets carry country rows, "
               "regional 'Totals for X' rows AND a 'Grand Totals' row; summing "
               "everything triple-counts."),
    ),
    SourceVariant(
        source="state_niv", applies=(2022, 2100),
        columns={"f1": "F1"},
        notes=("Unhyphenated headers, and no 'Grand Totals' row -- the total "
               "must be summed from the regional subtotals instead."),
    ),
)


def variant_for(source: str, year: int) -> SourceVariant:
    """The declared shape of `source` in `year`. Raises if undeclared."""
    for v in SOURCE_VARIANTS:
        if v.source == source and v.covers(year):
            return v
    known = sorted({v.source for v in SOURCE_VARIANTS})
    raise KeyError(f"No declared variant for source {source!r} in {year}. "
                   f"Known sources: {', '.join(known)}. Add a SourceVariant "
                   f"rather than branching inline.")


def award_level_basis(year: int) -> str:
    """The single award-level basis for research doctorates in `year`.

    One basis per year, never both: 2008 and 2009 carry both codings across
    different institutions, so summing them double-counts. This is THE
    definition -- callers must not re-derive it.
    """
    return "aw17" if year >= 2010 else "aw09"


# ---------------------------------------------------------------------------
# Field definitions -- one place, so two models cannot disagree
# ---------------------------------------------------------------------------

#: The narrow 8-family set behind every headline NRA share on the site.
STEM_NARROW = ("11", "14", "15", "26", "27", "30", "40", "42")

#: The broad 16-family set behind the per-university completions chart.
#: Kept because "non-STEM" on this site means the complement of THIS set --
#: the narrow complement would sweep health and agriculture in with the
#: humanities and misdescribe those pages.
STEM_BROAD = ("01", "03", "04", "10", "11", "14", "15", "26", "27", "29",
              "30", "40", "41", "42", "45", "51")

#: The pinned window for headline shares. All three parts matter.
HEADLINE_BASIS = {"cip_families": STEM_NARROW, "years": (2015, 2022),
                  "award_level": 17}

AWARD_LEVELS = {"7": "master's", "17": "research doctorate",
                "18": "professional practice", "9": "doctorate (pre-2010)",
                "5": "bachelor's"}


# ---------------------------------------------------------------------------
# Model contracts
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Invariant:
    name: str
    check: Callable[[Any], bool]
    why: str = ""


@dataclass(frozen=True)
class ModelContract:
    """What a model must look like, whatever source vintage produced it."""
    name: str
    layer: str                         # source | intermediate | final
    produces: str                      # repo-relative path
    grain: tuple[str, ...]             # columns that uniquely identify a row
    columns: tuple[str, ...]
    sources: tuple[str, ...] = ()
    invariants: tuple[Invariant, ...] = ()
    notes: str = ""
    #: False for models keyed by nested dicts rather than a row array, where
    #: "rows" and per-column checks do not apply. live_bundle is one: it is
    #: {level: {cip: {year: [...]}}} because the dashboard indexes into it
    #: directly, and flattening it would cost the responsiveness it exists for.
    row_oriented: bool = True

    def path(self) -> Path:
        return ROOT / self.produces


def _rows_of(obj: Any) -> list:
    """Best-effort row extraction from the shapes our artifacts actually use."""
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        for key in ("cases", "institutions", "rows", "records", "data"):
            if isinstance(obj.get(key), list):
                return obj[key]
    return []



def _index_check(path_or_data, which: str) -> bool:
    """Streaming checks over the gzipped NRA index.

    Reads the whole file once per invariant, which is fine at this size and
    keeps each invariant independently readable. Returns True when the
    artifact is absent so a missing file is reported once, by `validate`,
    rather than as several confusing invariant failures.
    """
    import csv
    import gzip
    from collections import defaultdict

    path = ROOT / "data" / "ipeds" / "nra_index.csv.gz"
    if not path.exists():
        return True

    bases_by_year: dict[int, set] = defaultdict(set)
    tot_by_year: dict[int, list] = defaultdict(lambda: [0, 0])
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            try:
                year = int(row["year"])
                total, nra = int(row["total"]), int(row["nra"])
            except (KeyError, ValueError):
                return False
            if which == "nra_le_total" and nra > total:
                return False
            bases_by_year[year].add(row["basis"])
            slot = tot_by_year[year]
            slot[0] += total
            slot[1] += nra

    if which == "one_basis_per_year":
        # 2008 and 2009 legitimately carry both codings across different
        # institutions; every other year must be single-basis.
        return all(len(b) == 1 for y, b in bases_by_year.items()
                   if y not in (2008, 2009))

    if which == "share_band":
        for year, (total, nra) in tot_by_year.items():
            if total < 1000:
                continue
            share = 100 * nra / total
            if not (15.0 <= share <= 45.0):
                return False
    return True

CONTRACTS: tuple[ModelContract, ...] = (
    ModelContract(
        name="nra_index",
        layer="intermediate",
        produces="data/ipeds/nra_index.csv.gz",
        grain=("year", "unitid", "cipcode", "basis"),
        columns=("year", "unitid", "cipcode", "basis", "total", "nra"),
        sources=("ipeds_completions",),
        invariants=(
            Invariant("nra never exceeds total",
                      lambda d: _index_check(d, "nra_le_total"),
                      "A subset cannot be larger than the set containing it. "
                      "This catches a column mapping that slipped a vintage."),
            Invariant("one award-level basis per year",
                      lambda d: _index_check(d, "one_basis_per_year"),
                      "2008 and 2009 carry both codings across different "
                      "institutions. Two bases live in one year means the "
                      "transition logic broke and totals are double-counted."),
            Invariant("national share stays in a plausible band",
                      lambda d: _index_check(d, "share_band"),
                      "The national NRA share of research doctorates has sat "
                      "between 20% and 40% for decades. Outside that, a join "
                      "or a column mapping is wrong."),
        ),
        notes=("The normalisation point. Every IPEDS vintage above collapses "
               "into this one shape, so downstream models never see a source "
               "variant. Research doctorates only -- master's is award level 7 "
               "and is NOT here."),
    ),
    ModelContract(
        name="concentration_cases",
        layer="final",
        produces="site/data/concentration_cases.json",
        grain=("unitid", "cip2"),
        columns=("unitid", "institution", "cip2", "field", "doctorates",
                 "nra", "share", "years_at_or_above_mark"),
        sources=("nra_index",),
        invariants=(
            Invariant("cohort floor respected",
                      lambda d: all(c["doctorates"] >= d["criteria"]["min_cohort"]
                                    for c in _rows_of(d)),
                      "A high share on a tiny cohort is noise."),
            Invariant("sustained, not a single cohort",
                      lambda d: all(c["years_at_or_above_mark"]
                                    >= d["criteria"]["min_high_years"]
                                    for c in _rows_of(d)),
                      "The claim is 'year after year'; one year cannot qualify."),
            Invariant("share is consistent with its own counts",
                      lambda d: all(abs(c["share"] - 100 * c["nra"] / c["doctorates"]) < 0.15
                                    for c in _rows_of(d) if c["doctorates"]),
                      "A stated share must equal its numerator over denominator."),
            Invariant("count matches the array",
                      lambda d: d.get("count") == len(_rows_of(d)),
                      "The headline number on the page reads this field."),
            Invariant("context ships with the cases",
                      lambda d: "context" in d and "honest_reading" in d,
                      "The page must not be able to show cases without the "
                      "national context that stops them being misread."),
        ),
    ),
    ModelContract(
        name="taxpayer_cost",
        layer="final",
        produces="site/data/taxpayer_cost.json",
        grain=("key",),
        columns=("key", "institution", "federal_obligations", "doctorates",
                 "nra", "share", "federal_per_doctorate"),
        sources=("nra_index", "nsf_federal_support"),
        invariants=(
            Invariant("per-doctorate figure is derivable",
                      lambda d: all(r["federal_per_doctorate"] > 0
                                    for r in _rows_of(d)),
                      "A zero or negative ratio means a bad join."),
            Invariant("doctorate floor respected",
                      lambda d: all(r["doctorates"] >= d["basis"]["min_doctorates"]
                                    for r in _rows_of(d)),
                      "Small denominators make the ratio meaningless."),
            Invariant("caveat ships with the data",
                      lambda d: "caveat" in d and "level_note" in d,
                      "The intensity-ratio caveat and the doctorate-only scope "
                      "must travel with the numbers."),
        ),
    ),
    ModelContract(
        name="live_bundle",
        layer="final",
        produces="site/data/live_bundle.json",
        grain=("level", "cip2", "year"),
        columns=("degrees", "f1", "meta"),
        sources=("ipeds_completions", "state_niv"),
        row_oriented=False,
        invariants=(
            Invariant("both award levels present",
                      lambda d: set(d.get("degrees", {})) >= {"masters", "doctorate"},
                      "The dashboard separates the two funding mechanisms."),
            Invariant("F-1 anchor holds",
                      lambda d: d.get("f1", {}).get("2015", {}).get("total") == 644233,
                      "FY2015 F-1 issuance is 644,233. If this moves, the "
                      "subtotal-row triple-count has returned."),
            Invariant("small enough to stay instant",
                      lambda d: len(json.dumps(d)) < 400_000,
                      "The dashboard's responsiveness depends on shipping the "
                      "whole dataset with the page."),
        ),
    ),
)

BY_NAME = {c.name: c for c in CONTRACTS}


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate(contract: ModelContract) -> list[str]:
    """Return a list of failures. Empty means the model honours its contract."""
    problems: list[str] = []
    data: Any = None
    path = contract.path()
    if not path.exists():
        return [f"missing artifact: {contract.produces}"]

    if path.suffix == ".json":
        try:
            data = json.loads(path.read_text())
        except Exception as e:                       # noqa: BLE001
            return [f"unparseable: {e}"]
        rows = _rows_of(data)
        if contract.row_oriented and not rows and contract.layer == "final":
            problems.append("no rows")
        if not contract.row_oriented:
            # Keyed model: check the declared top-level keys exist instead.
            for col in contract.columns:
                if col not in data:
                    problems.append(f"missing top-level key: {col}")
        for col in (contract.columns if contract.row_oriented else ()):
            if rows and isinstance(rows[0], dict) and col not in rows[0] \
                    and col not in data:
                problems.append(f"missing column: {col}")
        if contract.row_oriented and contract.grain and rows \
                and isinstance(rows[0], dict) \
                and all(g in rows[0] for g in contract.grain):
            keys = [tuple(r[g] for g in contract.grain) for r in rows]
            if len(keys) != len(set(keys)):
                problems.append(f"grain not unique: {contract.grain}")
    # Invariants run for EVERY artifact, not only JSON ones. They lived inside
    # the JSON branch at first, which silently skipped every check on
    # nra_index.csv.gz -- the model the rest of the site derives from. Three
    # deliberate corruptions went undetected before this was caught.
    for inv in contract.invariants:
        try:
            if not inv.check(data if path.suffix == ".json" else path):
                problems.append(f"invariant failed: {inv.name}"
                                + (f" -- {inv.why}" if inv.why else ""))
        except Exception as e:                       # noqa: BLE001
            problems.append(f"invariant errored: {inv.name} ({e})")
    return problems


def validate_all() -> dict[str, list[str]]:
    return {c.name: validate(c) for c in CONTRACTS}


def report() -> int:
    """Print contract status. Returns the number of failing models."""
    print(f"Model contracts — {len(CONTRACTS)} models, "
          f"{len(SOURCE_VARIANTS)} declared source variants\n")

    by_layer: dict[str, list] = {}
    for c in CONTRACTS:
        by_layer.setdefault(c.layer, []).append(c)

    failures = 0
    for layer in ("source", "intermediate", "final"):
        items = by_layer.get(layer, [])
        if not items:
            continue
        print(f"  {layer.upper()}")
        for c in items:
            problems = validate(c)
            if problems:
                failures += 1
            status = "ok" if not problems else f"{len(problems)} PROBLEM(S)"
            print(f"    {c.name:<22}{status}")
            print(f"    {'':<22}grain: {', '.join(c.grain)}")
            if c.sources:
                print(f"    {'':<22}from:  {', '.join(c.sources)}")
            for p_ in problems:
                print(f"    {'':<22}  -> {p_}")
        print()

    print("  SOURCE VARIANTS (year ranges are inclusive)")
    src = sorted({v.source for v in SOURCE_VARIANTS})
    for s in src:
        vs = [v for v in SOURCE_VARIANTS if v.source == s]
        print(f"    {s}")
        for v in sorted(vs, key=lambda x: x.applies):
            hi = "…" if v.applies[1] >= 2100 else str(v.applies[1])
            enc = f"{v.encoding}" + (" TAB" if v.delimiter == "\t" else "")
            print(f"      {v.applies[0]}–{hi:<6} {enc}")
    return failures
