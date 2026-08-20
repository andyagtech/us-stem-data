"""Answer cache for the assistant: exact match, then semantic.

WHY CACHE AT ALL

Every question currently reaches OpenAI. That is the one uncapped cost in this
system -- AWS is behind a free tier and a rate limit, OpenAI is billed directly
and no alarm sees it. A page built to attract attention will get thousands of
people asking the same twenty questions, and paying a model to re-derive "what
is the finding?" from scratch each time is the expensive way to be popular.

WHY CACHING THIS ASSISTANT IS NOT TRIVIAL

The whole design of this chat is that no figure exists until a tool returns it
in THIS conversation. A cached answer is, by construction, a figure from an
earlier conversation. Three things therefore go into the key, and one turn type
is refused outright:

  data version   The answer embeds numbers from a particular build of
                 chat_data/. When the corpus is rebuilt, every cached answer is
                 stale. The site map's `version` field stamps the build, so a
                 rebuild invalidates the whole cache without anyone remembering
                 to flush it.

  page context   The system prompt carries which page the reader is on, and the
                 assistant is told it may auto-navigate there. The same words
                 asked from /stem.html and from a university page should not
                 return the same blocks.

  the question   Normalised: lowercased, punctuation stripped, whitespace
                 collapsed. "What's the finding?" and "what is the finding"
                 share an entry.

  REFUSED        Any turn with conversation history. A follow-up means "of
                 those, which is highest?" and its answer depends on what came
                 before. Caching first turns only is the difference between a
                 cache and a wrong answer.

EXACT THEN SEMANTIC

The exact layer is a hash lookup and costs nothing. The semantic layer catches
"which school is worst" against a stored "what university has the highest
share" -- an embedding call (text-embedding-3-small, fractions of a cent) plus
cosine similarity against the stored vectors.

WHY NOT A VECTOR DATABASE, AND WHY NOT VALKEY

At the scale this operates -- hundreds of distinct questions, not millions --
brute-force cosine over a single DynamoDB query is microseconds of arithmetic
on data we already had to fetch. A vector database would be a second service to
run, pay for and keep in sync, buying nothing measurable.

Valkey or ElastiCache would be worth it at sustained high QPS where DynamoDB
round-trips dominate. It is an always-on instance cost, and reaching it from
Lambda means VPC attachment, which adds cold-start latency and a NAT path. That
is the wrong trade for a service whose current traffic is zero and whose owner
is explicitly watching the bill. This module keeps its storage behind a small
interface so swapping DynamoDB for Valkey later is a contained change -- if
measurements ever justify it.

CONSERVATIVE BY DESIGN

The similarity threshold is high (0.94). A cache miss costs one model call. A
false hit answers a question the reader did not ask, on a site whose entire
value is being checkable. The failure modes are not symmetric, so the threshold
is set where false hits are rare rather than where the hit rate looks good.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import re
import time

logger = logging.getLogger()

CACHE_TABLE = os.environ.get("CHAT_CACHE_TABLE", "")
CACHE_TTL_DAYS = int(os.environ.get("CHAT_CACHE_TTL_DAYS", "14"))
# Measured, not guessed. text-embedding-3-small on this site's own questions:
#
#   0.881  "what is the main finding of this site"
#          vs "whats the main finding of this website"      trivial rewording
#   0.839  "how much do taxpayers spend per stem doctorate"
#          vs "what do taxpayers pay for each stem phd"     genuine paraphrase
#   0.641  "which field has the highest non resident share"
#          vs "what field has the largest foreign student share"
#   0.389  "what is the nra share at mit" vs "show me mit data"
#   0.141  "what is opt" vs "how many stem phds in 2024"    unrelated
#
# The first draft used 0.94, which nothing would ever have reached -- even
# swapping "site" for "website" only scores 0.881, so the semantic layer was
# dead on arrival. 0.82 sits in the wide gap between real paraphrases (0.839+)
# and the nearest non-match (0.641), which keeps false hits rare while the
# layer actually does something.
#
# The asymmetry still governs: a miss costs one model call, a false hit answers
# a question nobody asked on a site whose value is being checkable. When in
# doubt, raise this rather than lower it.
SIMILARITY_THRESHOLD = float(os.environ.get("CHAT_CACHE_SIMILARITY", "0.82"))
EMBED_MODEL = os.environ.get("CHAT_EMBED_MODEL", "text-embedding-3-small")
SEMANTIC_ENABLED = os.environ.get("CHAT_CACHE_SEMANTIC", "1") == "1"
MAX_SEMANTIC_CANDIDATES = 250

_table = None
_key_cache: str | None = None
_PUNCT = re.compile(r"[^\w\s]+")
_WS = re.compile(r"\s+")


# ---------------------------------------------------------------- keys

def normalise(question: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    q = _PUNCT.sub(" ", (question or "").lower())
    return _WS.sub(" ", q).strip()


def data_version() -> str:
    """Stamp of the current data build; changing it invalidates everything."""
    try:
        try:
            from . import data_store as ds
        except ImportError:
            import data_store as ds
        return str((ds.site_map() or {}).get("version") or "0")
    except Exception:                                   # noqa: BLE001
        return "0"


def page_key(page: dict | None) -> str:
    """Only the parts of page context that change an answer."""
    if not isinstance(page, dict):
        return "-"
    path = str(page.get("path") or "-")[:120]
    uni = str(page.get("university_key") or "")[:40]
    return f"{path}|{uni}" if uni else path


def cache_key(question: str, page: dict | None) -> str:
    raw = f"{data_version()}\x1f{page_key(page)}\x1f{normalise(question)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def cacheable(question: str, history: list | None) -> bool:
    """First turns only, and only questions worth storing."""
    if history:
        return False                       # a follow-up depends on its context
    q = normalise(question)
    return 8 <= len(q) <= 300


# ------------------------------------------------------------- storage

def _get_table():
    global _table
    if _table is None and CACHE_TABLE:
        try:
            import boto3
            _table = boto3.resource("dynamodb", region_name="us-east-1").Table(CACHE_TABLE)
        except Exception as e:                          # noqa: BLE001
            logger.warning("cache table unavailable: %s", e)
            _table = False
    return _table or None


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def _openai_key() -> str:
    """The OpenAI key, resolved the same way the handler resolves it.

    This read os.environ["OPENAI_API_KEY"] at first, but keys live in SSM and
    are read by parameter name -- so the lookup always came back empty and the
    semantic layer silently did nothing while the exact layer kept working.
    A cache that quietly degrades to half its function is worse than one that
    fails, because nothing looks wrong.
    """
    direct = os.environ.get("OPENAI_API_KEY", "")
    if direct:
        return direct
    ssm_name = os.environ.get("OPENAI_API_KEY_SSM", "")
    if not ssm_name:
        return ""
    global _key_cache
    if _key_cache is not None:
        return _key_cache
    try:
        import boto3
        resp = boto3.client("ssm", region_name="us-east-1").get_parameter(
            Name=ssm_name, WithDecryption=True)
        _key_cache = resp["Parameter"]["Value"]
    except Exception as e:                              # noqa: BLE001
        logger.info("cache: could not resolve the OpenAI key: %s", e)
        _key_cache = ""
    return _key_cache


def _embed(text: str) -> list[float] | None:
    """One embedding call. Returns None on any failure -- the cache is an
    optimisation and must never be able to fail a request."""
    if not SEMANTIC_ENABLED:
        return None
    key = _openai_key()
    if not key:
        return None
    try:
        import urllib.request
        req = urllib.request.Request(
            "https://api.openai.com/v1/embeddings",
            data=json.dumps({"model": EMBED_MODEL, "input": text[:800]}).encode(),
            headers={"Authorization": f"Bearer {key}",
                     "Content-Type": "application/json"},
            method="POST")
        with urllib.request.urlopen(req, timeout=6) as r:
            return json.loads(r.read())["data"][0]["embedding"]
    except Exception as e:                              # noqa: BLE001
        logger.info("embedding unavailable: %s", e)
        return None


# --------------------------------------------------------------- API

def lookup(question: str, page: dict | None, history: list | None = None):
    """Return (payload, how) where how is 'exact' | 'semantic', or (None, None)."""
    if not cacheable(question, history):
        return None, None
    table = _get_table()
    if table is None:
        return None, None

    version, pk = data_version(), page_key(page)

    # 1. exact
    try:
        got = table.get_item(Key={"cache_key": cache_key(question, page)})
        item = got.get("Item")
        if item and item.get("payload"):
            return json.loads(item["payload"]), "exact"
    except Exception as e:                              # noqa: BLE001
        logger.info("cache exact lookup failed: %s", e)

    # 2. semantic, within the same data version and page context
    vec = _embed(normalise(question))
    if not vec:
        return None, None
    try:
        # `bucket` is a DynamoDB reserved keyword, so it cannot appear
        # literally in a KeyConditionExpression -- the Query is rejected with
        # a ValidationException. Alias it.
        resp = table.query(
            IndexName="bucket-index",
            KeyConditionExpression="#b = :b",
            ExpressionAttributeNames={"#b": "bucket"},
            ExpressionAttributeValues={":b": f"{version}|{pk}"},
            Limit=MAX_SEMANTIC_CANDIDATES)
        best, best_score = None, 0.0
        for item in resp.get("Items", []):
            stored = item.get("embedding")
            if not stored:
                continue
            score = _cosine(vec, [float(x) for x in stored])
            if score > best_score:
                best, best_score = item, score
        if best is not None and best_score >= SIMILARITY_THRESHOLD:
            logger.info("semantic cache hit at %.4f", best_score)
            return json.loads(best["payload"]), "semantic"
    except Exception as e:                              # noqa: BLE001
        logger.info("cache semantic lookup failed: %s", e)
    return None, None


def store(question: str, page: dict | None, payload: dict,
          history: list | None = None) -> bool:
    """Store an answer. Returns True if written."""
    if not cacheable(question, history):
        return False
    table = _get_table()
    if table is None:
        return False
    # Never cache a degraded or error response -- it would pin an outage in
    # place for the whole TTL.
    if not isinstance(payload, dict) or payload.get("degraded"):
        return False
    version, pk = data_version(), page_key(page)
    item = {
        "cache_key": cache_key(question, page),
        "bucket": f"{version}|{pk}",
        "question": normalise(question)[:300],
        "payload": json.dumps(payload)[:380_000],
        "data_version": version,
        "created": int(time.time()),
        "ttl": int(time.time()) + CACHE_TTL_DAYS * 86400,
    }
    vec = _embed(normalise(question))
    if vec:
        from decimal import Decimal
        item["embedding"] = [Decimal(str(round(x, 6))) for x in vec]
    try:
        table.put_item(Item=item)
        return True
    except Exception as e:                              # noqa: BLE001
        logger.info("cache store failed: %s", e)
        return False


def stats() -> dict:
    return {
        "table": CACHE_TABLE or None,
        "semantic": SEMANTIC_ENABLED,
        "threshold": SIMILARITY_THRESHOLD,
        "ttl_days": CACHE_TTL_DAYS,
        "data_version": data_version(),
    }
