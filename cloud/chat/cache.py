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
                 asked from /departments-stem.html and from a university page should not
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
from pathlib import Path

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


# ---------------------------------------------------------------- salience

"""THE ENTITY GATE

Cosine similarity measures sentence shape, and these questions are nearly all
the same shape. Observed on 2026-10-13, against the live assistant:

    asked:  "Which CIVIL engineering doctoral programmes lean most heavily on
             foreign students? I want the degree count, the NRA headcount and
             the share..."
    served: the MECHANICAL engineering answer, word for word, with its stored
            latency -- a semantic hit well over the 0.82 threshold.

One word apart out of thirty, and that word was the whole question. Raising
the threshold does not fix this: the pair scores higher than real paraphrases
the cache is meant to catch, so any threshold that rejects it rejects those
too.

So similarity is necessary and no longer sufficient. A semantic hit must ALSO
name the same things. `salient()` returns the concrete entities a question
mentions -- fields, institutions, years -- and two questions with different
sets never match, however close their vectors.

What counts as an entity is read from the data we already ship, not from a
hand-written list that would drift from the corpus:

  fields        tokens from cip_titles.csv that appear in at most MAX_DF
                titles. "mechanical" (4) and "civil" (4) qualify;
                "engineering" (94) and "studies" (140) do not, because a
                token in a hundred titles distinguishes nothing.
  institutions  the same test over hd_names.csv -- "stanford" (1) counts,
                "university" (827) does not -- plus every university key in
                universities_compact.json, which is where the short ones
                live: mit, byu, caltech.
  years         any four-digit year. "since 2015" and "since 2020" are
                different questions.

Ordinary English leaks into both files -- "foreign" and "student" each sit in
a handful of CIP titles -- and a word every reader uses discriminates nothing.
The site's own knowledge base is the corpus that says which words those are:
a token in more than KB_MAX_DF of the 42 knowledge files is this site's
everyday vocabulary and is dropped. Measured: "with" 34 files, "foreign" 19,
"student" 17, against "electrical" 4, "mechanical" 2, "civil" 1, "mit" 0. The
gap is wide and the rule needs no hand-written stoplist to stay current.

A question naming nothing concrete has an empty set, which still matches
another empty set. That is the paraphrase case the semantic layer exists for
-- "which field has the highest non resident share" against "what field has
the largest foreign student share" -- and it is untouched.

The cost is a false miss when two questions name the same thing in different
words. A miss costs one model call. A false hit answers a question nobody
asked, on a site whose entire value is being checkable.
"""

#: A token in more than this many titles names a category, not a thing.
MAX_DF = 25

#: A token in more than this many knowledge files is this site's own everyday
#: vocabulary, whoever is asking. "electrical" sits at 4 and survives.
KB_MAX_DF = 4

#: What the knowledge corpus cannot catch. The site is written in British
#: spelling -- "programme" -- so the American forms readers actually type are
#: absent from it, sit in a handful of CIP titles, and would otherwise count
#: as entities: "mechanical programs" and "mechanical programmes" would be
#: two different questions. Checked against 180 ordinary question words; these
#: four are all that leaked.
ALWAYS_EVERYDAY = frozenset({"program", "programs", "make", "well"})

_SALIENT_VOCAB: frozenset | None = None
_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
_WORD_RE = re.compile(r"[a-z]{4,}")


def _selective_tokens(titles, max_df: int = MAX_DF) -> set:
    """Tokens appearing in at most `max_df` of `titles`."""
    df: dict[str, int] = {}
    for t in titles:
        for tok in set(_WORD_RE.findall((t or "").lower())):
            df[tok] = df.get(tok, 0) + 1
    return {tok for tok, n in df.items() if n <= max_df}


def _everyday_words(max_df: int = KB_MAX_DF) -> set:
    """Words this site uses all the time, read from its own knowledge base.

    Degrades to an empty set if the prose is unreadable: the gate then keeps a
    few ordinary words and costs an occasional cache miss, which is the safe
    direction.
    """
    try:
        from . import prompt as _prompt
    except ImportError:                                   # flat Lambda layout
        try:
            import prompt as _prompt
        except Exception:                                 # noqa: BLE001
            return set()
    try:
        df: dict[str, int] = {}
        for f in sorted(Path(_prompt.KNOWLEDGE_DIR).glob("*.md")):
            for tok in set(_WORD_RE.findall(
                    f.read_text(encoding="utf-8", errors="replace").lower())):
                df[tok] = df.get(tok, 0) + 1
        return {tok for tok, n in df.items() if n > max_df}
    except Exception as e:                                # noqa: BLE001
        logger.info("everyday words unavailable: %s", e)
        return set()


def salient_vocab() -> frozenset:
    """Every token that names a particular field or institution. Built once."""
    global _SALIENT_VOCAB
    if _SALIENT_VOCAB is not None:
        return _SALIENT_VOCAB
    vocab: set = set()
    try:
        from . import data_store as _ds
    except ImportError:                                   # flat Lambda layout
        try:
            import data_store as _ds
        except Exception:                                 # noqa: BLE001
            _ds = None
    if _ds is not None:
        try:
            vocab |= _selective_tokens(_ds.cip_titles().values())
        except Exception as e:                            # noqa: BLE001
            logger.info("salient vocab: no cip titles (%s)", e)
        try:
            vocab |= _selective_tokens(
                (v.get("name") if isinstance(v, dict) else v)
                for v in _ds.institutions().values())
        except Exception as e:                            # noqa: BLE001
            logger.info("salient vocab: no institution names (%s)", e)
        try:
            # The short keys -- mit, byu, caltech -- are below the four-letter
            # floor the token rule uses, and they are exactly what a reader
            # types.
            vocab |= {k.lower() for k in _ds.universities()
                      if isinstance(k, str) and len(k) >= 2}
        except Exception as e:                            # noqa: BLE001
            logger.info("salient vocab: no university keys (%s)", e)
    vocab -= _everyday_words()
    vocab -= ALWAYS_EVERYDAY
    _SALIENT_VOCAB = frozenset(vocab)
    logger.info("salient vocab: %d tokens", len(_SALIENT_VOCAB))
    return _SALIENT_VOCAB


def salient(question: str) -> frozenset:
    """The concrete things a question names: fields, institutions, years."""
    norm = normalise(question)
    vocab = salient_vocab()
    words = {w for w in norm.split() if w in vocab}
    return frozenset(words | set(_YEAR_RE.findall(norm)))


_KB_FINGERPRINT: str | None = None


def knowledge_version() -> str:
    """Fingerprint of the knowledge bundle shipped in this Lambda.

    WHY THIS IS IN THE CACHE KEY

    The data version alone was not enough, and the gap was not theoretical.
    A knowledge file was added saying that the PERM files DO carry the
    worker's citizenship. The assistant, asked afterwards, still answered that
    they do not -- word for word, from a cached answer written before the file
    existed. The corpus had not been rebuilt, so the data version had not
    moved, so the cache was never invalidated.

    A cached answer is a figure AND a claim from an earlier conversation. The
    data version covers the figures. This covers the claims.

    Computed once per container from the file contents, not mtimes: a fresh
    deploy of unchanged prose should keep its cache, and mtimes change on
    every unzip.
    """
    global _KB_FINGERPRINT
    if _KB_FINGERPRINT is not None:
        return _KB_FINGERPRINT
    h = hashlib.sha256()
    try:
        kb = Path(__file__).resolve().parent / "knowledge"
        for f in sorted(kb.glob("*.md")):
            h.update(f.name.encode("utf-8"))
            h.update(f.read_bytes())
        _KB_FINGERPRINT = h.hexdigest()[:12]
    except Exception:                                   # noqa: BLE001
        #: A fingerprint we could not compute must not silently become a
        #: constant that pins the cache forever. "0" is distinct from any
        #: real digest, and the data version still varies underneath it.
        _KB_FINGERPRINT = "0"
    return _KB_FINGERPRINT


def data_version() -> str:
    """Stamp of the current build; changing it invalidates everything.

    Two parts: the data corpus and the knowledge bundle. Either moving
    invalidates the cache, because either can change the right answer.
    """
    try:
        try:
            from . import data_store as ds
        except ImportError:
            import data_store as ds
        corpus = str((ds.site_map() or {}).get("version") or "0")
    except Exception:                                   # noqa: BLE001
        corpus = "0"
    return f"{corpus}.{knowledge_version()}"


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
        asked = salient(question)
        best, best_score = None, 0.0
        gated = 0
        for item in resp.get("Items", []):
            stored = item.get("embedding")
            if not stored:
                continue
            # The entity gate, applied BEFORE the score is compared: a stored
            # answer about a different field is not a near miss to be beaten,
            # it is not a candidate at all.
            if frozenset(item.get("salient") or ()) != asked:
                gated += 1
                continue
            score = _cosine(vec, [float(x) for x in stored])
            if score > best_score:
                best, best_score = item, score
        if best is not None and best_score >= SIMILARITY_THRESHOLD:
            logger.info("semantic cache hit at %.4f", best_score)
            return json.loads(best["payload"]), "semantic"
        if gated:
            logger.info("semantic cache: %d candidate(s) named different things", gated)
    except Exception as e:                              # noqa: BLE001
        logger.info("cache semantic lookup failed: %s", e)
    return None, None


#: The fixed opening of the off-topic reply prompt.py instructs the model to
#: give. Matched as a prefix of the reply, not anywhere in it, so an answer that
#: merely quotes the phrase is still cacheable.
REFUSAL_PREFIX = "i can only help with questions about"

#: THE MODEL PARAPHRASES ITS OWN CANNED LINE. Asked "how much federal funding
#: goes to these programs?" on 2026-10-14 -- a question prompt.py names
#: explicitly as one never to refuse -- the deployed assistant answered "I CAN
#: help with questions about international student data...", dropping one word
#: from the prefix above. That is the same non-answer, but it matched neither
#: this prefix nor the handler's misplaced-refusal guard, so no retry fired
#: and the deflection was cacheable.
#:
#: So the shape is matched instead of the opening: the distinctive clause, in
#: the first sentence or two, from a reply that called no data tool. Anchored
#: near the start so a page that discusses the refusal in passing is unaffected.
DEFLECTION_RE = re.compile(
    r"^.{0,120}?\bhelp with questions about\b.{0,80}?"
    r"\b(international student data|visa programs|university demographics)\b",
    re.I | re.S)


#: A deflection states no figure. A real answer that happens to echo the
#: phrase -- "the site can help with questions about international student
#: data, and here it is: 63.1%" -- does, and must not be treated as one: it
#: would cost a retry and keep a good answer out of the cache.
_HAS_FIGURE = re.compile(r"\d")


def looks_like_deflection(text: str) -> bool:
    """The canned off-topic reply, however the model worded its opening."""
    t = (text or "").strip()
    if t.lower().startswith(REFUSAL_PREFIX):
        return True
    return bool(DEFLECTION_RE.match(t)) and not _HAS_FIGURE.search(t)


def is_refusal(payload: dict) -> bool:
    texts = [payload.get("reply") or ""]
    texts += [b.get("md") or b.get("text") or ""
              for b in (payload.get("blocks") or []) if isinstance(b, dict)]
    return any(looks_like_deflection(t) for t in texts if t)


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
    # Nor a refusal. The model occasionally refuses a question that is plainly
    # on topic -- on 2026-09-11 "How many Indian students are in the US on
    # SEVIS?" was refused two times in three -- and one misfire, stored, became
    # the answer for everyone who asked it, and through semantic matching for
    # everyone who asked something like it, for the whole TTL. A genuine
    # refusal costs nothing to regenerate, so none is kept.
    if is_refusal(payload):
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
    # Stored alongside the vector, because the gate compares sets, not text,
    # and recomputing it per candidate at lookup time would re-tokenise every
    # row in the bucket. A row written before this field existed carries an
    # empty set and so only ever matches a question that names nothing --
    # which is the conservative direction, and it ages out with the TTL.
    marks = salient(question)
    if marks:
        item["salient"] = sorted(marks)
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
        "salient_vocab": len(salient_vocab()),
        "ttl_days": CACHE_TTL_DAYS,
        "data_version": data_version(),
    }
