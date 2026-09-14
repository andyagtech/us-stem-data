"""A daily dollar ceiling on what the assistant spends at the model provider.

WHY DOLLARS, NOT QUESTIONS

The service used to cap questions: 6,000 a day. That bounded nothing useful.
A question is not a unit of cost -- one question can take up to four model
calls through the tool loop, plus a retry, and every call ships the whole
knowledge base (about 43,000 prompt tokens, measured). 6,000 questions a day
permitted several hundred dollars a day. The thing to cap is the thing that is
billed.

HOW IT HOLDS UNDER CONCURRENCY

Check-then-spend does not: twenty requests arriving together all read "under
budget", all call the model, and together overshoot. So every model call
RESERVES its worst-case cost first, in one conditional DynamoDB update that
succeeds only if the reservation still fits under the ceiling. Concurrent
Lambdas are serialised by DynamoDB, not by us. After the call the reservation
is SETTLED to the real cost, computed from the token counts the provider
returns. The ceiling can only be exceeded if a call costs more than its
worst-case estimate, and the estimate is built so that it does not.

HOW IT FAILS

Closed. If the reservation cannot be written, the call does not happen. This
is the opposite of the per-IP limiter, which fails open: a limiter that is down
should not take the service down, but a spending cap that fails open is not a
cap.

WHAT IT DOES NOT COVER

Cached answers cost nothing and are served without a reservation, so the
common questions keep working after the ceiling is reached. The /realtime voice
endpoint is billed per audio minute to a browser-held token and is not metered
here; it is unconfigured in production (no OPENAI_API_KEY), so it spends
nothing today, but enabling it would need its own entry in this budget.

PRICES

gpt-4o, per 1M tokens, from developers.openai.com/api/docs/models/gpt-4o
(snapshot gpt-4o-2024-08-06), read 2026-09-14: input $2.50, cached input
$1.25, output $10.00. Environment-overridable, because they change and a stale
price makes the ceiling wrong in the direction nobody notices.

Money is held as integer micro-dollars (1 USD = 1,000,000). DynamoDB's atomic
ADD and its condition expressions are exact on integers; floats would drift.
"""
from __future__ import annotations

import json
import os
import time

MICRO = 1_000_000

DAILY_BUDGET_USD = float(os.environ.get("DAILY_BUDGET_USD", "25"))
PRICE_INPUT_PER_M = float(os.environ.get("PRICE_INPUT_PER_M", "2.50"))
PRICE_CACHED_PER_M = float(os.environ.get("PRICE_CACHED_PER_M", "1.25"))
PRICE_OUTPUT_PER_M = float(os.environ.get("PRICE_OUTPUT_PER_M", "10.00"))

# Kept well past the analytics window (90 days) so the dashboard's history is
# never cut short by expiry in the table it reads.
RETENTION_SECONDS = 400 * 86400

# Characters per token used to ESTIMATE a prompt before sending it. English
# averages about four; three over-counts on purpose, because the estimate must
# be an upper bound or the ceiling leaks.
CHARS_PER_TOKEN_ESTIMATE = 3.0


class BudgetExhausted(Exception):
    """Today's ceiling would be exceeded by the next model call."""


class BudgetUnavailable(Exception):
    """The spend ledger could not be written, so the call must not happen."""


def budget_micro() -> int:
    return int(round(DAILY_BUDGET_USD * MICRO))


def day_of(now: float | None = None) -> str:
    return time.strftime("%Y-%m-%d", time.gmtime(now if now is not None else time.time()))


def key_for(day: str) -> dict:
    return {"pk": f"SPEND:{day}"}


def seconds_until_reset(now: float | None = None) -> int:
    now = int(now if now is not None else time.time())
    return 86400 - (now % 86400)


def cost_micro(usage: dict | None) -> int | None:
    """What one call cost, from the provider's own token counts.

    prompt_tokens INCLUDES the cached ones, which are billed at the lower
    rate, so they are subtracted before the full input price is applied.
    Returns None when the response carried no usage, so the caller can keep
    the worst-case reservation instead of recording a free call.
    """
    if not usage:
        return None
    try:
        prompt = int(usage.get("prompt_tokens") or 0)
        completion = int(usage.get("completion_tokens") or 0)
        cached = int((usage.get("prompt_tokens_details") or {}).get("cached_tokens") or 0)
    except (TypeError, ValueError):
        return None
    if prompt == 0 and completion == 0:
        return None
    cached = max(0, min(cached, prompt))
    usd = ((prompt - cached) * PRICE_INPUT_PER_M
           + cached * PRICE_CACHED_PER_M
           + completion * PRICE_OUTPUT_PER_M) / 1_000_000
    return int(round(usd * MICRO))


def estimate_micro(body: dict, max_tokens: int) -> int:
    """An upper bound on what a request can cost, before it is sent.

    The whole request body -- system prompt, history, tool schemas -- is
    counted as input at the uncached price, and the output is assumed to run
    to max_tokens. Both are worst cases; settlement corrects to the truth.
    """
    chars = len(json.dumps(body, ensure_ascii=False))
    in_tokens = int(chars / CHARS_PER_TOKEN_ESTIMATE) + 1
    usd = (in_tokens * PRICE_INPUT_PER_M + max_tokens * PRICE_OUTPUT_PER_M) / 1_000_000
    return int(round(usd * MICRO)) + 1


def reserve(table, est: int, now: float | None = None) -> None:
    """Hold `est` micro-dollars against today, or refuse.

    One conditional update: it applies only if what is already spent plus this
    reservation stays within the ceiling. Raises BudgetExhausted when it would
    not, BudgetUnavailable when the ledger cannot be written at all.
    """
    now = time.time() if now is None else now
    ceiling = budget_micro()
    try:
        table.update_item(
            Key=key_for(day_of(now)),
            UpdateExpression=("ADD #s :est, #inflight :one "
                              "SET #b = :budget, #t = :ttl"),
            ConditionExpression="attribute_not_exists(#s) OR #s <= :room",
            ExpressionAttributeNames={"#s": "spent_micro", "#inflight": "reservations",
                                      "#b": "budget_micro", "#t": "ttl"},
            ExpressionAttributeValues={":est": est, ":one": 1, ":budget": ceiling,
                                       ":room": ceiling - est,
                                       ":ttl": int(now) + RETENTION_SECONDS},
        )
    except Exception as exc:                                   # noqa: BLE001
        code = getattr(exc, "response", {}).get("Error", {}).get("Code", "")
        if code == "ConditionalCheckFailedException":
            raise BudgetExhausted() from exc
        raise BudgetUnavailable(str(exc)) from exc


def settle(table, est: int, actual: int | None, usage: dict | None,
           provider: str = "", now: float | None = None) -> int:
    """Replace a reservation with what the call really cost.

    `actual` None means the provider gave no usage; the reservation is kept as
    the charge rather than released, so an unmeasured call is never free.
    `actual` 0 means the call did not happen (every provider failed) and the
    whole reservation is returned. Returns the micro-dollars charged.
    """
    now = time.time() if now is None else now
    charged = est if actual is None else actual
    usage = usage or {}
    prompt = int(usage.get("prompt_tokens") or 0)
    cached = int((usage.get("prompt_tokens_details") or {}).get("cached_tokens") or 0)
    completion = int(usage.get("completion_tokens") or 0)
    names = {"#s": "spent_micro", "#inflight": "reservations"}
    values = {":delta": charged - est, ":minus": -1}
    adds = ["#s :delta", "#inflight :minus"]
    if charged > 0:
        names.update({"#c": "calls", "#pi": "prompt_tokens", "#ci": "cached_tokens",
                      "#co": "completion_tokens"})
        values.update({":one": 1, ":pi": prompt, ":ci": cached, ":co": completion})
        adds += ["#c :one", "#pi :pi", "#ci :ci", "#co :co"]
        if actual is None:
            names["#u"] = "unmeasured_calls"
            adds.append("#u :one")
        if provider:
            names["#p"] = f"calls_{provider}"
            adds.append("#p :one")
    try:
        table.update_item(Key=key_for(day_of(now)),
                          UpdateExpression="ADD " + ", ".join(adds),
                          ExpressionAttributeNames=names,
                          ExpressionAttributeValues=values)
    except Exception:                                          # noqa: BLE001
        # The reservation stays standing, so the ledger over-states spend
        # rather than under-states it. That is the safe direction to be wrong.
        pass
    return charged


def record_refusal(table, now: float | None = None) -> None:
    """Count a question turned away by the ceiling, for the dashboard."""
    now = time.time() if now is None else now
    try:
        table.update_item(
            Key=key_for(day_of(now)),
            UpdateExpression="ADD #r :one SET #b = :budget, #t = :ttl",
            ExpressionAttributeNames={"#r": "refused", "#b": "budget_micro", "#t": "ttl"},
            ExpressionAttributeValues={":one": 1, ":budget": budget_micro(),
                                       ":ttl": int(now) + RETENTION_SECONDS},
        )
    except Exception:                                          # noqa: BLE001
        pass


def today(table, now: float | None = None) -> dict:
    """Today's ledger row as plain numbers, for log lines. Never raises."""
    try:
        item = table.get_item(Key=key_for(day_of(now))).get("Item") or {}
    except Exception:                                          # noqa: BLE001
        item = {}
    return {"spent_micro": int(item.get("spent_micro") or 0),
            "budget_micro": int(item.get("budget_micro") or budget_micro()),
            "calls": int(item.get("calls") or 0),
            "refused": int(item.get("refused") or 0)}


def usd(micro: int) -> str:
    return f"${micro / MICRO:,.4f}"
