"""
Step 4: ENRICH — Merge all data sources into final per-university JSONs.

This is the ONLY step that writes to site/data/{stem,nonstem}/.
It reads from data/processed/ and produces the complete enriched JSONs.

Input:  site/data/{stem,nonstem}/{key}.json (base records from step2+step5)
        data/h1b/h1b_by_university.json
        data/h1b/opt_by_university.json
        data/h1b/lca_by_university.json
        data/h1b/perm_by_university.json
        + IPEDS, GSS, HERD data
Output: site/data/{stem,nonstem}/{key}.json (enriched with all federal data)
"""
from __future__ import annotations
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from .state import PipelineState, StepOutcome


_system_map_cache = None

def _load_system_map(base_dir) -> dict:
    """Load system H-1B mapping (campus → parent system)."""
    global _system_map_cache
    if _system_map_cache is not None:
        return _system_map_cache
    path = Path(__file__).parent / "system_h1b_map.json"
    if path.exists():
        with open(path) as f:
            _system_map_cache = json.load(f)
    else:
        _system_map_cache = {}
    return _system_map_cache


def _load_json(path: Path) -> dict:
    """Load a JSON file, returning empty dict if missing."""
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


def _load_h1b(base_dir: Path) -> dict[str, list]:
    """Load and convert H-1B data to compact format: key → [[year, approvals, denials], ...]"""
    raw = _load_json(base_dir / "data" / "h1b" / "h1b_by_university.json")
    result = {}
    for key, years in raw.items():
        yearly = []
        for fy in sorted(years.keys()):
            if not fy.strip():
                continue
            counts = years[fy]
            yearly.append([
                int(fy),
                counts.get("initial_approvals", 0) + counts.get("continuing_approvals", 0),
                counts.get("initial_denials", 0) + counts.get("continuing_denials", 0),
            ])
        result[key] = yearly
    return result


def _enrich_university(uni_data: dict, key: str, h1b: dict, opt: dict, lca: dict, perm: dict) -> dict:
    """Pure function: merge federal data into university JSON. Returns new dict (no mutation)."""
    enriched = dict(uni_data)  # Shallow copy

    if key in h1b:
        enriched["h1b"] = h1b[key]
    if key in opt:
        enriched["opt"] = opt[key]
    if key in lca:
        enriched["lca"] = lca[key]
    if key in perm:
        enriched["perm"] = perm[key]

    # System H-1B mapping: if university doesn't have its own H-1B data,
    # use the parent system's data with a disclaimer
    system_map = _load_system_map(enriched.get("_base_dir", None))
    if key in system_map and "h1b" not in enriched:
        sys_info = system_map[key]
        sys_key = sys_info["system_key"]
        if sys_key in h1b:
            enriched["h1b"] = h1b[sys_key]
            enriched["h1b_system_note"] = sys_info["note"]
        if sys_key in opt and "opt" not in enriched:
            enriched["opt"] = opt[sys_key]
            enriched["h1b_system_note"] = sys_info["note"]
        if sys_key in lca and "lca" not in enriched:
            enriched["lca"] = lca[sys_key]
        if sys_key in perm and "perm" not in enriched:
            enriched["perm"] = perm[sys_key]

    return enriched


def step4_enrich(state: PipelineState) -> PipelineState:
    """Enrich all per-university JSONs with federal data sources."""
    if state.should_halt():
        return state

    base_dir = state.config.base_dir
    print("\n[Step 4: ENRICH] Loading federal data sources...")

    # Load all federal data sources
    h1b = _load_h1b(base_dir)
    opt = _load_json(base_dir / "data" / "h1b" / "opt_by_university.json")
    lca = _load_json(base_dir / "data" / "h1b" / "lca_by_university.json")
    perm = _load_json(base_dir / "data" / "h1b" / "perm_by_university.json")

    # Load department links
    dept_links = _load_json(base_dir / "data" / "dept_links.json")

    print(f"  H-1B: {len(h1b)} universities")
    print(f"  OPT:  {len(opt)} universities")
    print(f"  LCA:  {len(lca)} universities")
    print(f"  PERM: {len(perm)} universities")
    print(f"  Dept links: {len(dept_links)} universities")

    # Also run the existing IPEDS/GSS/HERD enrichment
    # Import and delegate to existing script's functions
    sys.path.insert(0, str(base_dir / "scripts"))
    try:
        from enrich_university_json import (
            load_gss_enrollment, load_ipeds_enrollment, load_herd_funding,
            load_ipeds_completions, load_tuition, load_financial_aid, load_faculty,
            KEY_TO_UNITID,
        )
        gss = load_gss_enrollment()
        ipeds_enroll = load_ipeds_enrollment()
        herd = load_herd_funding()
        completions = load_ipeds_completions()
        tuition = load_tuition()
        aid = load_financial_aid()
        faculty = load_faculty()
    except Exception as e:
        print(f"  WARNING: Could not load IPEDS/GSS/HERD data: {e}")
        gss = ipeds_enroll = herd = completions = tuition = aid = faculty = {}

    # Load SHEEO state appropriations (state-level time series per university)
    sheeo = {}
    sheeo_path = base_dir / "data" / "state_funding" / "sheeo_by_university.json"
    if sheeo_path.exists():
        try:
            sheeo_raw = json.load(open(sheeo_path))
            unis = sheeo_raw.get("universities", {})
            for k, v in unis.items():
                # Compact: only key metrics, only 2010-2024
                ts = v.get("state_time_series", {})
                compact = {}
                for yr, metrics in ts.items():
                    if not metrics: continue
                    compact[yr] = {
                        "total_state_support": metrics.get("total_state_support"),
                        "ed_approp_per_fte": metrics.get("ed_approp_per_fte"),
                        "ed_approp_per_fte_real25": metrics.get("ed_approp_per_fte_real25"),
                        "net_fte_enrollment": metrics.get("net_fte_enrollment"),
                        "student_share": metrics.get("student_share"),
                        "federal_stimulus": metrics.get("federal_stimulus"),
                    }
                sheeo[k] = {
                    "state": v.get("state_abbr"),
                    "state_name": v.get("state_name"),
                    "yearly": compact,
                }
            print(f"  SHEEO state appropriations: {len(sheeo)} universities")
        except Exception as e:
            print(f"  WARNING: Could not load SHEEO data: {e}")

    # Load state-specific per-institution funding (FL, TX, CA)
    state_specific = {}
    ss_path = base_dir / "data" / "state_funding" / "state_specific" / "state_specific_funding_by_university.json"
    if ss_path.exists():
        try:
            state_specific = json.load(open(ss_path))
            print(f"  State-specific funding: {len(state_specific)} universities")
        except Exception as e:
            print(f"  WARNING: Could not load state-specific funding: {e}")

    # Load USAspending federal awards (per-recipient totals)
    usaspending = {}
    usa_path = base_dir / "data" / "usaspending" / "usaspending_by_university.json"
    if usa_path.exists():
        try:
            usaspending = json.load(open(usa_path))
            print(f"  USAspending federal awards: {len(usaspending)} universities")
        except Exception as e:
            print(f"  WARNING: Could not load USAspending data: {e}")

    # Load NSF Awards and NIH RePORTER grant obligations. Both were fetched
    # for all 101 universities in a23a60a and then never read by anything,
    # so $82.8B of agency-side federal research funding never reached a page.
    # These differ from HERD, which is self-reported R&D expenditure: these
    # are what the funding agencies actually obligated, per grant.
    nsf_awards = {}
    nsf_path = base_dir / "data" / "state_funding" / "nsf_awards" / "nsf_by_university.json"
    if nsf_path.exists():
        try:
            nsf_awards = json.load(open(nsf_path))
            print(f"  NSF awards: {len(nsf_awards)} universities")
        except Exception as e:
            print(f"  WARNING: Could not load NSF awards: {e}")

    nih = {}
    nih_path = base_dir / "data" / "state_funding" / "nih_reporter" / "nih_by_university.json"
    if nih_path.exists():
        try:
            nih = json.load(open(nih_path))
            print(f"  NIH RePORTER: {len(nih)} universities")
        except Exception as e:
            print(f"  WARNING: Could not load NIH RePORTER data: {e}")

    # Process each university JSON
    enriched_count = 0
    errors = []

    for mode in ["stem", "nonstem"]:
        # Read from site/data/ if it exists (already-enriched run), else from data/processed/ (fresh).
        # ALWAYS write to site/data/ regardless of source — that's the canonical location.
        site_dir = base_dir / "site" / "data" / mode
        processed_dir = base_dir / "data" / "processed" / mode

        if site_dir.is_dir() and any(site_dir.glob("*.json")):
            read_dir = site_dir
        elif processed_dir.is_dir():
            read_dir = processed_dir
        else:
            continue

        # Ensure write target exists
        site_dir.mkdir(parents=True, exist_ok=True)

        for fname in sorted(os.listdir(read_dir)):
            if not fname.endswith(".json") or fname.startswith("_"):
                continue
            key = fname.replace(".json", "")
            read_path = read_dir / fname
            write_path = site_dir / fname

            try:
                with open(read_path) as f:
                    uni_data = json.load(f)

                # Enrich with H-1B/OPT/LCA/PERM (pure function)
                uni_data = _enrich_university(uni_data, key, h1b, opt, lca, perm)

                # Enrich with IPEDS/GSS/HERD (from existing script)
                unitid = KEY_TO_UNITID.get(key)
                if unitid and unitid in gss:
                    uni_data["enrollment"] = gss[unitid]
                if unitid and unitid in ipeds_enroll:
                    uni_data["enrollment_ipeds"] = ipeds_enroll[unitid]
                if key in herd:
                    uni_data["funding"] = herd[key]
                elif key == "ucirvine" and "uci" in herd:
                    uni_data["funding"] = herd["uci"]
                elif key == "ucriverside" and "ucr" in herd:
                    uni_data["funding"] = herd["ucr"]
                if unitid and unitid in completions:
                    uni_data["completions_trend"] = completions[unitid]
                if unitid and unitid in tuition:
                    uni_data["tuition"] = tuition[unitid]
                if unitid and unitid in aid:
                    uni_data["financial_aid"] = aid[unitid]
                if unitid and unitid in faculty:
                    uni_data["faculty"] = faculty[unitid]

                # Department links
                if key in dept_links:
                    uni_data["dept_links"] = dept_links[key]

                # SHEEO state appropriations (state-level proxy)
                if key in sheeo:
                    uni_data["state_funding"] = sheeo[key]

                # State-specific per-institution funding (FL/TX/CA)
                if key in state_specific:
                    uni_data["state_funding_institution"] = state_specific[key]

                # USAspending federal awards (per-recipient totals)
                if key in usaspending:
                    uni_data["usaspending"] = usaspending[key]

                # NSF grant obligations by year
                if key in nsf_awards:
                    entry = nsf_awards[key]
                    uni_data["nsf_awards"] = {
                        "by_year": entry.get("by_year", {}),
                        "total_awards": entry.get("total_awards"),
                        "total_obligated": entry.get(
                            "total_obligated", entry.get("total_obligated_5yr")
                        ),
                    }

                # NIH grant obligations by fiscal year
                if key in nih:
                    entry = nih[key]
                    uni_data["nih"] = {
                        "by_year": entry.get("by_year", {}),
                        "total_grants": entry.get(
                            "total_grants", entry.get("total_grants_2020_2024")
                        ),
                        "total_dollars": entry.get(
                            "total_dollars", entry.get("total_dollars_2020_2024")
                        ),
                        "top_departments": entry.get("top_departments", [])[:10],
                    }

                # Write to site/data/ (canonical location, regardless of read source)
                with open(write_path, "w") as f:
                    json.dump(uni_data, f, ensure_ascii=False, separators=(",", ":"))

                enriched_count += 1
            except Exception as e:
                errors.append(f"{key}: {e}")

    # Build outcome
    data = {
        "enriched": enriched_count,
        "h1b_universities": len(h1b),
        "opt_universities": len(opt),
        "lca_universities": len(lca),
        "perm_universities": len(perm),
    }

    if errors:
        outcome = StepOutcome(
            step_name="enrich",
            university_key="",
            success=len(errors) < enriched_count,  # Partial success OK
            message=f"Enriched {enriched_count} files, {len(errors)} errors",
            data=data,
            errors=tuple(errors[:10]),
            warnings=(),
            timestamp=datetime.utcnow().isoformat(),
        )
    else:
        outcome = StepOutcome.ok("enrich", message=f"Enriched {enriched_count} university files", data=data)

    print(f"  Enriched {enriched_count} files ({len(errors)} errors)")
    return state.with_outcome(outcome)
