"""Mint ephemeral OpenAI Realtime tokens for the live dashboard.

WHY A SERVER IS INVOLVED AT ALL

The dashboard's whole point is that it feels instant, and it does because the
browser speaks WebRTC directly to OpenAI -- audio never transits our
infrastructure, so there is no round trip to add latency. But the browser
cannot hold the API key, so exactly one server call remains: mint a short-lived
ephemeral token, hand it over, and get out of the way.

That call happens once per session, not once per utterance. Everything after it
is browser-to-OpenAI.

WHAT THIS DELIBERATELY DOES NOT DO

It does not proxy audio, hold conversation state, or see transcripts. It also
does not carry the site's data: the dashboard already has the whole bundle
client-side, so a tool call re-renders a chart without asking anyone. The
instructions below tell the model which tools exist; the browser executes them.

The session is capped (see MAX_SESSION_SECONDS) because an ephemeral token that
outlives its page is a billing hole.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

try:                                    # packaged as a module in the Lambda
    from . import budget as _budget
except ImportError:                     # and as a flat script in tests
    import budget as _budget

REALTIME_MODEL = os.environ.get("REALTIME_MODEL", "gpt-realtime")
REALTIME_VOICE = os.environ.get("REALTIME_VOICE", "alloy")
# Five minutes, not ten. The session length is what a voice session COSTS:
# it is reserved at its worst case before the token is minted, and there is no
# settlement, so halving the cap doubles the number of sessions a day can hold.
MAX_SESSION_SECONDS = int(os.environ.get("REALTIME_MAX_SECONDS", "300"))
# The GA endpoint. /v1/realtime/sessions was the beta and now 404s with
# "Invalid URL", which is what this code was still asking for -- verified
# against the live API, not assumed: client_secrets returns 200 and sessions
# returns 404 for the same key. The token comes back at the TOP level as
# "value", where the beta nested it under client_secret.value.
SESSION_URL = "https://api.openai.com/v1/realtime/client_secrets"

# The tool surface the voice agent may call. These are RENDER instructions --
# the browser owns the data and the drawing. Keeping the schema small matters:
# the model picks a tool mid-sentence, and every extra option is latency.
#: The pages the voice may open, read from the generated board
#: catalogue so this list cannot drift from the site.
def _pages():
    import json as _json
    import pathlib as _pl
    f = _pl.Path(__file__).resolve().parents[2] / "site" / "data" / "live_boards.json"
    try:
        return [d["path"] for d in _json.loads(f.read_text())["destinations"]]
    except Exception:
        #: Shipped copy, so a missing file degrades to a short list
        #: rather than a tool that advertises nothing.
        return ['/overview', '/postdocs', '/name-lists', '/departments-stem', '/expansion', '/visa-schools', '/bodyshops', '/public-sector-visas', '/query', '/data_requests']


PAGES = _pages()


TOOLS = [
    {
        "type": "function",
        "name": "show_series",
        "description": ("Draw the degree trend for one field. Use whenever the "
                        "listener names a field, or asks what a field looks like."),
        "parameters": {
            "type": "object",
            "properties": {
                "field": {"type": "string",
                          "description": "CIP family: 11 computer science, 14 engineering, "
                                         "15 engineering tech, 26 biological sciences, "
                                         "27 math & statistics, 30 interdisciplinary, "
                                         "40 physical sciences, 42 psychology"},
                "level": {"type": "string", "enum": ["masters", "doctorate"]},
                "mode": {"type": "string", "enum": ["counts", "share"],
                         "description": "counts shows domestic and non-resident as "
                                        "absolute lines; share shows the non-resident "
                                        "percentage. Prefer counts -- a share alone "
                                        "hides whether domestic numbers rose or fell."},
            },
            "required": ["field", "level"],
        },
    },
    {
        "type": "function",
        "name": "compare_fields",
        "description": "Put several fields side by side on one measure.",
        "parameters": {
            "type": "object",
            "properties": {
                "fields": {"type": "array", "items": {"type": "string"},
                           "maxItems": 8},
                "level": {"type": "string", "enum": ["masters", "doctorate"]},
                "measure": {"type": "string",
                            "enum": ["share", "growth_domestic", "growth_nra"]},
            },
            "required": ["fields", "level"],
        },
    },
    {
        "type": "function",
        "name": "show_f1",
        "description": ("Draw F-1 student visa issuance by fiscal year. Use when "
                        "the listener asks about visas, entries, or why degree "
                        "counts and visa counts disagree."),
        "parameters": {
            "type": "object",
            "properties": {
                "countries": {"type": "array", "items": {"type": "string"},
                              "description": "optional: china, india"},
            },
        },
    },
    {
        "type": "function",
        "name": "highlight",
        "description": ("Call out one number on screen, large. Use for the single "
                        "figure the listener should remember from what you just said."),
        "parameters": {
            "type": "object",
            "properties": {
                "label": {"type": "string"},
                "value": {"type": "string"},
                "caption": {"type": "string"},
            },
            "required": ["label", "value"],
        },
    },
    {
        "type": "function",
        "name": "show_board",
        "description": (
            "Put a named, pre-built board on screen. PREFER THIS over "
            "composing a chart from show_series or compare_fields: the "
            "board already carries the right title, subtitle and headline "
            "figure, so it appears instantly and cannot disagree with what "
            "you are saying. Call list_boards first if you are unsure which "
            "id fits."),
        "parameters": {
            "type": "object",
            "properties": {
                "id": {"type": "string",
                       "description": "A board id from list_boards, e.g. "
                                      "'11-masters' or 'rank-share-doctorate'."},
            },
            "required": ["id"],
        },
    },
    {
        "type": "function",
        "name": "list_boards",
        "description": ("The boards available, with their titles and the "
                        "headline figure each carries. Call this when the "
                        "listener asks something open-ended and you want to "
                        "pick the board that answers it."),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string",
                          "description": "optional: narrow by field, level "
                                         "or keyword, e.g. 'computer "
                                         "science' or 'doctorate'."},
            },
        },
    },
    {
        "type": "function",
        "name": "navigate",
        "description": (
            "Open one of this site's pages in a new tab for the listener. "
            "Use it when the answer is longer than a chart -- the names "
            "behind a number, the method, the source files. Say where you "
            "are sending them and why BEFORE calling it. Never invent a "
            "path: only the ones listed in the parameter description exist."),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string",
                         "description": "One of: " + ", ".join(PAGES)},
                "because": {"type": "string",
                            "description": "One short clause on why this "
                                           "page answers what was asked."},
            },
            "required": ["path"],
        },
    },
    {
        "type": "function",
        "name": "clear_board",
        "description": "Reset the dashboard to its opening state.",
        "parameters": {"type": "object", "properties": {}},
    },
]

INSTRUCTIONS = """\
You are the voice of a live data dashboard about who receives US graduate \
degrees. Someone is talking to you while looking at a screen you control.

# ALWAYS ENGLISH
- Answer in English, always, whatever language you think you heard. The
  listener is looking at an English page about US federal data. If a question
  is genuinely in another language, answer it in English anyway.

# THIS IS A CONVERSATION, NOT A REPORT
- Two or three sentences at a time. Never monologue.
- Plain spoken language. No markdown, no bullet points, no reading out lists.
- Say numbers the way a person says them: "about two thirds", "roughly a \
quarter of a million", not "64.9%" or "244,927".
- Draw first, then talk. Call the tool, then say what it shows while it appears.

# DRAW SOMETHING ALMOST EVERY TURN
The screen is the point. If a field, a level, a visa or a comparison comes up, \
put it on screen. Silence with a blank board is a failed turn.

# THE FINDING YOU ARE HERE TO EXPLAIN
Graduate programs in core STEM fields roughly doubled over the last decade, and \
international students captured most of that growth. Domestic numbers did NOT \
fall -- they rose in every core field, at both master's and doctorate level. \
What changed is who the expansion was built for.

Be precise about this, because it is easy to overstate and the overstatement is \
checkable. If someone says Americans are being displaced or pushed out, correct \
it: domestic degree counts went up. The real finding is that non-resident counts \
went up several times faster, so most of the new seats went to international \
students. That is a sharper claim and it survives scrutiny.

Prefer the counts view over the share view for exactly this reason -- a rising \
share is compatible with domestic numbers rising or falling, and only the counts \
distinguish them.

# WHEN VISAS COME UP
F-1 issuance peaked around 2015 and is well below that peak now, even though \
non-resident degree counts kept climbing. Those are not contradictory: new visa \
issuance is not the same as enrolled population. Continuing students, OPT and \
status changes carry the difference. Say you cannot fully attribute it from this \
data rather than inventing a mechanism.

# LIMITS - SAY THESE PLAINLY WHEN THEY COME UP
- These are degrees conferred, not enrolment or applications.
- Non-resident is a visa status at graduation. It is not ethnicity and not \
country of origin; this data cannot be split by nationality.
- Nothing here shows who applied, who was admitted, or who was funded, so it \
cannot establish that anyone was prioritised over anyone else. That would need \
admissions or funding data.
- If asked something the data cannot answer, say so in one sentence and offer \
what it can answer instead. Never guess a number.

# TONE
Interested, direct, unhurried. You are not selling a conclusion and you are not \
hedging one either. If someone pushes a stronger claim than the data supports, \
say what it does support and move on -- do not argue politics in either direction.
"""


def _cors(origin: str | None) -> dict:
    """Content type only.

    The Function URL applies Access-Control-Allow-Origin itself. Setting it
    here as well sent the header twice, and a browser rejects a response whose
    Access-Control-Allow-Origin "contains multiple values" -- so voice failed
    in the browser while curl, which does not enforce CORS, saw a perfect 200
    and a freshly minted token. handler.py already carries this lesson at
    _cors(); realtime.py did not.
    """
    return {"Content-Type": "application/json"}


def _reply(status: int, body: dict, origin: str | None = None):
    return {"statusCode": status, "headers": _cors(origin),
            "body": json.dumps(body)}


def _api_key() -> str:
    """The key, from SSM like every other model call here.

    This used to read OPENAI_API_KEY straight from the environment, which
    nothing sets: the chat path resolves its key from Parameter Store through
    OPENAI_API_KEY_SSM. So the key existed, the endpoint was deployed and
    routed, and voice still answered "not_configured" -- it was looking in a
    place nobody puts it. The plain variable is kept as a fallback for local
    runs, where there is no SSM.
    """
    ssm_name = os.environ.get("OPENAI_API_KEY_SSM", "")
    if ssm_name:
        try:
            import boto3
            resp = boto3.client("ssm", region_name="us-east-1").get_parameter(
                Name=ssm_name, WithDecryption=True)
            return resp["Parameter"]["Value"]
        except Exception:                             # noqa: BLE001
            pass                                      # fall through to the env var
    return os.environ.get("OPENAI_API_KEY", "")


def _spend_table():
    """The ONE ledger. Not a second one that happens to look like it.

    This first reached for CHAT_CACHE_TABLE, which is a different table, and
    the reservation failed to write -- so voice refused to start, which is the
    correct behaviour for a cap that cannot be recorded. Had it succeeded it
    would have been worse than an error: voice would have kept its own private
    ledger, the daily ceiling would not have been shared with typed questions,
    and "$25 a day" would have quietly meant fifty. The spend rows live on the
    rate-limit table, written by handler._get_rate_table, and voice must use
    that same object.
    """
    try:
        from . import handler as _h
    except ImportError:
        import handler as _h
    return _h._get_rate_table()


def handler(event, _context=None):
    """POST -> {client_secret, model, expires_at}. No body required."""
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    origin = headers.get("origin")

    method = ((event.get("requestContext") or {}).get("http") or {}).get("method")
    if method == "OPTIONS":
        return _reply(204, {}, origin)

    allowed = os.environ.get("ALLOWED_ORIGIN", "")
    if allowed and origin and origin != allowed:
        return _reply(403, {"error": "forbidden_origin"}, origin)

    api_key = _api_key()
    if not api_key:
        return _reply(500, {"error": "not_configured",
                            "detail": "no API key in SSM or the environment"}, origin)

    # Charge the session BEFORE minting the token. Audio never comes back
    # through here, so this reservation is the charge -- see budget.py. A
    # token minted without a reservation is an unmetered session, which is the
    # hole the retired public endpoint used to be.
    try:
        charged = _budget.reserve_realtime_session(_spend_table(), MAX_SESSION_SECONDS)
    except _budget.BudgetExhausted:
        return _reply(429, {"error": "daily_budget",
                            "detail": "Voice is at its daily limit. Typed questions "
                                      "still work, and the dashboard below is unchanged.",
                            "retry_after_seconds": _budget.seconds_until_reset()}, origin)
    except _budget.BudgetUnavailable:
        # Fails CLOSED. A spending cap that cannot be written is not a cap.
        return _reply(503, {"error": "budget_unavailable",
                            "detail": "Voice is unavailable right now."}, origin)

    # The GA request shape: everything is nested under "session", audio config
    # splits into input and output, and max_response_output_tokens became
    # max_output_tokens. Each field here was confirmed to survive the round
    # trip -- the API silently keeps what it understands.
    payload = {"session": {
        "type": "realtime",
        "model": REALTIME_MODEL,
        "instructions": INSTRUCTIONS,
        "audio": {
            # Server-side VAD: the listener just talks, no push-to-talk.
            # PIN THE LANGUAGE. Without a transcription language the model
            # auto-detects, and on a short or noisy first utterance it
            # guesses -- it answered a US-data question in French. The
            # instructions below say English too, because the reply language
            # follows the instructions and the transcript independently and
            # either one alone can be overridden.
            #
            # A transcription model is REQUIRED -- omitting it is a 400,
            # "Missing required parameter". gpt-realtime-whisper is the
            # realtime-paired one and is not on the 2026 retirement list that
            # whisper-1 and the gpt-4o-*-transcribe family are on. It also
            # honours `language` directly; gpt-transcribe silently rewrites
            # it to a `languages` array, which is a different contract.
            "input": {"transcription": {"model": "gpt-realtime-whisper",
                                        "language": "en"},
                      "turn_detection": {"type": "server_vad", "threshold": 0.5,
                                         "prefix_padding_ms": 300,
                                         "silence_duration_ms": 600}},
            "output": {"voice": REALTIME_VOICE},
        },
        "tools": TOOLS,
        "tool_choice": "auto",
        "max_output_tokens": 800,
    }}

    req = urllib.request.Request(
        SESSION_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}",
                 "Content-Type": "application/json"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:400]
        _budget.release_realtime_session(_spend_table(), charged)
        return _reply(502, {"error": "upstream", "status": e.code,
                            "detail": detail}, origin)
    except Exception as e:                        # noqa: BLE001
        _budget.release_realtime_session(_spend_table(), charged)
        return _reply(502, {"error": "upstream", "detail": str(e)[:200]}, origin)

    secret = data.get("value") or (data.get("client_secret") or {}).get("value")
    if not secret:
        _budget.release_realtime_session(_spend_table(), charged)
        return _reply(502, {"error": "no_client_secret"}, origin)

    return _reply(200, {
        "client_secret": secret,
        "charged_micro": charged,
        "model": REALTIME_MODEL,
        "expires_at": data.get("expires_at") or (data.get("client_secret") or {}).get("expires_at"),
        "max_session_seconds": MAX_SESSION_SECONDS,
    }, origin)
