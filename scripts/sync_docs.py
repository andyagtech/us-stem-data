#!/usr/bin/env python3
"""Single-source the numbers that appear in prose, so they cannot drift.

THE PROBLEM. Counts get written into documentation by hand and then rot. As of
2026-08-20, before this script existed:

    pipeline/PIPELINE.md  said 101 university configs   (really 105)
    pipeline/PIPELINE.md  said 292 employer mappings    (really 296)
    README.md             said BOTH 101 and 105 in the same file

Nothing was wrong with the data. The prose describing it was wrong, and nothing
checked. Meanwhile the machine-readable layer -- pipeline/datasets.py -- was
clean, because it is used rather than read.

THE FIX is not to check the prose but to generate it. A documented number is
wrapped in a marker:

    The registry holds <!--auto:universities_count-->105<!--/auto--> universities.

`--write` refills every marker from the real files. `--check` exits non-zero if
any is stale, and is wired into scripts/test_site.py. Markers are HTML comments,
so rendered Markdown is unaffected.

This deliberately does NOT try to find undocumented numbers or judge prose. It
guarantees one thing completely: any number inside a marker is current. Numbers
outside a marker are unprotected -- wrap them to protect them.

Usage:
    python3 scripts/sync_docs.py --list           # every fact and its value
    python3 scripts/sync_docs.py --check          # exit 1 if any marker is stale
    python3 scripts/sync_docs.py --write          # refill markers in place
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Files whose markers are managed. Adding a file here is safe: a file with no
# markers is simply left alone.
MANAGED = (
    "README.md",
    # The working rules. Its gate section quoted "873 tests" and "26 checks"
    # against a real 882 and 28 -- numbers a human typed once and nothing
    # checked, which is the exact failure this file exists to prevent.
    "CLAUDE.md",
    "pipeline/PIPELINE.md",
    "data/DATA_DICTIONARY.md",
    "HANDOFF.md",
    # The audit page is prose about the state of the project, which is exactly
    # the kind of document whose numbers rot fastest: by 2026-09-02 it claimed
    # 39 briefing pages, 42 published datasets, 31 knowledge files and 766
    # tests, against 41, 44, 34 and 797.
    "report/audit/audit.html",
    "site/index.html",
    # The footer, which is injected into all 227 pages. Its date was
    # typed once and read "August 2026" in October. The marker is an
    # HTML comment inside an innerHTML string, so it is a comment node
    # in the DOM and invisible to the reader.
    "site/sidebar.js",
    "site/workforce.html",
    "site/medical.html",
    "site/overview.html",
    "site/departments-nonstem.html",
)

#: A marker names either a fact function (universities_count) or, with the
#: "data:" prefix, a field in a built dataset. The character class has to admit
#: the path syntax: dots, a [key=value] selector, and a |format suffix.
MARKER = re.compile(
    r"(<!--auto:([a-z0-9_]+|data:[A-Za-z0-9_]+\.[^>|]+(?:\|[a-z0-9]+)?)-->)"
    r"(.*?)(<!--/auto-->)", re.S)

#: Set on any subprocess this file spawns. Three facts are counted by running
#: the very suites that validate these markers -- check_consistency.py calls
#: sync_docs.py --check, and would be called back by fact_consistency_checks --
#: so without a marker in the environment the two recurse until something times
#: out. The callee sees this and skips its own marker validation, which ends the
#: cycle at one level while still producing the count being asked for.
REENTRY = "SYNC_DOCS_INTERNAL"


def _child_env() -> dict:
    import os
    return {**os.environ, REENTRY: "1"}


def _json(path: str):
    return json.loads((ROOT / path).read_text())


def _catalog():
    sys.path.insert(0, str(ROOT))
    from pipeline.datasets import CATALOG, uncatalogued
    return CATALOG, uncatalogued()


def fact_universities_count() -> str:
    return f"{len(_json('pipeline/universities.json')):,}"


def fact_entity_map_count() -> str:
    return f"{len(_json('pipeline/entity_map.json')):,}"


def fact_dataset_count() -> str:
    return f"{len(_catalog()[0]):,}"


def fact_uncatalogued_scripts() -> str:
    return f"{len(_catalog()[1]):,}"


def fact_script_count() -> str:
    return f"{len(list((ROOT / 'scripts').glob('*.py'))):,}"


def fact_knowledge_files() -> str:
    return f"{len(list((ROOT / 'cloud' / 'chat' / 'knowledge').glob('*.md'))):,}"


def _corpus() -> dict:
    """Record counts straight from the built Parquet exports.

    These are the artefacts the site actually serves, so a number derived here
    cannot drift from what a reader downloads. Counted with duckdb rather than
    loaded, so the 21 MB export is never held in memory.
    """
    import duckdb
    out = {}
    for key, name in (("stem", "stem_records"), ("nonstem", "nonstem_records")):
        f = ROOT / "site" / "data" / "exports" / f"{name}.parquet"
        out[key] = duckdb.sql(f"select count(*) from '{f}'").fetchone()[0] if f.exists() else 0
    return out


def fact_stem_records() -> str:
    return f"{_corpus()['stem']:,}"


def fact_nonstem_records() -> str:
    return f"{_corpus()['nonstem']:,}"


def fact_total_records() -> str:
    c = _corpus()
    return f"{c['stem'] + c['nonstem']:,}"


def fact_record_years() -> str:
    """The year window the corpus is actually built on.

    Reports the MODAL window, not the extremes. A handful of universities have
    their own -- Caltech's scraped alumni source reaches 1966, utk is capped at
    2022 because its dates are bulk deposits -- and quoting the outer bound
    would describe the corpus as something it is not.
    """
    import collections
    sys.path.insert(0, str(ROOT / "scripts"))
    from generate_name_lists import CONFIGS
    windows = collections.Counter(tuple(c["years"]) for c in CONFIGS if c.get("years"))
    (lo, hi), _ = windows.most_common(1)[0]
    return f"{lo}-{hi}"


def fact_config_count() -> str:
    sys.path.insert(0, str(ROOT / "scripts"))
    from generate_name_lists import CONFIGS
    return f"{len(CONFIGS):,}"


def _lca_names() -> list[str]:
    """Filenames in the LCA archive, whether or not it is currently on disk.

    The 4 GB of DOL .xlsx files live in S3 and are pulled only when
    parse_federal is re-run. Deriving these facts from a glob meant that
    deleting the local copy rewrote the documentation to say the project
    covers 0 files across no years -- which is false, and would have been
    committed by running sync_docs.py --write as the failing check advised.
    The manifest records what the archive holds so the documented figures
    stay true regardless of what is on this machine.
    """
    local = sorted(f.name for f in (ROOT / "data" / "h1b" / "lca").glob("*.xlsx"))
    if local:
        return local
    man = ROOT / "data" / "h1b" / "lca_archive_manifest.json"
    if man.exists():
        import json as _json
        return [f["name"] for f in _json.loads(man.read_text()).get("files", [])]
    return []


def fact_lca_files() -> str:
    return f"{len(_lca_names()):,}"


def fact_lca_years() -> str:
    """Fiscal-year span of the LCA archive, from the filenames DOL uses."""
    import re as _re
    yrs = set()
    for name in _lca_names():
        for m in _re.finditer(r"FY_?(\d{2,4})", name, _re.I):
            v = int(m.group(1))
            yrs.add(v if v > 1000 else 2000 + v)
    return f"FY{min(yrs)}-FY{max(yrs)}" if yrs else "none"


def fact_site_checks() -> str:
    """How many assertions scripts/test_site.py makes -- counted by running it."""
    import subprocess
    r = subprocess.run([sys.executable, "scripts/test_site.py", "--offline"],
                       cwd=ROOT, capture_output=True, text=True, timeout=600,
                       env=_child_env())
    m = re.search(r"(\d+)/(\d+) checks pass", r.stdout)
    return m.group(2) if m else "unknown"


def fact_published_datasets() -> str:
    """Datasets the catalogue publishes under /data, which is fewer than it holds.

    The catalogue also covers raw collections and intermediates that are never
    served, so quoting the catalogue size as the number a reader can download
    overstates it.
    """
    import re as _re
    cat, _ = _catalog()
    files = {m.group(1) for d in cat for path in d.produces
             if (m := _re.fullmatch(r"site/data/([a-z0-9_]+\.json)", path))}
    return f"{len(files):,}"


def fact_briefing_pages() -> str:
    """Page fragments in the briefing, which is what the PDF renders one-to-one.

    Counted from the fragments rather than the PDF: if the two disagree a page
    is overflowing, and report/generate.py already fails loudly on that.
    """
    return f"{len(list((ROOT / 'report' / 'pages').glob('[0-9]*.html'))):,}"


def fact_consistency_checks() -> str:
    """How many assertions scripts/check_consistency.py makes -- by running it."""
    import subprocess
    r = subprocess.run([sys.executable, "scripts/check_consistency.py", "--quiet"],
                       cwd=ROOT, capture_output=True, text=True, timeout=600,
                       env=_child_env())
    m = re.search(r"(\d+)/(\d+) consistency checks pass", r.stdout)
    return m.group(2) if m else "unknown"


def fact_test_count() -> str:
    """Tests collected by pytest. Collected, not run: the count is the question."""
    import subprocess
    r = subprocess.run([sys.executable, "-m", "pytest", "tests/", "-q",
                        "--collect-only"], cwd=ROOT, capture_output=True,
                       text=True, timeout=600, env=_child_env())
    m = re.search(r"(\d+) tests? collected", r.stdout)
    return f"{int(m.group(1)):,}" if m else "unknown"


def fact_site_objects() -> str:
    """Files the deploy would upload -- one walk of site/, the same one it makes.

    Counted locally rather than from S3 so the number is derivable without
    credentials, and it matches: the deploy reports the same figure.
    """
    site = ROOT / "site"
    if not site.exists():
        return "unknown"
    n = sum(1 for f in site.rglob("*")
            if f.is_file() and not f.name.startswith(".")
            and not (f.suffix == ".gz" and f.with_suffix("").exists()))
    return f"{n:,}"


def fact_external_datasets() -> str:
    """Catalogued datasets that cite an external source URL."""
    cat, _ = _catalog()
    return f"{sum(1 for d in cat if d.source_url):,}"


def fact_repo_only_datasets() -> str:
    """Catalogued but never published under /data -- built and kept in the repo."""
    cat, _ = _catalog()
    return f"{sum(1 for d in cat if not any(p.startswith('site/data/') for p in d.produces)):,}"


def fact_data_on_disk() -> str:
    """Size of data/, the collected federal corpus, to one decimal place.

    Reported in the unit the audit page uses (GB, 1024-based) and rounded the
    way a person would read it, so the marker does not churn on every megabyte
    that lands in the archive.
    """
    root = ROOT / "data"
    if not root.exists():
        return "unknown"
    total = 0
    for p in root.rglob("*"):
        try:
            if p.is_file() and not p.is_symlink():
                total += p.stat().st_size
        except OSError:
            continue                      # vanished mid-walk; not worth failing
    return f"{total / 1024 ** 3:.1f}\u00a0GB"


def fact_data_last_updated() -> str:
    """The month the published data was last rebuilt.

    THE FOOTER ON EVERY PAGE SAID "August 2026" IN OCTOBER. It was typed
    into sidebar.js once and nothing could move it, which is the exact
    failure this file exists to prevent -- and it was the most-read line on
    the site, because the footer is on all 227 pages. A reader deciding
    whether the figures are current read a date two months old.

    Taken from the newest built dataset rather than from the clock, so it
    describes the DATA and not the deploy. Rebuilding nothing leaves it
    alone; rebuilding anything moves it.
    """
    site_data = ROOT / "site" / "data"
    newest = 0.0
    for f in site_data.glob("*.json"):
        try:
            newest = max(newest, f.stat().st_mtime)
        except OSError:
            continue
    if not newest:
        return "unknown"
    import datetime as _dt
    return _dt.datetime.fromtimestamp(newest).strftime("%B %Y")


def fact_university_pages() -> str:
    """How many institutions a reader can actually open a page for."""
    return f"{len(list((ROOT / 'site' / 'universities').glob('*.html'))):,}"


def _labs() -> dict:
    return _json("data/labs/lab_outliers.json")


def fact_lab_outliers() -> str:
    """Groups on the published list, AFTER the hand overrides drop the ones
    that are not what they look like (a symposium page, a roster too small to
    mean anything). The builder applies the same list, so this cannot drift
    from what the page shows."""
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    from lab_overrides import apply                        # noqa: PLC0415
    return f"{len(apply(list(_labs()['outliers']))):,}"


def fact_lab_institutions() -> str:
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    from lab_overrides import apply                        # noqa: PLC0415
    rows = apply(list(_labs()["outliers"]))
    return f"{len({r.get('institution') for r in rows if r.get('institution')}):,}"


def fact_lab_groups_tested() -> str:
    return f"{_labs()['tested']:,}"


def fact_query_tables() -> str:
    """Tables on /query.html: one per Parquet export actually published."""
    return f"{len(list((ROOT / 'site' / 'data' / 'exports').glob('*.parquet'))):,}"


def fact_opt_growth_since_2014() -> str:
    """How much the OPT population multiplied over a decade.

    A derivation, so it gets a function rather than a data: marker -- the
    marker syntax reads one field and this is a ratio of two.
    """
    s = _json("site/data/opt_national.json")["series"]
    return f"{s['2024']['opt'] / s['2014']['opt']:.1f}&times;"


def _medical():
    return _json("data/medical/medical_dashboard.json")


def fact_medical_graduates_latest() -> str:
    """Most recent year's MD graduates. The series ends in a null -- the year is
    open -- so the last REPORTED value is the one to quote."""
    g = [v for v in _medical()["ten_year_summary"]["graduates"] if v is not None]
    return f"{g[-1]:,}"


def fact_medical_acceptance_rate() -> str:
    """Matriculants as a share of applicants, latest year. A derivation."""
    h = _medical()["history"]
    i = h["years"].index(max(h["years"]))
    return f"{h['matriculants'][i] / h['applicants'][i] * 100:.0f}%"


def fact_medical_enrollment_growth() -> str:
    """Enrolment growth since 1980, the first year of the series."""
    e = _medical()["history"]["enrollment"]
    return f"{(e[-1] / e[0] - 1) * 100:.0f}%"


def fact_medical_j1_top10_total() -> str:
    """Physicians on J-1 from the ten largest source countries.

    Intealth publishes only the top ten, so this is a FLOOR on the total and
    must never be quoted as the whole J-1 physician population -- which is what
    the page did, calling it "~12,000 active foreign physicians"."""
    return f"{sum(v for _, v in _medical()['evsp_j1']['top_countries_2025']):,}"


FACTS = {name[5:]: fn for name, fn in sorted(globals().items())
         if name.startswith("fact_")}



# --- figures read straight out of a built dataset -------------------------
#
# A page figure does not get its own fact function. There are about 185 of them
# across the briefing pages, and 185 hand-written functions would be 185 more
# things that can be wrong -- the same trap as writing a resolver per knowledge
# figure. So a marker may instead name the field:
#
#     <!--auto:data:fica_exposure.rates.employer_side|pct2-->7.65%<!--/auto-->
#     <!--auto:data:graduate_balance.series.2025.masters.nra|n-->132,149<!--/auto-->
#
# The path walks through the same resolver the knowledge pins use, so it gets
# the [key=value] selectors and the dot-safe splitting for free.

sys.path.insert(0, str(ROOT / "cloud" / "chat"))
from knowledge_pins import resolve as _walk                       # noqa: E402


def _fmt(value, spec: str) -> str:
    """Render a number the way prose writes it."""
    if spec in ("pct0", "pct1", "pct2"):
        # A share may be stored as 0.0765 or as 7.65. Only scale the fraction.
        v = float(value) * 100 if abs(float(value)) <= 1 else float(value)
        places = {"pct0": 0, "pct1": 1, "pct2": 2}[spec]
        return f"{v:,.{places}f}%"
    if spec == "x1":
        return f"{float(value):,.1f}&times;"
    if spec in ("d1", "d2"):
        return f"{float(value):,.{int(spec[1])}f}"
    if spec == "usd":
        return f"${round(float(value)):,}"
    if spec == "usdm":
        # Dollars at the scale prose reads them: $69.5m, $1.56bn.
        v = float(value)
        if abs(v) >= 1_000_000_000:
            return f"${v / 1_000_000_000:,.2f}bn"
        if abs(v) >= 1_000_000:
            return f"${v / 1_000_000:,.1f}m"
        return f"${round(v):,}"
    if spec == "raw":
        return str(value)
    # Default: a count with thousands separators.
    return f"{round(float(value)):,}"


def _dataset_path(stem: str) -> str:
    """Where a dataset lives.

    Most are published under site/data, but some are only build outputs --
    medical_dashboard.json sits in data/medical and is inlined into its page
    rather than served. Prefer the published copy when there is one, so a
    marker reads what a reader's browser would get.
    """
    published = ROOT / "site" / "data" / f"{stem}.json"
    if published.exists():
        return f"site/data/{stem}.json"
    for cand in sorted((ROOT / "data").glob(f"**/{stem}.json")):
        return str(cand.relative_to(ROOT))
    return f"site/data/{stem}.json"      # let the caller report the absence


def data_fact(key: str) -> str:
    """Resolve a `data:<dataset>.<path>[|fmt]` marker.

    The path is unescaped first. These markers sit in HTML, so a selector
    naming "Electrical & Computer Eng" has to be written &amp; in the page and
    would otherwise never match the dataset's own "&".
    """
    body = html.unescape(key[len("data:"):])
    path, _, spec = body.partition("|")
    stem, _, rest = path.partition(".")
    payload = _json(_dataset_path(stem))
    value = _walk(payload, rest)
    if isinstance(value, (list, dict)):
        raise ValueError(f"{path} is a {type(value).__name__}, not a figure")
    return _fmt(value, spec or "n")


def resolve(keys: set[str]) -> dict[str, str]:
    out = {}
    for k in sorted(keys):
        if k.startswith("data:"):
            try:
                out[k] = data_fact(k)
            except Exception as exc:                   # noqa: BLE001
                out[k] = f"<error: {type(exc).__name__}: {exc}>"
            continue
        fn = FACTS.get(k)
        if fn is None:
            out[k] = None
            continue
        try:
            out[k] = str(fn())
        except Exception as exc:                       # noqa: BLE001
            out[k] = f"<error: {type(exc).__name__}>"
    return out


def scan() -> dict[Path, list[tuple[str, str]]]:
    """{path: [(key, current_text), ...]} for every managed file."""
    found = {}
    for rel in MANAGED:
        p = ROOT / rel
        if not p.exists():
            continue
        hits = [(m.group(2), m.group(3)) for m in MARKER.finditer(p.read_text())]
        if hits:
            found[p] = hits
    return found


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()
    if not any((args.check, args.write, args.list)):
        args.list = True

    if args.list:
        vals = resolve(set(FACTS))
        print(f"{'fact':<28}value")
        for k, v in vals.items():
            print(f"  {k:<26}{v}")
        used = {k for hits in scan().values() for k, _ in hits}
        unused = sorted(set(FACTS) - used)
        if unused:
            print(f"\n  defined but not referenced in any managed file: "
                  f"{', '.join(unused)}")
        return 0

    found = scan()
    if not found:
        print("No <!--auto:...--> markers in any managed file. Nothing to do.")
        print("Wrap a number to protect it, e.g.:")
        print("    <!--auto:universities_count-->105<!--/auto-->")
        return 0

    wanted = {k for hits in found.values() for k, _ in hits}
    vals = resolve(wanted)

    stale, unknown = [], []
    for path, hits in found.items():
        for key, cur in hits:
            if vals.get(key) is None:
                unknown.append((path, key))
            elif cur != vals[key]:
                stale.append((path, key, cur, vals[key]))

    rel = lambda p: p.relative_to(ROOT)                 # noqa: E731
    for path, key in unknown:
        print(f"  UNKNOWN  {rel(path)}: no fact named '{key}'")
    for path, key, cur, want in stale:
        print(f"  STALE    {rel(path)}: {key} says {cur!r}, should be {want!r}")

    if args.check:
        if stale or unknown:
            print(f"\n{len(stale)} stale, {len(unknown)} unknown. "
                  f"Run: python3 scripts/sync_docs.py --write")
            return 1
        n = sum(len(h) for h in found.values())
        print(f"  all {n} marker(s) across {len(found)} file(s) are current")
        return 0

    if unknown:
        print("\nRefusing to write while a marker names an unknown fact.")
        return 1
    for path, hits in found.items():
        text = path.read_text()
        text = MARKER.sub(lambda m: m.group(1) + vals[m.group(2)] + m.group(4), text)
        path.write_text(text)
    print(f"\n  wrote {len(found)} file(s), {len(stale)} marker(s) updated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
