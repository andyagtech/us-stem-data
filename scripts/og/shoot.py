#!/usr/bin/env python3
"""Screenshot card HTML to 1200x630 PNGs with headless Chrome, in parallel."""
import os
import shutil
import subprocess
import time
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
W, H = 1200, 630


def _complete_png(path):
    """True once the file on disk is a whole PNG (IEND chunk present)."""
    try:
        with open(path, "rb") as f:
            if f.read(8) != b"\x89PNG\r\n\x1a\n":
                return False
            f.seek(-12, os.SEEK_END)
            return f.read()[4:8] == b"IEND"
    except OSError:
        return False


def _shoot(job, timeout=90):
    """Chrome on this machine writes the screenshot and then hangs on shutdown,
    so we poll for a complete PNG and kill the process ourselves rather than
    waiting on exit."""
    html_path, png_path = job
    Path(png_path).unlink(missing_ok=True)
    profile = tempfile.mkdtemp(prefix="ogchrome-")
    proc = subprocess.Popen(
        [CHROME, "--headless", "--disable-gpu", "--no-sandbox",
         "--hide-scrollbars", "--force-device-scale-factor=1",
         "--disable-lcd-text", "--font-render-hinting=none",
         "--no-first-run", "--no-default-browser-check",
         "--disable-extensions", "--disable-dev-shm-usage",
         "--disable-background-networking", "--no-pdf-header-footer",
         f"--user-data-dir={profile}",
         "--virtual-time-budget=2000",
         f"--window-size={W},{H}",
         f"--screenshot={png_path}",
         f"file://{html_path}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    try:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if _complete_png(png_path):
                break
            if proc.poll() is not None:
                time.sleep(0.2)
                break
            time.sleep(0.15)
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(3)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(5)
        try:
            err = (proc.stderr.read() or b"")[-400:].decode(errors="replace")
        except Exception:
            err = ""
        proc.stderr.close()
        shutil.rmtree(profile, ignore_errors=True)
    if not _complete_png(png_path) or Path(png_path).stat().st_size < 2000:
        return png_path, False, err
    return png_path, True, ""


def shoot_all(jobs, workers=None, quiet=False, retries=2):
    """jobs: [(html_path, png_path)] -> (ok_count, [failures])

    Concurrent Chrome instances occasionally lose a crashpad handshake and drop
    a screenshot; on a 237-card run that cost six cards. Failures are retried,
    the last attempt serially, which clears them.
    """
    workers = workers or max(2, min(4, (os.cpu_count() or 4) // 2))
    done, fails = {}, []
    pending = list(jobs)
    by_png = {png: (html, png) for html, png in jobs}
    for attempt in range(retries + 1):
        w = 1 if attempt == retries else workers
        fails = []
        with ThreadPoolExecutor(max_workers=w) as ex:
            for i, (png, good, err) in enumerate(ex.map(_shoot, pending), 1):
                if good:
                    done[png] = True
                else:
                    fails.append((png, err))
                if not quiet and (i % 25 == 0 or i == len(pending)):
                    label = "" if attempt == 0 else f" (retry {attempt})"
                    print(f"    rendered {i}/{len(pending)}{label}", flush=True)
        if not fails:
            break
        pending = [by_png[png] for png, _ in fails]
        if not quiet:
            print(f"    {len(fails)} failed, retrying", flush=True)
    return len(done), fails


def png_size(path):
    """Read width/height straight out of the PNG IHDR."""
    with open(path, "rb") as f:
        head = f.read(33)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return int.from_bytes(head[16:20], "big"), int.from_bytes(head[20:24], "big")
