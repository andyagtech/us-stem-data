"""
AWS Lambda handler for the PhD Demographics AI chat assistant.

Security measures:
  - Origin validation (only phd-demographics.andy-barr.com)
  - Per-IP rate limiting via DynamoDB TTL
  - No client-side model/provider selection
  - Claude via Bedrock (IAM role auth, no API keys)
  - Input sanitization and length limits
  - No database access or code execution

Environment variables (set by SAM template):
  - RATE_LIMIT_TABLE: DynamoDB table for rate limiting
  - ALLOWED_ORIGIN: Override for allowed CORS origin
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
MODEL_ID = "anthropic.claude-sonnet-4-20250514"
MAX_INPUT_LENGTH = 2000  # max chars per message
MAX_HISTORY_MESSAGES = 20
MAX_TOKENS = 1024
RATE_LIMIT = 10  # requests per minute per IP
RATE_WINDOW = 60  # seconds

# Lazy-init clients
_bedrock = None
_dynamo = None


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


def _cors_headers(origin: str = "") -> dict:
    """Return CORS headers. Only allow the configured origin."""
    allowed = origin if origin == ALLOWED_ORIGIN else ALLOWED_ORIGIN
    return {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": allowed,
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "content-type",
        "Access-Control-Max-Age": "3600",
    }


def _get_client_ip(event: dict) -> str:
    """Extract client IP from Lambda Function URL or API Gateway event."""
    # Lambda Function URL
    rc = event.get("requestContext", {})
    http = rc.get("http", {})
    if http.get("sourceIp"):
        return http["sourceIp"]
    # API Gateway
    identity = rc.get("identity", {})
    if identity.get("sourceIp"):
        return identity["sourceIp"]
    # Fallback
    headers = event.get("headers", {})
    return headers.get("x-forwarded-for", "unknown").split(",")[0].strip()


def _check_rate_limit(ip: str) -> bool:
    """Check and increment rate limit. Returns True if allowed."""
    try:
        table = _get_dynamo()
        now = int(time.time())
        window_key = f"{ip}:{now // RATE_WINDOW}"
        ttl = now + RATE_WINDOW * 2  # expire after 2 windows

        response = table.update_item(
            Key={"pk": window_key},
            UpdateExpression="SET #cnt = if_not_exists(#cnt, :zero) + :one, #ttl = :ttl",
            ExpressionAttributeNames={"#cnt": "count", "#ttl": "ttl"},
            ExpressionAttributeValues={":zero": 0, ":one": 1, ":ttl": ttl},
            ReturnValues="UPDATED_NEW",
        )
        count = int(response["Attributes"]["count"])
        return count <= RATE_LIMIT
    except Exception as e:
        logger.warning(f"Rate limit check failed: {e}")
        return True  # fail open to avoid blocking on DynamoDB errors


def _sanitize_message(msg: str) -> str:
    """Sanitize user input."""
    if not isinstance(msg, str):
        return ""
    # Strip and truncate
    msg = msg.strip()[:MAX_INPUT_LENGTH]
    return msg


def _call_claude(system_prompt: str, messages: list[dict]) -> str:
    """Call Claude via Bedrock Converse API."""
    bedrock = _get_bedrock()

    # Convert to Bedrock message format
    bedrock_messages = []
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        if role in ("user", "assistant") and content:
            bedrock_messages.append({
                "role": role,
                "content": [{"text": content}],
            })

    response = bedrock.converse(
        modelId=MODEL_ID,
        system=[{"text": system_prompt}],
        messages=bedrock_messages,
        inferenceConfig={
            "maxTokens": MAX_TOKENS,
            "temperature": 0.3,
        },
    )

    # Extract text from response
    output = response.get("output", {})
    message = output.get("message", {})
    content = message.get("content", [])
    if content and content[0].get("text"):
        return content[0]["text"]
    return "I'm sorry, I couldn't generate a response."


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda handler for chat requests."""
    # Import here to avoid cold-start cost if just handling OPTIONS
    from .prompt import SYSTEM_PROMPT

    # Get origin for CORS
    headers = event.get("headers", {})
    origin = headers.get("origin", "")
    cors = _cors_headers(origin)

    # Handle CORS preflight
    method = event.get("requestContext", {}).get("http", {}).get("method", "")
    if method == "OPTIONS" or event.get("httpMethod") == "OPTIONS":
        return {"statusCode": 200, "headers": cors, "body": ""}

    # Validate origin
    if origin and origin != ALLOWED_ORIGIN:
        logger.warning(f"Rejected request from origin: {origin}")
        return {
            "statusCode": 403,
            "headers": cors,
            "body": json.dumps({"error": "Forbidden"}),
        }

    # Rate limit
    client_ip = _get_client_ip(event)
    if not _check_rate_limit(client_ip):
        return {
            "statusCode": 429,
            "headers": cors,
            "body": json.dumps({"error": "Rate limit exceeded. Try again in a minute."}),
        }

    # Parse body
    body = event.get("body", "{}")
    if isinstance(body, str):
        try:
            body = json.loads(body)
        except json.JSONDecodeError:
            return {
                "statusCode": 400,
                "headers": cors,
                "body": json.dumps({"error": "Invalid JSON"}),
            }

    message = _sanitize_message(body.get("message", ""))
    if not message:
        return {
            "statusCode": 400,
            "headers": cors,
            "body": json.dumps({"error": "message is required"}),
        }

    # Sanitize conversation history
    history = body.get("conversationHistory", [])
    if not isinstance(history, list):
        history = []
    history = history[-MAX_HISTORY_MESSAGES:]  # keep last N
    clean_history = []
    for m in history:
        if isinstance(m, dict) and m.get("role") in ("user", "assistant"):
            content = str(m.get("content", ""))[:MAX_INPUT_LENGTH]
            clean_history.append({"role": m["role"], "content": content})

    # Build messages
    messages = clean_history + [{"role": "user", "content": message}]

    try:
        reply = _call_claude(SYSTEM_PROMPT, messages)
        return {
            "statusCode": 200,
            "headers": cors,
            "body": json.dumps({
                "reply": reply,
                "model": MODEL_ID.split(".")[-1],
            }),
        }
    except Exception as e:
        logger.exception("Chat API error")
        return {
            "statusCode": 500,
            "headers": cors,
            "body": json.dumps({"error": "Chat service temporarily unavailable."}),
        }
