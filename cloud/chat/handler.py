"""
AWS Lambda handler for the PhD Demographics AI chat assistant.

Multi-provider support: Bedrock (Claude), OpenAI, OpenRouter.
Provider selection is server-side only — the client cannot choose.

Security measures:
  - Origin validation (only phd-demographics.andy-barr.com)
  - Per-IP rate limiting via DynamoDB TTL
  - No client-side model/provider selection
  - API keys in SSM Parameter Store (encrypted, never exposed)
  - Input sanitization and length limits
  - No database access or code execution

Environment variables (set by SAM template):
  - RATE_LIMIT_TABLE: DynamoDB table name for rate limiting
  - ALLOWED_ORIGIN: CORS origin lock
  - CHAT_PROVIDER: "bedrock" | "openai" | "openrouter"
  - CHAT_MODEL: Model ID (provider-specific)
  - OPENAI_API_KEY_SSM: SSM parameter name for OpenAI key
  - OPENROUTER_API_KEY_SSM: SSM parameter name for OpenRouter key
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# --- Configuration ---
ALLOWED_ORIGIN = os.environ.get(
    "ALLOWED_ORIGIN", "https://phd-demographics.andy-barr.com"
)
PROVIDER = os.environ.get("CHAT_PROVIDER", "bedrock")
MODEL_ID = os.environ.get("CHAT_MODEL", "anthropic.claude-sonnet-4-20250514")
MAX_INPUT_LENGTH = 2000
MAX_HISTORY_MESSAGES = 20
MAX_TOKENS = 1024
RATE_LIMIT = 10
RATE_WINDOW = 60

# Provider configuration (OpenAI-compatible APIs)
PROVIDER_CONFIG = {
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "ssm_param": os.environ.get("OPENAI_API_KEY_SSM", "/phd-demographics/openai-api-key"),
        "default_model": "gpt-4o",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "ssm_param": os.environ.get("OPENROUTER_API_KEY_SSM", "/phd-demographics/openrouter-api-key"),
        "default_model": "anthropic/claude-sonnet-4",
        "extra_headers": {
            "HTTP-Referer": "https://phd-demographics.andy-barr.com",
            "X-Title": "PhD Demographics Assistant",
        },
    },
}

# Lazy-init clients and cached keys
_bedrock = None
_dynamo = None
_api_keys: dict[str, str] = {}


def _get_bedrock():
    global _bedrock
    if _bedrock is None:
        _bedrock = boto3.client("bedrock-runtime", region_name="us-east-1")
    return _bedrock


def _get_dynamo():
    global _dynamo
    if _dynamo is None:
        table_name = os.environ.get("RATE_LIMIT_TABLE", "phd-demographics-chat-ratelimit")
        _dynamo = boto3.resource("dynamodb", region_name="us-east-1").Table(table_name)
    return _dynamo


def _get_api_key(provider: str) -> str:
    """Retrieve API key from SSM Parameter Store (cached across warm invocations)."""
    if provider in _api_keys:
        return _api_keys[provider]
    config = PROVIDER_CONFIG.get(provider)
    if not config:
        raise ValueError(f"Unknown provider: {provider}")
    ssm = boto3.client("ssm", region_name="us-east-1")
    resp = ssm.get_parameter(Name=config["ssm_param"], WithDecryption=True)
    key = resp["Parameter"]["Value"]
    _api_keys[provider] = key
    return key


def _cors_headers(origin: str = "") -> dict:
    allowed = origin if origin == ALLOWED_ORIGIN else ALLOWED_ORIGIN
    return {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": allowed,
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "content-type",
        "Access-Control-Max-Age": "3600",
    }


def _get_client_ip(event: dict) -> str:
    rc = event.get("requestContext", {})
    http = rc.get("http", {})
    if http.get("sourceIp"):
        return http["sourceIp"]
    identity = rc.get("identity", {})
    if identity.get("sourceIp"):
        return identity["sourceIp"]
    headers = event.get("headers", {})
    return headers.get("x-forwarded-for", "unknown").split(",")[0].strip()


def _check_rate_limit(ip: str) -> bool:
    try:
        table = _get_dynamo()
        now = int(time.time())
        window_key = f"{ip}:{now // RATE_WINDOW}"
        ttl = now + RATE_WINDOW * 2
        response = table.update_item(
            Key={"pk": window_key},
            UpdateExpression="SET #cnt = if_not_exists(#cnt, :zero) + :one, #ttl = :ttl",
            ExpressionAttributeNames={"#cnt": "count", "#ttl": "ttl"},
            ExpressionAttributeValues={":zero": 0, ":one": 1, ":ttl": ttl},
            ReturnValues="UPDATED_NEW",
        )
        return int(response["Attributes"]["count"]) <= RATE_LIMIT
    except Exception as e:
        logger.warning(f"Rate limit check failed: {e}")
        return True


def _sanitize_message(msg: str) -> str:
    if not isinstance(msg, str):
        return ""
    return msg.strip()[:MAX_INPUT_LENGTH]


# --- Provider implementations ---

def _call_bedrock(system_prompt: str, messages: list[dict]) -> str:
    """Call Claude via Bedrock Converse API (IAM auth, no API key needed)."""
    bedrock = _get_bedrock()
    bedrock_messages = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        if role in ("user", "assistant") and content:
            bedrock_messages.append({"role": role, "content": [{"text": content}]})

    response = bedrock.converse(
        modelId=MODEL_ID,
        system=[{"text": system_prompt}],
        messages=bedrock_messages,
        inferenceConfig={"maxTokens": MAX_TOKENS, "temperature": 0.3},
    )
    output = response.get("output", {}).get("message", {}).get("content", [])
    if output and output[0].get("text"):
        return output[0]["text"]
    return "I'm sorry, I couldn't generate a response."


def _call_openai_compatible(provider: str, system_prompt: str, messages: list[dict]) -> str:
    """Call OpenAI or OpenRouter via their chat completions API."""
    import urllib.request

    config = PROVIDER_CONFIG[provider]
    api_key = _get_api_key(provider)
    model = MODEL_ID if not MODEL_ID.startswith("anthropic.") else config["default_model"]

    api_messages = [
        {"role": "system", "content": system_prompt},
        *[{"role": m["role"], "content": m["content"]} for m in messages],
    ]

    payload = json.dumps({
        "model": model,
        "messages": api_messages,
        "max_tokens": MAX_TOKENS,
        "temperature": 0.3,
    }).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    # Add provider-specific headers (e.g., OpenRouter requires Referer)
    for k, v in config.get("extra_headers", {}).items():
        headers[k] = v

    url = f"{config['base_url']}/chat/completions"
    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")

    with urllib.request.urlopen(req, timeout=25) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    choices = data.get("choices", [])
    if choices and choices[0].get("message", {}).get("content"):
        return choices[0]["message"]["content"]
    return "I'm sorry, I couldn't generate a response."


def _call_ai(system_prompt: str, messages: list[dict]) -> str:
    """Route to the configured provider."""
    if PROVIDER == "bedrock":
        return _call_bedrock(system_prompt, messages)
    elif PROVIDER in PROVIDER_CONFIG:
        return _call_openai_compatible(PROVIDER, system_prompt, messages)
    else:
        raise ValueError(f"Unknown provider: {PROVIDER}")


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda handler for chat requests."""
    from .prompt import SYSTEM_PROMPT

    headers = event.get("headers", {})
    origin = headers.get("origin", "")
    cors = _cors_headers(origin)

    # CORS preflight
    method = event.get("requestContext", {}).get("http", {}).get("method", "")
    if method == "OPTIONS" or event.get("httpMethod") == "OPTIONS":
        return {"statusCode": 200, "headers": cors, "body": ""}

    # Origin validation
    if origin and origin != ALLOWED_ORIGIN:
        logger.warning(f"Rejected request from origin: {origin}")
        return {"statusCode": 403, "headers": cors, "body": json.dumps({"error": "Forbidden"})}

    # Rate limit
    client_ip = _get_client_ip(event)
    if not _check_rate_limit(client_ip):
        return {"statusCode": 429, "headers": cors, "body": json.dumps({"error": "Rate limit exceeded. Try again in a minute."})}

    # Parse body
    body = event.get("body", "{}")
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except json.JSONDecodeError:
            return {"statusCode": 400, "headers": cors, "body": json.dumps({"error": "Invalid JSON"})}

    message = _sanitize_message(body.get("message", ""))
    if not message:
        return {"statusCode": 400, "headers": cors, "body": json.dumps({"error": "message is required"})}

    # Sanitize conversation history
    history = body.get("conversationHistory", [])
    if not isinstance(history, list):
        history = []
    history = history[-MAX_HISTORY_MESSAGES:]
    clean_history = []
    for m in history:
        if isinstance(m, dict) and m.get("role") in ("user", "assistant"):
            clean_history.append({"role": m["role"], "content": str(m.get("content", ""))[:MAX_INPUT_LENGTH]})

    messages = clean_history + [{"role": "user", "content": message}]

    try:
        reply = _call_ai(SYSTEM_PROMPT, messages)
        return {
            "statusCode": 200,
            "headers": cors,
            "body": json.dumps({"reply": reply, "provider": PROVIDER}),
        }
    except Exception as e:
        logger.exception("Chat API error")
        return {"statusCode": 500, "headers": cors, "body": json.dumps({"error": "Chat service temporarily unavailable."})}
