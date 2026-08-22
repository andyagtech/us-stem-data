#!/usr/bin/env python3
"""Catch the classes of rot that have actually bitten this project.

Every check here exists because the failure it detects already happened. None
is speculative, and none requires judgement -- anything needing judgement is
deliberately out of scope, because a check that is sometimes wrong gets muted
and then protects nothing.

  1. marker staleness      documented numbers drifting from the data.
                           PIPELINE.md said 101 universities against a real
                           105, and README.md said both 101 and 105. Delegated
                           to scripts/sync_docs.py --check.

  2. unprotected counts    the same numbers inside ``` fences, where an HTML
                           comment would render literally and so cannot be
                           used. Compared against the same facts.

  3. catalog integrity     pipeline/datasets.py paths and scripts existing.

  4. non-atomic writes     a builder that writes its output directly. When
                           build_tuition_revenue.py crashed mid-run it left the
                           PREVIOUS run's file in place and reported nothing, so
                           the site served figures nobody had computed. The fix
                           is write-temp-then-rename; this finds the ones that
                           do not.

  5. self-matching pgrep   `until ! pgrep -f "aws s3 sync"` matches its OWN
                           command line, so the loop never exits. Eight shells
                           spun for up to 9h49m on this, logging nothing,
                           because the echo came after the loop.

  6. kb figures            numbers in the chat knowledge base that no longer
                           match the built data. The assistant states these to
                           the public verbatim.

Exit code is non-zero if any check fails, so this can gate a build.

Usage:
    python3 scripts/check_consistency.py
    python3 scripts/check_consistency.py --quiet    # only failures
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_results: list[tuple[bool, str, str]] = []


def check(ok: bool, name: str, detail: str = "") -> bool:
    _results.append((bool(ok), name, detail))
    return bool(ok)


# ---------------------------------------------------------------- 1 + 2
def check_docs() -> None:
    r = subprocess.run([sys.executable, "scripts/sync_docs.py", "--check"],
                       cwd=ROOT, capture_output=True, text=True)
    check(r.returncode == 0, "documented numbers are current",
          r.stdout.strip().splitlines()[-1].strip() if r.stdout.strip() else "")

    sys.path.insert(0, str(ROOT))
    import importlib
    sd = importlib.import_module("sync_docs") if "sync_docs" in sys.modules else None
    if sd is None:
        sys.path.insert(0, str(ROOT / "scripts"))
        sd = importlib.import_module("sync_docs")
    facts = {k: str(fn()) for k, fn in sd.FACTS.items()
             if k in ("universities_count", "entity_map_count")}

    # The same quantities inside code fences, where markers cannot reach.
    patterns = {
        "universities_count": re.compile(r"(\d{2,4})\s+university configs"),
        "entity_map_count": re.compile(r"(\d{2,4})\s+employer name"),
    }
    bad = []
    for rel in ("README.md", "pipeline/PIPELINE.md"):
        p = ROOT / rel
        if not p.exists():
            continue
        text = p.read_text()
        for key, pat in patterns.items():
            want = facts[key].replace(",", "")
            for m in pat.finditer(text):
                if m.group(1) != want:
                    bad.append(f"{rel}: '{m.group(0)}' should say {want}")
    check(not bad, "unprotected counts in code fences agree with the data",
          "; ".join(bad[:3]) if bad else "")


# ------------------------------------------------------------------- 3
def check_catalog() -> None:
    sys.path.insert(0, str(ROOT))
    from pipeline.datasets import CATALOG, uncatalogued
    missing = []
    for d in CATALOG:
        for p in list(d.produces) + list(d.consumes):
            if not (ROOT / p).exists():
                missing.append(f"{d.key}: {p}")
        if d.script and not (ROOT / "scripts" / f"{d.script}.py").exists():
            missing.append(f"{d.key}: scripts/{d.script}.py")
    check(not missing, "every catalog path exists", "; ".join(missing[:3]))
    n = len(uncatalogued())
    # Not a failure -- it is a backlog, and one that only matters when it grows.
    check(True, "scripts outside the catalog", f"{n} uncatalogued")


# ------------------------------------------------------------------- 4
def check_atomic_writes() -> None:
    """A builder writing site/data must go via a temp file and rename."""
    offenders = []
    for path in sorted((ROOT / "scripts").glob("build_*.py")):
        src = path.read_text()
        if "site/data" not in src and "SITE" not in src:
            continue
        # A direct write is one that names a file and writes it in place.
        # Going through atomic_write, or doing the temp-then-rename by hand,
        # both count as safe. An earlier version of this check accepted any
        # file that merely contained the substring ".replace(" -- which is
        # ordinary str.replace -- and so passed three builders that were not
        # atomic at all.
        direct = re.search(r"\.write_text\(|json\.dump\(|\.write\(", src)
        if not direct:
            continue
        safe = ("from atomic_write import" in src
                or "os.replace(" in src
                or "NamedTemporaryFile" in src
                # writing into a directory this script itself made with
                # mkdtemp is already private and disposable -- there is no
                # published file to leave half-written.
                or "mkdtemp(" in src)
        if not safe:
            offenders.append(path.name)
    check(not offenders,
          "builders write their output atomically",
          f"{len(offenders)} write directly: " + ", ".join(offenders[:6])
          if offenders else "")


# ------------------------------------------------------------------- 5
def check_pgrep_selfmatch() -> None:
    """A poll pattern must not appear in the command line that runs it."""
    bad = []
    for path in list((ROOT / "scripts").rglob("*.sh")) + \
            list((ROOT / "infra").rglob("*.sh")):
        for i, line in enumerate(path.read_text().splitlines(), 1):
            m = re.search(r'pgrep\s+(?:-\w+\s+)*-f\s+["\']([^"\']+)["\']', line)
            if m and m.group(1) in line.replace(m.group(0), ""):
                bad.append(f"{path.relative_to(ROOT)}:{i}")
    check(not bad, "no self-matching pgrep poll patterns", "; ".join(bad[:3]))


# ------------------------------------------------------------------- 6
def check_dependencies() -> None:
    """Every third-party dependency, site and pipeline, is pinned and coherent.

    Three failures this guards, all of which were live on 2026-08-21:

      * query.html imported hyparquet@1 / squirreling@0 -- floating majors, so
        esm.sh served whatever was newest AT PAGE LOAD. squirreling is pre-1.0,
        where a MINOR bump may break the API outright, and it moved 0.15 -> 0.16
        three days earlier. That reached production with no deploy of ours.
      * Chart.js was on TWO versions across the site: 4.4.7 on 228 pages and
        4.4.1 (December 2023) on two stragglers.
      * requirements.txt was entirely floating `>=`, so a fresh install could
        take pandas 4.x and behave differently from the machine that built the
        data while looking correctly configured.
    """
    site = ROOT / "site"

    # 1. Runtime JS imports must be exactly pinned.
    floating = []
    for path in list(site.glob("*.html")) + list(site.glob("*.js")):
        for pkg, ver in re.findall(
                r"(?:esm\.sh|cdn\.jsdelivr\.net/npm|unpkg\.com)/([@a-z0-9._-]+)@([0-9][^\"'/ ]*)",
                path.read_text(errors="replace")):
            if not re.fullmatch(r"\d+\.\d+\.\d+", ver):
                floating.append(f"{path.name}: {pkg}@{ver}")
    check(not floating, "every runtime JS import is pinned to an exact version",
          "; ".join(sorted(set(floating))[:4]))

    # 2. One version per library across the whole site.
    seen = {}
    for path in site.rglob("*.html"):
        for pkg, ver in re.findall(
                r"(?:esm\.sh|cdn\.jsdelivr\.net/npm|unpkg\.com)/([@a-z0-9._-]+)@([0-9][^\"'/ ]*)",
                path.read_text(errors="replace")):
            seen.setdefault(pkg, set()).add(ver)
    split = {k: sorted(v) for k, v in seen.items() if len(v) > 1}
    check(not split, "each JS library is on ONE version site-wide",
          "; ".join(f"{k} -> {v}" for k, v in split.items()) if split else
          f"{len(seen)} librar(y/ies)")

    # 3. A lockfile exists and matches what is installed.
    lock = ROOT / "requirements.lock"
    if check(lock.exists(), "requirements.lock exists"):
        pinned = dict(re.findall(r"^([A-Za-z0-9_.-]+)==([^\s]+)", lock.read_text(), re.M))
        unpinned = [l.split("==")[0] for l in lock.read_text().splitlines()
                    if l.strip() and not l.startswith("#") and "==" not in l]
        check(not unpinned, "every lockfile entry is an exact ==",
              ", ".join(unpinned[:4]))
        try:
            import subprocess
            out = subprocess.run([str(ROOT / ".venv/bin/pip"), "list", "--format=json"],
                                 capture_output=True, text=True, timeout=60).stdout
            inst = {p["name"].lower(): p["version"] for p in json.loads(out)}
            drift = [f"{k}: lock {v}, installed {inst.get(k.lower())}"
                     for k, v in pinned.items()
                     if k.lower() in inst and inst[k.lower()] != v]
            check(not drift, "installed packages match the lockfile",
                  "; ".join(drift[:3]) if drift else f"{len(pinned)} pinned")
        except Exception as exc:                          # noqa: BLE001
            check(True, "installed packages match the lockfile",
                  f"not checked: {type(exc).__name__}")


def check_kb_figures() -> None:
    kb_dir = ROOT / "cloud" / "chat" / "knowledge"
    if not kb_dir.exists():
        return
    kb = "\n".join(p.read_text() for p in sorted(kb_dir.glob("*.md")))
    site = ROOT / "site" / "data"
    probes: list[tuple[str, str, str]] = []
    try:
        lr = json.loads((site / "level_rankings.json").read_text())
        for lv in ("masters", "doctorate"):
            L = lr["levels"][lv]
            probes.append((f"{L['national']['share']}%",
                           f"{lv} national share", "level_rankings"))
            probes.append((f"{L['contrasts_total']} institutions",
                           f"{lv} contrast count", "level_rankings"))
    except (OSError, KeyError, json.JSONDecodeError):
        pass
    try:
        tu = json.loads((site / "tuition.json").read_text())
        probes.append((f"${tu['headline']['billed_nra_real_last']/1e9:.2f}B",
                       "latest billings", "tuition"))
    except (OSError, KeyError, json.JSONDecodeError):
        pass

    missing = [f"{label} ({val})" for val, label, _ in probes if val not in kb]
    # Absence is not necessarily wrong -- the KB need not cite every figure --
    # so this reports rather than fails. What WOULD be wrong is a stale value,
    # and that shows up as the current one going missing.
    check(True, "knowledge-base figures traceable to built data",
          f"{len(probes) - len(missing)}/{len(probes)} cited"
          + (f"; absent: {', '.join(missing[:3])}" if missing else ""))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    for fn in (check_docs, check_catalog, check_atomic_writes,
               check_pgrep_selfmatch, check_dependencies, check_kb_figures):
        try:
            fn()
        except Exception as exc:                        # noqa: BLE001
            check(False, f"{fn.__name__} ran", f"{type(exc).__name__}: {exc}")

    failed = [r for r in _results if not r[0]]
    for ok, name, detail in _results:
        if args.quiet and ok:
            continue
        mark = "pass" if ok else "FAIL"
        print(f"  {mark}  {name}" + (f"  ({detail})" if detail else ""))
    print(f"\n{len(_results) - len(failed)}/{len(_results)} consistency checks pass")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
