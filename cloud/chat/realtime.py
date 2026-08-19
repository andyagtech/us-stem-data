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

REALTIME_MODEL = os.environ.get("REALTIME_MODEL", "gpt-4o-realtime-preview")
REALTIME_VOICE = os.environ.get("REALTIME_VOICE", "alloy")
MAX_SESSION_SECONDS = int(os.environ.get("REALTIME_MAX_SECONDS", "600"))
SESSION_URL = "https://api.openai.com/v1/realtime/sessions"

# The tool surface the voice agent may call. These are RENDER instructions --
# the browser owns the data and the drawing. Keeping the schema small matters:
# the model picks a tool mid-sentence, and every extra option is latency.
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
        "name": "clear_board",
        "description": "Reset the dashboard to its opening state.",
        "parameters": {"type": "object", "properties": {}},
    },
]

INSTRUCTIONS = """\
You are the voice of a live data dashboard about who receives US graduate \
degrees. Someone is talking to you while looking at a screen you control.

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
    allowed = os.environ.get("ALLOWED_ORIGIN", "")
    return {
        "Access-Control-Allow-Origin": allowed or "null",
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Allow-Methods": "POST,OPTIONS",
        "Content-Type": "application/json",
    }


def _reply(status: int, body: dict, origin: str | None = None):
    return {"statusCode": status, "headers": _cors(origin),
            "body": json.dumps(body)}


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

    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        return _reply(500, {"error": "not_configured",
                            "detail": "OPENAI_API_KEY is unset"}, origin)

    payload = {
        "model": REALTIME_MODEL,
        "voice": REALTIME_VOICE,
        "modalities": ["audio", "text"],
        "instructions": INSTRUCTIONS,
        "tools": TOOLS,
        "tool_choice": "auto",
        # Server-side VAD: the listener just talks, no push-to-talk.
        "turn_detection": {"type": "server_vad", "threshold": 0.5,
                           "prefix_padding_ms": 300, "silence_duration_ms": 600},
        "max_response_output_tokens": 800,
    }

    req = urllib.request.Request(
        SESSION_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}",
                 "Content-Type": "application/json",
                 "OpenAI-Beta": "realtime=v1"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:400]
        return _reply(502, {"error": "upstream", "status": e.code,
                            "detail": detail}, origin)
    except Exception as e:                        # noqa: BLE001
        return _reply(502, {"error": "upstream", "detail": str(e)[:200]}, origin)

    secret = (data.get("client_secret") or {}).get("value")
    if not secret:
        return _reply(502, {"error": "no_client_secret"}, origin)

    return _reply(200, {
        "client_secret": secret,
        "model": REALTIME_MODEL,
        "expires_at": (data.get("client_secret") or {}).get("expires_at"),
        "max_session_seconds": MAX_SESSION_SECONDS,
    }, origin)
