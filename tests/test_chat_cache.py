"""The assistant's answer cache, and what must invalidate it.

These are offline tests: they read the knowledge directory and compute a
fingerprint. Nothing here calls the Lambda or OpenAI, which is why they live
apart from test_chat_assistant.py -- that suite is skipped unless
RUN_CHAT_INTEGRATION=1, and a check that only runs on request is a check that
does not run.
"""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


class TestKnowledgeInvalidatesTheCache:
    """A knowledge change must invalidate cached answers.

    The gap this closes was real and it was embarrassing. A knowledge file was
    added saying the PERM files DO carry the worker's citizenship. Asked
    afterwards, the deployed assistant still answered that they do not, word
    for word, from an answer cached before the file existed. The corpus had not
    been rebuilt, so the data version had not moved, so nothing invalidated it.
    """

    def _cache(self):
        import importlib
        import sys
        sys.path.insert(0, str(ROOT / "cloud" / "chat"))
        import cache
        importlib.reload(cache)
        return cache

    def test_the_version_carries_a_knowledge_fingerprint(self):
        cache = self._cache()
        assert cache.knowledge_version() in cache.data_version()

    def test_the_fingerprint_is_stable_across_calls(self):
        """It is computed once per container; a version that changed per call
        would make every answer a cache miss."""
        cache = self._cache()
        assert cache.knowledge_version() == cache.knowledge_version()

    def test_editing_a_knowledge_file_moves_the_fingerprint(self, tmp_path):
        cache = self._cache()
        before = cache.knowledge_version()
        kb = ROOT / "cloud" / "chat" / "knowledge"
        victim = sorted(kb.glob("*.md"))[0]
        original = victim.read_bytes()
        try:
            victim.write_bytes(original + b"\n<!-- cache fingerprint probe -->\n")
            cache._KB_FINGERPRINT = None
            assert cache.knowledge_version() != before
        finally:
            victim.write_bytes(original)
            cache._KB_FINGERPRINT = None
        assert cache.knowledge_version() == before

    def test_the_fingerprint_ignores_mtime(self):
        """A redeploy of unchanged prose should keep its cache. Unzipping sets
        a new mtime on every file, so an mtime-based stamp would flush the
        cache on every deploy and make it worthless."""
        cache = self._cache()
        before = cache.knowledge_version()
        victim = sorted((ROOT / "cloud" / "chat" / "knowledge").glob("*.md"))[0]
        victim.touch()
        cache._KB_FINGERPRINT = None
        assert cache.knowledge_version() == before
