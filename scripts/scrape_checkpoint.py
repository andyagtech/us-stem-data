#!/usr/bin/env python3
"""
Reusable checkpoint/dedup module for scraping at national scale.

Uses SQLite for O(1) lookups and crash-safe atomic writes instead of
loading all IDs into memory via JSON.

Usage:
    from scrape_checkpoint import CheckpointDB

    with CheckpointDB("data/my_scrape/checkpoint.db") as db:
        # Check if already scraped
        if db.is_done("some-uuid-1234"):
            continue

        # ... scrape the item ...

        # Mark as done (committed immediately)
        db.mark_done("some-uuid-1234")

        # Store/retrieve state (e.g., resumption tokens, last index)
        db.set_state("last_index", "500")
        idx = db.get_state("last_index")  # returns "500"

        # Stats
        print(db.count_done())  # number of completed items
"""

import sqlite3
from pathlib import Path


class CheckpointDB:
    """SQLite-backed checkpoint store for large-scale scraping."""

    def __init__(self, db_path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.execute("PRAGMA journal_mode=WAL")  # crash-safe writes
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self._init_tables()

    def _init_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS completed (
                item_id TEXT PRIMARY KEY
            );
            CREATE TABLE IF NOT EXISTS state (
                key TEXT PRIMARY KEY,
                value TEXT
            );
        """)
        self.conn.commit()

    def is_done(self, item_id: str) -> bool:
        """Check if an item has been scraped. O(1) via index."""
        row = self.conn.execute(
            "SELECT 1 FROM completed WHERE item_id = ?", (item_id,)
        ).fetchone()
        return row is not None

    def mark_done(self, item_id: str):
        """Mark an item as scraped. Committed immediately."""
        self.conn.execute(
            "INSERT OR IGNORE INTO completed (item_id) VALUES (?)", (item_id,)
        )
        self.conn.commit()

    def mark_done_batch(self, item_ids: list):
        """Mark multiple items as scraped in one transaction."""
        self.conn.executemany(
            "INSERT OR IGNORE INTO completed (item_id) VALUES (?)",
            [(iid,) for iid in item_ids]
        )
        self.conn.commit()

    def count_done(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) FROM completed").fetchone()
        return row[0]

    def set_state(self, key: str, value: str):
        """Store a key-value state entry (e.g., last_index, resumption_token)."""
        self.conn.execute(
            "INSERT OR REPLACE INTO state (key, value) VALUES (?, ?)",
            (key, value)
        )
        self.conn.commit()

    def get_state(self, key: str, default: str = None) -> str:
        row = self.conn.execute(
            "SELECT value FROM state WHERE key = ?", (key,)
        ).fetchone()
        return row[0] if row else default

    def close(self):
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def migrate_json_checkpoint(json_path: str, db_path: str) -> int:
    """
    Migrate an existing JSON checkpoint to SQLite.
    Returns the number of items migrated.
    """
    import json

    with open(json_path) as f:
        data = json.load(f)

    db = CheckpointDB(db_path)

    completed = data.get("completed", [])
    if completed:
        db.mark_done_batch(completed)

    # Migrate other state
    for key in ["last_index"]:
        if key in data:
            db.set_state(key, str(data[key]))

    # OAI-PMH tokens
    for key, val in data.get("tokens", {}).items():
        if val:
            db.set_state(f"token:{key}", val)

    for s in data.get("completed_sets", []):
        db.set_state(f"set_done:{s}", "1")

    count = db.count_done()
    db.close()
    return count


def dedup_csv(csv_path: str, id_column: str, output_path: str = None, in_place: bool = False) -> tuple:
    """
    Remove duplicate rows from a CSV based on an ID column.
    Returns (total_rows, unique_rows, dupes_removed).
    SAFETY: Will NOT write in-place unless in_place=True is explicitly set.
    If id_column is missing or all values are empty, aborts without writing.
    """
    import csv

    if output_path is None and not in_place:
        # Dry-run: count dupes but don't overwrite
        pass
    elif output_path is None:
        output_path = csv_path

    rows = []
    seen = set()
    dupes = 0
    empty_ids = 0

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames

        if id_column not in (fieldnames or []):
            raise ValueError(
                f"Column '{id_column}' not found in {csv_path}. "
                f"Available: {fieldnames}"
            )

        for row in reader:
            rid = row.get(id_column, "")
            if not rid:
                empty_ids += 1
            if rid in seen:
                dupes += 1
                continue
            seen.add(rid)
            rows.append(row)

    total = len(rows) + dupes

    # Safety: abort if most IDs are empty (wrong column)
    if empty_ids > total * 0.5:
        raise ValueError(
            f"Column '{id_column}' is empty in {empty_ids}/{total} rows. "
            f"Wrong ID column? Aborting to prevent data loss."
        )

    # Only write if we have an output path
    if output_path:
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    return total, len(rows), dupes


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Checkpoint & dedup utilities")
    sub = parser.add_subparsers(dest="cmd")

    # Migrate JSON → SQLite
    mig = sub.add_parser("migrate", help="Migrate JSON checkpoint to SQLite")
    mig.add_argument("json_path")
    mig.add_argument("db_path")

    # Dedup CSV
    dd = sub.add_parser("dedup", help="Deduplicate a CSV by ID column")
    dd.add_argument("csv_path")
    dd.add_argument("--id-column", default="uuid")
    dd.add_argument("--output", default=None)

    # Stats
    st = sub.add_parser("stats", help="Show checkpoint stats")
    st.add_argument("db_path")

    args = parser.parse_args()

    if args.cmd == "migrate":
        count = migrate_json_checkpoint(args.json_path, args.db_path)
        print(f"Migrated {count} items to {args.db_path}")

    elif args.cmd == "dedup":
        total, unique, dupes = dedup_csv(args.csv_path, args.id_column, args.output)
        print(f"Total: {total}, Unique: {unique}, Duplicates removed: {dupes}")

    elif args.cmd == "stats":
        db = CheckpointDB(args.db_path)
        print(f"Completed items: {db.count_done()}")
        # Show state entries
        for row in db.conn.execute("SELECT key, value FROM state"):
            val = row[1][:60] if row[1] else "null"
            print(f"  {row[0]}: {val}")
        db.close()

    else:
        parser.print_help()
