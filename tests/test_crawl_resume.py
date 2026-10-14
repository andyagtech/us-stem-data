"""A resume file may never run ahead of the data.

The crawlers here hold rows in memory and write at the end. One ran for
37 minutes, marked 233 departments done, and was killed: the rows lived
only in that process, and the resume file said never look again. That
is the failure this module exists to make impossible -- every caller
stores first and marks second -- and these tests pin the behaviour the
callers rely on.

The other half is what gets recorded. Each crawler used to derive its
skip set from its own OUTPUT, so only the addresses that produced
something were remembered: 304 faculty profiles that led nowhere were
followed again on every run, and --limit kept being spent on them. A
page that was tried and failed is a result.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import crawl_resume                                           # noqa: E402


@pytest.fixture
def resume(tmp_path, monkeypatch):
    monkeypatch.setattr(crawl_resume, "DIR", tmp_path)
    r = crawl_resume.Resume("unit")
    yield r


def test_starts_empty(resume):
    assert len(resume) == 0
    assert "http://a" not in resume


def test_a_mark_survives_a_restart_of_the_process(resume, tmp_path,
                                                  monkeypatch):
    resume.mark("http://a")
    monkeypatch.setattr(crawl_resume, "DIR", tmp_path)
    again = crawl_resume.Resume("unit")
    assert "http://a" in again


def test_marking_is_written_immediately(resume):
    """Not buffered: a kill between two marks must not lose the first."""
    resume.mark("http://a")
    assert resume.path.exists()
    assert "http://a" in json.loads(resume.path.read_text())["tried"]


def test_a_failure_is_recorded_like_a_success(resume):
    """The whole point. Nothing here knows or cares what came back."""
    resume.mark_many(["http://found", "http://nothing-there"])
    assert len(resume) == 2


def test_seed_only_applies_before_the_file_exists(resume):
    assert resume.seed(["http://a", "http://b"]) == 2
    assert resume.seed(["http://c"]) == 0, (
        "a seed after the first run would overwrite real history with a "
        "guess about it")
    assert "http://c" not in resume


def test_reset_clears_the_file(resume):
    resume.mark("http://a")
    resume.reset()
    assert len(resume) == 0
    assert not resume.path.exists()


def test_a_truncated_file_is_ignored_not_trusted(resume, tmp_path,
                                                 monkeypatch):
    """Half a resume file is a permanent gap; repeated work is not."""
    resume.mark("http://a")
    resume.path.write_text('{"tried": ["http://a", "http://')
    monkeypatch.setattr(crawl_resume, "DIR", tmp_path)
    again = crawl_resume.Resume("unit")
    assert len(again) == 0


def test_reads_the_older_key_names(resume, tmp_path, monkeypatch):
    """discover_research_labs wrote "departments"; walk wrote lists."""
    resume.path.write_text(json.dumps({"departments": ["http://a"]}))
    monkeypatch.setattr(crawl_resume, "DIR", tmp_path)
    again = crawl_resume.Resume("unit")
    assert "http://a" in again


EXPECTED = {
    "discover_research_labs.py": "discover",
    "follow_lab_links.py": "follow_profiles",
    "find_lab_member_pages.py": "member_pages",
    "retry_failed_rosters.py": "retry_rosters",
}


@pytest.mark.parametrize("script,name", sorted(EXPECTED.items()))
def test_every_long_crawler_can_resume_and_restart(script, name):
    src = (ROOT / "scripts" / script).read_text()
    assert f'Resume("{name}"' in src, f"{script} keeps no resume file"
    assert "--restart" in src, f"{script} offers no way to start over"


@pytest.mark.parametrize("script", sorted(EXPECTED))
def test_every_long_crawler_stores_before_it_marks(script):
    """The order is the invariant, so it is read off the source.

    In each flush(), the store happens above the mark_many() call. A
    future edit that swaps them is the bug this whole module is for.
    """
    src = (ROOT / "scripts" / script).read_text()
    body = src[src.index("def flush()"):]
    body = body[:body.index("\n    try:")] if "\n    try:" in body else body
    mark = body.index("resume.mark_many(")
    stores = [body.index(t) for t in ("lab_store.merge(", "OUT.write_text(")
              if t in body[:mark] or t in body]
    assert stores, f"{script}: flush() stores nothing"
    assert min(stores) < mark, (
        f"{script}: flush() marks the resume file before storing the rows")


@pytest.mark.parametrize("script", sorted(EXPECTED))
def test_every_long_crawler_flushes_on_the_way_out(script):
    """An interrupt must keep what is in hand, not discard it."""
    src = (ROOT / "scripts" / script).read_text()
    assert "KeyboardInterrupt" in src, f"{script} discards a Ctrl-C"
    assert "finally:" in src and "flush()" in src, (
        f"{script} does not store what it holds when it stops")


class _Resp:
    def __init__(self, status, headers=None, text="<html>x</html>"):
        self.status_code = status
        self.headers = headers or {"content-type": "text/html"}
        self.text = text
        self.url = "http://x/"


def test_a_429_is_waited_on_not_recorded_as_a_failure(monkeypatch):
    """A university asking us to slow down is not a dead page.

    The widened crawl collected 12 rows with status http_429, which
    reads downstream exactly like a 404.
    """
    import discover_research_labs as d

    calls = []
    slept = []
    monkeypatch.setattr(d.time, "sleep", lambda s: slept.append(s))

    def fake(url, **kw):
        calls.append(url)
        return _Resp(429 if len(calls) == 1 else 200)

    monkeypatch.setattr(d.requests, "get", fake)
    code, html, final = d.get("http://x/")
    assert code == 200, "a 429 should be retried, not returned"
    assert len(calls) == 2
    assert slept, "nothing waited before retrying"


def test_a_timeout_is_not_retried(monkeypatch):
    """Retrying a host that timed out doubles the cost for one answer."""
    import discover_research_labs as d
    calls = []

    def fake(url, **kw):
        calls.append(url)
        raise d.requests.Timeout()

    monkeypatch.setattr(d.requests, "get", fake)
    monkeypatch.setattr(d.time, "sleep", lambda s: None)
    assert d.get("http://x/")[0] == 0
    assert len(calls) == 1


def test_a_connection_error_is_retried_once(monkeypatch):
    """http_0 used to read like a page that is really gone."""
    import discover_research_labs as d
    calls = []

    def fake(url, **kw):
        calls.append(url)
        if len(calls) == 1:
            raise d.requests.ConnectionError()
        return _Resp(200)

    monkeypatch.setattr(d.requests, "get", fake)
    monkeypatch.setattr(d.time, "sleep", lambda s: None)
    assert d.get("http://x/")[0] == 200
    assert len(calls) == 2


def test_the_connect_timeout_is_separate_from_the_read(monkeypatch):
    """A scalar timeout spends its whole budget on the handshake."""
    import discover_research_labs as d
    seen = {}

    def fake(url, **kw):
        seen.update(kw)
        return _Resp(200)

    monkeypatch.setattr(d.requests, "get", fake)
    d.get("http://x/", timeout=15)
    assert isinstance(seen.get("timeout"), tuple), (
        "connect and read share one budget")
    assert seen["timeout"][0] <= 10
