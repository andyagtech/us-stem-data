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
import os
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
    # sync_docs counts some facts by running this script, so when it is the
    # caller, validating its markers here would recurse. Skipping at that one
    # point ends the cycle; the outer sync_docs --check still does the
    # validation, which is the run whose answer anyone wants.
    if os.environ.get("SYNC_DOCS_INTERNAL"):
        check(True, "documented numbers are current",
              "skipped: invoked from sync_docs, which is validating them")
    else:
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
    offloaded = []
    for d in CATALOG:
        # A large source may be archived to S3 and deleted locally. That is
        # allowed, but only when the catalogue says where it went -- otherwise
        # "it is on S3 somewhere" is a thing someone remembers, not a fact the
        # repo records, and the next person to need it has nothing to go on.
        archived = set(d.offloaded())
        for p in list(d.produces) + list(d.consumes):
            if (ROOT / p).exists():
                continue
            if p in archived:
                offloaded.append(f"{d.key}: {p} -> {d.archived_at}")
            else:
                missing.append(f"{d.key}: {p}")
        if d.script and d.script_path() is None:
            missing.append(f"{d.key}: {d.script_rel()}")
    check(not missing, "every catalog path exists", "; ".join(missing[:3]))

    # Anything drawn from outside this repo must say where a reader gets it.
    # A dataset whose source is "derived" is built from other entries and has
    # no external URL; everything else needs one, or the methodology page
    # silently omits it.
    no_url = [d.key for d in CATALOG
              if not d.source_url
              and not d.source.strip().lower().startswith("derived")]
    check(not no_url, "every external dataset cites a source URL",
          ", ".join(sorted(no_url)[:4]))
    if offloaded:
        # Reported, never failed: the whole point is that this is a supported
        # state. It stays visible so nobody is surprised when a step that
        # needs the data has to fetch it first.
        check(True, "archived sources are recorded", "; ".join(offloaded[:3]))
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
            # A check that could not RUN is not a check that PASSED. Reporting
            # green here is the same move as `|| true` in CI: it makes "we did
            # not look" indistinguishable from "we looked and it was fine".
            check(False, "installed packages match the lockfile",
                  f"could not verify: {type(exc).__name__}: {exc}")


def check_single_source_rules() -> None:
    """The analytical constants live in ONE place.

    Seven scripts each carried their own copy of the core-STEM CIP set. They
    all happened to agree, which is precisely what made the risk invisible:
    change pipeline/models.py and the copies keep the old definition without a
    word. The project already has a documented case of two STEM definitions
    coexisting and disagreeing by up to 17 points.

    Same for the award-level rule. build_concentration_cases.py still carries
    `return "aw17" if year >= 2010 else "aw09"` with no delegation and no guard
    -- correct today only because its callers filter to 2015-2022, and silently
    wrong the moment it is reused across the 2008-09 transition.
    """
    import sys as _s
    _s.path.insert(0, str(ROOT))
    from pipeline.models import STEM_NARROW as _canon
    CANON_STEM = set(_canon)
    offenders = []
    for path in sorted((ROOT / "scripts").glob("*.py")):
        src = path.read_text(errors="replace")
        if path.name in ("check_consistency.py", "test_site.py"):
            continue                      # this file, and the deliberate copy
        for m in re.finditer(r'^([A-Z_0-9]+)\s*=\s*(\{[^}]*"11"[^}]*\})',
                             src, re.M | re.S):
            fams = set(re.findall(r'"(\d{2})"', m.group(2)))
            # Only a set that IS the narrow eight is a duplicate. The full
            # 51-family CIP taxonomy in build_nra_index.py is a different
            # thing and must not be flagged.
            if fams != CANON_STEM:
                continue
            # A labelled dict (code -> display name) legitimately holds more
            # than the codes; it passes if it asserts its keys against the
            # canonical set instead of restating them.
            asserts = ("STEM_NARROW" in src and
                       re.search(r'set\(' + m.group(1) + r'\)\s*==', src))
            if not asserts and "from pipeline.models import" not in src:
                offenders.append(f"{path.name}: {m.group(1)}")
    check(not offenders, "the STEM CIP set is defined in exactly one place",
          "; ".join(offenders[:4]))

    stray = []
    for path in sorted((ROOT / "scripts").glob("*.py")):
        src = path.read_text(errors="replace")
        if re.search(r'return\s+"aw17"\s+if\s+year\s*>=\s*2010', src):
            # A fallback inside try/except that delegates first is acceptable.
            if "from pipeline.models import" not in src:
                stray.append(path.name)
    check(not stray, "no undelegated copy of the award-level rule",
          ", ".join(stray))


def check_steps_can_fail() -> None:
    """Every pipeline step must be able to report failure.

    PipelineState.with_outcome auto-halts on success=False, and every step
    opens with `if state.should_halt(): return state`. That is a working
    two-track railway -- but only for steps that can actually switch onto the
    failure track. A step that always returns ok() reads the track and can
    never signal onto it, so a failure inside it is invisible and everything
    downstream proceeds on bad data.

    This is an AST check rather than a grep because grepping got it wrong twice
    on 2026-08-22: `grep success=False` missed both computed conditions
    (`success=len(errors) == 0`) and the StepOutcome.err() constructor, and
    produced a confident, wrong claim that six of eight steps could not fail.
    Two of the resulting "fixes" were unnecessary. Parse the tree instead.

    Known non-step: step2b_ai_classify.py exposes no step function and is
    absent from the registry in pipeline/__main__.py. It is a standalone CLI
    that the `step2b_` prefix misleadingly dresses as part of the flow.
    """
    import ast
    NON_STEPS = {"step2b_ai_classify"}
    cannot = []
    for f in sorted((ROOT / "pipeline").glob("step*.py")):
        if f.stem in NON_STEPS:
            continue
        kinds = set()
        for n in ast.walk(ast.parse(f.read_text())):
            if not isinstance(n, ast.Call):
                continue
            fn = ast.unparse(n.func)
            if "StepOutcome" not in fn:
                continue
            if fn.endswith(".ok"):
                kinds.add("ok")
            elif fn.endswith(".err"):
                kinds.add("err")
            else:
                kw = {k.arg: ast.unparse(k.value) for k in n.keywords}
                kinds.add("success=" + kw.get("success", "?"))
        can_fail = any(
            k == "err" or (k.startswith("success=")
                           and k not in ("success=True", "success=?"))
            for k in kinds)
        if not can_fail:
            cannot.append(f"{f.stem} ({sorted(kinds) or 'no outcome'})")
    check(not cannot, "every pipeline step can report failure",
          "; ".join(cannot))


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


def check_published_datasets_are_listed() -> None:
    """The data sources page must name every dataset the catalogue publishes.

    site/data_sources.html kept that list by hand and had drifted to naming 34
    of 44 -- the level rankings, graduate support, stay rates, earnings and the
    per-institution profiles were all absent. Nothing looked wrong, because a
    missing entry in a list of forty is invisible. The list is now generated by
    scripts/build_derived_datasets_list.py between markers; this fails the build
    when the page is stale rather than waiting for someone to notice.
    """
    import re as _re
    page = ROOT / "site" / "data_sources.html"
    if not page.exists():
        return                       # site/ is a symlink and may be absent
    sys.path.insert(0, str(ROOT))
    from pipeline.datasets import CATALOG as _cat
    src = page.read_text(errors="replace")
    start, end = "<!-- derived:start -->", "<!-- derived:end -->"
    if start not in src or end not in src:
        check(False, "the data sources page lists every published dataset",
              "generator markers missing; run build_derived_datasets_list.py")
        return
    block = src.split(start, 1)[1].split(end, 1)[0]
    listed = set(_re.findall(r"/data/([a-z0-9_]+\.json)", block))
    want = {m.group(1) for d in _cat for p in d.produces
            if (m := _re.fullmatch(r"site/data/([a-z0-9_]+\.json)", p))}
    missing = sorted(want - listed)
    check(not missing, "the data sources page lists every published dataset",
          f"{len(listed)} listed" if not missing else
          f"absent: {', '.join(missing[:4])}"
          f"{f' and {len(missing) - 4} more' if len(missing) > 4 else ''}"
          " -- run scripts/build_derived_datasets_list.py")


def check_no_self_referencing_tokens() -> None:
    """No CSS custom property may be defined in terms of itself.

    `--bg: var(--bg)` is a dependency cycle; the browser discards it and
    `background: var(--bg)` falls through to transparent. A one-off colour
    pass on 2026-08-28 wrote 482 of these across 237 pages, and dark mode
    rendered near-white text on a white page for two weeks, because light mode
    kept working by the accident of a more specific selector and nobody looked
    at the dark one. scripts/fix_self_referencing_tokens.py restores them.
    """
    import re as _re
    site = ROOT / "site"
    if not site.exists():
        return
    pat = _re.compile(r"--([a-z0-9-]+)\s*:\s*var\(--\1\)")
    bad = []
    for p in site.rglob("*"):
        if p.suffix in (".html", ".css", ".js") and p.is_file():
            if pat.search(p.read_text(errors="replace")):
                bad.append(p.relative_to(site).as_posix())
    check(not bad, "no CSS custom property references itself",
          f"{len(bad)} file(s), e.g. {', '.join(sorted(bad)[:3])} -- run "
          "scripts/fix_self_referencing_tokens.py" if bad else "")


def check_hosted_briefing_is_current() -> None:
    """The hosted PDFs must hold as many pages as the briefing has fragments.

    site/briefing.pdf is a copy, so it goes stale the moment a page is added,
    removed or rewritten without re-running report/generate.py and
    scripts/publish_briefing.py. Page count is the cheapest signal that the
    copy is behind; it also catches a dark rendering that paginated differently
    from the light one, which is how a 42-page dark PDF was caught.
    """
    site = ROOT / "site"
    pages = ROOT / "report" / "pages"
    if not site.exists() or not pages.exists():
        return
    fragments = len(list(pages.glob("[0-9]*.html")))
    for name in ("briefing.pdf", "briefing-reader.pdf"):
        pdf = site / name
        if not pdf.exists():
            check(False, f"{name} is hosted",
                  "run report/generate.py then scripts/publish_briefing.py")
            continue
        raw = pdf.read_bytes()
        n = raw.count(b"/Type /Page") - raw.count(b"/Type /Pages")
        check(n == fragments, f"hosted {name} matches the briefing",
              f"{n} pages" if n == fragments else
              f"{n} pages against {fragments} fragments -- re-run "
              "report/generate.py then scripts/publish_briefing.py")


def check_contents_page_lists_every_page() -> None:
    """Every live page must appear in the table of contents.

    Twelve pages were reachable only by typing the URL -- the national
    overview among them -- because nothing linked them. Most are in the
    sidebar now and all are on /contents.html, which is generated from the
    navigation and the site map. This fails if a page exists and neither
    lists it.
    """
    import re as _re
    site = ROOT / "site"
    page = site / "contents.html"
    if not site.exists():
        return
    if not page.exists():
        check(False, "the contents page lists every page",
              "site/contents.html is missing; run scripts/build_contents_page.py")
        return
    listed = set(_re.findall(r'href="(/[a-z0-9_.-]+\.html)"', page.read_text()))
    # Top-level pages only: the university pages are listed from the site map.
    on_disk = {f"/{p.name}" for p in site.glob("*.html")}
    # Not destinations: the redirect stub, and the admin page, which is for
    # the operator and should not be advertised in a public list.
    on_disk -= {"/concentration.html", "/chat-admin.html"}
    missing = sorted(on_disk - listed)
    check(not missing, "the contents page lists every page",
          f"{len(listed)} listed" if not missing else
          f"absent: {', '.join(missing[:4])} -- run scripts/build_contents_page.py")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    for fn in (check_docs, check_catalog, check_atomic_writes,
               check_pgrep_selfmatch, check_dependencies,
               check_single_source_rules, check_steps_can_fail,
               check_kb_figures,
               check_published_datasets_are_listed,
               check_no_self_referencing_tokens,
               check_hosted_briefing_is_current,
               check_contents_page_lists_every_page):
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
