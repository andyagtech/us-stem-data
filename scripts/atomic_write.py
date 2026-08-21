#!/usr/bin/env python3
"""Write a file completely or not at all.

Why this exists: on 2026-08-20 `build_tuition_revenue.py` raised part-way
through `main()`. Its output file was left holding the PREVIOUS run's content,
the script printed nothing about it, and the site went on serving figures that
no longer corresponded to any run of the code. That is the same shape as the
duckdb failure that shipped an April snapshot for four months -- a build that
fails without failing loudly.

Writing to a temporary file in the same directory and renaming it makes the
replacement atomic on POSIX: a reader sees either the old file or the new one,
never a truncated one, and a crash before the rename leaves the old file
untouched and obviously stale rather than subtly wrong.

    from atomic_write import write_json, write_text
    write_json(OUT, payload, indent=1)
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


def write_text(path: str | Path, text: str, encoding: str = "utf-8") -> Path:
    """Replace `path` with `text` atomically."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.",
                               suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding=encoding) as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        # Leave the existing file alone and take the temp file with us.
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return path


def write_bytes(path: str | Path, blob: bytes) -> Path:
    """Replace `path` with `blob` atomically."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.",
                               suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(blob)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return path


def write_json(path: str | Path, obj: Any, **dumps_kwargs: Any) -> Path:
    """Serialise `obj` and replace `path` atomically."""
    dumps_kwargs.setdefault("ensure_ascii", False)
    return write_text(path, json.dumps(obj, **dumps_kwargs))
