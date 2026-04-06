"""
Step 2b: AI_CLASSIFY — Use Claude Haiku to classify unlabeled thesis records.

For records where infer_degree_type() returns '', use the thesis title + department
context to classify as PhD or MS using Claude Haiku API.

This is a supplementary step that runs after step2_process. Results are cached
in pipeline/ai_classifications.json to avoid re-classifying on future runs.

Cost: ~$4 for 50K records at Haiku pricing.
"""
from __future__ import annotations

import csv
import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

csv.field_size_limit(1_000_000)

# Import processing functions
_scripts_dir = str(Path(__file__).parent.parent / "scripts")
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from generate_name_lists import CONFIGS, infer_degree_type  # noqa: E402

CACHE_PATH = Path(__file__).parent / "ai_classifications.json"
BATCH_SIZE = 50  # titles per API call


def _load_cache() -> dict:
    """Load existing AI classifications cache."""
    if CACHE_PATH.exists():
        with open(CACHE_PATH) as f:
            return json.load(f)
    return {}


def _save_cache(cache: dict):
    """Save AI classifications cache."""
    with open(CACHE_PATH, "w") as f:
        json.dump(cache, f, indent=2)


def _get_unlabeled_records(config: dict) -> list[tuple[int, str, str]]:
    """Get unlabeled records from a university CSV.

    Returns list of (row_index, title, department_hint).
    """
    unlabeled = []
    if not os.path.exists(config["file"]):
        return unlabeled

    with open(config["file"], encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            deg = infer_degree_type(row, config)
            if deg:
                continue  # already labeled
            title = (row.get("title", "") or "").strip()
            if not title or len(title) < 10:
                continue  # too short to classify
            dept = (
                row.get("degree_discipline", "")
                or row.get("subject", "")
                or row.get("contributor", "")
                or ""
            ).strip()[:100]
            unlabeled.append((i, title, dept))

    return unlabeled


def classify_batch(titles_with_context: list[tuple[str, str]]) -> list[tuple[str, float]]:
    """Classify a batch of thesis titles as PhD or MS using Claude Haiku.

    Args:
        titles_with_context: list of (title, department_hint) tuples

    Returns:
        list of (degree, confidence) tuples where degree is 'phd' or 'ms'
    """
    import anthropic

    client = anthropic.Anthropic()

    # Build numbered list with department context
    lines = []
    for i, (title, dept) in enumerate(titles_with_context):
        ctx = f" [{dept}]" if dept else ""
        lines.append(f"{i+1}. {title[:120]}{ctx}")

    prompt = f"""Classify each thesis/dissertation title as either PhD or MS (Master's).

PhD dissertations tend to be:
- Original research contributions with novel findings
- Longer, more specific titles about narrow topics
- Words like "investigation", "analysis", "novel approach", "mechanism"

Master's theses tend to be:
- More applied, implementation-focused, or survey-oriented
- Words like "design and implementation", "evaluation", "study of"
- Shorter, more practical titles

For each, respond with ONLY the number followed by PhD or MS, one per line.
Example: "1. PhD" or "2. MS"

Titles:
{chr(10).join(lines)}"""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=len(titles_with_context) * 10,
        messages=[{"role": "user", "content": prompt}],
    )

    text = response.content[0].text.strip()
    results = []

    # Parse response lines
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        # Extract degree from patterns like "1. PhD", "2. MS", "PhD", "MS"
        upper = line.upper()
        if "PHD" in upper:
            results.append(("phd", 0.85))
        elif "MS" in upper or "MASTER" in upper:
            results.append(("ms", 0.85))
        else:
            results.append(("", 0.0))

    # Pad if response was truncated
    while len(results) < len(titles_with_context):
        results.append(("", 0.0))

    return results[: len(titles_with_context)]


def run_classification(
    min_unlabeled: int = 20,
    confidence_threshold: float = 0.8,
    dry_run: bool = False,
    max_records: int = 0,
) -> dict:
    """Run Claude Haiku classification on all unlabeled records.

    Args:
        min_unlabeled: Only classify universities with at least this many unlabeled
        confidence_threshold: Minimum confidence to accept classification
        dry_run: If True, just count unlabeled without calling API
        max_records: Maximum records to classify (0 = unlimited)

    Returns:
        dict with classification statistics
    """
    cache = _load_cache()
    total_classified = 0
    total_phd = 0
    total_ms = 0
    total_skipped = 0
    api_calls = 0

    print(f"\n[AI Classify] Scanning for unlabeled records...")

    for config in CONFIGS:
        key = config["key"]
        if config.get("_merge"):
            continue  # Skip merge configs (handled by primary)

        unlabeled = _get_unlabeled_records(config)
        if len(unlabeled) < min_unlabeled:
            continue

        # Filter out already-cached records
        cached_indices = set()
        if key in cache:
            cached_indices = {entry[0] for entry in cache[key]}

        new_unlabeled = [(i, t, d) for i, t, d in unlabeled if i not in cached_indices]
        if not new_unlabeled:
            continue

        print(
            f"  {key}: {len(new_unlabeled)} new unlabeled "
            f"(+{len(cached_indices)} cached)"
        )

        if dry_run:
            total_skipped += len(new_unlabeled)
            continue

        if max_records and total_classified >= max_records:
            break

        # Classify in batches
        if key not in cache:
            cache[key] = []

        for batch_start in range(0, len(new_unlabeled), BATCH_SIZE):
            batch = new_unlabeled[batch_start : batch_start + BATCH_SIZE]
            titles_ctx = [(t, d) for _, t, d in batch]

            try:
                results = classify_batch(titles_ctx)
                api_calls += 1

                for (idx, title, dept), (degree, conf) in zip(batch, results):
                    if degree and conf >= confidence_threshold:
                        cache[key].append([idx, degree, round(conf, 3)])
                        total_classified += 1
                        if degree == "phd":
                            total_phd += 1
                        else:
                            total_ms += 1

                # Rate limit
                time.sleep(0.5)

                if max_records and total_classified >= max_records:
                    break

            except Exception as e:
                err_msg = str(e)
                print(f"    ERROR at batch {batch_start}: {err_msg}")
                if "authentication" in err_msg.lower() or "api_key" in err_msg.lower():
                    print("    Set ANTHROPIC_API_KEY env variable and retry.")
                    _save_cache(cache)
                    return {
                        "total_classified": total_classified,
                        "phd": total_phd,
                        "ms": total_ms,
                        "api_calls": api_calls,
                        "error": "Missing API key",
                    }
                time.sleep(2)

        # Save cache after each university
        _save_cache(cache)

    if not dry_run:
        _save_cache(cache)

    stats = {
        "total_classified": total_classified,
        "phd": total_phd,
        "ms": total_ms,
        "api_calls": api_calls,
        "skipped": total_skipped,
    }
    print(
        f"\n  Classified {total_classified:,} records "
        f"({total_phd:,} PhD, {total_ms:,} MS) in {api_calls} API calls"
    )
    return stats


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="AI-classify unlabeled thesis records")
    parser.add_argument("--dry-run", action="store_true", help="Count unlabeled without classifying")
    parser.add_argument("--max", type=int, default=0, help="Max records to classify (0=unlimited)")
    parser.add_argument("--min-unlabeled", type=int, default=20, help="Min unlabeled per university")
    args = parser.parse_args()

    run_classification(
        dry_run=args.dry_run,
        max_records=args.max,
        min_unlabeled=args.min_unlabeled,
    )
