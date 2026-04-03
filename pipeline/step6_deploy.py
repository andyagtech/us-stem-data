"""
Step 6: DEPLOY — Sync site to S3 and invalidate CloudFront cache.

Input:  site/ directory (HTML + JSON + assets)
Output: S3 bucket updated, CloudFront cache invalidated
"""
from __future__ import annotations
import subprocess
from datetime import datetime
from pathlib import Path

from .state import PipelineState, StepOutcome


S3_BUCKET = "s3://phd-demographics-andy-barr/"
CLOUDFRONT_DISTRIBUTION = "E3IYHYCEQPE00Q"
AWS_PROFILE = "personal"


def step6_deploy(state: PipelineState) -> PipelineState:
    """Deploy site to S3 and invalidate CloudFront."""
    if state.should_halt():
        return state

    base_dir = state.config.base_dir
    site_dir = base_dir / "site"
    print("\n[Step 6: DEPLOY] Syncing to S3...")

    # S3 sync
    result = subprocess.run(
        ["aws", "s3", "sync", str(site_dir) + "/", S3_BUCKET,
         "--profile", AWS_PROFILE, "--exclude", ".DS_Store"],
        capture_output=True, text=True,
    )

    if result.returncode != 0:
        outcome = StepOutcome.err("deploy", message="S3 sync failed", errors=(result.stderr[:200],))
        print(f"  S3 FAILED: {result.stderr[:100]}")
        return state.with_outcome(outcome)

    # Count uploaded files
    uploaded = result.stdout.count("upload:")
    print(f"  S3: {uploaded} files uploaded")

    # CloudFront invalidation
    print("  Invalidating CloudFront cache...")
    cf_result = subprocess.run(
        ["aws", "cloudfront", "create-invalidation",
         "--distribution-id", CLOUDFRONT_DISTRIBUTION,
         "--paths", "/*",
         "--profile", AWS_PROFILE],
        capture_output=True, text=True,
    )

    if cf_result.returncode != 0:
        outcome = StepOutcome.ok(
            "deploy",
            message=f"S3 synced ({uploaded} files) but CloudFront invalidation failed",
            data={"uploaded": uploaded, "cloudfront": False},
        )
    else:
        outcome = StepOutcome.ok(
            "deploy",
            message=f"Deployed: {uploaded} files synced, CloudFront invalidated",
            data={"uploaded": uploaded, "cloudfront": True},
        )
        print("  CloudFront: invalidation started")

    return state.with_outcome(outcome)
