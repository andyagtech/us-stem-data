"""The incremental deploy must stay complete while it stops re-uploading.

A build is served from its own prefix, so it has to hold every file the site
has -- anything missing is a 404 the moment the origin moves. Skipping
unchanged uploads is therefore a correctness risk, not just a speed change:
the failure it can produce is a file silently left out.

These tests pin the plan (what a build must contain), the diff (what is worth
uploading), and the guards that stand between a wrong diff and the origin flip.
"""
from pathlib import Path

import pytest

from pipeline import step6_deploy as d


def _site(tmp_path: Path) -> Path:
    site = tmp_path / "site"
    (site / "universities" / "nonstem").mkdir(parents=True)
    (site / "data" / "stem").mkdir(parents=True)
    (site / "og").mkdir()
    (site / "index.html").write_text("<html>index</html>")
    (site / "style.css").write_text("body{}")
    (site / "sitemap.xml").write_text("<urlset/>")
    (site / "robots.txt").write_text("User-agent: *")
    (site / "universities" / "mit.html").write_text("<html>mit</html>")
    (site / "universities" / "nonstem" / "mit.html").write_text("<html>mit ns</html>")
    (site / "data" / "stem" / "mit.json").write_text('{"k":1}')
    (site / "og" / "mit.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (site / ".DS_Store").write_text("junk")
    return site


# --- the plan ----------------------------------------------------------

def test_the_plan_covers_every_file_including_subdirectories(tmp_path):
    site = _site(tmp_path)
    keys = {o.key for o in d._plan_objects(site)}
    assert keys == {
        "index.html", "style.css", "sitemap.xml", "robots.txt",
        "universities/mit.html", "universities/nonstem/mit.html",
        "data/stem/mit.json", "og/mit.png",
    }, "a build that omits a file serves a 404 for it"


def test_dotfiles_stay_out_of_the_build(tmp_path):
    site = _site(tmp_path)
    assert not [o for o in d._plan_objects(site) if ".DS_Store" in o.key]


def test_every_planned_object_has_a_real_content_type(tmp_path):
    site = _site(tmp_path)
    by_key = {o.key: o for o in d._plan_objects(site)}
    assert by_key["sitemap.xml"].ctype == "application/xml"
    assert by_key["robots.txt"].ctype.startswith("text/plain")
    assert by_key["style.css"].ctype.startswith("text/css")
    assert by_key["index.html"].ctype.startswith("text/html")


def test_university_pages_ship_compressed_and_small_json_does_not(tmp_path):
    site = _site(tmp_path)
    by_key = {o.key: o for o in d._plan_objects(site)}
    assert by_key["universities/mit.html"].gz
    assert by_key["universities/nonstem/mit.html"].gz
    assert not by_key["index.html"].gz, "top-level HTML is left to CloudFront"
    assert not by_key["data/stem/mit.json"].gz


def test_json_over_the_cloudfront_ceiling_is_pre_compressed(tmp_path):
    site = _site(tmp_path)
    big = site / "data" / "_search.json"
    big.write_bytes(b"x" * (d.CLOUDFRONT_COMPRESS_MAX + 1))
    by_key = {o.key: o for o in d._plan_objects(site)}
    assert by_key["data/_search.json"].gz, (
        "CloudFront does not compress above its ceiling, so this would ship raw"
    )


def test_a_stray_gzip_beside_its_source_is_not_shipped(tmp_path):
    site = _site(tmp_path)
    (site / "universities" / "mit.html.gz").write_bytes(b"\x1f\x8b junk")
    keys = {o.key for o in d._plan_objects(site)}
    assert "universities/mit.html.gz" not in keys
    assert "universities/mit.html" in keys


# --- the diff ----------------------------------------------------------

def test_identical_content_fingerprints_identically(tmp_path):
    site = _site(tmp_path)
    a = {o.key: d._fingerprint(o) for o in d._plan_objects(site)}
    b = {o.key: d._fingerprint(o) for o in d._plan_objects(site)}
    assert a == b, "an unstable fingerprint re-uploads the whole site every time"


def test_changing_a_file_changes_only_its_fingerprint(tmp_path):
    site = _site(tmp_path)
    before = {o.key: d._fingerprint(o) for o in d._plan_objects(site)}
    (site / "index.html").write_text("<html>edited</html>")
    after = {o.key: d._fingerprint(o) for o in d._plan_objects(site)}
    assert {k for k in after if after[k] != before[k]} == {"index.html"}


def test_changing_the_cache_rule_re_uploads_the_file(tmp_path, monkeypatch):
    site = _site(tmp_path)
    before = {o.key: d._fingerprint(o) for o in d._plan_objects(site)}
    monkeypatch.setitem(d.CACHE_RULES, ".css", "public, max-age=1")
    after = {o.key: d._fingerprint(o) for o in d._plan_objects(site)}
    assert after["style.css"] != before["style.css"], (
        "headers are part of the object; a rule change has to ship"
    )


def test_gzip_produces_a_file_outside_the_site_tree(tmp_path):
    site = _site(tmp_path)
    src = site / "universities" / "mit.html"
    gz = d._gzip_to_temp(src)
    try:
        assert site not in gz.parents, (
            "a compressed copy inside site/ becomes a build object if the "
            "deploy is killed before it is cleaned up"
        )
        import gzip as _g
        assert _g.decompress(gz.read_bytes()) == src.read_bytes()
    finally:
        gz.unlink(missing_ok=True)


# --- the guards --------------------------------------------------------

def test_the_live_build_is_read_from_cloudfront_not_from_s3(monkeypatch):
    """Seeding from the newest prefix would carry a failed deploy's gaps."""
    class R:
        returncode = 0
        stdout = ('{"DistributionConfig":{"Origins":{"Items":'
                  '[{"OriginPath":"/v/20260101T000000Z"}]}}}')
    monkeypatch.setattr(d, "_aws", lambda *a, **k: R())
    assert d._live_build_id() == "20260101T000000Z"


@pytest.mark.parametrize("path", ["", "/", "/v/b", "/v/notabuild", "/other"])
def test_a_non_build_origin_yields_no_seed(monkeypatch, path):
    class R:
        returncode = 0
        stdout = ('{"DistributionConfig":{"Origins":{"Items":'
                  '[{"OriginPath":"%s"}]}}}' % path)
    monkeypatch.setattr(d, "_aws", lambda *a, **k: R())
    assert d._live_build_id() is None, f"{path!r} must not be seeded from"


def test_a_manifest_from_another_version_is_ignored(monkeypatch):
    """A format change must force a full upload, not a bad diff."""
    class C:
        def get_object(self, **kw):
            import io, json
            return {"Body": io.BytesIO(json.dumps(
                {"version": d._MANIFEST_VERSION + 1,
                 "objects": {"a.html": "deadbeef"}}).encode())}
    assert d._load_manifest(C(), "20260101T000000Z") == {}


def test_an_unreadable_manifest_falls_back_to_a_full_upload():
    class C:
        def get_object(self, **kw):
            raise RuntimeError("NoSuchKey")
    assert d._load_manifest(C(), "20260101T000000Z") == {}


def test_the_manifest_is_stored_outside_the_served_prefix():
    """Anything under v/{build}/ is reachable from the site; this is not."""
    assert not d._MANIFEST_PREFIX.startswith(d.BUILD_PREFIX + "/")
    seen = {}

    class C:
        def put_object(self, **kw):
            seen.update(kw)
    d._write_manifest(C(), "20260101T000000Z", {"a.html": "abc"})
    assert seen["Key"] == "manifests/20260101T000000Z.json"
    assert not seen["Key"].startswith("v/")
