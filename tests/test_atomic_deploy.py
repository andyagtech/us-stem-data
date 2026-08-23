"""The deploy must be all-or-nothing.

The old scheme wrote file-by-file into the bucket root over ~15 minutes. A
deploy killed midway left the live site genuinely mixed -- some pages new,
some old -- with nothing to detect it, because verify_deploy samples ten
files. One WAS killed during this project and did no damage only because it
died before the first upload rather than during it.

Builds now go to their own prefix and the site is switched by moving the
CloudFront origin path, which is a single API call.
"""
import json
from unittest import mock

import pytest

from pipeline import step6_deploy as D


def _cfg(origin_path=""):
    return json.dumps({"ETag": "E1",
                       "DistributionConfig": {
                           "Origins": {"Items": [{"Id": "s3",
                                                  "OriginPath": origin_path}]}}})


def test_a_short_upload_is_never_published():
    """The whole point: refuse rather than switch to a half-uploaded build."""
    with mock.patch.object(D, "_count_objects", return_value=400):
        ok, why = D._publish_build("20260823T000000Z", expected=733)
    assert not ok
    assert "partial" in why and "400" in why


def test_an_unlistable_build_is_never_published():
    with mock.patch.object(D, "_count_objects", return_value=-1):
        ok, why = D._publish_build("b", expected=10)
    assert not ok and "list" in why


def test_a_complete_upload_moves_the_origin_path():
    calls = []

    def fake(*args, **kw):
        calls.append(args)
        r = mock.Mock(returncode=0, stderr="")
        r.stdout = _cfg("") if args[1] == "get-distribution-config" else ""
        return r

    with mock.patch.object(D, "_count_objects", return_value=733), \
         mock.patch.object(D, "_aws", side_effect=fake):
        ok, why = D._publish_build("20260823T000000Z", expected=733)
    assert ok, why
    assert any("update-distribution" in a for a in calls[-1])


def test_publishing_the_current_build_again_is_a_no_op():
    def fake(*args, **kw):
        r = mock.Mock(returncode=0, stderr="")
        r.stdout = _cfg("/v/B") if args[1] == "get-distribution-config" else ""
        return r
    with mock.patch.object(D, "_count_objects", return_value=5), \
         mock.patch.object(D, "_aws", side_effect=fake):
        ok, why = D._publish_build("B", expected=5)
    assert ok and why == "already current"


def test_prune_keeps_the_live_build_and_a_rollback_margin():
    """A rollback target has to still exist, so never prune to nothing."""
    listing = "".join(f"                           PRE b{i}/\n" for i in range(1, 8))
    removed = []

    def fake(*args, **kw):
        if args[1] == "ls":
            return mock.Mock(returncode=0, stdout=listing, stderr="")
        if args[1] == "rm":
            removed.append(args[2])
        return mock.Mock(returncode=0, stdout="", stderr="")

    with mock.patch.object(D, "_aws", side_effect=fake):
        D._prune_old_builds("b7")
    assert len(removed) == 7 - D.KEEP_BUILDS
    assert not any("b7" in r for r in removed), removed


def test_the_publish_gate_still_holds_with_a_sweep():
    """The sweep raises the object count; the short-upload gate must survive.

    The gate compares what S3 holds against what the run reported uploading.
    A sweep that adds files must not push the tally out of step and start
    rejecting complete builds.
    """
    with mock.patch.object(D, "_count_objects", return_value=738):
        ok, why = D._publish_build("b", expected=738)
    # Only the count check runs before the CloudFront calls; a matching count
    # must not be the thing that fails.
    assert "partial" not in (why or ""), why


def test_content_type_and_cache_exist_for_css():
    """/style.css returned 403 because .css was not in the upload list at all,
    taking every design token with it."""
    assert D.CONTENT_TYPES[".css"].startswith("text/css")
    assert "max-age" in D.CACHE_RULES[".css"]
