#!/usr/bin/env python3
"""
Live end-to-end test against the real model provider.

    AWS_PROFILE=personal python3 cloud/chat/test_live.py "your question"

Reads the OpenAI key from SSM by parameter name, exactly as the Lambda does.
The key is never printed, logged or written anywhere. Rate limiting and
DynamoDB analytics are disabled for the run so the test does not touch
production tables.

This does NOT deploy anything. It runs the handler in-process.
"""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

os.environ.pop("CHAT_LOGS_TABLE", None)          # do not write analytics rows
os.environ.setdefault("OPENAI_API_KEY_SSM", "/phd-demographics/openai-api-key")

import handler as H  # noqa: E402

H._check_rate = lambda ip: (True, 60)            # do not consume the limiter

QUESTION = (sys.argv[1] if len(sys.argv) > 1 else
            "Which universities have the highest non-resident-alien share in "
            "electrical engineering doctorates since 2020, and how has the national "
            "NRA share of STEM PhDs moved since 2015?")

event = {
    "headers": {"origin": "https://phd-demographics.andy-barr.com"},
    "requestContext": {"http": {"method": "POST", "sourceIp": "203.0.113.42"}},
    "body": json.dumps({
        "v": 2,
        "message": QUESTION,
        "conversationHistory": [],
        "page": {"path": "/stem.html"},
        "client": {"widget": "2.0.0-test"},
    }),
}

print(f"Q: {QUESTION}\n")
resp = H.handler(event)
body = json.loads(resp["body"])
print(f"HTTP {resp['statusCode']}")
if "error" in body:
    print(json.dumps(body, indent=2))
    sys.exit(1)
print(f"meta: {json.dumps(body.get('meta', {}))}\n")
print("--- reply ---")
print(body.get("reply", ""))
print("\n--- blocks ---")
for b in body.get("blocks", []):
    print(f"\n[{b['type']}]")
    print(json.dumps(b, indent=2, ensure_ascii=False)[:2500])
print(f"\n--- actions ---\n{json.dumps(body.get('actions', []), indent=2)}")
print(f"\nbody size: {len(resp['body'])/1024:.1f} KB")
