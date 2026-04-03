"""
CLI entry point: python -m pipeline run [--university KEY] [--step STEP] [--dry-run]
"""
import argparse
import sys
from pathlib import Path

from .runner import run_pipeline


# Import steps (lazy — only import what's needed)
STEP_REGISTRY = {}


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
        ("generate", "pipeline.step5_generate", "step5_generate"),
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
        order = ["harvest", "process", "parse_federal", "enrich", "generate", "deploy"]
        return [STEP_REGISTRY[s] for s in order if s in STEP_REGISTRY]


def cmd_run(args):
    base_dir = Path(__file__).parent.parent
    step_names = args.step.split(",") if args.step else None
    steps = get_steps(step_names)

    if not steps:
        print("No steps available. Implement step modules first.")
        sys.exit(1)

    state = run_pipeline(
        base_dir=base_dir,
        steps=steps,
        university_filter=args.university,
        dry_run=args.dry_run,
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


def main():
    parser = argparse.ArgumentParser(description="PhD Demographics Data Pipeline")
    subparsers = parser.add_subparsers(dest="command")

    # run command
    run_parser = subparsers.add_parser("run", help="Run pipeline steps")
    run_parser.add_argument("--university", "-u", help="Process only this university key")
    run_parser.add_argument("--step", "-s", help="Comma-separated step names (e.g., enrich,generate)")
    run_parser.add_argument("--dry-run", "-n", action="store_true", help="Show what would be done")
    run_parser.set_defaults(func=cmd_run)

    # status command
    status_parser = subparsers.add_parser("status", help="Show pipeline status")
    status_parser.set_defaults(func=cmd_status)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()
