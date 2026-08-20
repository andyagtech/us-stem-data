"""
CLI entry point: python -m pipeline run [--university KEY] [--step STEP] [--mode MODE] [--dry-run]
"""
import argparse
import sys
from pathlib import Path

from .runner import run_pipeline


# Import steps (lazy — only import what's needed)
STEP_REGISTRY = {}

# University subsets for --mode flag
MODE_TOP20 = [
    'missouri_st', 'siu', 'njit', 'utarlington', 'smu', 'caltech',
    'uhouston', 'mtu', 'purdue', 'sdsu', 'utdallas', 'kstate',
    'ttu', 'rit', 'binghamton', 'cmu', 'iowa_state', 'clemson',
    'uarkansas', 'ubuffalo',
]

MODE_TOP50 = MODE_TOP20 + [
    'msstate', 'lsu', 'marquette', 'wayne_state', 'umd', 'mit',
    'gatech', 'ncstate', 'rice', 'washu', 'gmu', 'uf',
    'cornell', 'penn_state', 'stanford', 'duke', 'ucdavis',
    'ucsd', 'ucberkeley', 'ucla', 'uiuc',
    'bu', 'stony_brook', 'usc_columbia', 'uw_seattle',
    'umissouri', 'vt', 'uoregon', 'utk', 'ucf',
]


def register_step(name):
    """Decorator to register a step function."""
    def decorator(fn):
        STEP_REGISTRY[name] = fn
        return fn
    return decorator


def get_steps(step_names: list[str] | None = None):
    """Import and return step functions."""
    # Import all available steps
    from importlib import import_module
    step_imports = [
        ("harvest", "pipeline.step1_harvest", "step1_harvest"),
        ("process", "pipeline.step2_process", "step2_process"),
        ("parse_federal", "pipeline.step3_parse_federal", "step3_parse_federal"),
        ("enrich", "pipeline.step4_enrich", "step4_enrich"),
        # Optional: site generation and deployment (not in public repo)
        ("generate", "pipeline.step5_generate", "step5_generate"),
        ("build_pages", "pipeline.step5b_build_pages", "step5b_build_pages"),
        ("deploy", "pipeline.step6_deploy", "step6_deploy"),
    ]
    for name, module_path, func_name in step_imports:
        try:
            mod = import_module(module_path)
            STEP_REGISTRY[name] = getattr(mod, func_name)
        except (ImportError, AttributeError) as e:
            pass

    if step_names:
        steps = []
        for name in step_names:
            if name not in STEP_REGISTRY:
                print(f"ERROR: Unknown step '{name}'. Available: {list(STEP_REGISTRY.keys())}")
                sys.exit(1)
            steps.append(STEP_REGISTRY[name])
        return steps
    else:
        # Default: all registered steps in order
        # IMPORTANT: enrich must run BEFORE generate.
        #   - enrich reads from data/processed/ (or existing site/data/) and writes federal data
        #     into site/data/{stem,nonstem}/{key}.json
        #   - generate now MERGES with existing site/data/ JSONs (preserves enrichment)
        #   - With this order, generate sees enriched JSONs and just refreshes records
        # Historical bug: when generate ran BEFORE enrich, it overwrote enrichment with bare records.
        # Mitigation in place: generate now does merge-not-overwrite (see generate_name_lists_html.py).
        order = ["harvest", "process", "parse_federal", "enrich", "generate", "build_pages", "deploy"]
        return [STEP_REGISTRY[s] for s in order if s in STEP_REGISTRY]


def cmd_run(args):
    base_dir = Path(__file__).parent.parent
    step_names = args.step.split(",") if args.step else None
    steps = get_steps(step_names)

    if not steps:
        print("No steps available. Implement step modules first.")
        sys.exit(1)

    # Resolve --mode to university filter
    uni_filter = args.university
    if args.mode and not uni_filter:
        if args.mode == 'top20':
            uni_filter = MODE_TOP20
            print(f"Mode: top20 ({len(MODE_TOP20)} universities)")
        elif args.mode == 'top50':
            uni_filter = MODE_TOP50
            print(f"Mode: top50 ({len(MODE_TOP50)} universities)")
        elif args.mode == 'full':
            uni_filter = None
            print("Mode: full (all universities)")
        else:
            print(f"ERROR: Unknown mode '{args.mode}'. Use: top20, top50, full")
            sys.exit(1)

    state = run_pipeline(
        base_dir=base_dir,
        steps=steps,
        university_filter=uni_filter,
        dry_run=args.dry_run,
        harvest_since=args.since,
    )

    sys.exit(0 if state.error_count == 0 else 1)


def cmd_status(args):
    import json
    base_dir = Path(__file__).parent.parent
    manifest_path = base_dir / "pipeline" / "manifest.json"

    if not manifest_path.exists():
        print("No manifest found. Run the pipeline first.")
        sys.exit(0)

    manifest = json.load(open(manifest_path))
    print(f"Pipeline Manifest: {len(manifest)} universities tracked\n")

    for key in sorted(manifest.keys()):
        entry = manifest[key]
        steps_done = [s for s in entry if isinstance(entry[s], dict) and entry[s].get("last_run")]
        errors = entry.get("errors", [])
        warnings = entry.get("warnings", [])
        status = "OK" if not errors else f"ERRORS: {len(errors)}"
        print(f"  {key:<25} steps: {', '.join(steps_done):<40} {status}")


def cmd_datasets(args):
    """Report the data catalog: what builds what, and what is out of date."""
    from pipeline import datasets as D

    if args.run:
        import subprocess
        keys = [k.strip() for k in args.run.split(",") if k.strip()]
        unknown = [k for k in keys if k not in D.BY_KEY]
        if unknown:
            print(f"Unknown dataset(s): {', '.join(unknown)}")
            print(f"Known: {', '.join(D.BY_KEY)}")
            sys.exit(2)
        plan = D.order_for(keys)
        print("Rebuild order (dependencies pulled in automatically):")
        for d in plan:
            print(f"  scripts/{d.script}.py {d.args}".rstrip())
        if args.dry_run:
            print("\n[DRY RUN] Nothing executed.")
            return
        for d in plan:
            argv = [sys.executable, f"scripts/{d.script}.py"] + (
                d.args.split() if d.args and "PATH" not in d.args else [])
            print(f"\n=== {d.key} ===")
            r = subprocess.run(argv, cwd=str(D.ROOT))
            if r.returncode != 0:
                print(f"FAILED: {d.key} exited {r.returncode}. Stopping — "
                      f"later datasets may consume its output.")
                sys.exit(r.returncode)
        return

    problems = D.report(verbose=args.verbose)
    if problems:
        print(f"\n{problems} dataset(s) need attention.")
    sys.exit(1 if problems else 0)


def cmd_models(args):
    """Validate models against their declared contracts."""
    from pipeline import models as M
    if args.variants:
        for src in sorted({v.source for v in M.SOURCE_VARIANTS}):
            print(f"{src}")
            for v in sorted((x for x in M.SOURCE_VARIANTS if x.source == src),
                            key=lambda x: x.applies):
                hi = "..." if v.applies[1] >= 2100 else str(v.applies[1])
                print(f"  {v.applies[0]}-{hi:<6} encoding={v.encoding} "
                      f"delimiter={'TAB' if v.delimiter == chr(9) else 'comma'}")
                if v.notes:
                    print(f"    {v.notes}")
            print()
        return
    failures = M.report()
    sys.exit(1 if failures else 0)


def main():
    parser = argparse.ArgumentParser(description="PhD Demographics Data Pipeline")
    subparsers = parser.add_subparsers(dest="command")

    # run command
    run_parser = subparsers.add_parser("run", help="Run pipeline steps")
    run_parser.add_argument("--university", "-u", help="Process only this university key")
    run_parser.add_argument("--step", "-s", help="Comma-separated step names (e.g., enrich,generate)")
    run_parser.add_argument("--mode", "-m", choices=["top20", "top50", "full"], help="University subset: top20 (highest NRA), top50, or full (all 101)")
    run_parser.add_argument("--dry-run", "-n", action="store_true", help="Show what would be done")
    run_parser.add_argument("--since", type=str, default="",
                            help="Harvest step: fetch only records deposited or "
                                 "modified since this date (YYYY-MM-DD)")
    run_parser.set_defaults(func=cmd_run)

    # status command
    status_parser = subparsers.add_parser("status", help="Show pipeline status")
    status_parser.set_defaults(func=cmd_status)

    # datasets command
    ds_parser = subparsers.add_parser(
        "datasets",
        help="What builds each derived artifact, and what is out of date")
    ds_parser.add_argument("--verbose", "-v", action="store_true",
                           help="Show script, source, summary and caveats")
    ds_parser.add_argument("--run", metavar="KEYS",
                           help="Comma-separated dataset keys to rebuild, in "
                                "dependency order (dependencies are added)")
    ds_parser.add_argument("--dry-run", "-n", action="store_true",
                           help="With --run: print the plan, execute nothing")
    ds_parser.set_defaults(func=cmd_datasets)

    # models command
    m_parser = subparsers.add_parser(
        "models", help="Validate models against their declared contracts")
    m_parser.add_argument("--variants", action="store_true",
                          help="Show declared source variants by year instead")
    m_parser.set_defaults(func=cmd_models)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()
