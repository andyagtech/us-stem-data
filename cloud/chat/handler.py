"""
PhD Demographics chat assistant — Lambda handler (contract v2).

Wire format: one buffered JSON POST response.  The v2 envelope adds `blocks`,
an ordered array of render instructions, and keeps `reply` and `actions` for
back-compat.  See chat_contract.md sections 4.2 - 4.9.

Security posture (unchanged from v1 except where noted):
  * CORS origin-locked to ALLOWED_ORIGIN; the Function URL emits the headers.
  * Per-IP rate limiting in DynamoDB.  Fails open, but now emits a CloudWatch
    EMF metric so a silently broken limiter is visible.
  * API keys live in SSM and are read by parameter name only.
  * Chat analytics are written to CHAT_LOGS_TABLE with the FULL client IP —
    deliberate, for geo-analysis.  Do not hash it.
  * Every model-produced string is validated and clamped in blocks.py before
    it is serialised; scraped free text is treated as data, never instructions.
"""
from __future__ import annotations

import json
import logging
import os
import time
import urllib.request

import boto3

try:
    from . import blocks as B
    from . import cache as _cache
    from . import facts as _facts
    from . import data_store as ds
    from . import prompt as P
    from . import tools as T
except ImportError:  # flat Lambda layout
    import blocks as B
    import cache as _cache
    import facts as _facts
    import data_store as ds
    import prompt as P
    import tools as T

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ALLOWED_ORIGIN = os.environ.get("ALLOWED_ORIGIN", "https://phd-demographics.andy-barr.com")
MAX_INPUT = 2000
MAX_HISTORY = 20
MAX_TOKENS = 2000
MAX_TOOL_ROUNDS = 4
RATE_LIMIT = 10
RATE_WINDOW = 60

# A per-IP limit caps one visitor, not the bill. Ten a minute across a hundred
# addresses is a thousand a minute, and nothing counted the total: OpenAI is
# billed directly, outside the AWS budget, with no alarm on it. This is the
# ceiling that turns an unbounded spend into a bounded one.
#
# Past DAILY_SOFT_CAP the assistant serves cache hits and refuses everything
# else, so the questions people actually ask keep working while novel ones
# stop costing money. Past DAILY_HARD_CAP it refuses outright.
DAILY_SOFT_CAP = int(os.environ.get("DAILY_SOFT_CAP", "4000"))
DAILY_HARD_CAP = int(os.environ.get("DAILY_HARD_CAP", "6000"))

# Failing open once is right; failing open all afternoon because DynamoDB is
# unhappy is not. After this many consecutive limiter errors in one container,
# requests are refused until one succeeds.
LIMITER_FAILS_OPEN_UNTIL = int(os.environ.get("LIMITER_FAILS_OPEN_UNTIL", "20"))
_limiter_failures = 0
CONTRACT_VERSION = 2

DEGRADED_REPLY = ("I can't reach the model right now, so I can't answer that one. "
                  "The data itself is all still on the site.")


# ---------------------------------------------------------------------------
# AWS clients (lazy, cached across warm invocations)
# ---------------------------------------------------------------------------
_api_keys = {}
_rate_table = None
_logs_table = None


def _get_rate_table():
    global _rate_table
    if _rate_table is None:
        _rate_table = boto3.resource("dynamodb", region_name="us-east-1").Table(
            os.environ.get("RATE_LIMIT_TABLE", "phd-chat-ratelimit")
        )
    return _rate_table


def _get_api_key(ssm_name):
    if ssm_name in _api_keys:
        return _api_keys[ssm_name]
    ssm = boto3.client("ssm", region_name="us-east-1")
    resp = ssm.get_parameter(Name=ssm_name, WithDecryption=True)
    _api_keys[ssm_name] = resp["Parameter"]["Value"]
    return _api_keys[ssm_name]


def _metric(name, value=1):
    """CloudWatch EMF, so operational faults are visible without a dependency."""
    try:
        logger.info(json.dumps({
            "_aws": {"Timestamp": int(time.time() * 1000),
                     "CloudWatchMetrics": [{"Namespace": "PhdChat",
                                            "Dimensions": [[]],
                                            "Metrics": [{"Name": name}]}]},
            name: value,
        }))
    except Exception:                                        # noqa: BLE001
        pass


def _cors():
    # The Function URL applies Access-Control-Allow-Origin itself; setting it
    # here too would duplicate the header.
    return {"Content-Type": "application/json"}


def _resp(status, payload, extra_headers=None):
    headers = _cors()
    if extra_headers:
        headers.update(extra_headers)
    return {"statusCode": status, "headers": headers,
            "body": json.dumps(payload, ensure_ascii=False)}


def _err(status, code, message, retry_after=None):
    payload = {"v": CONTRACT_VERSION, "error": message, "error_code": code}
    headers = {}
    if retry_after is not None:
        payload["retry_after_s"] = retry_after
        headers["Retry-After"] = str(retry_after)
    return _resp(status, payload, headers)


def _get_ip(event):
    rc = event.get("requestContext", {})
    return (rc.get("http", {}).get("sourceIp")
            or rc.get("identity", {}).get("sourceIp")
            or event.get("headers", {}).get("x-forwarded-for", "unknown").split(",")[0].strip())


def _check_rate(ip):
    """(allowed, seconds_until_window_resets)."""
    now = int(time.time())
    reset_in = RATE_WINDOW - (now % RATE_WINDOW)
    try:
        r = _get_rate_table().update_item(
            Key={"pk": f"{ip}:{now // RATE_WINDOW}"},
            UpdateExpression="SET #c = if_not_exists(#c, :z) + :o, #t = :t",
            ExpressionAttributeNames={"#c": "count", "#t": "ttl"},
            ExpressionAttributeValues={":z": 0, ":o": 1, ":t": now + RATE_WINDOW * 2},
            ReturnValues="UPDATED_NEW",
        )
        global _limiter_failures
        _limiter_failures = 0
        return int(r["Attributes"]["count"]) <= RATE_LIMIT, reset_in
    except Exception as exc:                                  # noqa: BLE001
        # Fail open, but loudly, and not indefinitely: a limiter that is
        # quietly dead is worse than one that is down, and one that fails open
        # for an hour is an open tab at the model provider.
        _limiter_failures += 1
        logger.warning("Rate limit check failed (%d in a row): %s",
                       _limiter_failures, exc)
        _metric("RateLimiterError")
        if _limiter_failures >= LIMITER_FAILS_OPEN_UNTIL:
            _metric("RateLimiterFailClosed")
            return False, reset_in
        return True, reset_in


def _check_daily(now=None):
    """(state, count) where state is 'ok', 'soft' or 'hard'.

    One counter for the whole service, keyed on the UTC day. Costs a single
    DynamoDB update per request in the same table the per-IP limiter uses.

    This one fails OPEN on error without a strike counter: it is a backstop,
    and a broken backstop should not take the service down. The per-IP limit
    is still in front of it.
    """
    now = now or int(time.time())
    day = time.strftime("%Y-%m-%d", time.gmtime(now))
    try:
        r = _get_rate_table().update_item(
            Key={"pk": f"GLOBAL:{day}"},
            UpdateExpression="SET #c = if_not_exists(#c, :z) + :o, #t = :t",
            ExpressionAttributeNames={"#c": "count", "#t": "ttl"},
            ExpressionAttributeValues={":z": 0, ":o": 1, ":t": now + 172800},
            ReturnValues="UPDATED_NEW",
        )
        n = int(r["Attributes"]["count"])
    except Exception as exc:                                  # noqa: BLE001
        logger.warning("Daily cap check failed: %s", exc)
        _metric("DailyCapError")
        return "ok", 0
    if n > DAILY_HARD_CAP:
        _metric("DailyCapHard")
        return "hard", n
    if n > DAILY_SOFT_CAP:
        _metric("DailyCapSoft")
        return "soft", n
    return "ok", n


def _log_chat(record):
    """Analytics for chat-admin.html.

    The full client IP is stored on purpose (geo-analysis). Do not anonymise.
    """
    table_name = os.environ.get("CHAT_LOGS_TABLE")
    if not table_name:
        _metric("ChatLogTableUnset")
        return
    global _logs_table
    try:
        if _logs_table is None:
            _logs_table = boto3.resource("dynamodb", region_name="us-east-1").Table(table_name)
        now = int(time.time())
        iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))
        day = time.strftime("%Y-%m-%d", time.gmtime(now))
        ip = record.get("ip", "unknown")
        item = {
            "pk": day,
            "sk": f"{iso}#{ip}",
            "ip": ip,
            "timestamp": iso,
            "epoch": now,
            "message": (record.get("message") or "")[:500],
            "reply_preview": (record.get("reply") or "")[:300],
            # tools_used stays the dashboard's existing key; it now carries the
            # real tool names rather than just "navigate"/"query".
            "tools_used": record.get("tools_used") or ["none"],
            "data_tools": record.get("data_tools") or [],
            "block_types": record.get("block_types") or [],
            "action_count": int(record.get("action_count") or 0),
            "latency_ms": int(record.get("latency_ms") or 0),
            "contract_v": int(record.get("v") or 1),
            "degraded": bool(record.get("degraded")),
            "truncated": bool(record.get("truncated")),
            "page": (record.get("page") or "")[:120],
            "widget": (record.get("widget") or "")[:20],
            "ttl": now + 90 * 86400,
        }
        _logs_table.put_item(Item=item)
    except Exception as exc:                                  # noqa: BLE001
        logger.warning("Chat log failed: %s", exc)
        _metric("ChatLogError")


# ---------------------------------------------------------------------------
# providers
# ---------------------------------------------------------------------------
PROVIDERS = [
    {"name": "openai",
     "url": "https://api.openai.com/v1/chat/completions",
     "ssm_env": "OPENAI_API_KEY_SSM",
     "ssm_default": "/phd-demographics/openai-api-key",
     "model": os.environ.get("CHAT_MODEL", "gpt-4o"),
     "extra_headers": {}},
    {"name": "openrouter",
     "url": "https://openrouter.ai/api/v1/chat/completions",
     "ssm_env": "OPENROUTER_API_KEY_SSM",
     "ssm_default": "/phd-demographics/openrouter-api-key",
     "model": "openai/" + os.environ.get("CHAT_MODEL", "gpt-4o"),
     "extra_headers": {"HTTP-Referer": "https://phd-demographics.andy-barr.com",
                       "X-Title": "PhD Demographics Assistant"}},
]

_last_provider = {"name": None, "model": None}


def _provider_request(provider, messages, use_tools=True):
    key = _get_api_key(os.environ.get(provider["ssm_env"], provider["ssm_default"]))
    body = {"model": provider["model"], "messages": messages,
            "max_tokens": MAX_TOKENS, "temperature": 0.2}
    if use_tools:
        body["tools"] = T.TOOLS
        body["tool_choice"] = "auto"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {key}"}
    headers.update(provider.get("extra_headers", {}))
    req = urllib.request.Request(provider["url"], data=json.dumps(body).encode(),
                                 headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=25) as resp:
        data = json.loads(resp.read())
    _last_provider["name"] = provider["name"]
    _last_provider["model"] = provider["model"]
    # Usage lives on the response, not on the message this returns, so it has
    # to be read here. Counting it anywhere else silently measures nothing.
    try:
        usage = data.get("usage") or {}
        if usage.get("prompt_tokens"):
            _metric("PromptTokens", int(usage["prompt_tokens"]))
        if usage.get("completion_tokens"):
            _metric("CompletionTokens", int(usage["completion_tokens"]))
        cached_tok = (usage.get("prompt_tokens_details") or {}).get("cached_tokens")
        if cached_tok:
            _metric("CachedPromptTokens", int(cached_tok))
    except Exception:                                           # noqa: BLE001
        pass
    return data["choices"][0]["message"]


def _model_request(messages, use_tools=True):
    """Call the model, and count what it cost.

    Nothing measured token usage, so the one uncapped cost in the system was
    also the one nobody could see. These metrics are what a spend alarm can be
    hung on, and what tells you whether the cache is doing its job: a low
    ModelCalls-to-request ratio means it is.
    """
    last = None
    for provider in PROVIDERS:
        try:
            out = _provider_request(provider, messages, use_tools)
            _metric("ModelCalls")
            return out
        except Exception as exc:                              # noqa: BLE001
            last = exc
            logger.warning("Provider %s failed: %s", provider["name"], exc)
    raise RuntimeError(f"All AI providers failed. Last error: {last}")


# ---------------------------------------------------------------------------
# the tool loop
# ---------------------------------------------------------------------------
class Turn:
    def __init__(self):
        self.ledger = B.Ledger()
        self.ctx = B.Ctx(ds.site_paths(), ds.enumerated_anchors(), self.ledger)
        self.blocks = []
        self.tools_used = []
        self.data_tools = []
        self.rejected = 0
        self.facts = []          # labelled figures this turn established


def _run_turn(messages, turn: Turn):
    """Returns the final prose.  Mutates `turn` with blocks and telemetry."""
    render_only_rounds = 0
    for _round in range(MAX_TOOL_ROUNDS):
        msg = _model_request(messages)
        tool_calls = msg.get("tool_calls") or []
        if not tool_calls:
            return msg.get("content") or ""

        messages.append(msg)
        saw_data_tool = False
        for tc in tool_calls:
            name = (tc.get("function") or {}).get("name", "")
            try:
                args = json.loads((tc.get("function") or {}).get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            if not isinstance(args, dict):
                args = {}
            turn.tools_used.append(name)

            if name in T.DATA_TOOL_NAMES:
                saw_data_tool = True
                turn.data_tools.append(name)
                result = T.run_data_tool(name, args)
                # Everything this returned is now quotable; nothing else is.
                turn.ledger.add(result)
                fact = _facts.distil(name, args, result)
                if fact:
                    turn.facts.append(fact)
                if isinstance(result, dict) and result.get("source"):
                    turn.ledger.note_source(result["source"])
            elif name in B.BUILDERS:
                try:
                    block = B.BUILDERS[name](args, turn.ctx)
                    turn.blocks.append(block)
                    result = {"ok": True, "block": B.BLOCK_FOR_TOOL[name]}
                except B.BlockError as exc:
                    turn.rejected += 1
                    result = {"ok": False, "block": B.BLOCK_FOR_TOOL[name],
                              "error": str(exc)}
                    logger.info("block rejected (%s): %s", name, exc)
                except Exception as exc:                      # noqa: BLE001
                    turn.rejected += 1
                    result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
                    logger.warning("block build failed (%s): %s", name, exc)
                if result.get("ok") and not any(b["type"] == "suggest" for b in turn.blocks):
                    result["reminder"] = ("Before writing the prose, call suggest_followups "
                                          "with 2-4 chips, plus any other blocks you still "
                                          "want. Then answer.")
            else:
                result = {"ok": False, "error": f"Unknown tool: {name}"}

            messages.append({"role": "tool", "tool_call_id": tc.get("id"),
                             "content": json.dumps(result, ensure_ascii=False)[:12000]})

        # Contract 5.1: render tools do not consume a round on their own. One
        # extra pass is allowed so the model can add the blocks it forgot; two
        # render-only rounds in a row means it is done, so go to the prose.
        if saw_data_tool:
            render_only_rounds = 0
        else:
            render_only_rounds += 1
            if render_only_rounds >= 2:
                break

    msg = _model_request(messages, use_tools=False)
    return msg.get("content") or ""


# ---------------------------------------------------------------------------
# handler
# ---------------------------------------------------------------------------
def _clean_history(raw):
    if not isinstance(raw, list):
        return []
    out = []
    for m in raw[-MAX_HISTORY:]:
        if isinstance(m, dict) and m.get("role") in ("user", "assistant"):
            content = str(m.get("content", ""))[:MAX_INPUT]
            if content:
                out.append({"role": m["role"], "content": content})
    return out


def _degraded_envelope():
    blocks = [
        {"type": "notice", "kind": "warn", "title": "Assistant offline",
         "md": "The assistant backend is unreachable. Everything below is still live."},
        {"type": "nav", "url": "/stem.html", "path": "stem.html",
         "label": "Browse the 101 university pages", "auto": False, "highlight": False},
        {"type": "nav", "url": "/query.html", "path": "query.html",
         "label": "Query the raw records yourself", "auto": False, "highlight": False},
    ]
    return {"v": CONTRACT_VERSION, "reply": DEGRADED_REPLY, "blocks": blocks,
            "actions": B.mirror_actions(blocks), "meta": {"degraded": True}}


def handler(event, context=None):
    hdrs = event.get("headers") or {}
    origin = hdrs.get("origin") or hdrs.get("Origin") or ""

    # The Function URL routes every path here, so dispatch on it. /realtime
    # mints an ephemeral token for the live voice dashboard and shares nothing
    # else with the chat path -- different lifetime, different upstream API.
    raw_path = (event.get("rawPath")
                or ((event.get("requestContext") or {}).get("http") or {}).get("path")
                or "")
    if raw_path.rstrip("/").endswith("/realtime"):
        try:
            from . import realtime as _rt
        except ImportError:
            import realtime as _rt
        return _rt.handler(event, context)

    method = ((event.get("requestContext") or {}).get("http") or {}).get("method") \
        or event.get("httpMethod") or ""
    if method == "OPTIONS":
        return {"statusCode": 200, "headers": _cors(), "body": ""}


    if origin and origin != ALLOWED_ORIGIN:
        return _err(403, "forbidden_origin", "Forbidden")

    body = event.get("body") or "{}"
    if isinstance(body, str):
        try:
            body = json.loads(body or "{}")
        except Exception:                                     # noqa: BLE001
            return _err(400, "bad_request", "Invalid JSON")
    if not isinstance(body, dict):
        return _err(400, "bad_request", "Invalid JSON")

    # Warm-up ping: no model call, no rate-limit consumption, no logging.
    if body.get("ping") is True:
        return _resp(200, {"v": CONTRACT_VERSION, "ok": True,
                           "data": ds.available()})

    want_v2 = int(body.get("v") or 1) >= 2

    raw_message = body.get("message")
    if not isinstance(raw_message, str) or not raw_message.strip():
        return _err(400, "bad_request", "message required")
    if len(raw_message) > MAX_INPUT:
        return _err(400, "too_long",
                    f"That question is {len(raw_message)} characters; the limit is "
                    f"{MAX_INPUT}. Trim it and send again.")
    message = raw_message.strip()

    client_ip = _get_ip(event)
    allowed, reset_in = _check_rate(client_ip)
    if not allowed:
        return _err(429, "rate_limited",
                    f"Rate limit exceeded. Try again in {reset_in} seconds.", reset_in)

    # The global ceiling. Checked after the per-IP limit so an abusive client
    # is turned away before it can consume the day's allowance.
    day_state, day_count = _check_daily()
    if day_state == "hard":
        return _err(429, "daily_cap",
                    "The assistant has answered its limit of questions for today. "
                    "Everything it draws on is published on the site, and it will "
                    "be back tomorrow.", 3600)

    page = body.get("page") if isinstance(body.get("page"), dict) else None
    widget = ds.clean_text(((body.get("client") or {}) if isinstance(body.get("client"), dict)
                            else {}).get("widget", ""), 20)

    # `fresh: true` skips the cache LOOKUP for this turn (the answer is still
    # stored). scripts/curated_answers.py needs it: the export reads answers
    # back through this endpoint, and without a bypass it receives its own
    # previously cached answers and reports that nothing changed -- which is
    # exactly what happened before this existed.
    want_fresh = body.get("fresh") is True

    # Cache lookup before any model call. Only first turns with no history
    # qualify; see cache.py for why a follow-up must never be served from here.
    history = _clean_history(body.get("conversationHistory"))
    try:
        cached, how = (None, None) if want_fresh else _cache.lookup(message, page, history)
    except Exception:                                           # noqa: BLE001
        cached, how = None, None      # the cache may never fail a request
    if not cached and day_state == "soft":
        # Past the soft cap: known questions still answer from cache, novel
        # ones stop costing money. The common path keeps working.
        _metric("DailyCapRefused")
        return _err(429, "daily_cap_soft",
                    "The assistant is at its daily limit for new questions. It can "
                    "still answer the common ones, and everything it draws on is "
                    "published on the site.", 3600)

    if cached:
        _metric("CacheHit")
        _log_chat({"ip": client_ip, "message": message,
                   "reply": cached.get("reply", ""), "cache": how,
                   "latency_ms": 0, "v": 2 if want_v2 else 1,
                   "page": (page or {}).get("path", ""), "widget": widget})
        if not want_v2:
            out = {"reply": cached.get("reply", "")}
            if cached.get("actions"):
                out["actions"] = cached["actions"]
            return _resp(200, out)
        served = dict(cached)
        served.setdefault("meta", {})
        served["meta"] = {**served["meta"], "cache": how}
        return _resp(200, served)

    prior_facts = _facts.clean(body.get("facts"), _cache.data_version())
    system = P.build_system_prompt(page)
    fact_block = _facts.as_prompt(prior_facts)
    if fact_block:
        system = system + "\n\n" + fact_block
    messages = ([{"role": "system", "content": system}]
                + history
                + [{"role": "user", "content": message}])

    t0 = time.time()
    turn = Turn()
    # Earlier figures are re-grounded, so quoting one is checked rather than
    # remembered. Without this the model could restate a prior number and the
    # ledger would have no record of it.
    _facts.replay_into_ledger(prior_facts, turn.ledger)
    try:
        reply = _run_turn(messages, turn)
    except RuntimeError as exc:
        logger.error("All providers failed: %s", exc)
        _metric("ProviderOutage")
        latency = int((time.time() - t0) * 1000)
        _log_chat({"ip": client_ip, "message": message, "reply": DEGRADED_REPLY,
                   "latency_ms": latency, "degraded": True, "v": 2 if want_v2 else 1,
                   "page": (page or {}).get("path", ""), "widget": widget})
        env = _degraded_envelope()
        if not want_v2:
            return _resp(200, {"reply": env["reply"], "actions": env["actions"]})
        return _resp(200, env)
    except Exception as exc:                                  # noqa: BLE001
        logger.exception("Chat error")
        latency = int((time.time() - t0) * 1000)
        _log_chat({"ip": client_ip, "message": message, "reply": f"ERROR: {exc}",
                   "latency_ms": latency, "v": 2 if want_v2 else 1,
                   "page": (page or {}).get("path", ""), "widget": widget})
        return _err(502, "upstream_unavailable", "Chat service temporarily unavailable.")

    latency = int((time.time() - t0) * 1000)
    block_list, truncated = B.assemble(turn.blocks, reply)
    actions = B.mirror_actions(block_list)

    _log_chat({"ip": client_ip, "message": message, "reply": reply,
               "tools_used": turn.tools_used or ["none"],
               "data_tools": turn.data_tools,
               "block_types": [b["type"] for b in block_list],
               "action_count": len(actions), "latency_ms": latency,
               "truncated": truncated, "v": 2 if want_v2 else 1,
               "page": (page or {}).get("path", ""), "widget": widget})

    if not want_v2:
        out = {"reply": reply}
        if actions:
            out["actions"] = actions
        return _resp(200, out)

    envelope = {
        "v": CONTRACT_VERSION,
        "reply": reply,
        "blocks": block_list,
        "actions": actions,
        "meta": {"provider": _last_provider["name"], "model": _last_provider["model"],
                 "latency_ms": latency, "tools_used": turn.tools_used,
                 "blocks_rejected": turn.rejected, "truncated": truncated,
                 "facts": {"version": _cache.data_version(),
                           "facts": _facts.merge(prior_facts, turn.facts)}},
    }
    # Store only answers that actually rendered something. An empty-block
    # reply is usually a refusal or a stumble, and pinning one for the TTL
    # would make a transient failure look permanent.
    if block_list and not truncated:
        try:
            _cache.store(message, page, envelope, history)
        except Exception:                                       # noqa: BLE001
            pass
    return _resp(200, envelope)
