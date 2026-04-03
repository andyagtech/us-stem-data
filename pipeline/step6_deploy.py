"""
Step 6: DEPLOY — Pre-compress, sync to S3, and invalidate CloudFront.

Pre-compresses JSON files with gzip before uploading for optimal performance.
Sets appropriate Cache-Control headers by file type.

Input:  site/ directory (HTML + JSON + assets)
Output: S3 bucket updated with compressed files, CloudFront cache invalidated
"""
from __future__ import annotations
import gzip
import os
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

from .state import PipelineState, StepOutcome


S3_BUCKET = "phd-demographics-andy-barr"
S3_URI = f"s3://{S3_BUCKET}/"
CLOUDFRONT_DISTRIBUTION = "E3IYHYCEQPE00Q"
AWS_PROFILE = "personal"

# Cache-Control by file type
CACHE_RULES = {
    ".html": "public, max-age=300, stale-while-revalidate=86400",  # 5 min + stale ok for 24h
    ".json": "public, max-age=3600",  # 1 hour
    ".js": "public, max-age=604800",  # 1 week
    ".ico": "public, max-age=604800",
    ".png": "public, max-age=604800",
}

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".json": "application/json",
    ".js": "application/javascript",
    ".ico": "image/x-icon",
    ".png": "image/png",
}


def _gzip_file(src: Path) -> Path:
    """Gzip a file, return path to the compressed version."""
    gz_path = src.with_suffix(src.suffix + ".gz")
    with open(src, "rb") as f_in:
        with gzip.open(str(gz_path), "wb", compresslevel=9) as f_out:
            f_out.write(f_in.read())
    return gz_path


def step6_deploy(state: PipelineState) -> PipelineState:
    """Deploy site to S3 with pre-compression and cache headers."""
    if state.should_halt():
        return state

    base_dir = state.config.base_dir
    site_dir = base_dir / "site"
    print("\n[Step 6: DEPLOY] Deploying to S3 with compression...")

    uploaded = 0
    errors = []

    # Step 1: Upload HTML files (uncompressed, short cache)
    print("  Uploading HTML files...")
    for f in site_dir.glob("*.html"):
        key = f.name
        cache = CACHE_RULES.get(".html", "public, max-age=300")
        ctype = CONTENT_TYPES.get(".html", "text/html")
        result = subprocess.run(
            ["aws", "s3", "cp", str(f), f"{S3_URI}{key}",
             "--profile", AWS_PROFILE,
             "--cache-control", cache,
             "--content-type", ctype],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            uploaded += 1

    # Step 2: Upload JSON data files (pre-compressed with gzip)
    print("  Pre-compressing and uploading JSON data...")
    for mode in ["stem", "nonstem"]:
        data_dir = site_dir / "data" / mode
        if not data_dir.is_dir():
            continue
        for f in sorted(data_dir.glob("*.json")):
            key = f"data/{mode}/{f.name}"
            try:
                gz_path = _gzip_file(f)
                result = subprocess.run(
                    ["aws", "s3", "cp", str(gz_path), f"{S3_URI}{key}",
                     "--profile", AWS_PROFILE,
                     "--cache-control", CACHE_RULES.get(".json", "public, max-age=3600"),
                     "--content-type", "application/json",
                     "--content-encoding", "gzip"],
                    capture_output=True, text=True,
                )
                gz_path.unlink()  # Clean up temp gzip file
                if result.returncode == 0:
                    uploaded += 1
                else:
                    errors.append(f"Upload failed: {key}")
            except Exception as e:
                errors.append(f"Compress/upload failed: {key}: {e}")

    # Step 3: Upload static assets
    print("  Uploading static assets...")
    for ext in [".ico", ".png", ".js"]:
        for f in site_dir.glob(f"*{ext}"):
            key = f.name
            cache = CACHE_RULES.get(ext, "public, max-age=604800")
            ctype = CONTENT_TYPES.get(ext, "application/octet-stream")
            result = subprocess.run(
                ["aws", "s3", "cp", str(f), f"{S3_URI}{key}",
                 "--profile", AWS_PROFILE,
                 "--cache-control", cache,
                 "--content-type", ctype],
                capture_output=True, text=True,
            )
            if result.returncode == 0:
                uploaded += 1

    print(f"  Uploaded {uploaded} files")

    # Step 4: CloudFront invalidation
    print("  Invalidating CloudFront cache...")
    cf_result = subprocess.run(
        ["aws", "cloudfront", "create-invalidation",
         "--distribution-id", CLOUDFRONT_DISTRIBUTION,
         "--paths", "/*",
         "--profile", AWS_PROFILE],
        capture_output=True, text=True,
    )

    cf_ok = cf_result.returncode == 0
    if cf_ok:
        print("  CloudFront: invalidation started")
    else:
        print(f"  CloudFront: FAILED")
        errors.append("CloudFront invalidation failed")

    data = {"uploaded": uploaded, "cloudfront": cf_ok, "errors": len(errors)}
    if errors:
        outcome = StepOutcome(
            step_name="deploy", university_key="", success=True,
            message=f"Deployed {uploaded} files ({len(errors)} errors)",
            data=data, errors=tuple(errors[:5]), warnings=(),
            timestamp=datetime.utcnow().isoformat(),
        )
    else:
        outcome = StepOutcome.ok(
            "deploy",
            message=f"Deployed: {uploaded} files (pre-compressed), CloudFront invalidated",
            data=data,
        )

    return state.with_outcome(outcome)
