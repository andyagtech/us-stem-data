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
)

MARKER = re.compile(r"(<!--auto:([a-z0-9_]+)-->)(.*?)(<!--/auto-->)", re.S)

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


FACTS = {name[5:]: fn for name, fn in sorted(globals().items())
         if name.startswith("fact_")}


def resolve(keys: set[str]) -> dict[str, str]:
    out = {}
    for k in sorted(keys):
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
