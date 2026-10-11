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
sys.path.insert(0, str(ROOT / "scripts"))
from private_pages import is_private as _is_private          # noqa: E402

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
    site = ROOT / "site"
    if not site.exists():
        return
    from add_theme_toggle import self_referencing_tokens
    bad = self_referencing_tokens(site)
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
    # Links dropped their extension; the files on disk did not. Compare the
    # two as pages rather than as strings.
    listed = {h[:-5] if h.endswith(".html") else h
              for h in _re.findall(r'href="(/[a-z0-9_.-]+(?:\.html)?)"',
                                   page.read_text())}
    # Top-level pages only: the university pages are listed from the site map.
    on_disk = {f"/{p.stem}" for p in site.glob("*.html")}
    # Not destinations: the redirect stub, and the private pages, which are
    # the owner's and must not be advertised in a public list.
    on_disk -= {"/concentration", "/name_lists"}
    on_disk = {p for p in on_disk if not _is_private(p)}
    missing = sorted(on_disk - listed)
    check(not missing, "the contents page lists every page",
          f"{len(listed)} listed" if not missing else
          f"absent: {', '.join(missing[:4])} -- run scripts/build_contents_page.py")


def check_inlined_dashboards_are_current() -> None:
    """A page that inlines its dataset must inline the CURRENT one.

    medical, workforce, canada and uk write the whole dataset into the page as
    `const D = {...}` instead of fetching it. Nothing ran the inliner, so the
    pages held snapshots: /workforce.html served a topline whose own shares
    disagreed with the dataset, and published "22% naturalized citizens + 7%
    green card holders" where the counts give 20.2% and 7.9%. Link checks and
    page tests all passed throughout, because the page was internally
    consistent with its stale copy.
    """
    import importlib.util as _ilu
    spec = _ilu.spec_from_file_location(
        "_inl", ROOT / "scripts" / "inline_dashboard_data.py")
    if spec is None or spec.loader is None:
        return
    mod = _ilu.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except Exception as exc:                                  # noqa: BLE001
        check(False, "inlined dashboard data is current", f"cannot load inliner: {exc}")
        return

    stale = []
    for json_rel, html_name, var in mod.PAIRS:
        jf = ROOT / json_rel
        hf = ROOT / "site" / html_name
        if not jf.exists() or not hf.exists():
            continue
        want = json.dumps(json.loads(jf.read_text()), separators=(",", ":"))
        m = re.search(rf"const {re.escape(var)} = (\{{.*?\}});", hf.read_text(), re.S)
        if m is None:
            stale.append(f"{html_name}: no `const {var}` block")
            continue
        got = json.dumps(json.loads(m.group(1)), separators=(",", ":"))
        if got != want:
            stale.append(f"{html_name} is behind {json_rel}")
    check(not stale, "inlined dashboard data is current",
          "; ".join(stale) if stale else
          f"{len(mod.PAIRS)} pages match their dataset")


def check_kb_pins_still_match() -> None:
    """Volatile figures must still equal the field they were taken from.

    A HARD check, not a ratchet. The provenance scan is a ratchet because its
    backlog is historical prose nobody has got to yet. A pin is different: it was
    correct the day it was written, so a mismatch means the data moved under it
    and the prose is now wrong. There is no backlog to tolerate.
    """
    import subprocess as _sp
    script = ROOT / "scripts" / "pin_kb_figures.py"
    if not script.exists():
        return
    r = _sp.run([sys.executable, str(script)], capture_output=True, text=True, cwd=ROOT)
    out = [l.strip() for l in (r.stdout or "").splitlines() if l.strip()]
    detail = next((l for l in out if l.startswith(("STALE", "BROKEN"))), None)
    check(r.returncode == 0, "pinned knowledge figures match their source",
          detail or (out[0] if out else "run scripts/pin_kb_figures.py"))


def check_kb_figures_are_traceable() -> None:
    """Figures in the knowledge base must be findable in the data behind them.

    A ratchet rather than a gate: the backlog came to about 45 and comes down
    when someone has time, but new prose may not add to it. See
    scripts/check_kb_provenance.py for why this is separate from
    knowledge_figures.py, which proves a figure is CURRENT rather than that it
    exists at all.
    """
    import subprocess as _sp
    script = ROOT / "scripts" / "check_kb_provenance.py"
    if not script.exists():
        return
    r = _sp.run([sys.executable, str(script)], capture_output=True, text=True, cwd=ROOT)
    tail = [l for l in (r.stdout or "").splitlines() if l.strip()]
    check(r.returncode == 0, "knowledge-base figures trace to a dataset",
          tail[-1].strip() if tail else "run scripts/check_kb_provenance.py")


def check_the_links_file_is_current() -> None:
    """LINKS.md is what gets sent to people, so it must match the live nav.

    It is generated from site/sidebar.js for that reason: a hand-kept list of
    URLs is wrong the first time a page is renamed, and three moved this week.
    """
    import subprocess as _sp
    script = ROOT / "scripts" / "build_links_page.py"
    if not script.exists():
        return
    r = _sp.run([sys.executable, str(script), "--check"],
                capture_output=True, text=True, cwd=ROOT)
    check(r.returncode == 0, "the shareable links file is current",
          (r.stdout or r.stderr).strip().splitlines()[-1] if (r.stdout or r.stderr)
          else "run scripts/build_links_page.py")


def check_the_assistant_can_reach_every_page() -> None:
    """The chat assistant may only link to paths in the site map it SHIPS WITH.

    The site and the chat lambda deploy separately, and the lambda carries its
    own copy of the site map inside its bundle. So a page can be live, linked,
    indexed and in the sidebar while the assistant still cannot send anyone to
    it -- which is what happened to /visa-schools.html and /bodyshops.html: the
    prompt tells the model those paths are the only valid nav targets, and
    neither was in the copy it had. Nothing failed; the assistant was simply
    unable to mention two of the site's pages.

    This compares the built site map with the one in the chat bundle. Failing
    means the chat lambda needs redeploying, not that the site is wrong.
    """
    built = ROOT / "site" / "data" / "chat" / "site_map.json"
    shipped = ROOT / "cloud" / "chat" / "chat_data" / "site_map.json"
    if not built.exists() or not shipped.exists():
        return
    def paths(f):
        # One form per page: the built map is clean, a shipped bundle from
        # before the migration is not, and a mismatch of extension is not a
        # missing page.
        return {(p.get("path") or "").removesuffix(".html")
                for p in json.loads(f.read_text()).get("pages", [])}
    missing = sorted(paths(built) - paths(shipped))
    check(not missing, "the chat assistant can link to every page",
          f"{len(paths(shipped))} pages in the bundle" if not missing else
          f"absent from the chat bundle: {', '.join(missing[:4])} -- "
          f"redeploy the chat lambda (infra/chat/deploy.sh)")


def check_the_search_index_covers_the_corpus() -> None:
    """The assistant's record search must not be older than the records.

    search_index.bin is expensive to build, so it was left out of the chat
    deploy's rebuild block and then shipped untouched for a month while the
    corpus grew by 190,678 records. A stale index does not error: it answers
    normally and simply cannot find anything harvested since it was built.
    """
    idx = ROOT / "cloud" / "chat" / "chat_data" / "search_index.bin"
    if not idx.exists():
        return
    cut = idx.stat().st_mtime
    newer = [d for d in ("site/data/stem", "site/data/nonstem")
             if (ROOT / d).exists()
             for f in (ROOT / d).glob("*.json") if f.stat().st_mtime > cut]
    check(not newer, "the assistant's search index covers the corpus",
          "index is current" if not newer else
          f"{len(newer)} record file(s) are newer than search_index.bin -- "
          f"run scripts/build_chat_search_index.py")


def check_the_knowledge_base_covers_the_argument() -> None:
    """Every step of the argument must have a knowledge file behind it.

    The assistant answers "what is this site saying?" from knowledge/, not from
    the pages. A step that exists on the homepage and in the rail but nowhere
    in knowledge/ is a step the assistant cannot explain.
    """
    kb = ROOT / "cloud" / "chat" / "knowledge"
    if not kb.exists():
        return
    text = "\n".join(f.read_text().lower() for f in kb.glob("*.md"))
    # One probe per step of the argument, plus the two newest pages.
    # Page probes carry no extension: the site stopped serving .html and the
    # knowledge base followed, at which point this check failed on its own
    # convention rather than on a real gap.
    probes = {"the public pays for the doctorate": "public pays for the doctorate",
              "the master's is sold": "master's is sold",
              "the degree becomes a visa": "degree becomes a visa",
              "who profits": "who profits",
              "/visa-schools": "/visa-schools",
              "/bodyshops": "/bodyshops"}
    absent = sorted(k for k, probe in probes.items() if probe not in text)
    check(not absent, "the knowledge base covers every step of the argument",
          f"{len(list(kb.glob('*.md')))} knowledge files" if not absent else
          f"nothing in knowledge/ mentions: {', '.join(absent)}")


def check_every_page_has_the_sidebar() -> None:
    """One navigation, on every page that is a destination.

    Nineteen top-level pages loaded no navigation at all. rankings.html and
    institutions.html had zero internal links of any kind, so a shared link to
    either was a dead end: no way to reach the rest of the site, and nothing
    on the page saying there was a rest of the site. submit.html meanwhile
    used nav.js, a second drawer with its own hardcoded page list.

    Exempt, and only these: the private pages, which must NOT advertise the
    site's navigation, and redirect stubs, which are identified by their
    meta-refresh rather than by a list here -- a list would be one more thing
    to keep in step.
    """
    import re as _re
    site = ROOT / "site"
    if not site.exists():
        return
    from private_pages import PRIVATE
    # Subdirectory pages are destinations too, and this check used to glob the
    # top level only -- so the five /industries/ pages could have shipped with
    # no navigation and nothing would have said a word. The list of scanned
    # subdirectories is declared once, in build_site_map, and read here rather
    # than repeated.
    def destinations():
        return every_published_page(site)

    pages = list(destinations())
    missing, stubs = [], []
    for page in pages:
        if page.name in PRIVATE:
            continue
        text = page.read_text(errors="replace")
        if 'http-equiv="refresh"' in text:
            stubs.append(page.name)
            continue
        if not _re.search(r'<script[^>]*src="/sidebar\.js"', text):
            missing.append(page.name)
    # The superseded drawer must not come back alongside the sidebar.
    both = [p.name for p in pages
            if _re.search(r'<script[^>]*src="/nav\.js"',
                          p.read_text(errors="replace"))]
    problems = ([f"{n} has no sidebar" for n in missing]
                + [f"{n} still loads the superseded nav.js" for n in both])
    check(not problems, "every page carries the shared sidebar",
          f"{len(pages) - len(missing) - len(PRIVATE) - len(stubs)}"
          f" pages, {len(stubs)} redirect stubs exempt" if not problems
          else "; ".join(problems[:5]))



#: PAGE_DIRS is what the assistant's site map navigates to, and it is
#: deliberately narrow. The CHECKS must not inherit that narrowness: scanning
#: only the top level and industries meant the 106 university pages and 56
#: state pages were never checked for a sidebar, and the university pages
#: spent months serving their own baked-in 21 KB nav instead of the shared
#: one. A reader arriving on a shared university link saw a different site.
CHECKED_PAGE_DIRS = ("industries", "universities", "states")


def every_published_page(site):
    yield from sorted(site.glob("*.html"))
    for sub in CHECKED_PAGE_DIRS:
        yield from sorted((site / sub).glob("*.html"))


def check_every_page_loads_the_stylesheet() -> None:
    """Every page must load /style.css, so the theme is defined once.

    35 pages did not, and each carried its own copy of the design tokens.
    That is why the presentation deck had a warm-grey paper and its own
    serif, and why the IPEDS dashboard had a navy header nothing else used:
    the palette was redefined per page and drifted page by page.

    The sharper failure was a page that used a token without defining it.
    stem.html set --bg and not --hl, so `background: var(--hl)` resolved to
    nothing and a button rendered transparent on white -- invisible, with no
    error anywhere.
    """
    import re as _re
    from private_pages import PRIVATE
    site = ROOT / "site"
    NEVER = {"chat-admin.html"}
    missing = []
    for page in every_published_page(site):
        if page.name in PRIVATE or page.name in NEVER:
            continue
        text = page.read_text(errors="replace")
        if 'http-equiv="refresh"' in text:
            continue
        if not _re.search(r'<link[^>]+href="/style\.css"', text):
            missing.append(page.name)
    check(not missing, "every page loads the shared stylesheet",
          "one theme, defined once" if not missing
          else f"{len(missing)} page(s) define their own: "
               + ", ".join(sorted(missing)[:6]))


def check_every_page_is_instrumented() -> None:
    """Every public page must load the analytics beacon.

    The beacon was added to a page at a time by hand, so it reached the eight
    original argument pages and then stopped. By the time anyone asked, 12 of
    113 pages carried it: the whole H-1B site, every industry page, every
    state page and all 106 university pages were invisible in the analytics,
    and nothing said so because a page with no beacon looks exactly like a
    page nobody visited.

    Two pages are exempt on purpose. The analytics dashboard must not record
    every look at the analytics dashboard as site traffic, and the chat admin
    page is private.
    """
    import re as _re
    from build_site_map import PAGE_DIRS
    from private_pages import PRIVATE

    site = ROOT / "site"
    #: Exempt because measuring them would corrupt the measurement.
    NEVER = {"analytics.html", "chat-admin.html"}

    def destinations():
        yield from sorted(site.glob("*.html"))
        for sub in PAGE_DIRS:
            yield from sorted((site / sub).glob("*.html"))

    missing, stubs, exempt = [], 0, 0
    for page in destinations():
        if page.name in PRIVATE or page.name in NEVER:
            exempt += 1
            continue
        text = page.read_text(errors="replace")
        if 'http-equiv="refresh"' in text:
            stubs += 1
            continue
        if not _re.search(r'<script[^>]*src="/analytics-beacon\.js"', text):
            missing.append(page.name)
    check(not missing, "every public page reports to analytics",
          f"{exempt} exempt, {stubs} redirect stubs" if not missing
          else f"{len(missing)} page(s) with no beacon: "
               + ", ".join(sorted(missing)[:6]))


def check_executive_brief_is_current() -> None:
    """The executive brief must still say what the data says.

    The full briefing is 41 pages with 545 figures typed in by hand, and it
    was a month out of date before anyone asked: nothing in the build could
    tell that a number written in September described data that moved in
    October. The short brief is generated, so this re-renders it and
    compares. A difference means a figure in the published PDF is wrong and
    the document needs rebuilding, which is a thing a check can know and a
    reader cannot.
    """
    import importlib.util as _ilu
    src = ROOT / "scripts" / "build_executive_brief.py"
    built = ROOT / "report" / "exec-brief.html"
    pdf = ROOT / "site" / "executive-brief.pdf"
    if not src.exists():
        return
    if not pdf.exists():
        check(False, "the executive brief is current", "no PDF published")
        return
    spec = _ilu.spec_from_file_location("_exec_brief", src)
    mod = _ilu.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
        fresh = mod.build_html()
    except Exception as exc:                                # noqa: BLE001
        check(False, "the executive brief is current",
              f"cannot rebuild it: {type(exc).__name__}: {exc}")
        return
    #: The date line changes every month and is not a data drift.
    import re as _re
    strip = lambda t: _re.sub(r"Built from federal data &middot; [^<]+", "", t)
    stale = (not built.exists()) or strip(built.read_text()) != strip(fresh)
    check(not stale, "the executive brief is current",
          "4 pages, every figure live" if not stale
          else "a figure moved; run python3 report/exec_brief.py")


def check_tour_stops_resolve() -> None:
    """Every guided-tour stop must be a page that exists, at an anchor that
    exists on it.

    The tour is a hand-written list of pages and anchors, and nothing checked
    it. It walked readers through live.html and presentation.html, which carry
    their own dark treatment, so the theme flipped mid-tour; and a renamed
    anchor would have dropped a reader at the top of a page with the assistant
    describing something further down.
    """
    import re as _re
    site = ROOT / "site"
    src = (site / "tour.js").read_text(errors="replace")
    #: Every stop in the file, across every track. The first version read
    #: only the default list, so the ten section tours added later were
    #: unchecked -- and a tour that drops a reader on a missing page or a
    #: renamed anchor is worse than no tour.
    stops = _re.findall(
        r"page: '([^']+)'(?:,\s*\n?\s*anchor: '([^']+)')?", src)
    problems = []
    for page, anchor in stops:
        name = page.lstrip("/") or "index"
        target = site / (name if name.endswith(".html") else name + ".html")
        if not target.exists():
            problems.append(f"{page} does not exist")
            continue
        text = target.read_text(errors="replace")
        #: A dark-treatment page inside a light tour reads as a broken link
        #: mid-sentence. Test the ATTRIBUTE on the document element, not the
        #: string: every themed page mentions data-theme="dark" inside its
        #: prefers-color-scheme guard, which is the normal pattern and not a
        #: forced theme.
        if _re.search(r'<(?:html|body)[^>]*\sdata-theme="dark"', text):
            problems.append(f"{page} forces a dark theme")
        if anchor and f'id="{anchor}"' not in text:
            problems.append(f"{page} has no #{anchor}")
    check(not problems, "every guided-tour stop resolves",
          f"{len(stops)} stops" if not problems else "; ".join(problems[:4]))


def check_tour_pages_can_run_the_tour() -> None:
    """Every page the guided tour visits must load the chat widget.

    The tour narrates through the chat panel and keeps its position in
    sessionStorage, so each stop on a new page needs the widget there to
    resume. It had 16 stops across four pages and three of them loaded
    neither the widget nor tour.js: the tour reached stop 4, navigated to
    /presentation.html, and died silently with 13 stops unseen. Nothing
    failed, so nothing said so. A stop added to a page without the widget
    now fails the build instead.
    """
    import re as _re
    site = ROOT / "site"
    tour = site / "tour.js"
    if not site.exists() or not tour.exists():
        return
    pages = {p if p != "/" else "/index.html"
             for p in _re.findall(r"page: '([^']+)'", tour.read_text())}
    missing = []
    for page in sorted(pages):
        #: Stops are written the way the site serves them, without .html.
        #: Resolving them literally made every clean URL look like a missing
        #: page.
        name = page.lstrip("/") or "index"
        f = site / (name if name.endswith(".html") else name + ".html")
        if not f.exists():
            missing.append(f"{page} does not exist")
            continue
        text = f.read_text(errors="replace")
        # Either directly, or via sidebar.js which injects it.
        if "chat-widget.js" not in text and "sidebar.js" not in text:
            missing.append(f"{page} loads no chat widget")
    check(not missing, "every tour stop has the chat widget",
          f"{len(pages)} pages" if not missing else "; ".join(missing[:4]))


def check_private_pages_are_unlisted() -> None:
    """A private page must not be advertised in any of the four indexes.

    analytics.html was password-protected and still named in sitemap.xml, in
    contents.html and in the assistant's site_map.json, so a crawler, a reader
    of the contents page and anyone who asked the assistant for the traffic
    figures could all find the URL. The password held and the privacy did not.
    Privacy takes four omissions plus a noindex; this checks all five.
    """
    import json as _json
    site = ROOT / "site"
    if not site.exists():
        return
    from private_pages import PRIVATE, NOINDEX

    problems = []
    for name in sorted(PRIVATE):
        page = site / name
        if not page.exists():
            continue
        head = page.read_text(errors="replace")[:2000]
        if "noindex" not in head:
            problems.append(f"{name} has no {NOINDEX} in its head")
        for index, label in ((site / "sitemap.xml", "sitemap.xml"),
                             (site / "contents.html", "contents.html"),
                             (site / "robots.txt", None),
                             (site / "sidebar.js", "sidebar.js")):
            if not index.exists():
                continue
            text = index.read_text(errors="replace")
            if label is None:            # robots.txt must NAME it, to disallow
                if f"Disallow: /{name}" not in text:
                    problems.append(f"robots.txt does not disallow /{name}")
            elif name in text:
                problems.append(f"{label} names {name}")
        smap = site / "data" / "chat" / "site_map.json"
        if smap.exists():
            paths = {p.get("path") for p in
                     _json.loads(smap.read_text()).get("pages", [])}
            if f"/{name}" in paths:
                problems.append(f"the assistant's site_map.json routes to {name}")

    #: AND NOTHING LINKS TO ONE. The four indexes above are how a
    #: private page got advertised before, so they are checked. An
    #: ordinary <a href> from any other page does the same thing and
    #: was not checked at all: a link added to the briefing or the
    #: press-conference page would have passed every test here.
    linked: dict = {}
    for page in sorted(site.glob("*.html")):
        if page.name in PRIVATE:
            continue                       # a private page may link to itself
        text = page.read_text(errors="replace")
        for name in sorted(PRIVATE):
            stem = name[:-5] if name.endswith(".html") else name
            #: both spellings, because the site serves /x and /x.html
            if f'href="/{name}"' in text or f'href="/{stem}"' in text:
                linked.setdefault(name, []).append(page.name)
    for name, pages in sorted(linked.items()):
        problems.append(f"{name} is linked from {', '.join(sorted(pages)[:4])}")

    check(not problems, "private pages are unlisted",
          f"{len(PRIVATE)} private, none advertised, none linked"
          if not problems
          else "; ".join(problems[:4]))


def check_exports_are_not_behind_their_sources() -> None:
    """A downloadable export must not be older than the data it came from.

    site/data/exports/*.parquet is what the query console reads and what a
    reader downloads. It is built FROM site/data/{stem,nonstem}/*.json, and
    nothing connected the two, so the pair could silently diverge.

    It did. Cleaning catalogue junk out of the author names rewrote every
    record file and left the parquet untouched, so the site showed 'Dai,
    Siyu' while the export and every SQL query still returned 'Dai,
    Siyu(Scientist in mechanical engineering) Massachusetts Institute of
    Technology'. 2,731 names disagreed between the page and the download of
    the same data, and every other check passed.

    An export older than its newest input is stale by definition, which is
    the one thing that can be tested without rebuilding it.
    """
    pairs = {
        "stem_records.parquet": ROOT / "site" / "data" / "stem",
        "nonstem_records.parquet": ROOT / "site" / "data" / "nonstem",
    }
    stale = []
    for name, src in pairs.items():
        out = ROOT / "site" / "data" / "exports" / name
        if not out.exists():
            stale.append(f"{name} has never been built")
            continue
        if not src.is_dir():
            continue
        newest = max((f.stat().st_mtime for f in src.glob("*.json")),
                     default=0)
        if newest > out.stat().st_mtime:
            behind = int((newest - out.stat().st_mtime) // 60)
            stale.append(f"{name} is {behind} min behind "
                         f"{src.relative_to(ROOT)}")
    check(not stale, "exports are current for their sources",
          ("; ".join(stale) + " -- run scripts/build_parquet_from_site.py")
          if stale else f"{len(pairs)} export(s) newer than their inputs")


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
               check_contents_page_lists_every_page,
               check_inlined_dashboards_are_current,
               check_kb_pins_still_match,
               check_kb_figures_are_traceable,
               check_the_links_file_is_current,
               check_the_assistant_can_reach_every_page,
               check_the_knowledge_base_covers_the_argument,
               check_the_search_index_covers_the_corpus,
               check_private_pages_are_unlisted,
               check_every_page_loads_the_stylesheet,
               check_every_page_is_instrumented,
               check_executive_brief_is_current,
               check_exports_are_not_behind_their_sources,
               check_tour_stops_resolve,
               check_tour_pages_can_run_the_tour,
               check_every_page_has_the_sidebar):
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
